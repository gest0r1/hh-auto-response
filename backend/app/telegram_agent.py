from __future__ import annotations

import fcntl
import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any

import httpx

from app.agent import JobSearchAgent
from app.config import default_applicant_profile, default_candidate_profile, get_settings
from app.hh_public import HHPublicSearchClient
from app.hh_vacancy import HHPublicVacancyClient, extract_hh_vacancy_id
from app.repository import CRMRepository
from app.responses import (
    ResponseContext,
    check_cover_letter_quality,
    generate_cover_letter,
    load_cover_letter_methodology,
)
from app.scoring import score_vacancy

TELEGRAM_MESSAGE_LIMIT = 4096
DEFAULT_TELEGRAM_API_BASE = "https://api.telegram.org"
RETRYABLE_TELEGRAM_STATUS_CODES = {500, 502, 503, 504}
TELEGRAM_COMMAND_MENU: tuple[tuple[str, str], ...] = (
    ("start", "Подключить чат и показать очередь"),
    ("run", "Запустить свежий поиск HH"),
    ("queue", "Показать черновики откликов"),
    ("summary", "Сводка CRM"),
    ("guide", "Методичка по откликам"),
    ("edit", "Заменить черновик: /edit ID текст"),
    ("help", "Список команд и безопасный режим"),
)


class TelegramAPIError(RuntimeError):
    """Raised when Telegram returns a non-retryable API error."""


class TelegramNetworkError(TelegramAPIError):
    """Raised when Telegram API transport fails transiently."""


class RunLockUnavailable(RuntimeError):
    """Raised when a HH search run is already active."""


@contextmanager
def exclusive_file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RunLockUnavailable(f"lock is already held: {path}") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@dataclass(slots=True)
class TelegramReviewSettings:
    chat_id_path: Path = Path("./data/hh_telegram_chat_id.txt")
    offset_path: Path = Path("./data/hh_telegram_offset.txt")
    run_lock_path: Path = Path("./data/hh_telegram_run.lock")
    min_score: int = 80
    limit: int = 5
    per_query: int = 20
    draft_threshold: int = 80
    poll_timeout: int = 30
    poll_interval_seconds: float = 1.0
    queries: list[str] = field(
        default_factory=lambda: [
            "React Python CRM",
            "Telegram bot Python",
            "AI automation developer",
            "Full-stack developer удалённо",
        ]
    )


