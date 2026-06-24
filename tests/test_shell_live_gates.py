import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _stub_python(tmp_path: Path) -> Path:
    stub = tmp_path / "python-stub"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"$HH_STUB_LOG\"\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


def _run_script(
    script: str,
    tmp_path: Path,
    *,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    python_env: str,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    log_path = tmp_path / "calls.log"
    run_env = os.environ.copy()
    for key in (
        "HH_AUTO_APPLY_SEND",
        "HH_AUTO_APPLY_ALLOW_LIVE_SEND",
        "HH_CHAT_REPLY_SEND",
        "HH_CHAT_REPLY_ALLOW_LIVE_SEND",
        "HH_CHAT_REPLY_ANSWER_LOW_FIT",
        "HH_CHAT_REPLY_ALL_TITLES",
        "HH_CHAT_REPLY_ACK_EXTERNAL_HANDOFF",
        "HH_CHAT_REPLY_ALL_MESSAGES",
        "HH_CHAT_EXTERNAL_SUBMIT",
        "HH_TELEGRAM_BOT_TOKEN",
        "HH_TELEGRAM_CHAT_ID",
    ):
        run_env.pop(key, None)
    run_env.update(
        {
            "HH_STUB_LOG": str(log_path),
            "HH_CRM_DB_PATH": str(tmp_path / "crm.sqlite3"),
            "HH_TELEGRAM_SECRETS_FILE": str(tmp_path / "missing.env"),
            "HH_AUTO_APPLY_QUERIES": "Python Backend",
            "HH_AUTO_APPLY_LIVE_SEND_DISABLED_FLAG": str(
                tmp_path / "missing-hh-auto-apply-live-send-disabled.flag"
            ),
            "HH_CHAT_REPLY_STATE_FILE": str(tmp_path / "hh-chat-state.json"),
            "HH_CHAT_LIVE_SEND_DISABLED_FLAG": str(tmp_path / "missing-hh-chat-live-send-disabled.flag"),
            python_env: str(_stub_python(tmp_path)),
        }
    )
    if env:
        run_env.update(env)

    result = subprocess.run(
        [str(ROOT / script), *(args or [])],
        cwd=ROOT,
        env=run_env,
        text=True,
        capture_output=True,
        check=False,
    )
    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    return result, calls


def test_auto_apply_runner_blocks_raw_send_without_double_env_gate(tmp_path):
    result, calls = _run_script(
        "scripts/run_hh_auto_apply.sh",
        tmp_path,
        args=["--send", "--user-data-dir", str(tmp_path / "browser")],
        python_env="HH_AUTO_APPLY_PYTHON",
    )

    assert result.returncode == 0
    assert "live send blocked" in result.stderr
    assert calls[0] == "-m app.cli init-db"
    final_args = calls[-1].split()
    assert "auto-apply" in final_args
    assert "--send" not in final_args
    assert "--user-data-dir" in final_args


def test_auto_apply_runner_allows_send_only_when_double_env_gate_is_set(tmp_path):
    result, calls = _run_script(
        "scripts/run_hh_auto_apply.sh",
        tmp_path,
        env={"HH_AUTO_APPLY_SEND": "1", "HH_AUTO_APPLY_ALLOW_LIVE_SEND": "1"},
        python_env="HH_AUTO_APPLY_PYTHON",
    )

    assert result.returncode == 0
    assert "blocked --send" not in result.stderr
    assert "--send" in calls[-1].split()


def test_auto_apply_runner_respects_emergency_disabled_flag(tmp_path):
    disabled_flag = tmp_path / "hh-auto-apply-live-send-disabled.flag"
    disabled_flag.write_text("blocked", encoding="utf-8")

    result, calls = _run_script(
        "scripts/run_hh_auto_apply.sh",
        tmp_path,
        env={
            "HH_AUTO_APPLY_SEND": "1",
            "HH_AUTO_APPLY_ALLOW_LIVE_SEND": "1",
            "HH_AUTO_APPLY_LIVE_SEND_DISABLED_FLAG": str(disabled_flag),
        },
        python_env="HH_AUTO_APPLY_PYTHON",
    )

    assert result.returncode == 0
    assert "live send blocked" in result.stderr
    assert "--send" not in calls[-1].split()


def test_daily_auto_apply_wrapper_forces_dry_run_even_with_live_env(tmp_path):
    result, calls = _run_script(
        "scripts/run_hh_auto_apply_daily.sh",
        tmp_path,
        env={"HH_AUTO_APPLY_SEND": "1", "HH_AUTO_APPLY_ALLOW_LIVE_SEND": "1"},
        python_env="HH_AUTO_APPLY_PYTHON",
    )

    assert result.returncode == 0
    final_args = calls[-1].split()
    assert "auto-apply" in final_args
    assert "--send" not in final_args


def test_auto_apply_live_approved_wrapper_sends_with_high_volume_defaults(tmp_path):
    result, calls = _run_script(
        "scripts/run_hh_auto_apply_live_approved.sh",
        tmp_path,
        python_env="HH_AUTO_APPLY_PYTHON",
    )

    assert result.returncode == 0
    final_args = calls[-1].split()
    assert "auto-apply" in final_args
    assert "--send" in final_args
    assert "--limit" in final_args
    assert final_args[final_args.index("--limit") + 1] == "50"
    assert "--daily-limit" in final_args
    assert final_args[final_args.index("--daily-limit") + 1] == "50"
    assert "--company-guard" in final_args
    assert final_args[final_args.index("--company-guard") + 1] == "family"


def test_hh_chat_runner_blocks_raw_live_flags_without_double_env_gate(tmp_path):
    result, calls = _run_script(
        "scripts/run_hh_chat_replies.sh",
        tmp_path,
        args=["--send", "--external-submit", "--user-data-dir", str(tmp_path / "browser")],
        python_env="HH_CHAT_REPLY_PYTHON",
    )

    assert result.returncode == 0
    assert "live send blocked" in result.stderr
    assert "external submit blocked" in result.stderr
    final_args = calls[-1].split()
    assert "reply-hh-chats" in final_args
    assert "--send" not in final_args
    assert "--external-submit" not in final_args
    assert "--user-data-dir" in final_args


def test_hh_chat_runner_allows_raw_external_submit_only_with_reply_live_gate(tmp_path):
    result, calls = _run_script(
        "scripts/run_hh_chat_replies.sh",
        tmp_path,
        args=["--external-submit"],
        env={"HH_CHAT_REPLY_SEND": "1", "HH_CHAT_REPLY_ALLOW_LIVE_SEND": "1"},
        python_env="HH_CHAT_REPLY_PYTHON",
    )

    assert result.returncode == 0
    final_args = calls[-1].split()
    assert "--send" in final_args
    assert "--external-submit" in final_args


def test_hh_chat_runner_blocks_external_submit_env_without_reply_live_gate(tmp_path):
    result, calls = _run_script(
        "scripts/run_hh_chat_replies.sh",
        tmp_path,
        env={"HH_CHAT_EXTERNAL_SUBMIT": "1"},
        python_env="HH_CHAT_REPLY_PYTHON",
    )

    assert result.returncode == 0
    assert "external submit blocked" in result.stderr
    assert "--external-submit" not in calls[-1].split()


def test_hh_chat_approved_live_wrapper_is_fail_closed_by_default(tmp_path):
    result, calls = _run_script(
        "scripts/run_hh_chat_replies_live_approved.sh",
        tmp_path,
        env={"HH_CHAT_EXTERNAL_SUBMIT": "1"},
        python_env="HH_CHAT_REPLY_PYTHON",
    )

    assert result.returncode == 0
    final_args = calls[-1].split()
    assert "reply-hh-chats" in final_args
    assert "--send" not in final_args
    assert "--external-submit" not in final_args
