from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from app.agent import JobSearchAgent
from app.auto_apply import AutoApplySettings, _quality_checked_drafts, run_auto_apply_once
from app.config import default_applicant_profile, default_candidate_profile, get_settings
from app.db import initialize_database
from app.google_forms import ConservativeGoogleFormRunner
from app.hh_browser import HHWebApplyRunner
from app.hh_chat import (
    ExternalHandoffAlert,
    HHChatReplyState,
    HHChatRunner,
    format_external_handoff_alert_messages,
)
from app.hh_client import HHClient
from app.hh_public import HHPublicSearchClient
from app.repository import CRMRepository
from app.responses import ResponseContext, generate_cover_letter
from app.review_export import render_markdown_review_queue
from app.scoring import Vacancy, score_vacancy
from app.telegram_agent import TelegramBotClient, settings_from_env


def _repo() -> CRMRepository:
    settings = get_settings()
    initialize_database(settings.db_path)
    return CRMRepository(settings.db_path)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _hh_chat_live_send_allowed() -> bool:
    return _env_flag("HH_CHAT_REPLY_SEND") and _env_flag("HH_CHAT_REPLY_ALLOW_LIVE_SEND")


def _hh_chat_reply_send_enabled(args: argparse.Namespace) -> bool:
    if not bool(args.send):
        return False
    if _hh_chat_live_send_allowed():
        return True
    print(
        "HH chat replies: live send blocked (--send); set HH_CHAT_REPLY_SEND=1 and "
        "HH_CHAT_REPLY_ALLOW_LIVE_SEND=1",
        file=sys.stderr,
    )
    return False


def _hh_auto_apply_live_send_allowed() -> bool:
    return _env_flag("HH_AUTO_APPLY_SEND") and _env_flag("HH_AUTO_APPLY_ALLOW_LIVE_SEND")


def _hh_browser_submit_enabled(args: argparse.Namespace) -> bool:
    if not bool(args.send):
        return False
    if _hh_auto_apply_live_send_allowed():
        return True
    print(
        "HH auto-apply: live send blocked (--send); set HH_AUTO_APPLY_SEND=1 and "
        "HH_AUTO_APPLY_ALLOW_LIVE_SEND=1",
        file=sys.stderr,
    )
    return False


def _hh_chat_external_submit_enabled(args: argparse.Namespace) -> bool:
    requested = bool(args.external_submit or _env_flag("HH_CHAT_EXTERNAL_SUBMIT"))
    return requested and _hh_chat_live_send_allowed()


def _coerce_chat_id(value: str) -> int | str:
    stripped = value.strip()
    return int(stripped) if stripped.lstrip("-").isdigit() else stripped


_HH_TELEGRAM_CHAT_ID_PLACEHOLDERS = {
    "chatid",
    "demo",
    "demochatid",
    "example",
    "examplechatid",
    "hhtelegramchatid",
    "placeholder",
    "placeholderchatid",
    "telegramchatid",
    "yourchatid",
    "yourhhtelegramchatid",
    "yourtelegramchatid",
}


def _is_configured_hh_telegram_chat_id(value: str | None) -> bool:
    if value is None:
        return False

    stripped = value.strip().strip("\"'")
    if not stripped:
        return False

    if stripped.lstrip("-").isdigit():
        chat_id = int(stripped)
        return chat_id not in {0, 12345, 123456}

    normalized = "".join(char for char in stripped.strip("<>{}[]()").lower() if char.isalnum())
    return normalized not in _HH_TELEGRAM_CHAT_ID_PLACEHOLDERS


class TelegramExternalAlertNotifier:
    def __init__(self, *, bot: TelegramBotClient, chat_id: int | str) -> None:
        self.bot = bot
        self.chat_id = chat_id

    def send_alert(self, alert: ExternalHandoffAlert) -> None:
        for message in format_external_handoff_alert_messages(alert):
            for start in range(0, len(message), 4096):
                self.bot.send_message(self.chat_id, message[start : start + 4096])


def _build_hh_chat_alert_notifier() -> TelegramExternalAlertNotifier | None:
    token = os.getenv("HH_TELEGRAM_BOT_TOKEN")
    if not token:
        return None

    chat_id_value = os.getenv("HH_TELEGRAM_CHAT_ID")
    if not _is_configured_hh_telegram_chat_id(chat_id_value):
        telegram_settings = settings_from_env()
        if telegram_settings.chat_id_path.exists():
            chat_id_value = telegram_settings.chat_id_path.read_text(encoding="utf-8").strip()
    if not _is_configured_hh_telegram_chat_id(chat_id_value):
        return None

    return TelegramExternalAlertNotifier(
        bot=TelegramBotClient(token=token),
        chat_id=_coerce_chat_id(chat_id_value),
    )


