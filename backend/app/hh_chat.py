from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol, Sequence
from urllib.parse import urljoin, urlparse

from app.responses import ApplicantProfile

HH_CHAT_URL = "https://hh.ru/chat"
CHAT_LINK_SELECTOR = 'a[data-qa^="chatik-open-chat-"]'
MESSAGE_INPUT_SELECTORS = [
    '[data-qa="chatik-new-message-text"]',
    'textarea[data-qa="chatik-new-message-text"]',
    '[contenteditable="true"][data-qa="chatik-new-message-text"]',
    'textarea',
    '[contenteditable="true"]',
]
SEND_BUTTON_SELECTORS = [
    '[data-qa="chatik-do-send-message"]',
    'button[data-qa="chatik-do-send-message"]',
    'button:has-text("Отправить")',
]
LOGIN_SELECTORS = [
    '[data-qa="login-input-username"]',
    'input[name="username"]',
    'input[name="login"]',
    'input[type="password"]',
]
CLOSED_MARKERS = [
    "спасибо, всё записал",
    "спасибо всё записал",
    "спасибо, все записал",
    "спасибо все записал",
    "спасибо за уделённое время",
    "спасибо за уделенное время",
    "ваши ответы отправлены работодателю",
    "представитель работодателя изучит резюме",
    "если ваш отклик его заинтересует",
    "всё зафиксировал",
    "все зафиксировал",
    "всё записал",
    "все записал",
    "передаю информацию работодателю",
    "передал информацию работодателю",
    "информация передана работодателю",
    "покинул чат",
    "чат завершен",
    "чат завершён",
    "отклик отклонен",
    "отклик отклонён",
    "работодатель отказал",
    "вакансия в архиве",
    "спасибо за ответ",
    "рассмотрим ваше резюме",
    "если навыки и опыт подойдут",
]
QUICK_REPLY_PROMPTS = [
    "какой график работы?",
    "какая схема оплаты?",
    "где находится офис?",
    "где находится место работы?",
    "какой размер зарплаты?",
    "какой опыт нужен?",
    "можно без опыта?",
    "у меня есть профильный опыт",
    "какой стек используется?",
    "чем предстоит заниматься?",
    "можно удаленно?",
    "можно удалённо?",
    "какой формат работы?",
    "могу работать в гибком графике",
    "могу работать только удаленно",
    "могу работать только удалённо",
    "могу работать в офисе",
    "готов к переезду",
    "не готов к переезду",
    "готов пройти тестовое",
    "отправить резюме",
]
FIRST_PERSON_QUICK_REPLY_PREFIXES = [
    "могу ",
    "готов ",
    "готова ",
    "не готов ",
    "не готова ",
    "у меня ",
    "рассматриваю ",
    "хочу ",
    "ищу ",
]
QUESTION_CHIP_PREFIXES = [
    "где находится ",
    "какой график ",
    "какая схема ",
    "какой размер зарплат",
    "какой опыт нужен",
    "можно без опыта",
]
PROBABLE_APPLICANT_STATEMENT_MARKERS = [
    " делал",
    " делала",
    " работал",
    " работала",
    " был опыт",
    " была опыт",
    " могу ",
    " готов ",
    " готова ",
    " строю ",
    " использовал",
    " применял",
    " мой ",
    " у меня ",
]
JOB_DESCRIPTION_SNIPPET_MARKERS = [
    "писать в сопроводительном",
    "укажите в сопроводительном",
    "в сопроводительном сообщении",
    "в сопроводительном письме",
]
QUESTION_MARKERS = [
    "?",
    "подскажите",
    "расскажите",
    "укажите",
    "заполните",
    "ответьте",
    "проставьте",
    "перечислите",
    "готовы ли",
    "готовы рассмотреть",
    "актуально ли",
    "актуальна ли",
    "интересно ли",
    "рассматриваете",
    "удобно ли",
    "когда удобно",
    "есть ли опыт",
    "есть опыт",
    "какой опыт",
    "опыт с",
    "опыт работы",
    "сколько лет",
    "сколько хотите",
    "уровень дохода",
    "желаемый доход",
    "ожидаемый доход",
    "дохода на который",
    "на который вы ориентируетесь",
    "зарплатные ожидания",
    "ожидания по зарплате",
    "какая вилка",
    "какой формат",
    "какой график",
    "можете",
    "сможете",
    "напишите",
    "уточните",
    "пришлите",
    "отправьте",
    "ждем ответ",
    "ждём ответ",
]
DEEP_SCAN_PREVIEW_MARKERS = [
    "собеседование",
    "анкета",
    "опросник",
    "чек-лист",
    "чек лист",
    "чеклист",
    "напоминаю про мой вопрос",
    "напоминаю про вопрос",
    "напоминаю",
]
QUESTIONNAIRE_MARKERS = [
    "анкета",
    "опросник",
    "google forms",
    "forms.gle",
    "docs.google.com/forms",
]
QUESTIONNAIRE_ACTION_MARKERS = [
    "заполн",
    "ответ",
    "перед встреч",
    "перед собесед",
    "ссылка",
    "http://",
    "https://",
]
CHECKLIST_MARKERS = [
    "чек-лист",
    "чек лист",
    "чеклист",
    "checklist",
    "плюс",
    "минус",
    "plus",
    "minus",
]
SAP_HANA_CHECKLIST_MARKERS = [
    "sap hana",
    "trace",
    "трейс",
    "kafka",
    "iceberg",
    "paimon",
]
EXTERNAL_INTERVIEW_MARKERS = [
    "t.me/",
    "telegram.me/",
    "gigarecruiter",
    "giga recruiter",
    "giga-рекрутер",
    "sber",
    "сбер",
]
EXTERNAL_ACTION_MARKERS = [
    "анкет",
    "заполн",
    "опрос",
    "форм",
    "ссылк",
    "перейд",
    "напиш",
    "отправ",
    "пришл",
    "свяж",
    "собесед",
    "интерв",
]
GOOGLE_FORM_HOSTS = {"forms.gle"}
GOOGLE_FORM_DOCS_HOST = "docs.google.com"
SAFE_INTERNAL_URL_HOSTS = {
    "hh.ru",
    "www.hh.ru",
    "spb.hh.ru",
    "moscow.hh.ru",
}
URL_PATTERN = re.compile(r"https?://[^\s<>()\"']+", re.I)
TELEGRAM_HANDLE_PATTERN = re.compile(r"(?<![\w/])@[a-zA-Z0-9_]{5,32}\b")
TELEGRAM_CONTACT_PHRASES = [
    "в телеграм",
    "в telegram",
    "через телеграм",
    "через telegram",
]
TELEGRAM_EXTERNAL_ACTION_MARKERS = [
    "анкет",
    "напиш",
    "отправ",
    "пришл",
    "свяж",
    "собесед",
    "интерв",
]
KNOWN_STACK_TERMS = [
    "python",
    "fastapi",
    "django",
    "react",
    "next.js",
    "node.js",
    "typescript",
    "postgresql",
    "sqlite",
    "redis",
    "docker",
    "telegram",
    "llm",
    "rag",
    "crm",
    "bitrix24",
    "amocrm",
]
HONESTY_TERM_PATTERNS = [
    (re.compile(r"\bkubernetes\b|\bk8s\b", re.I), "Kubernetes"),
    (re.compile(r"\bopenstack\b", re.I), "OpenStack"),
    (re.compile(r"\bjava\b", re.I), "Java"),
    (re.compile(r"\bgolang\b|\bgo\b", re.I), "Go"),
    (re.compile(r"c\+\+", re.I), "C++"),
    (re.compile(r"c#", re.I), "C#"),
    (re.compile(r"\b1[сc]\b", re.I), "1C"),
    (re.compile(r"\bflutter\b", re.I), "Flutter"),
    (re.compile(r"\bswift\b", re.I), "Swift"),
    (re.compile(r"\bvue(?:\.js)?\b|vue\s*3", re.I), "Vue 3"),
    (re.compile(r"\bandroid\b", re.I), "Android"),
    (re.compile(r"\bios\b", re.I), "iOS"),
    (re.compile(r"\bpytorch\b", re.I), "PyTorch"),
    (re.compile(r"\bhadoop\b", re.I), "Hadoop"),
]
LOW_FIT_CHAT_TITLE_PATTERNS = [
    (re.compile(r"(?<![a-z0-9])a?qa(?![a-z0-9])", re.I), "QA/AQA"),
    (
        re.compile(
            r"(?<![a-z0-9])tester(?![a-z0-9])|тестировщик|тестировани[ея]|автотест",
            re.I,
        ),
        "tester/testing",
    ),
    (re.compile(r"(?<![a-z0-9])mlops(?![a-z0-9])", re.I), "MLOps"),
    (re.compile(r"(?<![a-z0-9])devops(?![a-z0-9])|dev\s*ops", re.I), "DevOps"),
]


class LocatorLike(Protocol):
    def count(self) -> int: ...
    def fill(self, value: str) -> None: ...
    def click(self) -> None: ...
    def is_visible(self) -> bool: ...


class PageLike(Protocol):
    url: str

    def goto(self, url: str, wait_until: str = "domcontentloaded") -> None: ...
    def wait_for_load_state(self, state: str) -> None: ...
    def locator(self, selector: str) -> LocatorLike: ...


@dataclass(slots=True)
class HHChatPreview:
    chat_id: str
    url: str
    title: str
    preview: str


@dataclass(slots=True)
class HHChatMessage:
    text: str
    is_mine: bool = False


@dataclass(slots=True)
class ExternalTarget:
    kind: str
    value: str
    url: str | None = None


@dataclass(slots=True)
class QuestionnaireAnswer:
    question: str
    answer: str


@dataclass(slots=True)
class PreparedExternalResponse:
    copy_paste_message: str
    answers: list[QuestionnaireAnswer] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def answers_text(self) -> str:
        return "\n".join(f"{item.question}: {item.answer}" for item in self.answers)


@dataclass(slots=True)
class ExternalHandoffAlert:
    chat_id: str
    title: str
    chat_url: str
    external_targets: list[ExternalTarget]
    original_message: str
    prepared_response: PreparedExternalResponse
    reason: str = "external_handoff"


@dataclass(slots=True)
class GoogleFormRequest:
    chat_id: str
    title: str
    chat_url: str
    form_url: str
    original_message: str
    prepared_response: PreparedExternalResponse


@dataclass(slots=True)
class ExternalFormResult:
    status: str
    message: str
    url: str
    filled_fields: int = 0
    submitted: bool = False


class ExternalFormHandler(Protocol):
    def handle_google_form(self, request: GoogleFormRequest, *, submit: bool = False) -> ExternalFormResult: ...