class TelegramBotClient:
    def __init__(
        self,
        *,
        token: str,
        api_base: str = DEFAULT_TELEGRAM_API_BASE,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def _url(self, method: str) -> str:
        return f"{self.api_base}/bot{self.token}/{method}"

    def request(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.post(self._url(method), json=payload or {})
        except httpx.HTTPError as exc:
            raise TelegramNetworkError(f"Telegram API {method} failed: network error") from exc

        try:
            data = response.json()
        except ValueError:
            data = {"ok": False, "description": response.text[:300]}

        if response.status_code >= 400 or not data.get("ok", False):
            description = str(data.get("description") or "unknown error")[:300]
            if response.status_code in RETRYABLE_TELEGRAM_STATUS_CODES:
                raise TelegramNetworkError(
                    f"Telegram API {method} failed transiently: HTTP {response.status_code}: {description}"
                )
            raise TelegramAPIError(f"Telegram API {method} failed: HTTP {response.status_code}: {description}")
        return data

    def send_message(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        *,
        parse_mode: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self.request("sendMessage", payload)

    def set_my_commands(self, commands: list[dict[str, str]]) -> dict[str, Any]:
        return self.request("setMyCommands", {"commands": commands})

    def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
        *,
        show_alert: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id, "show_alert": show_alert}
        if text:
            payload["text"] = text
        return self.request("answerCallbackQuery", payload)

    def get_updates(self, *, offset: int | None = None, timeout: int = 30) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            payload["offset"] = offset
        data = self.request("getUpdates", payload)
        result = data.get("result") or []
        return result if isinstance(result, list) else []

    def get_me(self) -> dict[str, Any]:
        data = self.request("getMe")
        result = data.get("result") or {}
        return result if isinstance(result, dict) else {}


def telegram_command_menu() -> list[dict[str, str]]:
    return [{"command": command, "description": description} for command, description in TELEGRAM_COMMAND_MENU]


def format_help_message() -> str:
    return "\n".join(
        [
            "Команды HH агента:",
            "/run — свежий поиск HH и обновление очереди",
            "/queue — показать черновики откликов с кнопками send/edit/reject/archive",
            "/summary — сводка CRM",
            "/guide — методичка по откликам",
            "/edit ID текст — заменить черновик отклика",
            "/help — показать эту справку",
            "",
            "Можно просто прислать ссылку на HH-вакансию — я прочитаю её, подберу проекты из портфолио и сделаю проверенный черновик.",
            "",
            "Безопасность: бот не нажимает HH submit сам; отправка остаётся ручным действием.",
        ]
    )


def _truncate(value: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _html(value: Any) -> str:
    return escape(str(value), quote=False)


def _bullets(values: list[str], *, limit: int = 6, fallback: str = "—") -> str:
    if not values:
        return fallback
    return "\n".join(f"- {value}" for value in values[:limit])


def format_vacancy_message(row: dict[str, Any], *, index: int) -> str:
    title = row.get("title") or "Без названия"
    company = row.get("company") or "Компания не указана"
    score = row.get("score")
    decision = row.get("decision") or "review"
    vacancy_url = row.get("url") or ""
    apply_url = row.get("apply_url") or vacancy_url
    reasons = [str(value) for value in row.get("score_reasons") or []]
    penalties = [str(value) for value in row.get("score_penalties") or []]
    cover_letter = str(row.get("cover_letter") or "")
    application_id = row.get("application_id")

    prefix = "\n".join(
        [
            f"HH #{index}: {_html(title)}",
            f"Компания: {_html(company)}",
            f"ID отклика: {_html(application_id or '—')}",
            f"Score: {_html(score)} / {_html(decision)}",
            f"Вакансия: {_html(vacancy_url)}",
            f"Отклик: {_html(apply_url)}",
            "Почему подходит:",
            _bullets([_html(value) for value in reasons]),
        ]
    )
    if penalties:
        prefix += "\nРиски:\n" + _bullets([_html(value) for value in penalties], limit=4)

    draft_prefix = "\n\nЧерновик:\n<pre>"
    draft_suffix = "</pre>"
    remaining = TELEGRAM_MESSAGE_LIMIT - len(prefix) - len(draft_prefix) - len(draft_suffix)
    escaped_cover_letter = _truncate(_html(cover_letter), remaining)
    return prefix + draft_prefix + escaped_cover_letter + draft_suffix


def format_send_gate_message(row: dict[str, Any]) -> str:
    prefix = "\n".join(
        [
            "Бот не нажимает submit на HH.",
            "Открой ссылку отклика, проверь текст и отправь вручную. После ручной отправки нажми mark sent.",
            "",
            f"Вакансия: {_html(row.get('url') or '')}",
            f"Отклик: {_html(row.get('apply_url') or row.get('url') or '')}",
            "",
            "Черновик:\n<pre>",
        ]
    )
    suffix = "</pre>"
    remaining = TELEGRAM_MESSAGE_LIMIT - len(prefix) - len(suffix)
    return prefix + _truncate(_html(row.get("cover_letter") or ""), remaining) + suffix


def _review_callback(action: str, application_id: int | str | None) -> str:
    return f"hh:{action}:{application_id or 0}"


def build_review_keyboard(row: dict[str, Any]) -> dict[str, Any] | None:
    application_id = row.get("application_id")
    if not application_id:
        return None
    return {
        "inline_keyboard": [
            [
                {"text": "send", "callback_data": _review_callback("send", application_id)},
                {"text": "edit", "callback_data": _review_callback("edit", application_id)},
            ],
            [
                {"text": "reject", "callback_data": _review_callback("reject", application_id)},
                {"text": "archive", "callback_data": _review_callback("archive", application_id)},
            ],
        ]
    }


def build_send_confirmation_keyboard(application_id: int | str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "mark sent", "callback_data": _review_callback("mark_sent", application_id)},
                {"text": "cancel", "callback_data": _review_callback("cancel", application_id)},
            ]
        ]
    }