def cmd_init_db(_: argparse.Namespace) -> None:
    settings = get_settings()
    initialize_database(settings.db_path)
    print(json.dumps({"ok": True, "db_path": str(settings.db_path)}, ensure_ascii=False))


def cmd_seed_demo(_: argparse.Namespace) -> None:
    repo = _repo()
    candidate = default_candidate_profile(repo.get_learning_weights())
    applicant = default_applicant_profile()
    samples = [
        Vacancy(
            external_id="demo-hh-1",
            title="Full-stack developer для AI CRM",
            company="Demo Product",
            description="Удалённо, долгосрочный контракт. React, Python, FastAPI, Telegram, CRM, dashboard.",
            url="https://hh.ru/vacancy/demo-1",
            salary_from=220000,
            salary_to=320000,
            currency="RUR",
            schedule="remote",
            employment="part",
            skills=["React", "Python", "FastAPI", "Telegram", "CRM"],
        ),
        Vacancy(
            external_id="demo-hh-2",
            title="Backend Python integrations engineer",
            company="OpsCloud",
            description="API integrations, automation, PostgreSQL. Можно удалённо.",
            url="https://hh.ru/vacancy/demo-2",
            salary_from=180000,
            salary_to=240000,
            currency="RUR",
            schedule="remote",
            employment="full",
            skills=["Python", "API", "PostgreSQL"],
        ),
    ]
    created = 0
    for vacancy in samples:
        score = score_vacancy(vacancy, candidate)
        vacancy_id = repo.upsert_vacancy(vacancy, score)
        response = generate_cover_letter(ResponseContext(profile=applicant, vacancy=vacancy, score=score.score))
        repo.create_or_update_application(vacancy_id, cover_letter=response.message, status="draft", score_at_apply=score.score)
        created += 1
    print(json.dumps({"seeded": created, "summary": repo.dashboard_summary()}, ensure_ascii=False))


def _default_queries() -> list[str]:
    return ["React Python CRM", "Telegram bot Python", "AI automation developer"]