class ExternalAlertNotifier(Protocol):
    def send_alert(self, alert: ExternalHandoffAlert) -> None: ...


@dataclass(slots=True)
class HHChatReplyResult:
    chat_id: str | None
    title: str
    status: str
    question: str
    reply: str
    url: str
    message: str
    external_targets: list[dict[str, Any]] = field(default_factory=list)
    external_result: dict[str, Any] | None = None


@dataclass(slots=True)
class HHChatRunResult:
    scanned: int
    candidates: int
    sent: int
    drafted: int
    skipped: int
    blocked: int
    send_enabled: bool
    statuses: list[str]
    replies: list[dict[str, Any]]
    external_submit_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HHChatReplyDraft:
    message: str
    reasons: list[str]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\u00a0", " ")).strip()


def _lower(value: str) -> str:
    return normalize_text(value).lower()


def _text_hash(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()[:16]


class HHChatReplyState:
    def __init__(self, path: str | Path = "./data/hh_chat_reply_state.json") -> None:
        self.path = Path(path)
        self.data: dict[str, Any] = {"answered": {}, "external": {}}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if isinstance(loaded, dict):
            answered = loaded.get("answered")
            external = loaded.get("external")
            self.data = {
                "answered": answered if isinstance(answered, dict) else {},
                "external": external if isinstance(external, dict) else {},
            }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _key(self, chat_id: str, question: str) -> str:
        return f"{chat_id}:{_text_hash(question)}"

    def _external_key(self, chat_id: str, question: str, target: str, action: str) -> str:
        return f"{chat_id}:{_text_hash(question)}:{_text_hash(target)}:{action}"

    def was_answered(self, chat_id: str, question: str) -> bool:
        return self._key(chat_id, question) in self.data.get("answered", {})

    def mark_answered(self, *, chat_id: str, question: str, reply: str, status: str) -> None:
        self.data.setdefault("answered", {})[self._key(chat_id, question)] = {
            "chat_id": chat_id,
            "question_hash": _text_hash(question),
            "reply_hash": _text_hash(reply),
            "status": status,
        }
        self.save()

    def was_external_handled(self, *, chat_id: str, question: str, target: str, action: str) -> bool:
        return self._external_key(chat_id, question, target, action) in self.data.get("external", {})

    def mark_external_handled(
        self,
        *,
        chat_id: str,
        question: str,
        target: str,
        action: str,
        status: str,
        message: str = "",
    ) -> None:
        self.data.setdefault("external", {})[
            self._external_key(chat_id, question, target, action)
        ] = {
            "chat_id": chat_id,
            "question_hash": _text_hash(question),
            "target_hash": _text_hash(target),
            "action": action,
            "status": status,
            "message_hash": _text_hash(message),
        }
        self.save()


def _strip_url_punctuation(url: str) -> str:
    return normalize_text(url).strip(" \t\r\n'\"").rstrip(".,!?;:)]}")


def extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for match in URL_PATTERN.finditer(text or ""):
        url = _strip_url_punctuation(match.group(0))
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _host(url: str) -> str:
    return (urlparse(url).netloc or "").lower().removeprefix("www.")


def is_google_form_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower().removeprefix("www.")
    path = parsed.path.lower()
    return host in GOOGLE_FORM_HOSTS or (host == GOOGLE_FORM_DOCS_HOST and path.startswith("/forms/"))


def extract_google_form_links(text: str) -> list[str]:
    return [url for url in extract_urls(text) if is_google_form_url(url)]


def _is_internal_hh_url(url: str) -> bool:
    return _host(url) in SAFE_INTERNAL_URL_HOSTS


def _is_telegram_url(url: str) -> bool:
    return _host(url) in {"t.me", "telegram.me", "telegram.dog"}


def _has_external_action_context(text: str) -> bool:
    lowered = _lower(text)
    return any(marker in lowered for marker in EXTERNAL_ACTION_MARKERS)


def extract_external_targets(text: str, *, include_google_forms: bool = False) -> list[ExternalTarget]:
    lowered = _lower(text)
    targets: list[ExternalTarget] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, value: str, url: str | None = None) -> None:
        key = (kind, value)
        if value and key not in seen:
            seen.add(key)
            targets.append(ExternalTarget(kind=kind, value=value, url=url))

    for url in extract_urls(text):
        if is_google_form_url(url):
            if include_google_forms:
                add("google_form", url, url)
            continue
        if _is_internal_hh_url(url):
            continue
        if _is_telegram_url(url):
            add("telegram_link", url, url)
            continue
        if any(marker in url.lower() for marker in ["gigarecruiter", "sber"]) or _has_external_action_context(text):
            add("external_url", url, url)

    for match in TELEGRAM_HANDLE_PATTERN.finditer(text or ""):
        handle = match.group(0)
        has_telegram_destination = any(phrase in lowered for phrase in TELEGRAM_CONTACT_PHRASES)
        has_plain_telegram_instruction = "telegram" in lowered and any(
            marker in lowered for marker in TELEGRAM_EXTERNAL_ACTION_MARKERS
        )
        if has_telegram_destination or has_plain_telegram_instruction:
            add("telegram_handle", handle, None)

    for marker in ("gigarecruiter", "giga recruiter", "giga-рекрутер", "sber", "сбер"):
        if marker in lowered and _has_external_action_context(text):
            add("external_reference", marker, None)

    return targets


def is_external_interview_link(text: str) -> bool:
    if extract_external_targets(text):
        return True
    lowered = _lower(text)
    if any(marker in lowered for marker in EXTERNAL_INTERVIEW_MARKERS):
        return _has_external_action_context(text)
    if not TELEGRAM_HANDLE_PATTERN.search(text):
        return False
    has_telegram_destination = any(phrase in lowered for phrase in TELEGRAM_CONTACT_PHRASES)
    has_plain_telegram_instruction = "telegram" in lowered and any(
        marker in lowered for marker in TELEGRAM_EXTERNAL_ACTION_MARKERS
    )
    return has_telegram_destination or has_plain_telegram_instruction


def _punctuation_insensitive_text(value: str) -> str:
    return normalize_text(re.sub(r"[^\w\s]+", " ", _lower(value)))


def is_closed_chat_text(text: str) -> bool:
    lowered = _lower(text)
    compact = _punctuation_insensitive_text(lowered)
    for marker in CLOSED_MARKERS:
        marker_lowered = _lower(marker)
        if marker_lowered in lowered or _punctuation_insensitive_text(marker_lowered) in compact:
            return True
    return False


def should_deep_scan_preview(text: str) -> bool:
    lowered = _lower(text)
    return bool(lowered) and any(marker in lowered for marker in DEEP_SCAN_PREVIEW_MARKERS)


def is_questionnaire_prompt(text: str) -> bool:
    lowered = _lower(text)
    if not lowered:
        return False
    has_marker = any(marker in lowered for marker in QUESTIONNAIRE_MARKERS)
    if not has_marker:
        return False
    if "forms.gle" in lowered or "docs.google.com/forms" in lowered:
        return True
    return any(marker in lowered for marker in QUESTIONNAIRE_ACTION_MARKERS)


def is_checklist_prompt(text: str) -> bool:
    lowered = _lower(text)
    if not lowered:
        return False
    has_checklist_marker = any(marker in lowered for marker in CHECKLIST_MARKERS)
    has_action = any(marker in lowered for marker in ["ответьте", "проставьте", "укажите"])
    has_technical_marker = any(marker in lowered for marker in SAP_HANA_CHECKLIST_MARKERS)
    return has_checklist_marker or (has_action and has_technical_marker)


def is_sap_hana_checklist_prompt(text: str) -> bool:
    lowered = _lower(text)
    return "sap hana" in lowered and is_checklist_prompt(lowered)


def is_quick_reply_prompt(text: str) -> bool:
    lowered = _lower(text).rstrip(".!…")
    padded = f" {lowered} "
    if any(lowered == prompt.rstrip("?") or lowered == prompt for prompt in QUICK_REPLY_PROMPTS):
        return True
    if any(lowered.startswith(prefix) for prefix in FIRST_PERSON_QUICK_REPLY_PREFIXES):
        return True
    if any(lowered.startswith(prefix) for prefix in QUESTION_CHIP_PREFIXES):
        return True
    return "?" not in lowered and any(marker in padded for marker in PROBABLE_APPLICANT_STATEMENT_MARKERS)


def is_job_description_snippet(text: str) -> bool:
    lowered = _lower(text)
    return any(marker in lowered for marker in JOB_DESCRIPTION_SNIPPET_MARKERS)


def is_reply_candidate(text: str) -> bool:
    lowered = _lower(text)
    if not lowered or is_closed_chat_text(lowered) or is_quick_reply_prompt(lowered) or is_job_description_snippet(lowered):
        return False
    if is_external_interview_link(text):
        return True
    if is_questionnaire_prompt(lowered) or is_checklist_prompt(lowered):
        return True
    return any(marker in lowered for marker in QUESTION_MARKERS)


def extract_chat_id(value: str) -> str:
    match = re.search(r"chatik-open-chat-([\w-]+)", value or "") or re.search(r"/chat/([\w-]+)", value or "")
    return match.group(1) if match else _text_hash(value or HH_CHAT_URL)


def _is_chat_list_metadata_line(line: str) -> bool:
    lowered = _lower(line)
    if not lowered:
        return True
    if re.fullmatch(r"\d+", lowered):
        return True
    if re.fullmatch(r"\d{1,2}:\d{2}", lowered):
        return True
    return lowered in {"сегодня", "вчера"}


def preview_from_raw(raw: dict[str, Any]) -> HHChatPreview | None:
    href = str(raw.get("href") or raw.get("url") or "")
    data_qa = str(raw.get("dataQa") or raw.get("data_qa") or raw.get("data-qa") or "")
    text = normalize_text(str(raw.get("text") or ""))
    if not href and not data_qa and not text:
        return None
    chat_id = extract_chat_id(" ".join([href, data_qa, text]))
    url = urljoin(HH_CHAT_URL, href) if href else f"{HH_CHAT_URL}/{chat_id}"
    lines = [normalize_text(line) for line in str(raw.get("text") or "").splitlines() if normalize_text(line)]
    title = lines[0] if lines else (normalize_text(str(raw.get("title") or "")) or chat_id)
    message_lines = [line for line in lines[1:] if not _is_chat_list_metadata_line(line)]
    preview = message_lines[-1] if message_lines else (lines[-1] if lines else text)
    return HHChatPreview(chat_id=chat_id, url=url, title=title, preview=preview)