def format_summary_message(summary: dict[str, Any]) -> str:
    metrics = summary.get("metrics") or {}
    pipeline = summary.get("pipeline") or {}
    return "\n".join(
        [
            "HH CRM summary",
            f"Вакансий в базе: {metrics.get('vacancies_total', 0)}",
            f"Hot: {metrics.get('hot_total', 0)}",
            f"Черновиков: {metrics.get('drafts_total', 0)}",
            f"Отправлено: {metrics.get('sent_total', 0)}",
            f"Собеседований: {metrics.get('interviews_total', 0)}",
            f"Pipeline: {json.dumps(pipeline, ensure_ascii=False, sort_keys=True)}",
        ]
    )


def format_quality_summary(issues: list[str]) -> str:
    if not issues:
        return "Double-check: ✅ приветствие, привязка к вакансии, проекты из портфолио и ссылка на портфолио на месте."
    readable = {
        "bad_greeting": "проверить приветствие",
        "employer_in_greeting": "убрать обращение к компании из приветствия",
        "company_in_first_sentence": "не упоминать компанию в первом предложении",
        "missing_portfolio": "добавить портфолио отдельной строкой",
        "missing_relevant_case": "добавить релевантный проект",
        "missing_vacancy_anchors": "сильнее привязать к вакансии",
        "too_long": "сократить текст",
        "template_artifact": "убрать шаблонные скобки",
    }
    labels = [readable.get(issue, issue.replace("generic_phrase:", "убрать шаблонную фразу: ")) for issue in issues]
    return "Double-check: ⚠️ " + "; ".join(labels[:6]) + "."


def _parse_review_callback(data: str) -> tuple[str, int] | None:
    parts = data.split(":", 2)
    if len(parts) != 3 or parts[0] != "hh" or not parts[2].isdigit():
        return None
    return parts[1], int(parts[2])


def _row_ids(row: dict[str, Any]) -> tuple[int | None, int | None]:
    vacancy_id = int(row["id"]) if row.get("id") is not None else None
    application_id = int(row["application_id"]) if row.get("application_id") is not None else None
    return vacancy_id, application_id