def cmd_run_once(args: argparse.Namespace) -> None:
    settings = get_settings()
    repo = _repo()
    queries = args.query or _default_queries()
    agent = JobSearchAgent(
        repo=repo,
        hh_client=HHClient(user_agent=settings.hh_user_agent, access_token=settings.hh_access_token),
        candidate_profile=default_candidate_profile(repo.get_learning_weights()),
        applicant_profile=default_applicant_profile(),
    )
    result = agent.run_once(queries=queries, per_query=args.per_query, draft_threshold=args.draft_threshold)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_run_public_once(args: argparse.Namespace) -> None:
    settings = get_settings()
    repo = _repo()
    queries = args.query or _default_queries()
    agent = JobSearchAgent(
        repo=repo,
        hh_client=HHPublicSearchClient(
            user_agent=settings.hh_user_agent,
            fetch_details=True,
            require_details=True,
        ),
        candidate_profile=default_candidate_profile(repo.get_learning_weights()),
        applicant_profile=default_applicant_profile(),
    )
    result = agent.run_once(queries=queries, per_query=args.per_query, draft_threshold=args.draft_threshold)
    if args.export_review_queue:
        output_path = Path(args.export_review_queue)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            render_markdown_review_queue(
                repo.review_queue(
                    min_score=args.draft_threshold,
                    limit=args.review_limit,
                    include_demo=args.include_demo,
                )
            ),
            encoding="utf-8",
        )
        result["review_queue_path"] = str(output_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_export_review_queue(args: argparse.Namespace) -> None:
    repo = _repo()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = repo.review_queue(min_score=args.min_score, limit=args.limit, include_demo=args.include_demo)
    output_path.write_text(render_markdown_review_queue(rows), encoding="utf-8")
    print(json.dumps({"exported": len(rows), "output": str(output_path)}, ensure_ascii=False))


def _keep_browser_open_for_review(enabled: bool, results: list) -> None:
    if not enabled or not results:
        return
    try:
        input("HH browser is open for manual review. Press Enter here to close it…")
    except EOFError:
        return


def cmd_apply_browser_queue(args: argparse.Namespace) -> None:
    settings = get_settings()
    repo = _repo()
    rows = repo.review_queue(min_score=args.min_score, limit=args.limit, include_demo=args.include_demo)
    drafts, quality_issues = _quality_checked_drafts(
        repo=repo,
        rows=rows,
        applicant_profile=default_applicant_profile(),
    )
    user_data_dir = args.user_data_dir or settings.hh_browser_user_data_dir
    send_enabled = _hh_browser_submit_enabled(args)
    results = []
    if drafts:
        runner = HHWebApplyRunner.launch(user_data_dir=user_data_dir, headless=args.headless)
        try:
            results = runner.run(drafts, send=send_enabled)
            _keep_browser_open_for_review(args.keep_open, results)
        finally:
            runner.close()

    sent = 0
    prepared = 0
    blocked = 0
    for result in results:
        if result.status == "sent" and send_enabled:
            sent += 1
            repo.record_feedback(
                vacancy_id=result.vacancy_id,
                application_id=result.application_id,
                event_type="sent",
                notes="Sent via no-API HH browser runner",
            )
        elif result.status == "prepared":
            prepared += 1
        else:
            blocked += 1

    print(
        json.dumps(
            {
                "queued": len(drafts),
                "queue_candidates": len(rows),
                "prepared": prepared,
                "sent": sent,
                "blocked": blocked,
                "quality_skipped": len(quality_issues),
                "quality_issues": quality_issues,
                "send_enabled": send_enabled,
                "statuses": [result.status for result in results],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def cmd_auto_apply(args: argparse.Namespace) -> None:
    settings = get_settings()
    repo = _repo()
    queries = args.query or _default_queries()
    user_data_dir = args.user_data_dir or settings.hh_browser_user_data_dir
    fetch_details = os.getenv("HH_AUTO_APPLY_FETCH_DETAILS", "1") == "1"
    require_details = fetch_details and os.getenv("HH_AUTO_APPLY_REQUIRE_DETAILS", "1") == "1"
    send_enabled = _hh_browser_submit_enabled(args)
    runner = HHWebApplyRunner.launch(user_data_dir=user_data_dir, headless=args.headless)
    try:
        result = run_auto_apply_once(
            repo=repo,
            search_client=HHPublicSearchClient(
                user_agent=settings.hh_user_agent,
                fetch_details=fetch_details,
                require_details=require_details,
            ),
            candidate_profile=default_candidate_profile(repo.get_learning_weights()),
            applicant_profile=default_applicant_profile(),
            apply_runner=runner,
            settings=AutoApplySettings(
                queries=queries,
                per_query=args.per_query,
                draft_threshold=args.draft_threshold,
                min_score=args.min_score,
                limit=args.limit,
                daily_limit=args.daily_limit,
                send=send_enabled,
                include_demo=args.include_demo,
                company_guard=args.company_guard,
            ),
        )
    finally:
        runner.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_reply_hh_chats(args: argparse.Namespace) -> None:
    settings = get_settings()
    repo = _repo()
    user_data_dir = args.user_data_dir or settings.hh_browser_user_data_dir
    state = HHChatReplyState(args.state_file)
    profile = default_applicant_profile()
    send_enabled = _hh_chat_reply_send_enabled(args)
    external_submit = _hh_chat_external_submit_enabled(args)
    alert_notifier = _build_hh_chat_alert_notifier()
    try:
        runner = HHChatRunner.launch(
            profile=profile,
            state=state,
            user_data_dir=user_data_dir,
            headless=args.headless,
            alert_notifier=alert_notifier,
        )
        runner.external_form_handler = ConservativeGoogleFormRunner(page=runner.page, profile=profile)
        try:
            result = runner.run(
                send=send_enabled,
                limit=args.limit,
                max_chats=args.max_chats,
                external_submit=external_submit,
            )
        finally:
            runner.close()
    except Exception as exc:
        details = {"error": f"{type(exc).__name__}: {exc}"}
        repo.record_run_log(agent_name="hh-chat-replies", status="error", details=details)
        print(json.dumps({"ok": False, **details}, ensure_ascii=False, indent=2))
        raise SystemExit(1) from exc

    details = result.to_dict()
    status = (
        "blocked"
        if any(item in {"needs_login", "form_not_found"} or "needs_login" in item for item in result.statuses)
        else "ok"
    )
    repo.record_run_log(agent_name="hh-chat-replies", status=status, details=details)
    print(json.dumps(details, ensure_ascii=False, indent=2))


def cmd_summary(_: argparse.Namespace) -> None:
    repo = _repo()
    print(json.dumps(repo.dashboard_summary(), ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HH CRM Agent CLI")
    sub = parser.add_subparsers(required=True)

    init_db = sub.add_parser("init-db", help="Initialize SQLite CRM database")
    init_db.set_defaults(func=cmd_init_db)

    seed_demo = sub.add_parser("seed-demo", help="Create demo CRM data and drafts")
    seed_demo.set_defaults(func=cmd_seed_demo)

    run_once = sub.add_parser("run-once", help="Search HH API, score vacancies, create drafts")
    run_once.add_argument("--query", action="append", help="HH search query; can be repeated")
    run_once.add_argument("--per-query", type=int, default=20)
    run_once.add_argument("--draft-threshold", type=int, default=80)
    run_once.set_defaults(func=cmd_run_once)

    run_public_once = sub.add_parser(
        "run-public-once",
        help="No-API mode: parse public HH search pages, score vacancies, create drafts",
    )
    run_public_once.add_argument("--query", action="append", help="HH search query; can be repeated")
    run_public_once.add_argument("--per-query", type=int, default=20)
    run_public_once.add_argument("--draft-threshold", type=int, default=80)
    run_public_once.add_argument(
        "--export-review-queue",
        default="./data/review_queue.md",
        help="Write a markdown queue with vacancy links, response links, and drafts; empty string disables",
    )
    run_public_once.add_argument("--review-limit", type=int, default=20)
    run_public_once.add_argument(
        "--include-demo",
        action="store_true",
        help="Include seed-demo drafts in the exported review queue",
    )
    run_public_once.set_defaults(func=cmd_run_public_once)

    export_review = sub.add_parser(
        "export-review-queue",
        help="Export current draft queue to markdown with no-API HH response links",
    )
    export_review.add_argument("--output", default="./data/review_queue.md")
    export_review.add_argument("--min-score", type=int, default=80)
    export_review.add_argument("--limit", type=int, default=20)
    export_review.add_argument(
        "--include-demo",
        action="store_true",
        help="Include seed-demo drafts; disabled by default for real HH review queues",
    )
    export_review.set_defaults(func=cmd_export_review_queue)

    apply_browser = sub.add_parser(
        "apply-browser-queue",
        help="No-API browser mode: open HH apply links and fill cover letters from CRM drafts",
    )
    apply_browser.add_argument("--min-score", type=int, default=80)
    apply_browser.add_argument("--limit", type=int, default=5)
    apply_browser.add_argument("--user-data-dir", default=None)
    apply_browser.add_argument("--headless", action="store_true")
    apply_browser.add_argument(
        "--keep-open",
        action="store_true",
        help="After inserting drafts, keep the browser open until Enter is pressed for manual review",
    )
    apply_browser.add_argument(
        "--include-demo",
        action="store_true",
        help="Include seed-demo drafts; disabled by default for real HH browser applications",
    )
    apply_browser.add_argument(
        "--send",
        action="store_true",
        help="Actually click HH submit buttons. Without this flag drafts are only inserted.",
    )
    apply_browser.set_defaults(func=cmd_apply_browser_queue)

    auto_apply = sub.add_parser(
        "auto-apply",
        help="Full loop: public HH search, scoring, draft generation, and browser apply with daily limit",
    )
    auto_apply.add_argument("--query", action="append", help="HH search query; can be repeated")
    auto_apply.add_argument("--per-query", type=int, default=20)
    auto_apply.add_argument("--draft-threshold", type=int, default=80)
    auto_apply.add_argument("--min-score", type=int, default=80)
    auto_apply.add_argument("--limit", type=int, default=5)
    auto_apply.add_argument("--daily-limit", type=int, default=5)
    auto_apply.add_argument(
        "--company-guard",
        choices=("strict", "family", "off"),
        default=os.getenv("HH_AUTO_APPLY_COMPANY_GUARD", "strict"),
        help=(
            "Company duplicate guard: strict blocks any previously handled employer, "
            "family blocks only known noisy employer families such as Sber, off disables broad company blocking."
        ),
    )
    auto_apply.add_argument("--user-data-dir", default=None)
    auto_apply.add_argument("--headless", action="store_true")
    auto_apply.add_argument(
        "--include-demo",
        action="store_true",
        help="Include seed-demo drafts; disabled by default for real HH auto-apply",
    )
    auto_apply.add_argument(
        "--send",
        action="store_true",
        help="Actually click HH submit buttons. Without this flag auto-apply only fills drafts.",
    )
    auto_apply.set_defaults(func=cmd_auto_apply)

    reply_hh_chats = sub.add_parser(
        "reply-hh-chats",
        help="Open HH chats, detect employer questions, draft or send safe follow-up replies",
    )
    reply_hh_chats.add_argument("--limit", type=int, default=5)
    reply_hh_chats.add_argument("--max-chats", type=int, default=80)
    reply_hh_chats.add_argument("--user-data-dir", default=None)
    reply_hh_chats.add_argument("--state-file", default="./data/hh_chat_reply_state.json")
    reply_hh_chats.add_argument("--headless", action="store_true")
    reply_hh_chats.add_argument(
        "--send",
        action="store_true",
        help="Actually send HH chat replies. Without this flag only drafts are generated.",
    )
    reply_hh_chats.add_argument(
        "--external-submit",
        action="store_true",
        help=(
            "Allow safe Google Form submission after HH_CHAT_REPLY_SEND and "
            "HH_CHAT_REPLY_ALLOW_LIVE_SEND gates. "
            "Without it Google Forms may be filled but not submitted."
        ),
    )
    reply_hh_chats.set_defaults(func=cmd_reply_hh_chats)

    summary = sub.add_parser("summary", help="Print dashboard summary")
    summary.set_defaults(func=cmd_summary)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