def chat_message_from_raw(raw: dict[str, Any] | HHChatMessage) -> HHChatMessage | None:
    if isinstance(raw, HHChatMessage):
        text = normalize_text(raw.text)
        return HHChatMessage(text=text, is_mine=raw.is_mine) if text else None
    if not isinstance(raw, dict):
        return None
    text = normalize_text(str(raw.get("text") or ""))
    if not text:
        return None
    is_mine = bool(raw.get("isMine") or raw.get("is_mine") or raw.get("mine"))
    return HHChatMessage(text=text, is_mine=is_mine)


def extract_latest_question_from_messages(
    messages: list[dict[str, Any] | HHChatMessage],
    fallback_preview: str = "",
) -> str | None:
    parsed = [message for raw in messages if (message := chat_message_from_raw(raw))]
    if not parsed:
        return None

    for message in reversed(parsed):
        if message.is_mine:
            continue
        if is_closed_chat_text(message.text):
            return message.text
        if is_reply_candidate(message.text):
            return message.text

    fallback = normalize_text(fallback_preview)
    if fallback and (is_closed_chat_text(fallback) or is_reply_candidate(fallback)):
        return fallback
    return ""


def extract_latest_question(conversation_text: str, fallback_preview: str) -> str:
    lines = [normalize_text(line) for line in conversation_text.splitlines() if normalize_text(line)]
    ignored = (
        "чат",
        "написать сообщение",
        "отправить",
        "hh.ru",
        "сегодня",
        "вчера",
        "понедельник",
        "вторник",
        "среда",
        "четверг",
        "пятница",
        "суббота",
        "воскресенье",
    )
    for line in reversed(lines[-80:]):
        lowered = line.lower()
        if len(line) > 1200 or lowered in ignored:
            continue
        if is_closed_chat_text(line):
            return line
        if is_reply_candidate(line):
            return line
    return normalize_text(fallback_preview)


def format_chat_context(
    messages: Sequence[dict[str, Any] | HHChatMessage],
    *,
    max_messages: int = 24,
) -> str:
    parsed = [message for raw in messages if (message := chat_message_from_raw(raw))]
    lines: list[str] = []
    for message in parsed[-max(max_messages, 1) :]:
        speaker = "Я" if message.is_mine else "Работодатель"
        text = normalize_text(message.text)
        if text:
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def _contains_any(text: str, markers: list[str]) -> bool:
    lowered = _lower(text)
    return any(marker in lowered for marker in markers)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def low_fit_chat_title_guard_enabled() -> bool:
    return not (
        _env_flag("HH_CHAT_REPLY_ANSWER_LOW_FIT")
        or _env_flag("HH_CHAT_REPLY_ALL_TITLES")
    )


def external_handoff_ack_enabled() -> bool:
    return _env_flag("HH_CHAT_REPLY_ACK_EXTERNAL_HANDOFF")


def external_handoff_ack_message(question: str, profile: ApplicantProfile) -> str:
    telegram = _telegram_nick(profile)
    if is_google_form_url(question) or "forms.gle" in _lower(question) or "docs.google.com/forms" in _lower(question):
        base = "Здравствуйте! Ссылку получил, спасибо."
    else:
        base = "Здравствуйте! Ссылку получил, спасибо."
    if telegram:
        return f"{base} Telegram: {telegram}"
    return base


def low_fit_chat_title_reason(title: str) -> str | None:
    normalized = normalize_text(title)
    if not normalized:
        return None
    for pattern, label in LOW_FIT_CHAT_TITLE_PATTERNS:
        if pattern.search(normalized):
            return label
    return None


def is_database_experience_question(text: str) -> bool:
    lowered = _lower(text)
    has_database_term = _contains_any(
        lowered,
        [
            "sql",
            "nosql",
            "вектор",
            "vector",
            "postgres",
            "redis",
            "elastic",
            "elasticsearch",
            "database",
            "субд",
            "база данных",
            "базы данных",
            "баз данных",
            "базами",
            "базах",
        ],
    )
    if not has_database_term:
        return False
    return is_concrete_experience_question(lowered) or _contains_any(
        lowered,
        [
            "какие базы",
            "какими базами",
            "с какими баз",
            "базы данных вы",
            "базами данных вы",
        ],
    )


def is_concrete_experience_question(text: str) -> bool:
    lowered = _lower(text)
    return _contains_any(
        lowered,
        [
            "какой опыт",
            "какой у вас опыт",
            "какой у вас production-опыт",
            "production-опыт",
            "продакшн-опыт",
            "каким опытом",
            "есть ли опыт",
            "есть ли у вас опыт",
            "был ли опыт",
            "был ли у вас опыт",
            "опыт с",
            "работали с",
            "работал с",
            "использовали",
            "использовал",
            "применяли",
            "приходилось",
            "расскажите",
            "опишите",
            "перечислите",
            "с какими",
            "что вы",
            "как вы",
            "сколько лет",
        ],
    )


def is_stack_experience_question(text: str) -> bool:
    lowered = _lower(text)
    has_stack_term = _contains_any(
        lowered,
        [
            "стек",
            "python",
            "fastapi",
            "react",
            "next",
            "node",
            "node.js",
            "typescript",
            "vue",
            "llm",
            "rag",
            "telegram",
            "docker",
            "backend",
            "frontend",
        ],
    )
    has_stack_question = _contains_any(
        lowered,
        ["какой стек", "стек технологий", "технологический стек"],
    )
    return has_stack_term and (has_stack_question or is_concrete_experience_question(lowered))


def is_python_vue_experience_question(text: str) -> bool:
    lowered = _lower(text)
    if not lowered:
        return False
    return (
        "python" in lowered
        and "vue" in lowered
        and _contains_any(lowered, ["production-опыт", "продакшн-опыт", "какой у вас", "опыт"])
    )


def is_algorithms_data_structures_question(text: str) -> bool:
    lowered = _lower(text)
    if not lowered:
        return False
    return _contains_any(lowered, ["алгоритм", "структур"]) and _contains_any(
        lowered,
        ["пример", "использовали", "использовал", "применяли", "решить задачу", "помогло"],
    )


def is_autotest_ci_metrics_question(text: str) -> bool:
    lowered = _lower(text)
    if not lowered:
        return False
    asks_for_detail = _contains_any(
        lowered,
        ["опишите", "как именно", "какие метрики", "метрики качества", "этапы пайплайна"],
    )
    if not asks_for_detail:
        return False
    has_autotest = _contains_any(lowered, ["автотест", "auto test", "autotest", "pytest", "playwright"])
    has_pipeline = _contains_any(
        lowered,
        ["конвейер", "pipeline", "ci/cd", "сборк", "разверт", "развёрт", "деплой", "deploy"],
    )
    has_metrics = _contains_any(lowered, ["метрик", "качества", "этапы пайплайна"])
    return has_autotest and (has_pipeline or has_metrics)


def is_availability_only_prompt(text: str) -> bool:
    lowered = _lower(text)
    if not lowered:
        return False
    has_availability = _contains_any(
        lowered,
        [
            "актуально ли",
            "актуальна ли",
            "актуален ли",
            "готовы ли рассмотреть",
            "готовы рассмотреть",
            "готовы ли обсудить",
            "готовы обсудить",
            "готов ли обсудить",
            "интересно ли",
            "интересна ли",
            "рассматриваете ли",
            "рассматриваете вакансию",
            "рассмотреть эту вакансию",
            "рассмотреть вакансию",
        ],
    )
    if not has_availability:
        return False
    if is_database_experience_question(lowered) or is_stack_experience_question(lowered):
        return False
    return not _contains_any(
        lowered,
        [
            "есть ли",
            "был ли",
            "приходилось",
            "расскажите",
            "опишите",
            "перечислите",
            "сколько",
            "какой у вас",
            "какую заработ",
            "зарплат",
            "доход",
            "ожидания",
            "график",
            "формат",
            "уровень англ",
            "где вы",
            "локац",
            "когда удобно",
            "с какими",
            "что вы",
            "как вы",
            "тестовое",
            "тз",
            "задание",
        ],
    )


def is_vacancy_point_fit_prompt(text: str) -> bool:
    lowered = _lower(text)
    if not lowered:
        return False
    has_fit = _contains_any(lowered, ["соответств", "подходит", "подхожу", "матч"])
    has_vacancy_context = _contains_any(lowered, ["ваканс", "описанн"])
    has_stack_context = _contains_any(lowered, ["стек", "технолог", "опыт", "навык", "скилл"])
    has_point_context = bool(re.search(r"\b\d+\s+пункт", lowered)) or (
        "по каждому" in lowered and "пункт" in lowered
    )
    # Do not hijack normal recruiter screening questions. The point-fit template is only for
    # explicit vacancy/checklist fit prompts, not for concrete Django/FastAPI/salary questions.
    has_concrete_screening = _contains_any(
        lowered,
        ["django", "fastapi", "drf", "модел", "миграц", "dependency injection", "websocket"],
    ) and _contains_any(lowered, ["зарплат", "вилка", "график", "сколько", "оптимиз"])
    if has_concrete_screening:
        return False
    return (has_point_context and (has_fit or has_stack_context)) or (
        has_fit and has_vacancy_context and has_stack_context
    )


def is_django_fastapi_screening_prompt(text: str) -> bool:
    lowered = _lower(text)
    if not lowered:
        return False
    has_frameworks = "django" in lowered and "fastapi" in lowered
    has_screening = _contains_any(
        lowered,
        [
            "drf",
            "модел",
            "миграц",
            "websocket",
            "dependency injection",
            "оптимиз",
            "orm",
            "sql",
        ],
    )
    return has_frameworks and has_screening


def is_contract_logistics_prompt(text: str) -> bool:
    lowered = _lower(text)
    if not lowered:
        return False
    has_location = _contains_any(
        lowered,
        ["где вы проживаете", "где проживаете", "ваш город", "город проживания", "локац", "location"],
    )
    has_b2b_contract = _contains_any(lowered, ["b2b", "б2б"]) and _contains_any(
        lowered,
        ["контракт", "договор", "сотруднич", "оформлен", "оформление"],
    )
    has_legal_contract = _contains_any(lowered, ["ип", "самозан", "гпх"]) and _contains_any(
        lowered,
        ["контракт", "договор", "сотруднич", "оформлен", "формат"],
    )
    return has_location or has_b2b_contract or has_legal_contract


def is_choice_required_prompt(text: str) -> bool:
    lowered = _lower(text)
    if not lowered:
        return False
    return _contains_any(
        lowered,
        [
            "выберите один из предложенных вариантов",
            "выберите один вариант",
            "выберите вариант",
            "один из предложенных вариантов",
            "предложенных вариантов",
        ],
    )


def _profile_location_sentence(profile: ApplicantProfile) -> str:
    location = _profile_location(profile) or "[указать город/часовой пояс]"
    return f"Проживаю: {location}."


