from __future__ import annotations

import fcntl

import httpx
import pytest

from app.repository import CRMRepository
from app.responses import ApplicantProfile, CaseStudy
from app.scoring import CandidateProfile, ScoreResult, Vacancy
from app.telegram_agent import (
    HHTelegramReviewAgent,
    TelegramAPIError,
    TelegramBotClient,
    TelegramNetworkError,
    TelegramReviewSettings,
    deliver_startup_messages,
    format_help_message,
    format_vacancy_message,
    register_command_menu,
    telegram_command_menu,
)


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[tuple[int | str, str, dict | None]] = []
        self.message_kwargs: list[dict[str, str | None]] = []
        self.callback_answers: list[tuple[str, str | None, bool]] = []
        self.commands: list[dict[str, str]] | None = None

    def set_my_commands(self, commands: list[dict[str, str]]) -> dict:
        self.commands = commands
        return {"ok": True}

    def send_message(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: dict | None = None,
        *,
        parse_mode: str | None = None,
    ) -> dict:
        self.messages.append((chat_id, text, reply_markup))
        self.message_kwargs.append({"parse_mode": parse_mode})
        return {"ok": True}

    def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
        *,
        show_alert: bool = False,
    ) -> dict:
        self.callback_answers.append((callback_query_id, text, show_alert))
        return {"ok": True}


def _draft(repo: CRMRepository, *, external_id: str, title: str, company: str = "AgentCo", score: int = 91) -> int:
    vacancy = Vacancy(
        external_id=external_id,
        title=title,
        company=company,
        description="Удалённо. Python, LLM, Telegram, CRM.",
        url=f"https://hh.ru/vacancy/{external_id}",
        raw={"apply_url": f"https://hh.ru/applicant/vacancy_response?vacancyId={external_id}"},
    )
    vacancy_id = repo.upsert_vacancy(
        vacancy,
        ScoreResult(
            score=score,
            decision="hot",
            reasons=["skill match: Python", "remote/удалёнка"],
            penalties=[],
        ),
    )
    return repo.create_or_update_application(
        vacancy_id,
        cover_letter="Здравствуйте! Готов быстро включиться.\n\nПортфолио: https://portfolio.viably.dev.",
        status="draft",
        score_at_apply=score,
    )


def _texts(bot: FakeBot) -> str:
    return "\n".join(text for _chat_id, text, _markup in bot.messages)


def test_telegram_command_menu_contains_all_text_commands() -> None:
    commands = telegram_command_menu()
    command_names = [item["command"] for item in commands]

    assert command_names == ["start", "run", "queue", "summary", "guide", "edit", "help"]
    assert all(1 <= len(item["command"]) <= 32 for item in commands)
    assert all(item["description"] for item in commands)
    assert "/edit ID текст" in format_help_message()


def test_telegram_bot_client_registers_command_menu_payload() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json_loads(request.content))
        assert request.url.path.endswith("/setMyCommands")
        return httpx.Response(200, json={"ok": True, "result": True})

    client = TelegramBotClient(token="123456:REDACTED", transport=httpx.MockTransport(handler))

    result = client.set_my_commands(telegram_command_menu())

    assert result["ok"] is True
    assert requests == [{"commands": telegram_command_menu()}]


def test_register_command_menu_does_not_send_messages(tmp_path) -> None:
    bot = FakeBot()
    agent = HHTelegramReviewAgent(repo=CRMRepository(tmp_path / "crm.sqlite3"), bot=bot)

    registered = register_command_menu(agent)

    assert registered is True
    assert bot.commands == telegram_command_menu()
    assert bot.messages == []


def json_loads(raw: bytes) -> dict:
    import json

    return json.loads(raw.decode("utf-8"))


