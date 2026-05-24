#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WATCHDOG = PROJECT_ROOT / "scripts" / "ensure_hh_telegram_agent.sh"
DAILY = PROJECT_ROOT / "scripts" / "run_hh_telegram_daily.sh"
WATCHDOG_LOG = PROJECT_ROOT / "logs" / "hh_telegram_watchdog.log"
DAILY_LOG = PROJECT_ROOT / "logs" / "hh_telegram_daily.log"

BEGIN = "# BEGIN HH CRM Telegram agent"
END = "# END HH CRM Telegram agent"
BLOCK_LINES = [
    BEGIN,
    f"@reboot {WATCHDOG} >> {WATCHDOG_LOG} 2>&1",
    f"*/5 * * * * {WATCHDOG} >> {WATCHDOG_LOG} 2>&1",
    f"10 6 * * * {DAILY} >> {DAILY_LOG} 2>&1",
    END,
]


def _current_crontab() -> str:
    result = subprocess.run(
        ["crontab", "-l"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout if result.returncode == 0 else ""


def _without_managed_block(current: str) -> list[str]:
    kept: list[str] = []
    in_block = False
    for line in current.splitlines():
        if line.strip() == BEGIN:
            in_block = True
            continue
        if line.strip() == END:
            in_block = False
            continue
        if not in_block:
            kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    return kept


def main() -> int:
    WATCHDOG_LOG.parent.mkdir(parents=True, exist_ok=True)
    DAILY_LOG.parent.mkdir(parents=True, exist_ok=True)
    new_lines = _without_managed_block(_current_crontab())
    if new_lines:
        new_lines.append("")
    new_lines.extend(BLOCK_LINES)
    new_crontab = "\n".join(new_lines) + "\n"
    subprocess.run(["crontab", "-"], input=new_crontab, text=True, check=True)
    print("Installed HH Telegram watchdog cron: @reboot, every 5 minutes, daily 06:10 UTC.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