def _unknown_terms(question: str, skills: list[str]) -> list[str]:
    lowered = _lower(question)
    known = {skill.lower() for skill in skills}
    unknown: list[str] = []
    for pattern, label in HONESTY_TERM_PATTERNS:
        if pattern.search(lowered) and label.lower() not in known:
            unknown.append(label)
    return sorted(set(unknown))


def _portfolio_url(profile: ApplicantProfile) -> str | None:
    return profile.portfolio_url or getattr(profile, "website_url", None)


def _telegram_nick(profile: ApplicantProfile) -> str | None:
    for field_name in ("telegram", "telegram_nick", "telegram_username"):
        value = normalize_text(str(getattr(profile, field_name, "") or ""))
        if value:
            return value
    value = normalize_text(os.getenv("HH_PROFILE_TELEGRAM") or os.getenv("HH_TELEGRAM_NICK") or "")
    return value or None


def _profile_location(profile: ApplicantProfile) -> str | None:
    value = normalize_text(
        os.getenv("HH_PROFILE_LOCATION")
        or str(getattr(profile, "location", "") or "")
        or str(getattr(profile, "city", "") or "")
        or ""
    )
    return value or None


def _context_focus_sentence(context: str) -> str | None:
    lowered = _lower(context)
    if not lowered:
        return None
    if _contains_any(lowered, ["llm", "rag", "ai", "искусственн", "агент", "agent", "нейросет"]):
        return "По контексту ближе всего мой опыт в AI-агентах, LLM/RAG, Python/FastAPI и интеграциях."
    if _contains_any(lowered, ["python", "fastapi", "django", "backend", "api", "postgres", "redis"]):
        return "По контексту ближе всего мой опыт в Python/backend, FastAPI/Django, API, PostgreSQL/Redis и интеграциях."
    if _contains_any(lowered, ["react", "next.js", "nextjs", "frontend", "fullstack", "full-stack"]):
        return "По контексту ближе всего мой опыт в full-stack: React/Next.js, backend/API и интеграции."
    return None


def humanize_hh_chat_reply(text: str) -> str:
    text = text.replace("—", "-").replace("–", "-").replace("«", "").replace("»", "")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    return text


def _humanize_multiline(text: str) -> str:
    lines = [humanize_hh_chat_reply(line) for line in (text or "").splitlines()]
    return "\n".join(line for line in lines if line)