class HHTelegramReviewAgent:
    def __init__(
        self,
        *,
        repo: CRMRepository,
        bot: TelegramBotClient,
        settings: TelegramReviewSettings | None = None,
    ) -> None:
        self.repo = repo
        self.bot = bot
        self.settings = settings or TelegramReviewSettings()

    def saved_chat_id(self) -> int | str | None:
        path = self.settings.chat_id_path
        if not path.exists():
            return None
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            return None
        return int(value) if value.lstrip("-").isdigit() else value

    def register_chat(self, chat_id: int | str) -> None:
        self.settings.chat_id_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings.chat_id_path.write_text(str(chat_id), encoding="utf-8")

    def send_text(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        *,
        parse_mode: str | None = None,
    ) -> None:
        chunks = _split_message(text)
        for index, chunk in enumerate(chunks):
            markup = reply_markup if index == len(chunks) - 1 else None
            self.bot.send_message(chat_id, chunk, reply_markup=markup, parse_mode=parse_mode)

    def send_queue(self, *, chat_id: int | str | None = None) -> int:
        target_chat_id = chat_id or self.saved_chat_id()
        if target_chat_id is None:
            return 0
        rows = self.repo.review_queue(min_score=self.settings.min_score, limit=self.settings.limit)
        if not rows:
            self.send_text(target_chat_id, "HH очередь пуста: подходящих draft-вакансий выше порога пока нет.")
            return 0
        for index, row in enumerate(rows, start=1):
            self.send_text(
                target_chat_id,
                format_vacancy_message(row, index=index),
                reply_markup=build_review_keyboard(row),
                parse_mode="HTML",
            )
        return len(rows)

    def send_summary(self, *, chat_id: int | str | None = None) -> bool:
        target_chat_id = chat_id or self.saved_chat_id()
        if target_chat_id is None:
            return False
        self.send_text(target_chat_id, format_summary_message(self.repo.dashboard_summary()))
        return True

    def run_public_once(self) -> dict[str, Any]:
        app_settings = get_settings()
        agent = JobSearchAgent(
            repo=self.repo,
            hh_client=HHPublicSearchClient(user_agent=app_settings.hh_user_agent),
            candidate_profile=default_candidate_profile(self.repo.get_learning_weights()),
            applicant_profile=default_applicant_profile(),
        )
        return agent.run_once(
            queries=self.settings.queries,
            per_query=self.settings.per_query,
            draft_threshold=self.settings.draft_threshold,
        )

    def run_public_and_send(self, *, chat_id: int | str | None = None) -> dict[str, Any]:
        target_chat_id = chat_id or self.saved_chat_id()
        try:
            with exclusive_file_lock(self.settings.run_lock_path):
                result = self.run_public_once()
        except RunLockUnavailable:
            if target_chat_id is not None:
                self.send_text(
                    target_chat_id,
                    "HH поиск уже выполняется. Дождись текущего прогона, потом повтори /queue.",
                )
            return {"skipped": "already_running"}
        if target_chat_id is not None:
            self.send_text(
                target_chat_id,
                "HH no-API прогон завершён: "
                f"вакансий просмотрено {result.get('vacancies_seen', 0)}, "
                f"черновиков создано {result.get('drafts_created', 0)}, "
                f"архивировано stale {result.get('drafts_archived', 0)}, "
                f"ошибок {len(result.get('errors') or [])}.",
            )
            self.send_queue(chat_id=target_chat_id)
        return result

    def generate_single_vacancy_draft(self, text: str) -> dict[str, Any]:
        app_settings = get_settings()
        vacancy = HHPublicVacancyClient(user_agent=app_settings.hh_user_agent).fetch_vacancy(text)
        candidate_profile = default_candidate_profile(self.repo.get_learning_weights())
        applicant_profile = default_applicant_profile()
        score = score_vacancy(vacancy, candidate_profile)
        vacancy_id = self.repo.upsert_vacancy(vacancy, score)
        context = ResponseContext(profile=applicant_profile, vacancy=vacancy, score=score.score)
        generated = generate_cover_letter(context)
        quality = check_cover_letter_quality(generated.message, context)
        application_id = self.repo.create_or_update_application(
            vacancy_id,
            cover_letter=generated.message,
            status="draft",
            score_at_apply=score.score,
        )
        return {
            "vacancy_id": vacancy_id,
            "application_id": application_id,
            "score": score.score,
            "decision": score.decision,
            "quality_issues": quality.issues,
        }

    def handle_hh_vacancy_link(self, *, chat_id: int | str, text: str) -> bool:
        self.register_chat(chat_id)
        try:
            result = self.generate_single_vacancy_draft(text)
        except RuntimeError as exc:
            self.send_text(
                chat_id,
                "Не смог прочитать вакансию HH безопасным публичным способом. "
                f"Причина: {str(exc)[:220]}. Если HH открыл антибот/ошибку — пришли текст вакансии сюда.",
            )
            return True
        row = self.repo.application_review_item(int(result["application_id"]))
        if row is None:
            self.send_text(chat_id, "Черновик создан, но не смог сразу достать его из CRM. Попробуй /queue.")
            return True
        self.send_text(
            chat_id,
            "Готово, сделал целевой черновик по ссылке HH.\n"
            f"Score: {result['score']} / {result['decision']}\n"
            + format_quality_summary([str(issue) for issue in result.get("quality_issues") or []]),
        )
        self.send_text(
            chat_id,
            format_vacancy_message(row, index=1),
            reply_markup=build_review_keyboard(row),
            parse_mode="HTML",
        )
        return True

    def send_methodology(self, *, chat_id: int | str) -> None:
        self.send_text(chat_id, _truncate(load_cover_letter_methodology(), TELEGRAM_MESSAGE_LIMIT))

    def answer_callback(self, callback_query_id: str, text: str, *, show_alert: bool = False) -> None:
        if callback_query_id:
            self.bot.answer_callback_query(callback_query_id, text, show_alert=show_alert)

    def handle_callback_query(self, callback: dict[str, Any]) -> bool:
        callback_query_id = str(callback.get("id") or "")
        data = str(callback.get("data") or "")
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        parsed = _parse_review_callback(data)
        if parsed is None:
            self.answer_callback(callback_query_id, "Не понял действие", show_alert=True)
            return False
        action, application_id = parsed
        if chat_id is not None:
            self.register_chat(chat_id)

        row = self.repo.application_review_item(application_id)
        if row is None:
            self.answer_callback(callback_query_id, "Не нашёл этот отклик в CRM", show_alert=True)
            return True
        vacancy_id, app_id = _row_ids(row)
        if app_id is None:
            self.answer_callback(callback_query_id, "У отклика нет application_id", show_alert=True)
            return True

        if action == "archive":
            self.repo.record_feedback(
                vacancy_id=vacancy_id,
                application_id=app_id,
                event_type="archived",
                notes="Archived from Telegram inline button",
            )
            self.answer_callback(callback_query_id, "Архивировал")
            if chat_id is not None:
                self.send_text(chat_id, f"Архивировал: {row.get('title') or 'вакансия'}")
            return True

        if action == "reject":
            self.repo.record_feedback(
                vacancy_id=vacancy_id,
                application_id=app_id,
                event_type="rejected",
                rating=1,
                notes="Rejected from Telegram inline button",
            )
            for skill in [str(value) for value in row.get("skills") or []][:5]:
                self.repo.update_learning_signal(skill, 0.85, positive=False)
            self.answer_callback(callback_query_id, "Отклонил и убрал из очереди")
            if chat_id is not None:
                self.send_text(chat_id, f"Отклонил: {row.get('title') or 'вакансия'}")
            return True

        if action == "edit":
            self.answer_callback(callback_query_id, "Жду новый текст")
            if chat_id is not None:
                self.send_text(
                    chat_id,
                    "Чтобы заменить черновик, пришли одной командой:\n"
                    f"/edit {app_id} новый текст отклика\n\n"
                    "Правило: начинаем с «Здравствуйте!» и не обращаемся к работодателю "
                    "по названию компании/ИП.",
                )
            return True

        if action == "send":
            self.repo.record_feedback(
                vacancy_id=vacancy_id,
                application_id=app_id,
                event_type="send_requested",
                notes="Safe send gate opened from Telegram inline button",
            )
            self.answer_callback(callback_query_id, "Открыл безопасный send gate")
            if chat_id is not None:
                self.send_text(
                    chat_id,
                    format_send_gate_message(row),
                    reply_markup=build_send_confirmation_keyboard(app_id),
                    parse_mode="HTML",
                )
            return True

        if action == "mark_sent":
            self.repo.record_feedback(
                vacancy_id=vacancy_id,
                application_id=app_id,
                event_type="sent",
                notes="Marked sent from Telegram after manual HH submit",
            )
            self.answer_callback(callback_query_id, "Отметил отправленным")
            if chat_id is not None:
                self.send_text(chat_id, f"Отметил как отправленное: {row.get('title') or 'вакансия'}")
            return True

        if action == "cancel":
            self.answer_callback(callback_query_id, "Оставил в draft")
            if chat_id is not None:
                self.send_text(chat_id, "Ок, оставил черновик в очереди.")
            return True

        self.answer_callback(callback_query_id, "Неизвестное действие", show_alert=True)
        return False

    def handle_edit_command(self, *, chat_id: int | str, text: str) -> bool:
        parts = text.split(maxsplit=2)
        if len(parts) < 3 or not parts[1].isdigit() or not parts[2].strip():
            self.send_text(chat_id, "Формат: /edit ID новый текст отклика")
            return True
        application_id = int(parts[1])
        new_cover_letter = parts[2].strip()
        row = self.repo.application_review_item(application_id)
        if row is None:
            self.send_text(chat_id, f"Не нашёл отклик ID {application_id} в CRM.")
            return True
        if not self.repo.update_application_cover_letter(
            application_id,
            cover_letter=new_cover_letter,
            status="draft",
        ):
            self.send_text(chat_id, f"Не смог обновить отклик ID {application_id}.")
            return True
        vacancy_id, app_id = _row_ids(row)
        self.repo.record_feedback(
            vacancy_id=vacancy_id,
            application_id=app_id,
            event_type="edited",
            notes="Edited from Telegram /edit command",
            edited_cover_letter=new_cover_letter,
        )
        updated = self.repo.application_review_item(application_id)
        self.send_text(chat_id, f"Обновил черновик ID {application_id}.")
        if updated is not None:
            self.send_text(
                chat_id,
                format_vacancy_message(updated, index=1),
                reply_markup=build_review_keyboard(updated),
                parse_mode="HTML",
            )
        return True

    def handle_update(self, update: dict[str, Any]) -> bool:
        if "callback_query" in update:
            return self.handle_callback_query(update.get("callback_query") or {})

        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = str(message.get("text") or "").strip()
        if chat_id is None or not text:
            return False

        if extract_hh_vacancy_id(text) and not text.startswith("/"):
            return self.handle_hh_vacancy_link(chat_id=chat_id, text=text)

        if text.startswith("/start"):
            self.register_chat(chat_id)
            self.send_text(chat_id, "HH агент подключён.\n\n" + format_help_message())
            self.send_queue(chat_id=chat_id)
            return True
        if text.startswith("/queue"):
            self.register_chat(chat_id)
            self.send_queue(chat_id=chat_id)
            return True
        if text.startswith("/summary"):
            self.register_chat(chat_id)
            self.send_summary(chat_id=chat_id)
            return True
        if text.startswith("/run"):
            self.register_chat(chat_id)
            self.run_public_and_send(chat_id=chat_id)
            return True
        if text.startswith("/guide"):
            self.register_chat(chat_id)
            self.send_methodology(chat_id=chat_id)
            return True
        if text.startswith("/edit"):
            self.register_chat(chat_id)
            return self.handle_edit_command(chat_id=chat_id, text=text)
        if text.startswith("/help"):
            self.send_text(chat_id, format_help_message())
            return True
        return False

    def poll_forever(self) -> None:
        offset = _read_int(self.settings.offset_path)
        while True:
            try:
                updates = self.bot.get_updates(offset=offset, timeout=self.settings.poll_timeout)
            except TelegramNetworkError as exc:
                print(f"HH Telegram polling network error; retrying: {exc}", flush=True)
                time.sleep(self.settings.poll_interval_seconds)
                continue
            retry_current_batch = False
            for update in updates:
                update_id = int(update.get("update_id", 0))
                try:
                    self.handle_update(update)
                except TelegramNetworkError as exc:
                    print(f"HH Telegram update handling network error; retrying: {exc}", flush=True)
                    retry_current_batch = True
                    time.sleep(self.settings.poll_interval_seconds)
                    break
                except TelegramAPIError as exc:
                    print(f"HH Telegram update handling API error; skipped update: {exc}", flush=True)
                offset = max(offset or 0, update_id + 1)
                _write_int(self.settings.offset_path, offset)
            if retry_current_batch:
                continue
            if not updates:
                time.sleep(self.settings.poll_interval_seconds)