def test_format_vacancy_message_contains_apply_link_reasons_and_draft() -> None:
    row = {
        "title": "Python AI Engineer",
        "company": "AgentCo",
        "score": 91,
        "decision": "hot",
        "url": "https://hh.ru/vacancy/123",
        "apply_url": "https://hh.ru/applicant/vacancy_response?vacancyId=123",
        "score_reasons": ["skill match: Python", "remote/удалёнка"],
        "score_penalties": [],
        "application_id": 7,
        "cover_letter": "Здравствуйте!\n\nОпыт <RAG> & CRM.\nПортфолио: https://portfolio.viably.dev.",
    }

    message = format_vacancy_message(row, index=1)

    assert "Python AI Engineer" in message
    assert "AgentCo" in message
    assert "ID отклика: 7" in message
    assert "Score: 91 / hot" in message
    assert "https://hh.ru/applicant/vacancy_response?vacancyId=123" in message
    assert "skill match: Python" in message
    assert "Черновик:\n<pre>" in message
    assert "Опыт &lt;RAG&gt; &amp; CRM." in message
    assert "Опыт <RAG> & CRM." not in message
    assert "Портфолио: https://portfolio.viably.dev." in message
    assert message.endswith("</pre>")
    assert len(message) <= 4096


def test_agent_sends_real_review_queue_with_inline_buttons_and_excludes_demo_by_default(tmp_path) -> None:
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    _draft(repo, external_id="demo-hh-1", title="Demo vacancy", company="Demo", score=99)
    app_id = _draft(repo, external_id="hh-777", title="Python AI automation", score=91)
    bot = FakeBot()
    agent = HHTelegramReviewAgent(
        repo=repo,
        bot=bot,
        settings=TelegramReviewSettings(chat_id_path=tmp_path / "chat_id", min_score=80, limit=5),
    )

    sent = agent.send_queue(chat_id=12345)

    assert sent == 1
    combined = _texts(bot)
    assert "Python AI automation" in combined
    assert "Demo vacancy" not in combined
    assert bot.messages[0][0] == 12345
    assert bot.message_kwargs[0]["parse_mode"] == "HTML"
    markup = bot.messages[0][2]
    assert markup == {
        "inline_keyboard": [
            [
                {"text": "send", "callback_data": f"hh:send:{app_id}"},
                {"text": "edit", "callback_data": f"hh:edit:{app_id}"},
            ],
            [
                {"text": "reject", "callback_data": f"hh:reject:{app_id}"},
                {"text": "archive", "callback_data": f"hh:archive:{app_id}"},
            ],
        ]
    }


def test_agent_registers_chat_on_start_command_and_sends_queue(tmp_path) -> None:
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    _draft(repo, external_id="hh-888", title="Telegram bot developer", score=88)
    bot = FakeBot()
    settings = TelegramReviewSettings(chat_id_path=tmp_path / "chat_id", min_score=80, limit=5)
    agent = HHTelegramReviewAgent(repo=repo, bot=bot, settings=settings)

    handled = agent.handle_update(
        {
            "update_id": 10,
            "message": {
                "text": "/start",
                "chat": {"id": 67890},
            },
        }
    )

    assert handled is True
    assert settings.chat_id_path.read_text(encoding="utf-8") == "67890"
    combined = _texts(bot)
    assert "HH агент подключён" in combined
    assert "Telegram bot developer" in combined