def generate_hh_chat_reply(question: str, profile: ApplicantProfile, *, context: str = "") -> HHChatReplyDraft:
    lowered = _lower(question)
    context_focus = _context_focus_sentence(context)
    skills = list(getattr(profile, "skills", []) or [])
    # ApplicantProfile in responses.py does not expose skills directly, so derive a compact known set
    # from headline, strengths and case stacks when available.
    for case in getattr(profile, "cases", []) or []:
        skills.extend(getattr(case, "stack", []) or [])
    strengths = list(getattr(profile, "strengths", []) or [])
    portfolio = _portfolio_url(profile)

    sentences: list[str] = ["Здравствуйте!"]
    reasons: list[str] = []

    if is_questionnaire_prompt(lowered):
        return HHChatReplyDraft(
            message=humanize_hh_chat_reply("Здравствуйте! Спасибо, получил анкету, посмотрю."),
            reasons=["questionnaire_ack"],
        )

    if is_sap_hana_checklist_prompt(lowered):
        telegram = _telegram_nick(profile)
        location = _profile_location(profile)
        manual_required = not telegram or not location
        message = _humanize_multiline(
            "Здравствуйте! Отвечаю по полному чек-листу.\n\n"
            "Требования:\n"
            "[-] SAP HANA diagnostic/trace files - глубокого production опыта нет.\n"
            "[+] Python - основной production стек; backend tooling, парсинг логов/файлов, интеграции.\n"
            "[-] Go - не основной production стек.\n"
            "[-] Java - не основной production стек.\n"
            "[-] C++ - не основной production стек.\n"
            "[-] Rust - не основной production стек.\n"
            "[-] SAP HANA как источник данных - не заявляю production опыт.\n"
            "[-] Iceberg/Paimon - production опыт не заявляю.\n"
            "[-] Apache Kafka - production опыт не заявляю.\n"
            "[+/-] Data engineering / observability / SRE - смежно делал backend pipelines, health-checks, мониторинг и recovery, но не как выделенный SRE/Data Engineer.\n\n"
            "Условия:\n"
            "1) ИП/СЗ - можно обсуждать.\n"
            "2) Аутстафф - можно обсуждать.\n"
            f"3) ЗП - {_salary_positioning_text()}\n"
            f"4) Локация - {location or '[указать город/часовой пояс]'}.\n"
            f"5) Telegram - {telegram or '[указать Telegram-ник]'} .\n\n"
            "Если по роли критичны именно SAP HANA/Iceberg/Paimon/Kafka в production, честно скажу: я не самый точный кандидат. "
            "Если нужен сильный Python/backend-инженер под tooling, pipelines, интеграции и автоматизацию анализа, тогда можем обсудить."
        ).replace("[указать Telegram-ник] .", "[указать Telegram-ник].")
        reasons = ["sap_hana_checklist_honesty", "salary"]
        if manual_required:
            reasons.append("manual_required")
        return HHChatReplyDraft(message=message, reasons=reasons)

    if "ansible" in lowered:
        return HHChatReplyDraft(
            message=humanize_hh_chat_reply(
                "Здравствуйте! Глубокого production опыта с Ansible не заявляю. "
                "Смежная автоматизация развёртывания у меня была через Docker/Docker Compose, "
                "CI/CD, scripts и health-checks/monitoring."
            ),
            reasons=["ansible_honesty"],
        )

    if _contains_any(lowered, ["node.js", "node js", "node"]) and is_concrete_experience_question(lowered):
        return HHChatReplyDraft(
            message=humanize_hh_chat_reply(
                "Здравствуйте! Да, опыт с Node.js есть в реальных проектах на стыке backend/full-stack: "
                "API, интеграции и связка с React/Next.js. При этом основной production-стек у меня Python/FastAPI/Django, "
                "поэтому Node.js не называю главным стеком, но работать с ним в продуктовых задачах могу."
            ),
            reasons=["nodejs_experience", "python_primary_stack"],
        )

    if is_python_vue_experience_question(lowered):
        return HHChatReplyDraft(
            message=humanize_hh_chat_reply(
                "Здравствуйте! По Python production-опыт основной: примерно с 2025 года. "
                "Делал FastAPI/backend, API, LLM/RAG и агентные сервисы, интеграции, PostgreSQL/Redis/Docker, деплой и поддержку. "
                "По Vue 3 честно: глубокий production-опыт не заявляю. На frontend ближе React/Next.js, "
                "но с Vue 3 смогу быстро встроиться, потому что fullstack-логика, API, компоненты и состояние мне понятны."
            ),
            reasons=["python_vue_screening", "python_production", "vue_honesty"],
        )

    if is_algorithms_data_structures_question(lowered):
        return HHChatReplyDraft(
            message=humanize_hh_chat_reply(
                "Здравствуйте! Пример ближе всего из проекта по поиску арбитражных связок на 30+ криптобиржах. "
                "Использовал словари для быстрого доступа к котировкам по бирже и торговой паре, "
                "очереди задач для обновления данных, сортировку и фильтры по спреду, комиссиям и ликвидности. "
                "Это помогло быстро отсекать слабые варианты и показывать только связки, которые имело смысл проверять дальше."
            ),
            reasons=["algorithms_data_structures"],
        )

    if is_autotest_ci_metrics_question(lowered):
        return HHChatReplyDraft(
            message=humanize_hh_chat_reply(
                "Здравствуйте! В чистой роли не pure QA я не работал, но автотесты и проверки в CI/CD интегрировал "
                "на backend/automation проектах. Обычно это были pytest/unit/integration, smoke-проверки после сборки "
                "или деплоя, линтеры, проверки API и health-checks. В пайплайне важнее всего были этапы: install/build, "
                "lint/test, подготовка окружения, deploy, smoke/health-check. По метрикам смотрел прохождение тестов, "
                "падения сборки, время пайплайна, стабильность деплоя и ошибки после релиза."
            ),
            reasons=["autotest_ci_metrics", "qa_honesty"],
        )

    if is_django_fastapi_screening_prompt(lowered):
        return HHChatReplyDraft(
            message=_humanize_multiline(
                "Здравствуйте! По FastAPI опыт сильнее: примерно с 2025 года, около 1,5 лет. "
                "Делал backend/API, async endpoints, dependency injection, связку с PostgreSQL/Redis/Docker, "
                "интеграции, OAuth/billing/deploy и production-support. WebSocket-контуры тоже были, "
                "но не буду завышать это как главный фокус.\n\n"
                "По Django/DRF опыт есть, но меньше, чем FastAPI: модели, миграции, DRF/API, админка и backend-задачи. "
                "Если нужно строго по годам: FastAPI примерно 1,5 года, Django/DRF - около года проектного опыта.\n\n"
                "Медленный запрос в Django/ORM обычно разбираю от факта: смотрю SQL/EXPLAIN, N+1, индексы, "
                "select_related/prefetch_related, форму запроса и только потом кеширование.\n\n"
                "График МСК+2 с 09:00 до 18:00 в целом комфортен. По вилке: "
                "120000 для удаленного формата могу обсудить, особенно если есть быстрый старт, "
                "стабильность или понятный рост. В целом сейчас рассматриваю удаленные варианты от 100000 до 200000. "
                "300000+ - комфортный ориентир, не жесткий порог."
            ),
            reasons=["django_fastapi_screening", "salary", "format"],
        )

    if is_choice_required_prompt(lowered):
        return HHChatReplyDraft(
            message=humanize_hh_chat_reply(
                "Здравствуйте! Тут нужно выбрать один из вариантов в интерфейсе, а вариантов в тексте чата не видно. "
                "Оставлю на ручную проверку, чтобы не выбрать не то."
            ),
            reasons=["choice_required", "manual_required"],
        )

    if is_contract_logistics_prompt(lowered):
        location_missing = not _profile_location(profile)
        reasons = ["contract_logistics"]
        if location_missing:
            reasons.append("manual_required")
        return HHChatReplyDraft(
            message=_humanize_multiline(
                "Здравствуйте!\n\n"
                f"{_profile_location_sentence(profile)}\n\n"
                "К B2B-контракту открыт, такой формат сотрудничества можно обсуждать. "
                "По юридическим деталям готов свериться под ваш процесс оформления."
            ),
            reasons=reasons,
        )

    if is_vacancy_point_fit_prompt(lowered):
        return HHChatReplyDraft(
            message=humanize_hh_chat_reply(
                "Здравствуйте! Если кратко: основное соответствие - Python/backend, "
                "PostgreSQL/Redis/Docker, APIs/интеграции и LLM/agent-инфраструктура. "
                "По глубокому Go/Kafka/Elastic/Geo и другим production-only пунктам "
                "без подтвержденного опыта не буду ставить себе плюс. "
                "В сообщении нет самих 21 пунктов, поэтому не буду делать вид, "
                "что могу разметить их точно. Если нужен строгий +/- по каждому пункту, "
                "пришлите список в чат, отвечу построчно."
            ),
            reasons=["vacancy_point_fit_honesty"],
        )

    if _contains_any(lowered, ["сколько лет", "опыт в коммерческих", "коммерческих ml", "коммерческих ai"]):
        if _contains_any(lowered, ["ml", "ai", "llm", "нейросет", "искусствен", "машинн"]):
            return HHChatReplyDraft(
                message=humanize_hh_chat_reply(
                    "Здравствуйте! Если именно про коммерческие AI/ML/LLM-проекты, то с 2025 года, примерно 1,5 года. "
                    "Основной фокус - прикладные LLM/agent systems: Viably, Vibegent, LLM-proxy, RAG/agent runtime, backend и интеграции. "
                    "Классический ML research/fine-tuning не заявляю как основной профиль."
                ),
                reasons=["commercial_ai_years_honesty"],
            )

    if is_availability_only_prompt(lowered):
        message = "Здравствуйте! Да, актуально, готов обсудить."
        reasons = ["actuality"]
        if context_focus:
            message = f"{message} {context_focus}"
            reasons.append("context_focus")
        return HHChatReplyDraft(
            message=humanize_hh_chat_reply(message),
            reasons=reasons,
        )

    if _contains_any(lowered, ["актуаль", "интерес", "рассматриваете", "готовы", "готов ли"]):
        sentences.append("Да, актуально, готов обсудить.")
        reasons.append("actuality")

    if _contains_any(lowered, ["англ", "english", "язык"]):
        sentences.append(
            "По английскому без завышения: в профиле отдельный уровень не указан. "
            "Техническую документацию читаю, для регулярного spoken English лучше проверить на коротком интервью."
        )
        reasons.append("english_honesty")

    if _contains_any(lowered, ["b2b", "б2б", "продаж", "sales", "enterprise"]):
        sentences.append(
            "В чистой роли sales manager не буду придумывать отдельные годы B2B-продаж. "
            "Мой основной профиль - AI/product/backend и автоматизация бизнес-процессов; "
            "как founder/product общался с клиентами и вел проектные переговоры, но это не классический sales-only опыт."
        )
        reasons.append("sales_honesty")

    if _contains_any(lowered, ["c-level", "c level", "руководител", "переговор"]):
        sentences.append(
            "Многоэтапные переговоры именно как enterprise sales manager не буду приписывать себе. "
            "Как founder/product вел обсуждения с заказчиками и руководителями по задачам, архитектуре, срокам и коммерческим условиям; "
            "мой сильный угол здесь - tech/product и AI-автоматизация, не чистые продажи."
        )
        reasons.append("clevel_negotiations_honesty")

    if _contains_any(
        lowered,
        ["зарплат", "заработн", "доход", "ожидания", "вилка", "ставка", "компенсац", "оплат"],
    ):
        sentences.append("По ожиданиям: " + _salary_positioning_text())
        reasons.append("salary")

    if _contains_any(lowered, ["postgresql", "postgres", "explain", "partition", "индекс"]):
        sentences.append(
            "PostgreSQL использовал в production как основной SQL-слой. По оптимизации: индексы, структура схемы, форма запросов, миграции и связка с Redis/cache. "
            "Глубокий DBA-профиль с постоянным partitioning/EXPLAIN-тюнингом не буду приписывать, это не основной фокус."
        )
        reasons.append("postgres_optimization_honesty")

    if is_database_experience_question(lowered) and "postgres_optimization_honesty" not in reasons:
        sentences.append(
            "По базам: в production работал с PostgreSQL и SQLite как SQL-слоем, Redis как cache/queue/state, "
            "Elasticsearch и vector search для поиска/RAG. Встраивал это в backend, CRM/админки, LLM/RAG и агентные контуры."
        )
        reasons.append("databases")

    if _contains_any(lowered, ["сбп", "нспк", "161-фз", "161‑фз"]):
        sentences.append(
            "С СБП, НСПК и 161-ФЗ не буду заявлять глубокий профильный опыт. "
            "Знаком на уровне платежных продуктов и интеграций, а практический опыт ближе к YooKassa/Stripe, billing/credits, webhook-обработке и Web3/CEX/DEX интеграциям."
        )
        reasons.append("payment_regulation_honesty")

    if _contains_any(lowered, ["legaltech", "legal tech", "легалтех"]):
        sentences.append(
            "LegalTech как отдельный production-домен не буду приписывать. "
            "По FinTech есть смежный опыт через платежи, billing/credits, YooKassa/Stripe, Web3/CEX/DEX и trading-bot интеграции."
        )
        reasons.append("legaltech_fintech_honesty")

    if (
        _contains_any(lowered, ["финтех", "fintech", "эквайр", "банк", "банках", "платеж", "платёж", "billing", "yookassa", "stripe"])
        and "payment_regulation_honesty" not in reasons
        and "legaltech_fintech_honesty" not in reasons
    ):
        sentences.append(
            "По финтеху честно: в банке или эквайринге как штатный core-разработчик не работал. "
            "Но делал платежные и биллинговые контуры: YooKassa/Stripe, credits/plans, webhook-обработку, "
            "а также Web3/CEX/DEX и trading-bot интеграции. Роль была backend/platform/product, не чистый sales."
        )
        reasons.append("fintech_honesty")

    if _contains_any(lowered, ["финмодел", "финансов", "бизнес-кейс", "бизнес кейс", "презентац"]):
        sentences.append(
            "Финмодели как finance analyst не буду себе приписывать. "
            "На своих продуктах считал тарифы, платежные схемы, credits/plans, unit-экономику на прикладном уровне и упаковывал бизнес-кейсы/презентации как founder/product."
        )
        reasons.append("financial_model_honesty")

    if _contains_any(lowered, ["rps", "нагруз", "подключен", "production-сервис", "продакшн-сервис", "масштаб"]):
        sentences.append(
            "По нагрузке без выдуманных цифр: точный RPS сейчас не назову без логов/метрик конкретного проекта. "
            "Работал с production backend/LLM-proxy/worker-контурами, Redis/PostgreSQL, Docker/Hetzner, provider limits, health-checks и мониторингом."
        )
        reasons.append("load_honesty")

    if _contains_any(lowered, ["график", "формат", "удален", "удалён", "офис", "гибрид", "full-time", "частичная"]):
        sentences.append("Приоритет - удалённый формат. Full-time или проектную загрузку можно обсуждать по задачам.")
        reasons.append("format")

    unknown = _unknown_terms(question, skills)
    if unknown:
        sentences.append(
            f"По {', '.join(unknown)} не буду придумывать глубокий production опыт. "
            "Могу разобраться и встроиться, но основной production стек у меня другой: "
            "Python/FastAPI, React/Next.js, Telegram/Web, Docker и LLM/agent infrastructure."
        )
        reasons.append("honesty_unknown_stack")

    if is_stack_experience_question(lowered) and not _contains_any(
        lowered,
        ["llm council", "council", "маршрутиз", "router", "routing"],
    ):
        sentences.append(
            "По стеку ближе всего Python/FastAPI, React/Next.js, PostgreSQL/Redis/Docker, Telegram/Web и LLM/RAG. "
            "Это использовал в Viably, Vibegent и FPV40: backend, интерфейсы, агентные контуры, деплой и мониторинг."
        )
        reasons.append("stack_experience")

    if _contains_any(lowered, ["инженерн", "дисциплин", "cto", "head of engineering", "engineering"]):
        sentences.append(
            "Из инженерной дисциплины внедрял CI/CD и release gates, code review/QA gates, "
            "health-checks/watchdogs, мониторинг, recovery-процедуры, структуру окружений и правила деплоя. "
            "В агентных системах отдельно делал роли, память, handoff, owner-return и проверки результата."
        )
        reasons.append("engineering_discipline")

    if _contains_any(lowered, ["промпт", "prompt", "декомпоз", "decomposition"]):
        sentences.append(
            "В промпт-инжиниринге и декомпозиции начинаю с роли агента, границ ответственности, входов/выходов и критериев готовности. "
            "Дальше разбиваю задачу на tools, memory/retrieval, handoff между агентами, проверки результата и fallback, чтобы это работало не как один длинный промпт, а как управляемый контур."
        )
        reasons.append("prompt_decomposition")

    if _contains_any(lowered, ["llm council", "council", "маршрутиз", "router", "routing"]):
        sentences.append(
            "Да, близкие контуры делал: маршрутизация между агентами/ролями, tools, memory/retrieval, handoff, owner-return и проверки результата. "
            "Если строго называть LLM Council как конкретный продуктовый паттерн - скорее делал архитектурно похожие multi-agent/router решения, не отдельный брендированный модуль."
        )
        reasons.append("agent_routing")

    if _contains_any(lowered, ["langchain", "langgraph", "crewai", "агентн", "фреймворк", "framework"]):
        sentences.append(
            "По агентным фреймворкам: основной опыт у меня не в одном готовом фреймворке, "
            "а в сборке agent runtime вокруг ролей, tools, памяти, routing, handoff и проверок результата. "
            "Это ближе к AgentOps/LLMOps и production-инфраструктуре для агентов."
        )
        reasons.append("agent_frameworks")

    if _contains_any(lowered, ["собесед", "интервью", "созвон", "встреч", "слот", "когда удобно"]):
        sentences.append("К короткому созвону готов. Лучше пришлите 2-3 слота, я подтвержу удобный.")
        reasons.append("interview")

    if _contains_any(lowered, ["тестов", "тестовое", "тз", "задание"]):
        sentences.append(
            "Тестовое могу посмотреть, если оно небольшое и связано с реальной задачей. "
            "Полноценную бесплатную разработку вместо этапа отбора не беру."
        )
        reasons.append("test_task")

    if len(sentences) == 1 and is_concrete_experience_question(lowered):
        return HHChatReplyDraft(
            message=humanize_hh_chat_reply(
                "Здравствуйте! Вопрос требует точного ответа по конкретному опыту. "
                "Не буду отправлять общий шаблон вместо ответа, лучше проверю вручную."
            ),
            reasons=["manual_required", "unmatched_concrete_screening"],
        )

    if len(sentences) == 1:
        if context_focus:
            sentences.append(f"Да, готов обсудить. {context_focus}")
            reasons.extend(["generic", "context_focus"])
        else:
            proof = (
                strengths[0]
                if strengths
                else "строю AI-агентные и full-stack/backend контуры: Telegram/Web, CRM, LLM/RAG, деплой и мониторинг"
            )
            sentences.append(f"Да, готов обсудить. По профилю я ближе всего к AI Agent Systems / AgentOps и backend/full-stack: {proof}.")
            reasons.append("generic")

    portfolio_requested = _contains_any(lowered, ["портфолио", "пример", "кейсы", "ссылка", "резюме"])
    if (
        portfolio
        and (
            portfolio_requested
            or is_concrete_experience_question(lowered)
            or is_database_experience_question(lowered)
            or is_stack_experience_question(lowered)
        )
        and portfolio not in " ".join(sentences)
    ):
        sentences.append(f"Портфолио: {portfolio}")
        reasons.append("portfolio")

    return HHChatReplyDraft(message=humanize_hh_chat_reply(" ".join(sentences)), reasons=reasons)