def _split_message(text: str) -> list[str]:
    if len(text) <= TELEGRAM_MESSAGE_LIMIT:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        chunk = remaining[:TELEGRAM_MESSAGE_LIMIT]
        chunks.append(chunk)
        remaining = remaining[TELEGRAM_MESSAGE_LIMIT:]
    return chunks


def _read_int(path: Path) -> int | None:
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return int(value) if value.isdigit() else None


def _write_int(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(value), encoding="utf-8")


def settings_from_env() -> TelegramReviewSettings:
    queries = [query.strip() for query in os.getenv("HH_TELEGRAM_QUERIES", "").split("|") if query.strip()]
    settings = TelegramReviewSettings(
        chat_id_path=Path(os.getenv("HH_TELEGRAM_CHAT_ID_PATH", "./data/hh_telegram_chat_id.txt")),
        offset_path=Path(os.getenv("HH_TELEGRAM_OFFSET_PATH", "./data/hh_telegram_offset.txt")),
        run_lock_path=Path(os.getenv("HH_TELEGRAM_RUN_LOCK_PATH", "./data/hh_telegram_run.lock")),
        min_score=int(os.getenv("HH_TELEGRAM_MIN_SCORE", "80")),
        limit=int(os.getenv("HH_TELEGRAM_LIMIT", "5")),
        per_query=int(os.getenv("HH_TELEGRAM_PER_QUERY", "20")),
        draft_threshold=int(os.getenv("HH_TELEGRAM_DRAFT_THRESHOLD", "80")),
        poll_timeout=int(os.getenv("HH_TELEGRAM_POLL_TIMEOUT", "30")),
    )
    if queries:
        settings.queries = queries
    return settings


