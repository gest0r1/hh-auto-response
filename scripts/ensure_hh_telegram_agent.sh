#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=hh_telegram_env.sh
source "$SCRIPT_DIR/hh_telegram_env.sh"

# Watchdog restarts must be quiet: no startup summary/queue spam.
export HH_TELEGRAM_SEND_ON_START=0
export HH_TELEGRAM_PID_PATH="${HH_TELEGRAM_PID_PATH:-./data/hh_telegram_agent.pid}"
export HH_TELEGRAM_LOG_PATH="${HH_TELEGRAM_LOG_PATH:-./logs/hh_telegram_agent.log}"

"$HH_TELEGRAM_PYTHON" - <<'PY'
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path.cwd().resolve()
PID_PATH = Path(os.environ["HH_TELEGRAM_PID_PATH"])
LOG_PATH = Path(os.environ["HH_TELEGRAM_LOG_PATH"])


def _process_matches(pid: int) -> bool:
    proc = Path("/proc") / str(pid)
    try:
        args = [
            part.decode("utf-8", "ignore")
            for part in (proc / "cmdline").read_bytes().split(b"\0")
            if part
        ]
        cwd = (proc / "cwd").resolve()
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
        return False
    if cwd != PROJECT_ROOT or len(args) < 3:
        return False
    return Path(args[0]).name.startswith("python") and args[1:3] == ["-m", "app.telegram_agent"]


def _pid_from_file() -> int | None:
    try:
        value = PID_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return int(value) if value.isdigit() else None


def _find_running_agent() -> int | None:
    pid = _pid_from_file()
    if pid is not None and _process_matches(pid):
        return pid
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if _process_matches(pid):
            PID_PATH.parent.mkdir(parents=True, exist_ok=True)
            PID_PATH.write_text(str(pid), encoding="utf-8")
            return pid
    return None


def main() -> int:
    if not os.environ.get("HH_TELEGRAM_BOT_TOKEN"):
        print("HH Telegram watchdog: bot token is not configured; agent not started.")
        return 0

    if _find_running_agent() is not None:
        return 0

    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    launcher = PROJECT_ROOT / "scripts" / "run_hh_telegram_agent.sh"
    env = os.environ.copy()
    env["HH_TELEGRAM_SEND_ON_START"] = "0"

    with LOG_PATH.open("ab") as log_file:
        process = subprocess.Popen(
            [str(launcher)],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    PID_PATH.write_text(str(process.pid), encoding="utf-8")
    time.sleep(2)
    if process.poll() is not None:
        print("HH Telegram watchdog: attempted restart, but agent exited immediately. Check logs/hh_telegram_agent.log.")
        return 1

    print("HH Telegram watchdog: agent was down and has been restarted.")
    return 0


raise SystemExit(main())
PY