def _strip_greeting(text: str) -> str:
    return re.sub(r"^здравствуйте!\s*", "", humanize_hh_chat_reply(text), flags=re.I).strip()


def _salary_positioning_text() -> str:
    return (
        "Сейчас приоритет - удаленная работа и быстрый старт. "
        "Готов рассматривать варианты от 100000 до 200000, если задачи нормальные, "
        "есть стабильность или понятный потенциал роста. "
        "300000+ - комфортный ориентир, но не жесткий порог."
    )


def _profile_summary_for_external(profile: ApplicantProfile) -> str:
    strengths = [normalize_text(item) for item in (getattr(profile, "strengths", []) or []) if item]
    cases = [case for case in (getattr(profile, "cases", []) or []) if getattr(case, "title", "")]
    proof_parts: list[str] = []
    for case in cases[:2]:
        title = normalize_text(case.title)
        result = normalize_text(getattr(case, "result", "") or getattr(case, "description", "") or "")
        proof_parts.append(f"{title}: {result}" if result else title)

    parts = [
        f"Здравствуйте! Я {profile.full_name}.",
        f"Мой основной профиль - {profile.headline}.",
    ]
    if strengths:
        parts.append(f"Сильнее всего: {strengths[0]}.")
    if proof_parts:
        parts.append("Кейсы: " + "; ".join(proof_parts) + ".")
    parts.append(_salary_positioning_text())
    parts.append("Приоритет - удаленный формат.")
    portfolio = _portfolio_url(profile)
    if portfolio:
        parts.append(f"Портфолио: {portfolio}")
    return humanize_hh_chat_reply(" ".join(parts))


def answer_google_form_question(label: str, profile: ApplicantProfile) -> str | None:
    """Return a deterministic answer only for fields we can answer safely."""

    lowered = _lower(label)
    if not lowered:
        return None

    if _contains_any(lowered, ["фио", "имя и фамилия", "ваше имя", "как вас зовут"]):
        if "возраст" in lowered or "лет" in lowered:
            age = getattr(profile, "age", None)
            return f"{profile.full_name}, {age} лет" if age else profile.full_name
        return profile.full_name

    if _contains_any(lowered, ["возраст", "сколько лет"]):
        age = getattr(profile, "age", None)
        return str(age) if age else None

    if _contains_any(lowered, ["телефон", "номер", "phone", "whatsapp", "ватсап"]):
        phone = normalize_text(str(getattr(profile, "phone", "") or ""))
        return phone or None

    if _contains_any(lowered, ["telegram", "телеграм", "tg", "ник"]):
        telegram = _telegram_nick(profile)
        return telegram or None

    if _contains_any(
        lowered,
        ["зарплат", "доход", "ожидан", "компенсац", "ставка", "оплат", "вилка"],
    ):
        return _salary_positioning_text()

    if _contains_any(lowered, ["формат", "график", "удален", "удалён", "офис", "гибрид"]):
        return "Приоритет - удаленный формат. Full-time или проектную загрузку можно обсуждать по задачам."

    if _contains_any(lowered, ["портфолио", "github", "гитхаб", "ссылка", "кейсы", "резюме"]):
        portfolio = _portfolio_url(profile)
        return f"Портфолио: {portfolio}" if portfolio else None

    if _contains_any(lowered, ["англ", "english", "язык"]):
        return _strip_greeting(generate_hh_chat_reply(label, profile).message)

    if _contains_any(lowered, ["ип", "самозан", "outstaff", "аутстаф", "договор"]):
        return "ИП/самозанятость и outstaff можно обсуждать."

    if _contains_any(
        lowered,
        [
            "опыт",
            "стек",
            "навык",
            "skill",
            "технолог",
            "о себе",
            "расскажите",
            "проект",
            "backend",
            "frontend",
            "full-stack",
            "fullstack",
            "python",
            "fastapi",
            "react",
            "llm",
            "rag",
            "agent",
            "агент",
        ],
    ):
        draft = generate_hh_chat_reply(label, profile)
        if draft.reasons == ["questionnaire_ack"]:
            return _profile_summary_for_external(profile)
        return _strip_greeting(draft.message)

    if _contains_any(lowered, ["собесед", "созвон", "интервью", "слот", "когда удобно"]):
        return "К короткому созвону готов. Лучше пришлите 2-3 слота, я подтвержу удобный."

    return None