def build_agent_from_env() -> HHTelegramReviewAgent:
    token = os.getenv("HH_TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("HH_TELEGRAM_BOT_TOKEN is required")
    app_settings = get_settings()
    settings = settings_from_env()
    repo = CRMRepository(app_settings.db_path)
    bot = TelegramBotClient(token=token, timeout=max(30.0, float(settings.poll_timeout) + 10.0))
    return HHTelegramReviewAgent(repo=repo, bot=bot, settings=settings)


def register_command_menu(agent: HHTelegramReviewAgent) -> bool:
    try:
        agent.bot.set_my_commands(telegram_command_menu())
    except TelegramNetworkError as exc:
        print(f"HH Telegram command menu skipped after transient network error: {exc}", flush=True)
        return False
    except TelegramAPIError as exc:
        print(f"HH Telegram command menu skipped after Telegram API error: {exc}", flush=True)
        return False
    return True


def deliver_startup_messages(agent: HHTelegramReviewAgent, saved_chat_id: int | str | None) -> None:
    if saved_chat_id is None or os.getenv("HH_TELEGRAM_SEND_ON_START", "1") == "0":
        return
    try:
        agent.send_summary(chat_id=saved_chat_id)
        agent.send_queue(chat_id=saved_chat_id)
    except TelegramNetworkError as exc:
        print(f"HH Telegram startup delivery skipped after transient network error: {exc}", flush=True)
    except TelegramAPIError as exc:
        print(f"HH Telegram startup delivery skipped after Telegram API error: {exc}", flush=True)


def main() -> None:
    agent = build_agent_from_env()
    register_command_menu(agent)
    me = agent.bot.get_me()
    username = me.get("username") or me.get("first_name") or "unknown"
    saved_chat_id = agent.saved_chat_id()
    print(f"HH Telegram agent started as @{username}; chat_id_registered={bool(saved_chat_id)}", flush=True)
    deliver_startup_messages(agent, saved_chat_id)
    agent.poll_forever()


if __name__ == "__main__":
    main()