def test_agent_generates_checked_cover_letter_when_user_sends_hh_vacancy_link(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeVacancyClient:
        def __init__(self, *, user_agent: str) -> None:
            self.user_agent = user_agent

        def fetch_vacancy(self, url_or_text: str) -> Vacancy:
            assert "132885649" in url_or_text
            return Vacancy(
                external_id="hh-132885649",
                title="AI Delivery Lead / Архитектор разработки на AI-агентах",
                company="Фордевинд",
                description=(
                    "LandComp 2.0. Нужно спроектировать agentic SDLC, роли AI agents, "
                    "Definition of Done, CI/CD, test automation, security checks и release gates. "
                    "Будет плюсом LLM/RAG. Удаленный формат."
                ),
                url="https://hh.ru/vacancy/132885649",
                salary_from=270000,
                salary_to=420000,
                currency="RUR",
                schedule="remote",
                skills=["AI agents", "agentic SDLC", "CI/CD", "LLM", "RAG", "security checks", "release gates"],
                raw={"apply_url": "https://hh.ru/applicant/vacancy_response?vacancyId=132885649"},
            )

    monkeypatch.setattr("app.telegram_agent.HHPublicVacancyClient", FakeVacancyClient)
    monkeypatch.setattr(
        "app.telegram_agent.default_candidate_profile",
        lambda learning_weights=None: CandidateProfile(
            target_roles=["AI Infrastructure Engineer", "Platform Architect", "Tech Lead"],
            skills=["AI agents", "agentic SDLC", "CI/CD", "LLM", "RAG", "security checks", "release gates"],
            preferred_keywords=["удаленный"],
            min_monthly_salary=180000,
            learning_weights=learning_weights or {},
        ),
    )
    monkeypatch.setattr(
        "app.telegram_agent.default_applicant_profile",
        lambda: ApplicantProfile(
            headline="AI Infrastructure Engineer / Platform Architect",
            cases=[
                CaseStudy(
                    title="Vibegent — Мультитенантная AI-агент платформа",
                    stack=["AI agents", "LLM"],
                    result="платформа пользовательских AI-агентов с LLM-прокси, Telegram-интерфейсами и воркер-нодами",
                ),
                CaseStudy(
                    title="Viably — AI Product Platform",
                    stack=["LLM", "CI/CD"],
                    result="AI generation pipeline, preview/deploy runtime, OAuth, billing и production-инфраструктура",
                ),
            ],
            portfolio_url="https://portfolio.viably.dev",
        ),
    )
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    bot = FakeBot()
    settings = TelegramReviewSettings(chat_id_path=tmp_path / "chat_id", min_score=80, limit=5)
    agent = HHTelegramReviewAgent(repo=repo, bot=bot, settings=settings)

    handled = agent.handle_update(
        {
            "update_id": 11,
            "message": {
                "text": "https://hh.ru/vacancy/132885649",
                "chat": {"id": 12345},
            },
        }
    )

    assert handled is True
    queue = repo.review_queue(min_score=80)
    assert len(queue) == 1
    assert queue[0]["title"] == "AI Delivery Lead / Архитектор разработки на AI-агентах"
    assert "Vibegent" in queue[0]["cover_letter"]
    assert "Viably" in queue[0]["cover_letter"]
    assert "Портфолио: https://portfolio.viably.dev" in queue[0]["cover_letter"]
    combined = _texts(bot)
    assert "Double-check: ✅" in combined
    assert "AI Delivery Lead / Архитектор разработки на AI-агентах" in combined
    assert bot.message_kwargs[-1]["parse_mode"] == "HTML"


def test_run_public_and_send_skips_when_another_run_holds_lock(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    bot = FakeBot()
    settings = TelegramReviewSettings(chat_id_path=tmp_path / "chat_id", run_lock_path=tmp_path / "run.lock")
    agent = HHTelegramReviewAgent(repo=repo, bot=bot, settings=settings)

    settings.run_lock_path.parent.mkdir(parents=True, exist_ok=True)
    with settings.run_lock_path.open("w", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        def fail_if_called() -> dict:
            raise AssertionError("run_public_once should not start while the lock is held")

        monkeypatch.setattr(agent, "run_public_once", fail_if_called)

        result = agent.run_public_and_send(chat_id=12345)

    assert result == {"skipped": "already_running"}
    assert "HH поиск уже выполняется" in _texts(bot)


def test_archive_and_reject_callbacks_update_crm_status(tmp_path) -> None:
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    archive_app_id = _draft(repo, external_id="hh-archive", title="Archive me", score=88)
    reject_app_id = _draft(repo, external_id="hh-reject", title="Reject me", score=87)
    bot = FakeBot()
    agent = HHTelegramReviewAgent(repo=repo, bot=bot, settings=TelegramReviewSettings(chat_id_path=tmp_path / "chat_id"))

    archived = agent.handle_update(
        {
            "callback_query": {
                "id": "cb-archive",
                "data": f"hh:archive:{archive_app_id}",
                "message": {"chat": {"id": 12345}},
            }
        }
    )
    rejected = agent.handle_update(
        {
            "callback_query": {
                "id": "cb-reject",
                "data": f"hh:reject:{reject_app_id}",
                "message": {"chat": {"id": 12345}},
            }
        }
    )

    assert archived is True
    assert rejected is True
    summary = repo.dashboard_summary()
    assert summary["pipeline"]["archived"] == 1
    assert summary["pipeline"]["rejected"] == 1
    assert repo.review_queue(min_score=80) == []
    assert bot.callback_answers == [
        ("cb-archive", "Архивировал", False),
        ("cb-reject", "Отклонил и убрал из очереди", False),
    ]


def test_send_callback_is_safe_confirmation_gate_before_marking_sent(tmp_path) -> None:
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    app_id = _draft(repo, external_id="hh-send", title="Send me", score=91)
    bot = FakeBot()
    agent = HHTelegramReviewAgent(repo=repo, bot=bot, settings=TelegramReviewSettings(chat_id_path=tmp_path / "chat_id"))

    requested = agent.handle_update(
        {
            "callback_query": {
                "id": "cb-send",
                "data": f"hh:send:{app_id}",
                "message": {"chat": {"id": 12345}},
            }
        }
    )

    assert requested is True
    assert repo.dashboard_summary()["pipeline"]["draft"] == 1
    assert "Бот не нажимает submit на HH" in _texts(bot)
    confirm_markup = bot.messages[-1][2]
    assert confirm_markup == {
        "inline_keyboard": [
            [
                {"text": "mark sent", "callback_data": f"hh:mark_sent:{app_id}"},
                {"text": "cancel", "callback_data": f"hh:cancel:{app_id}"},
            ]
        ]
    }

    marked = agent.handle_update(
        {
            "callback_query": {
                "id": "cb-mark-sent",
                "data": f"hh:mark_sent:{app_id}",
                "message": {"chat": {"id": 12345}},
            }
        }
    )

    assert marked is True
    assert repo.dashboard_summary()["pipeline"]["sent"] == 1
    assert repo.review_queue(min_score=80) == []


def test_edit_callback_explains_command_and_edit_command_updates_cover_letter(tmp_path) -> None:
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    app_id = _draft(repo, external_id="hh-edit", title="Edit me", score=91)
    bot = FakeBot()
    agent = HHTelegramReviewAgent(repo=repo, bot=bot, settings=TelegramReviewSettings(chat_id_path=tmp_path / "chat_id"))

    prompted = agent.handle_update(
        {
            "callback_query": {
                "id": "cb-edit",
                "data": f"hh:edit:{app_id}",
                "message": {"chat": {"id": 12345}},
            }
        }
    )
    edited = agent.handle_update(
        {
            "message": {
                "text": f"/edit {app_id} Здравствуйте! Новый текст под вакансию.\n\nПортфолио: https://portfolio.viably.dev",
                "chat": {"id": 12345},
            }
        }
    )

    assert prompted is True
    assert edited is True
    assert f"/edit {app_id}" in _texts(bot)
    item = repo.application_review_item(app_id)
    assert item is not None
    assert item["cover_letter"].startswith("Здравствуйте! Новый текст")
    assert repo.dashboard_summary()["feedback_recent"][0]["event_type"] == "edited"


def test_poll_forever_survives_transient_get_updates_timeout(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    class StopPolling(Exception):
        pass

    calls = {"polls": 0, "sleeps": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["polls"] += 1
        raise httpx.ReadTimeout("telegram long polling timed out", request=request)

    def stop_after_retry_sleep(_seconds: float) -> None:
        calls["sleeps"] += 1
        raise StopPolling

    bot = TelegramBotClient(token="123456:REDACTED", transport=httpx.MockTransport(handler))
    agent = HHTelegramReviewAgent(
        repo=CRMRepository(tmp_path / "crm.sqlite3"),
        bot=bot,
        settings=TelegramReviewSettings(offset_path=tmp_path / "offset", poll_timeout=30, poll_interval_seconds=0.01),
    )
    monkeypatch.setattr("app.telegram_agent.time.sleep", stop_after_retry_sleep)

    with pytest.raises(StopPolling):
        agent.poll_forever()

    assert calls == {"polls": 1, "sleeps": 1}


def test_poll_forever_survives_transient_update_delivery_error(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    class StopPolling(Exception):
        pass

    class SendFailingBot:
        def get_updates(self, *, offset: int | None = None, timeout: int = 30) -> list[dict]:
            return [{"update_id": 42, "message": {"text": "/summary", "chat": {"id": 12345}}}]

        def send_message(
            self,
            chat_id: int | str,
            text: str,
            reply_markup: dict | None = None,
            *,
            parse_mode: str | None = None,
        ) -> dict:
            raise TelegramNetworkError("transient send failure")

        def answer_callback_query(
            self,
            callback_query_id: str,
            text: str | None = None,
            *,
            show_alert: bool = False,
        ) -> dict:
            return {"ok": True}

    def stop_after_retry_sleep(_seconds: float) -> None:
        raise StopPolling

    settings = TelegramReviewSettings(offset_path=tmp_path / "offset", poll_timeout=30, poll_interval_seconds=0.01)
    agent = HHTelegramReviewAgent(repo=CRMRepository(tmp_path / "crm.sqlite3"), bot=SendFailingBot(), settings=settings)
    monkeypatch.setattr("app.telegram_agent.time.sleep", stop_after_retry_sleep)

    with pytest.raises(StopPolling):
        agent.poll_forever()

    assert not settings.offset_path.exists()


def test_poll_forever_does_not_skip_later_updates_after_transient_update_error(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StopPolling(Exception):
        pass

    class FlakySendBot:
        def __init__(self) -> None:
            self.send_attempts = 0

        def get_updates(self, *, offset: int | None = None, timeout: int = 30) -> list[dict]:
            return [
                {"update_id": 42, "message": {"text": "/summary", "chat": {"id": 12345}}},
                {"update_id": 43, "message": {"text": "/help", "chat": {"id": 12345}}},
            ]

        def send_message(
            self,
            chat_id: int | str,
            text: str,
            reply_markup: dict | None = None,
            *,
            parse_mode: str | None = None,
        ) -> dict:
            self.send_attempts += 1
            if self.send_attempts == 1:
                raise TelegramNetworkError("transient send failure")
            return {"ok": True}

        def answer_callback_query(
            self,
            callback_query_id: str,
            text: str | None = None,
            *,
            show_alert: bool = False,
        ) -> dict:
            return {"ok": True}

    def stop_after_retry_sleep(_seconds: float) -> None:
        raise StopPolling

    settings = TelegramReviewSettings(offset_path=tmp_path / "offset", poll_timeout=30, poll_interval_seconds=0.01)
    bot = FlakySendBot()
    agent = HHTelegramReviewAgent(repo=CRMRepository(tmp_path / "crm.sqlite3"), bot=bot, settings=settings)
    monkeypatch.setattr("app.telegram_agent.time.sleep", stop_after_retry_sleep)

    with pytest.raises(StopPolling):
        agent.poll_forever()

    assert bot.send_attempts == 1
    assert not settings.offset_path.exists()


def test_poll_forever_skips_non_retryable_update_delivery_error_and_advances_offset(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StopPolling(Exception):
        pass

    class BadRequestBot:
        def __init__(self) -> None:
            self.polls = 0

        def get_updates(self, *, offset: int | None = None, timeout: int = 30) -> list[dict]:
            self.polls += 1
            if self.polls == 1:
                return [{"update_id": 42, "message": {"text": "/summary", "chat": {"id": 12345}}}]
            return []

        def send_message(
            self,
            chat_id: int | str,
            text: str,
            reply_markup: dict | None = None,
            *,
            parse_mode: str | None = None,
        ) -> dict:
            raise TelegramAPIError("Telegram API sendMessage failed: HTTP 400: Bad Request")

        def answer_callback_query(
            self,
            callback_query_id: str,
            text: str | None = None,
            *,
            show_alert: bool = False,
        ) -> dict:
            return {"ok": True}

    def stop_after_idle_sleep(_seconds: float) -> None:
        raise StopPolling

    settings = TelegramReviewSettings(offset_path=tmp_path / "offset", poll_timeout=30, poll_interval_seconds=0.01)
    agent = HHTelegramReviewAgent(repo=CRMRepository(tmp_path / "crm.sqlite3"), bot=BadRequestBot(), settings=settings)
    monkeypatch.setattr("app.telegram_agent.time.sleep", stop_after_idle_sleep)

    with pytest.raises(StopPolling):
        agent.poll_forever()

    assert settings.offset_path.read_text(encoding="utf-8") == "43"


def test_telegram_get_updates_502_is_retryable_without_leaking_token() -> None:
    secret_token = "123456:SECRET_TOKEN_SHOULD_NOT_LEAK"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"ok": False, "description": "Bad Gateway"})

    client = TelegramBotClient(token=secret_token, transport=httpx.MockTransport(handler))

    with pytest.raises(TelegramNetworkError) as exc_info:
        client.get_updates(timeout=1)

    message = str(exc_info.value)
    assert "HTTP 502" in message
    assert "Bad Gateway" in message
    assert secret_token not in message
    assert "bot123456" not in message


def test_poll_forever_survives_transient_get_updates_502(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    class StopPolling(Exception):
        pass

    calls = {"polls": 0, "sleeps": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["polls"] += 1
        return httpx.Response(502, json={"ok": False, "description": "Bad Gateway"})

    def stop_after_retry_sleep(_seconds: float) -> None:
        calls["sleeps"] += 1
        raise StopPolling

    bot = TelegramBotClient(token="123456:REDACTED", transport=httpx.MockTransport(handler))
    agent = HHTelegramReviewAgent(
        repo=CRMRepository(tmp_path / "crm.sqlite3"),
        bot=bot,
        settings=TelegramReviewSettings(offset_path=tmp_path / "offset", poll_timeout=30, poll_interval_seconds=0.01),
    )
    monkeypatch.setattr("app.telegram_agent.time.sleep", stop_after_retry_sleep)

    with pytest.raises(StopPolling):
        agent.poll_forever()

    assert calls == {"polls": 1, "sleeps": 1}


def test_startup_delivery_api_error_does_not_stop_polling(monkeypatch: pytest.MonkeyPatch) -> None:
    class StartupFailingAgent:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def send_summary(self, *, chat_id: int | str | None = None) -> bool:
            self.calls.append("summary")
            raise TelegramAPIError("Telegram API sendMessage failed: HTTP 400: Bad Request: chat not found")

        def send_queue(self, *, chat_id: int | str | None = None) -> int:
            self.calls.append("queue")
            return 0

    monkeypatch.setenv("HH_TELEGRAM_SEND_ON_START", "1")
    agent = StartupFailingAgent()

    deliver_startup_messages(agent, 12345)  # type: ignore[arg-type]

    assert agent.calls == ["summary"]


def test_telegram_bot_client_errors_do_not_leak_token() -> None:
    secret_token = "123456:SECRET_TOKEN_SHOULD_NOT_LEAK"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    client = TelegramBotClient(token=secret_token, transport=httpx.MockTransport(handler))

    try:
        client.send_message(1, "hello")
    except RuntimeError as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("send_message should fail")

    assert "Unauthorized" in message
    assert secret_token not in message
    assert "bot123456" not in message
