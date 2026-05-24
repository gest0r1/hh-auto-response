from app.cli import (
    TelegramExternalAlertNotifier,
    _build_hh_chat_alert_notifier,
    _is_configured_hh_telegram_chat_id,
    build_parser,
)
from app.hh_chat import ExternalHandoffAlert, ExternalTarget, HHChatRunResult, PreparedExternalResponse


def test_cli_has_no_api_public_search_command():
    args = build_parser().parse_args(["run-public-once", "--query", "React Python", "--per-query", "7"])

    assert args.query == ["React Python"]
    assert args.per_query == 7
    assert callable(args.func)


def test_cli_has_review_queue_export_command(tmp_path):
    output = tmp_path / "queue.md"
    args = build_parser().parse_args(
        ["export-review-queue", "--output", str(output), "--min-score", "75", "--include-demo"]
    )

    assert args.output == str(output)
    assert args.min_score == 75
    assert args.include_demo is True
    assert callable(args.func)


def test_cli_has_browser_apply_queue_command():
    args = build_parser().parse_args(
        [
            "apply-browser-queue",
            "--min-score",
            "80",
            "--limit",
            "3",
            "--user-data-dir",
            "./data/hh-browser-profile",
            "--include-demo",
            "--keep-open",
            "--send",
        ]
    )

    assert args.min_score == 80
    assert args.limit == 3
    assert args.user_data_dir == "./data/hh-browser-profile"
    assert args.include_demo is True
    assert args.keep_open is True
    assert args.send is True
    assert callable(args.func)


def test_cli_has_auto_apply_command():
    args = build_parser().parse_args(
        [
            "auto-apply",
            "--query",
            "Python React AI",
            "--per-query",
            "10",
            "--min-score",
            "85",
            "--limit",
            "4",
            "--daily-limit",
            "2",
            "--send",
            "--headless",
        ]
    )

    assert args.query == ["Python React AI"]
    assert args.per_query == 10
    assert args.min_score == 85
    assert args.limit == 4
    assert args.daily_limit == 2
    assert args.send is True
    assert args.headless is True
    assert callable(args.func)


def test_cli_has_hh_chat_reply_command():
    args = build_parser().parse_args(
        [
            "reply-hh-chats",
            "--limit",
            "6",
            "--max-chats",
            "40",
            "--state-file",
            "./data/state.json",
            "--user-data-dir",
            "./data/hh-browser-profile",
            "--send",
            "--headless",
        ]
    )

    assert args.limit == 6
    assert args.max_chats == 40
    assert args.state_file == "./data/state.json"
    assert args.user_data_dir == "./data/hh-browser-profile"
    assert args.send is True
    assert args.headless is True
    assert args.external_submit is False
    assert callable(args.func)


def test_cli_parses_hh_chat_external_submit_flag():
    args = build_parser().parse_args(
        [
            "reply-hh-chats",
            "--external-submit",
        ]
    )

    assert args.external_submit is True
    assert callable(args.func)


def test_reply_hh_chats_external_submit_env_still_requires_live_allow(monkeypatch, tmp_path):
    class FakeRunner:
        run_kwargs = {}
        page = object()

        @classmethod
        def launch(cls, **_kwargs):
            return cls()

        def run(self, **kwargs):
            type(self).run_kwargs = kwargs
            return HHChatRunResult(
                scanned=0,
                candidates=0,
                sent=0,
                drafted=0,
                skipped=0,
                blocked=0,
                send_enabled=kwargs["send"],
                statuses=[],
                replies=[],
                external_submit_enabled=kwargs["external_submit"],
            )

        def close(self):
            return None

    monkeypatch.setattr("app.cli.HHChatRunner", FakeRunner)
    monkeypatch.setattr("app.cli.ConservativeGoogleFormRunner", lambda **_kwargs: object())
    monkeypatch.setenv("HH_CRM_DB_PATH", str(tmp_path / "crm.sqlite3"))
    monkeypatch.setenv("HH_CHAT_EXTERNAL_SUBMIT", "1")
    monkeypatch.setenv("HH_CHAT_REPLY_SEND", "1")
    monkeypatch.delenv("HH_CHAT_REPLY_ALLOW_LIVE_SEND", raising=False)
    monkeypatch.delenv("HH_TELEGRAM_BOT_TOKEN", raising=False)
    args = build_parser().parse_args(
        [
            "reply-hh-chats",
            "--send",
            "--state-file",
            str(tmp_path / "state.json"),
        ]
    )

    args.func(args)

    assert FakeRunner.run_kwargs["external_submit"] is False

    monkeypatch.setenv("HH_CHAT_REPLY_ALLOW_LIVE_SEND", "1")
    args.func(args)

    assert FakeRunner.run_kwargs["external_submit"] is True


def test_hh_telegram_chat_id_validation_rejects_placeholders():
    for value in [
        None,
        "",
        " ",
        "0",
        "0000",
        "12345",
        "123456",
        "demo",
        "example",
        "placeholder",
        "your_chat_id",
        "<HH_TELEGRAM_CHAT_ID>",
    ]:
        assert _is_configured_hh_telegram_chat_id(value) is False


def test_hh_telegram_chat_id_validation_allows_real_looking_targets():
    for value in [
        "1",
        "67890",
        "-1001234567890",
        "@hh_alerts_channel",
        "hh_alerts_user",
    ]:
        assert _is_configured_hh_telegram_chat_id(value) is True


def test_build_hh_chat_alert_notifier_skips_placeholder_saved_chat_id(monkeypatch, tmp_path):
    chat_id_path = tmp_path / "chat_id"
    chat_id_path.write_text("12345", encoding="utf-8")
    monkeypatch.setenv("HH_TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.delenv("HH_TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("HH_TELEGRAM_CHAT_ID_PATH", str(chat_id_path))

    assert _build_hh_chat_alert_notifier() is None


def test_build_hh_chat_alert_notifier_allows_valid_saved_group_id(monkeypatch, tmp_path):
    chat_id_path = tmp_path / "chat_id"
    chat_id_path.write_text("-1001234567890", encoding="utf-8")
    monkeypatch.setenv("HH_TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.delenv("HH_TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("HH_TELEGRAM_CHAT_ID_PATH", str(chat_id_path))

    notifier = _build_hh_chat_alert_notifier()

    assert notifier is not None
    assert notifier.chat_id == -1001234567890


class _FakeBot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))


def test_external_alert_notifier_sends_readable_separate_messages():
    bot = _FakeBot()
    notifier = TelegramExternalAlertNotifier(bot=bot, chat_id=123)
    alert = ExternalHandoffAlert(
        chat_id="hh-chat-1",
        title="Senior MLOps / AI Platform Engineer",
        chat_url="https://hh.ru/chat/1",
        external_targets=[ExternalTarget(kind="telegram_url", value="https://t.me/Giga_recruiter_bot?start=abc")],
        original_message="Пройдите предварительное интервью по ссылке.",
        prepared_response=PreparedExternalResponse(
            copy_paste_message="Здравствуйте! Я Александр Олегович. Основной профиль - AI Agent Systems.",
        ),
    )

    notifier.send_alert(alert)

    assert len(bot.messages) == 3
    assert bot.messages[0][0] == 123
    assert bot.messages[0][1].startswith("Внешний контакт из HH\n\nВакансия:")
    assert "\n\nКуда перейти:\n- Telegram: https://t.me/Giga_recruiter_bot?start=abc" in bot.messages[0][1]
    assert bot.messages[1][1].startswith("Сообщение работодателя:\n\n")
    assert bot.messages[2][1].startswith("Готовый текст для вставки:\n\n")
