from __future__ import annotations

import argparse
from typing import Sequence

from app.telegram_agent import (
    TelegramAPIError,
    TelegramNetworkError,
    build_agent_from_env,
    register_command_menu,
)


def run_daily_review(*, check_only: bool = False) -> int:
    """Run the scheduled HH review task once.

    This is intentionally separate from the long-polling bot process: cron can refresh
    the CRM/review queue even if nobody manually sends /run that day.
    """
    agent = build_agent_from_env()
    register_command_menu(agent)

    try:
        agent.bot.get_me()
    except TelegramNetworkError as exc:
        print(f"HH Telegram daily check skipped after transient Telegram error: {exc}", flush=True)
        return 75
    except TelegramAPIError as exc:
        print(f"HH Telegram daily check failed during Telegram setup: {exc}", flush=True)
        return 2

    saved_chat_id = agent.saved_chat_id()
    if saved_chat_id is None:
        print("HH Telegram daily skipped: no chat registered; send /start to the HH bot.", flush=True)
        return 0

    if check_only:
        print("HH Telegram daily check ok: bot token and saved chat are present.", flush=True)
        return 0

    try:
        result = agent.run_public_and_send(chat_id=saved_chat_id)
    except TelegramNetworkError as exc:
        print(f"HH Telegram daily run skipped after transient Telegram error: {exc}", flush=True)
        return 75
    except TelegramAPIError as exc:
        print(f"HH Telegram daily delivery skipped after Telegram API error: {exc}", flush=True)
        return 0

    print(
        "HH Telegram daily review completed: "
        f"vacancies_seen={result.get('vacancies_seen', 0)}, "
        f"drafts_created={result.get('drafts_created', 0)}, "
        f"errors={len(result.get('errors') or [])}.",
        flush=True,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the scheduled HH Telegram review task")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate Telegram token/chat state without running HH search or sending the queue.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_daily_review(check_only=args.check_only)


if __name__ == "__main__":
    raise SystemExit(main())