def _candidate_questionnaire_lines(text: str) -> list[str]:
    candidates: list[str] = []
    for raw_line in re.split(r"[\n\r]+", text or ""):
        line = normalize_text(re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", raw_line))
        if not line or line in extract_urls(line):
            continue
        if len(line) > 500:
            continue
        lowered = _lower(line)
        has_question_shape = "?" in line or any(
            marker in lowered
            for marker in [
                "укажите",
                "напишите",
                "расскажите",
                "ответьте",
                "опыт",
                "зарплат",
                "доход",
                "формат",
                "график",
                "англ",
                "стек",
                "портфолио",
                "telegram",
                "телеграм",
                "ип",
                "самозан",
            ]
        )
        if has_question_shape:
            candidates.append(line)
    return candidates[:10]


def generate_prepared_external_response(text: str, profile: ApplicantProfile) -> PreparedExternalResponse:
    reasons = ["external_copy_paste"]
    answers: list[QuestionnaireAnswer] = []

    if is_checklist_prompt(text):
        draft = generate_hh_chat_reply(text, profile)
        reasons.extend(draft.reasons)
        return PreparedExternalResponse(
            copy_paste_message=draft.message,
            answers=[
                QuestionnaireAnswer(
                    question="Чек-лист из HH",
                    answer=_strip_greeting(draft.message),
                )
            ],
            reasons=reasons,
        )

    for line in _candidate_questionnaire_lines(text):
        answer = answer_google_form_question(line, profile)
        if answer:
            answers.append(QuestionnaireAnswer(question=line, answer=answer))

    copy_paste_message = _profile_summary_for_external(profile)
    if answers:
        reasons.append("embedded_questionnaire_answers")
        answer_text = "\n".join(f"{item.question}: {item.answer}" for item in answers)
        copy_paste_message = _humanize_multiline(
            f"{copy_paste_message}\nОтветы по анкете:\n{answer_text}"
        )

    return PreparedExternalResponse(
        copy_paste_message=copy_paste_message,
        answers=answers,
        reasons=reasons,
    )


def _humanize_alert_block(text: str) -> str:
    lines: list[str] = []
    blank_seen = False
    for raw_line in (text or "").splitlines():
        line = humanize_hh_chat_reply(raw_line)
        if line:
            lines.append(line)
            blank_seen = False
        elif lines and not blank_seen:
            lines.append("")
            blank_seen = True
    return "\n".join(lines).strip()


def _external_target_label(target: ExternalTarget) -> str:
    if target.kind == "google_form":
        return f"Google Form: {target.value}"
    if target.kind in {"telegram_url", "telegram_handle"}:
        return f"Telegram: {target.value}"
    if target.kind == "external_url":
        return f"Внешняя ссылка: {target.value}"
    return target.value


def format_external_handoff_alert_messages(alert: ExternalHandoffAlert) -> list[str]:
    targets = [_external_target_label(target) for target in alert.external_targets]
    target_text = "\n".join(f"- {target}" for target in targets) or "- не распознан"
    messages = [
        _humanize_alert_block(
            "\n".join(
                [
                    "Внешний контакт из HH",
                    "",
                    f"Вакансия: {alert.title}",
                    f"HH чат: {alert.chat_url}",
                    "",
                    "Куда перейти:",
                    target_text,
                    "",
                    "Статус: сам туда ничего не отправляю. Ниже отдельно дам сообщение работодателя и текст для вставки.",
                ]
            )
        ),
        _humanize_alert_block(
            "\n".join(
                [
                    "Сообщение работодателя:",
                    "",
                    alert.original_message,
                ]
            )
        ),
        _humanize_alert_block(
            "\n".join(
                [
                    "Готовый текст для вставки:",
                    "",
                    alert.prepared_response.copy_paste_message,
                ]
            )
        ),
    ]
    answers_text = alert.prepared_response.answers_text()
    if answers_text:
        messages.append(
            _humanize_alert_block(
                "\n".join(
                    [
                        "Отдельные ответы по анкете:",
                        "",
                        answers_text,
                    ]
                )
            )
        )
    return [message for message in messages if message]


def format_external_handoff_alert(alert: ExternalHandoffAlert) -> str:
    return "\n\n".join(format_external_handoff_alert_messages(alert))


class HHChatRunner:
    def __init__(
        self,
        *,
        page: PageLike,
        profile: ApplicantProfile,
        state: HHChatReplyState | None = None,
        external_form_handler: ExternalFormHandler | None = None,
        alert_notifier: ExternalAlertNotifier | None = None,
        close_handles: list[Any] | None = None,
    ) -> None:
        self.page = page
        self.profile = profile
        self.state = state or HHChatReplyState()
        self.external_form_handler = external_form_handler
        self.alert_notifier = alert_notifier
        self._close_handles = close_handles or []

    @classmethod
    def launch(
        cls,
        *,
        profile: ApplicantProfile,
        state: HHChatReplyState | None = None,
        user_data_dir: str | Path = "./data/hh-browser-profile",
        headless: bool = False,
        external_form_handler: ExternalFormHandler | None = None,
        alert_notifier: ExternalAlertNotifier | None = None,
    ) -> "HHChatRunner":
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - depends on optional browser extra
            raise RuntimeError(
                "Playwright is not installed. Install browser mode with: "
                "pip install -e '.[browser]' && python -m playwright install chromium"
            ) from exc

        path = Path(user_data_dir)
        path.mkdir(parents=True, exist_ok=True)
        playwright = sync_playwright().start()
        context = playwright.chromium.launch_persistent_context(
            str(path),
            headless=headless,
            viewport={"width": 1440, "height": 1000},
            locale="ru-RU",
        )
        page = context.pages[0] if context.pages else context.new_page()
        return cls(
            profile=profile,
            page=page,
            state=state,
            external_form_handler=external_form_handler,
            alert_notifier=alert_notifier,
            close_handles=[context, playwright],
        )

    def close(self) -> None:
        for handle in self._close_handles:
            close = getattr(handle, "close", None)
            stop = getattr(handle, "stop", None)
            if callable(close):
                close()
            elif callable(stop):
                stop()

    def run(
        self,
        *,
        send: bool = False,
        limit: int = 5,
        max_chats: int = 160,
        external_submit: bool = False,
    ) -> HHChatRunResult:
        self.open_chat_list()
        if self._login_required():
            result = HHChatReplyResult(
                chat_id=None,
                title="HH chat",
                status="needs_login",
                question="",
                reply="",
                url=getattr(self.page, "url", HH_CHAT_URL),
                message="HH login is required in the browser profile",
            )
            return HHChatRunResult(
                0,
                0,
                0,
                0,
                0,
                1,
                send,
                [result.status],
                [asdict(result)],
                external_submit,
            )

        previews = self.collect_previews(max_chats=max_chats)
        candidates = [
            preview
            for preview in previews
            if is_reply_candidate(preview.preview) or should_deep_scan_preview(preview.preview)
        ]
        replies: list[HHChatReplyResult] = []
        for preview in candidates[: max(limit, 0)]:
            replies.append(self.reply_to_preview(preview, send=send, external_submit=external_submit))

        sent = sum(1 for item in replies if item.status == "sent")
        draft_statuses = {"draft", "google_form_draft"}
        drafted = sum(1 for item in replies if item.status in draft_statuses)
        skipped = sum(1 for item in replies if item.status.startswith("skipped"))
        blocked = sum(
            1
            for item in replies
            if item.status not in {"sent", *draft_statuses} and not item.status.startswith("skipped")
        )
        return HHChatRunResult(
            scanned=len(previews),
            candidates=len(candidates),
            sent=sent,
            drafted=drafted,
            skipped=skipped,
            blocked=blocked,
            send_enabled=send,
            statuses=[item.status for item in replies],
            replies=[asdict(item) for item in replies],
            external_submit_enabled=external_submit,
        )

    def open_chat_list(self) -> None:
        self.page.goto(HH_CHAT_URL, wait_until="domcontentloaded")
        self._safe_wait("domcontentloaded")
        self._safe_wait("networkidle")
        self._safe_pause(1000)

    def collect_previews(
        self,
        *,
        max_chats: int = 160,
        scroll_rounds: int | None = None,
        idle_rounds: int = 4,
    ) -> list[HHChatPreview]:
        seen: dict[str, HHChatPreview] = {}
        max_rounds = max(scroll_rounds if scroll_rounds is not None else 32, 1)
        idle_count = 0
        for _ in range(max_rounds):
            before_count = len(seen)
            for raw in self._read_preview_rows():
                preview = preview_from_raw(raw)
                if preview and preview.chat_id not in seen:
                    seen[preview.chat_id] = preview
                    if len(seen) >= max_chats:
                        return list(seen.values())
            if len(seen) == before_count:
                idle_count += 1
            else:
                idle_count = 0
            if idle_count >= max(idle_rounds, 1):
                break
            self._scroll_chat_list()
            self._safe_pause(250)
        return list(seen.values())[:max_chats]

    def reply_to_preview(
        self,
        preview: HHChatPreview,
        *,
        send: bool = False,
        external_submit: bool = False,
    ) -> HHChatReplyResult:
        self.page.goto(preview.url, wait_until="domcontentloaded")
        self._safe_wait("domcontentloaded")
        self._safe_wait("networkidle")
        self._safe_pause(700)
        if self._login_required():
            return HHChatReplyResult(
                chat_id=preview.chat_id,
                title=preview.title,
                status="needs_login",
                question=preview.preview,
                reply="",
                url=getattr(self.page, "url", preview.url),
                message="HH login is required in the browser profile",
            )

        chat_messages = self._read_chat_messages()
        chat_context = format_chat_context(chat_messages)
        question = extract_latest_question_from_messages(chat_messages, preview.preview)
        if question is None:
            conversation_text = self._body_text()
            question = extract_latest_question(conversation_text, preview.preview)
            if not chat_context:
                chat_context = conversation_text
        if is_closed_chat_text(question):
            return HHChatReplyResult(preview.chat_id, preview.title, "skipped_closed", question, "", preview.url, "Closed chat marker detected")
        if not is_reply_candidate(question):
            return HHChatReplyResult(
                preview.chat_id,
                preview.title,
                "skipped_no_question",
                question,
                "",
                preview.url,
                "No employer question detected",
            )
        low_fit_reason = low_fit_chat_title_reason(preview.title)
        if low_fit_reason and low_fit_chat_title_guard_enabled():
            return HHChatReplyResult(
                preview.chat_id,
                preview.title,
                "blocked_low_fit_title",
                question,
                "",
                preview.url,
                (
                    f"Low-fit chat title blocked ({low_fit_reason}); target is Python Backend, "
                    "AI AgentOps, and strong AI product/backend projects"
                ),
            )
        google_form_links = extract_google_form_links(question)
        if google_form_links:
            return self._handle_google_form_question(
                preview,
                question,
                google_form_links[0],
                send=send,
                external_submit=external_submit,
            )

        external_targets = extract_external_targets(question)
        if external_targets or is_external_interview_link(question):
            return self._handle_external_handoff(preview, question, external_targets, send=send)

        if self.state.was_answered(preview.chat_id, question):
            return HHChatReplyResult(preview.chat_id, preview.title, "skipped_duplicate", question, "", preview.url, "Question was already answered by this runner")

        draft = generate_hh_chat_reply(question, self.profile, context=chat_context)
        if "manual_required" in draft.reasons:
            return HHChatReplyResult(
                preview.chat_id,
                preview.title,
                "blocked_manual_review",
                question,
                draft.message,
                preview.url,
                ",".join(draft.reasons),
            )
        if not send:
            return HHChatReplyResult(preview.chat_id, preview.title, "draft", question, draft.message, preview.url, ",".join(draft.reasons))

        filled_selector = self._fill_first_available(MESSAGE_INPUT_SELECTORS, draft.message)
        if not filled_selector:
            return HHChatReplyResult(preview.chat_id, preview.title, "form_not_found", question, draft.message, preview.url, "Could not find HH chat message input")
        clicked_selector = self._click_first_available(SEND_BUTTON_SELECTORS)
        if not clicked_selector:
            return HHChatReplyResult(preview.chat_id, preview.title, "send_button_not_found", question, draft.message, preview.url, "Could not find HH chat send button")

        self._safe_pause(1500)
        verified = self._message_sent_confirmed(draft.message)
        status = "sent" if verified else "sent_unverified"
        self.state.mark_answered(chat_id=preview.chat_id, question=question, reply=draft.message, status=status)
        return HHChatReplyResult(
            preview.chat_id,
            preview.title,
            status,
            question,
            draft.message,
            getattr(self.page, "url", preview.url),
            f"Clicked {clicked_selector}; filled {filled_selector}",
        )

    @staticmethod
    def _targets_payload(targets: list[ExternalTarget]) -> list[dict[str, Any]]:
        return [asdict(target) for target in targets]

    def _send_plain_chat_reply(self, message: str) -> tuple[str, str]:
        filled_selector = self._fill_first_available(MESSAGE_INPUT_SELECTORS, message)
        if not filled_selector:
            return "form_not_found", "Could not find HH chat message input"
        clicked_selector = self._click_first_available(SEND_BUTTON_SELECTORS)
        if not clicked_selector:
            return "send_button_not_found", "Could not find HH chat send button"

        self._safe_pause(1500)
        verified = self._message_sent_confirmed(message)
        status = "sent" if verified else "sent_unverified"
        return status, f"Clicked {clicked_selector}; filled {filled_selector}"

    def _maybe_send_external_ack(self, preview: HHChatPreview, question: str) -> tuple[str | None, str, str | None]:
        message = external_handoff_ack_message(question, self.profile)
        if not external_handoff_ack_enabled() or self.state.was_answered(preview.chat_id, question):
            return None, message, None
        status, detail = self._send_plain_chat_reply(message)
        if status in {"sent", "sent_unverified"}:
            self.state.mark_answered(
                chat_id=preview.chat_id,
                question=question,
                reply=message,
                status=f"external_ack_{status}",
            )
        return status, message, detail

    def _handle_external_handoff(
        self,
        preview: HHChatPreview,
        question: str,
        external_targets: list[ExternalTarget],
        *,
        send: bool,
    ) -> HHChatReplyResult:
        targets = external_targets or [ExternalTarget(kind="external_reference", value="external")]
        prepared = generate_prepared_external_response(question, self.profile)
        payload = self._targets_payload(targets)
        target_key = "|".join(target.value for target in targets)
        external_result: dict[str, Any] = {"prepared_answers": [asdict(item) for item in prepared.answers]}

        if not send:
            return HHChatReplyResult(
                preview.chat_id,
                preview.title,
                "blocked_external_interview",
                question,
                prepared.copy_paste_message,
                preview.url,
                ",".join(prepared.reasons),
                payload,
                external_result,
            )

        ack_status, ack_message, ack_detail = self._maybe_send_external_ack(preview, question)
        if ack_status:
            external_result["hh_ack_status"] = ack_status

        if self.state.was_external_handled(
            chat_id=preview.chat_id,
            question=question,
            target=target_key,
            action="alert",
        ):
            if ack_status in {"sent", "sent_unverified"}:
                return HHChatReplyResult(
                    preview.chat_id,
                    preview.title,
                    ack_status,
                    question,
                    ack_message,
                    getattr(self.page, "url", preview.url),
                    f"HH external handoff ack sent; external alert already existed; {ack_detail}",
                    payload,
                    external_result,
                )
            return HHChatReplyResult(
                preview.chat_id,
                preview.title,
                "skipped_external_alert_duplicate",
                question,
                prepared.copy_paste_message,
                preview.url,
                "External alert was already sent by this runner",
                payload,
                external_result,
            )

        if self.alert_notifier is None:
            if ack_status in {"sent", "sent_unverified"}:
                return HHChatReplyResult(
                    preview.chat_id,
                    preview.title,
                    ack_status,
                    question,
                    ack_message,
                    getattr(self.page, "url", preview.url),
                    f"HH external handoff ack sent; Telegram alert notifier is not configured; {ack_detail}",
                    payload,
                    external_result,
                )
            return HHChatReplyResult(
                preview.chat_id,
                preview.title,
                "external_alert_not_configured",
                question,
                prepared.copy_paste_message,
                preview.url,
                "External handoff detected, but Telegram alert notifier is not configured",
                payload,
                external_result,
            )

        alert = ExternalHandoffAlert(
            chat_id=preview.chat_id,
            title=preview.title,
            chat_url=preview.url,
            external_targets=targets,
            original_message=question,
            prepared_response=prepared,
        )
        try:
            self.alert_notifier.send_alert(alert)
        except Exception as exc:
            return HHChatReplyResult(
                preview.chat_id,
                preview.title,
                "external_alert_failed",
                question,
                prepared.copy_paste_message,
                preview.url,
                f"Telegram alert failed: {type(exc).__name__}",
                payload,
                external_result,
            )

        self.state.mark_external_handled(
            chat_id=preview.chat_id,
            question=question,
            target=target_key,
            action="alert",
            status="external_alert_sent",
            message=prepared.copy_paste_message,
        )
        if ack_status in {"sent", "sent_unverified"}:
            return HHChatReplyResult(
                preview.chat_id,
                preview.title,
                ack_status,
                question,
                ack_message,
                getattr(self.page, "url", preview.url),
                f"HH external handoff ack sent; Telegram alert sent; {ack_detail}",
                payload,
                external_result,
            )
        return HHChatReplyResult(
            preview.chat_id,
            preview.title,
            "external_alert_sent",
            question,
            prepared.copy_paste_message,
            preview.url,
            "Telegram alert sent for external recruiter handoff",
            payload,
            external_result,
        )

    def _handle_google_form_question(
        self,
        preview: HHChatPreview,
        question: str,
        form_url: str,
        *,
        send: bool,
        external_submit: bool,
    ) -> HHChatReplyResult:
        targets = [ExternalTarget(kind="google_form", value=form_url, url=form_url)]
        payload = self._targets_payload(targets)
        prepared = generate_prepared_external_response(question, self.profile)

        if not send:
            return HHChatReplyResult(
                preview.chat_id,
                preview.title,
                "google_form_draft",
                question,
                prepared.copy_paste_message,
                preview.url,
                ",".join(prepared.reasons),
                payload,
                {"prepared_answers": [asdict(item) for item in prepared.answers]},
            )

        action = "submit" if external_submit else "prepare"
        if self.state.was_external_handled(
            chat_id=preview.chat_id,
            question=question,
            target=form_url,
            action=action,
        ):
            return HHChatReplyResult(
                preview.chat_id,
                preview.title,
                "skipped_google_form_duplicate",
                question,
                prepared.copy_paste_message,
                preview.url,
                "Google Form was already handled by this runner",
                payload,
                {"prepared_answers": [asdict(item) for item in prepared.answers]},
            )

        if self.external_form_handler is None:
            return HHChatReplyResult(
                preview.chat_id,
                preview.title,
                "google_form_handler_missing",
                question,
                prepared.copy_paste_message,
                preview.url,
                "Google Form detected, but external form handler is not configured",
                payload,
                {"prepared_answers": [asdict(item) for item in prepared.answers]},
            )

        request = GoogleFormRequest(
            chat_id=preview.chat_id,
            title=preview.title,
            chat_url=preview.url,
            form_url=form_url,
            original_message=question,
            prepared_response=prepared,
        )
        try:
            form_result = self.external_form_handler.handle_google_form(
                request,
                submit=external_submit,
            )
        except Exception as exc:
            form_result = ExternalFormResult(
                status="handler_error",
                message=f"Google Form handler failed: {type(exc).__name__}",
                url=form_url,
            )

        external_result = asdict(form_result) | {
            "prepared_answers": [asdict(item) for item in prepared.answers],
        }

        if form_result.status == "needs_login":
            self._send_google_login_alert(preview, question, form_url, prepared, payload, external_result)

        if form_result.status in {"submitted", "filled_not_submitted"}:
            self.state.mark_external_handled(
                chat_id=preview.chat_id,
                question=question,
                target=form_url,
                action=action,
                status=f"google_form_{form_result.status}",
                message=prepared.copy_paste_message,
            )

        return HHChatReplyResult(
            preview.chat_id,
            preview.title,
            f"google_form_{form_result.status}",
            question,
            prepared.copy_paste_message,
            form_result.url or preview.url,
            form_result.message,
            payload,
            external_result,
        )

    def _send_google_login_alert(
        self,
        preview: HHChatPreview,
        question: str,
        form_url: str,
        prepared: PreparedExternalResponse,
        payload: list[dict[str, Any]],
        external_result: dict[str, Any],
    ) -> None:
        if self.alert_notifier is None:
            external_result["alert_status"] = "not_configured"
            return
        if self.state.was_external_handled(
            chat_id=preview.chat_id,
            question=question,
            target=form_url,
            action="google_login_alert",
        ):
            external_result["alert_status"] = "duplicate"
            return
        alert = ExternalHandoffAlert(
            chat_id=preview.chat_id,
            title=preview.title,
            chat_url=preview.url,
            external_targets=[ExternalTarget(**target) for target in payload],
            original_message=(
                f"Google Form требует вход в браузерный профиль: {form_url}\n\n{question}"
            ),
            prepared_response=prepared,
            reason="google_form_needs_login",
        )
        try:
            self.alert_notifier.send_alert(alert)
        except Exception as exc:
            external_result["alert_status"] = f"failed:{type(exc).__name__}"
            return
        self.state.mark_external_handled(
            chat_id=preview.chat_id,
            question=question,
            target=form_url,
            action="google_login_alert",
            status="sent",
            message=prepared.copy_paste_message,
        )
        external_result["alert_status"] = "sent"

    def _read_preview_rows(self) -> list[dict[str, Any]]:
        script = """
        () => Array.from(document.querySelectorAll('a[data-qa^="chatik-open-chat-"]')).map((node) => ({
          href: node.href || node.getAttribute('href') || '',
          dataQa: node.getAttribute('data-qa') || '',
          text: (node.innerText || node.textContent || '').trim(),
        }))
        """
        rows = self._safe_evaluate(script, fallback=[])
        return rows if isinstance(rows, list) else []

    def _read_chat_messages(self) -> list[dict[str, Any]]:
        script = """
        () => {
          const classNameOf = (node) => {
            const value = node && node.className;
            if (!value) return '';
            return typeof value === 'string' ? value : (value.baseVal || String(value));
          };
          const hasMyClass = (node) => {
            if (!node) return false;
            if (classNameOf(node).includes('message_my')) return true;
            if (node.closest && node.closest('[class*="message_my"]')) return true;
            return Array.from(node.querySelectorAll('[class*="message_my"]')).length > 0;
          };
          return Array.from(document.querySelectorAll('[data-qa^="chatik-chat-message-"]'))
            .filter((node) => {
              const dataQa = node.getAttribute('data-qa') || '';
              return dataQa && !dataQa.endsWith('-text');
            })
            .map((node) => {
              const bubble = node.querySelector('[data-qa="chat-bubble-text"]') || node;
              return {
                text: (bubble.innerText || bubble.textContent || '').trim(),
                isMine: hasMyClass(node),
              };
            })
            .filter((message) => message.text);
        }
        """
        rows = self._safe_evaluate(script, fallback=[])
        return rows if isinstance(rows, list) else []

    def _scroll_chat_list(self) -> None:
        script = """
        () => {
          const scrollables = Array.from(document.querySelectorAll('*'))
            .filter((node) => node.scrollHeight > node.clientHeight + 80)
            .slice(0, 30);
          for (const node of scrollables) node.scrollTop = node.scrollTop + Math.max(300, node.clientHeight);
          window.scrollBy(0, window.innerHeight || 700);
          return scrollables.length;
        }
        """
        self._safe_evaluate(script, fallback=0)

    def _body_text(self) -> str:
        locator = self._safe_locator("body")
        if not locator:
            return ""
        inner_text = getattr(locator, "inner_text", None)
        if callable(inner_text):
            try:
                return str(inner_text())
            except Exception:
                return ""
        return ""

    def _message_sent_confirmed(self, reply: str) -> bool:
        reply_norm = normalize_text(reply)
        if reply_norm and reply_norm in normalize_text(self._body_text()):
            return True
        script = """
        () => Array.from(document.querySelectorAll('.message_my, [class*="message_my"]'))
          .map((node) => (node.innerText || node.textContent || '').trim())
          .filter(Boolean)
          .slice(-5)
        """
        rows = self._safe_evaluate(script, fallback=[])
        if isinstance(rows, list):
            return any(reply_norm in normalize_text(str(row)) for row in rows)
        return False

    def _login_required(self) -> bool:
        current_url = getattr(self.page, "url", "").lower()
        if any(marker in current_url for marker in ["/account/login", "/account/signup", "/login"]):
            return True
        for selector in LOGIN_SELECTORS:
            locator = self._safe_locator(selector)
            if locator and self._safe_count(locator) > 0 and self._safe_visible(locator):
                return True
        return False

    def _fill_first_available(self, selectors: list[str], value: str) -> str | None:
        for selector in selectors:
            locator = self._safe_locator(selector)
            if locator and self._safe_count(locator) > 0:
                try:
                    locator.fill(value)
                    return selector
                except Exception:
                    continue
        return None

    def _click_first_available(self, selectors: list[str]) -> str | None:
        for selector in selectors:
            locator = self._safe_locator(selector)
            if locator and self._safe_count(locator) > 0:
                try:
                    locator.click()
                    self._safe_wait("domcontentloaded")
                    return selector
                except Exception:
                    continue
        return None

    def _safe_wait(self, state: str) -> None:
        try:
            self.page.wait_for_load_state(state)
        except Exception:
            return

    def _safe_pause(self, ms: int) -> None:
        wait_for_timeout = getattr(self.page, "wait_for_timeout", None)
        if callable(wait_for_timeout):
            try:
                wait_for_timeout(ms)
            except Exception:
                return

    def _safe_locator(self, selector: str) -> LocatorLike | None:
        try:
            return self.page.locator(selector)
        except Exception:
            return None

    def _safe_evaluate(self, expression: str, *, fallback: Any) -> Any:
        evaluate = getattr(self.page, "evaluate", None)
        if not callable(evaluate):
            return fallback
        try:
            return evaluate(expression)
        except Exception:
            return fallback

    @staticmethod
    def _safe_count(locator: LocatorLike) -> int:
        try:
            return locator.count()
        except Exception:
            return 0

    @staticmethod
    def _safe_visible(locator: LocatorLike) -> bool:
        try:
            return locator.is_visible()
        except Exception:
            return False
