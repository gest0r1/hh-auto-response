import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_aleksandr_profile_keeps_python_backend_as_primary_axis():
    profile = json.loads((ROOT / "data/profile.aleksandr.json").read_text(encoding="utf-8"))

    assert profile["headline"].startswith("Python Backend Developer")
    assert profile["target_roles"][:3] == [
        "Python Backend Developer",
        "Backend Python Developer",
        "Python Backend Engineer",
    ]
    assert "Junior Python Backend Developer" in profile["target_roles"]
    assert "Senior Python Backend Developer" in profile["target_roles"]
    assert "Team Lead Python Developer" in profile["target_roles"]
    assert all("Architect" not in role for role in profile["target_roles"])
    assert "Solution Architect" in profile["secondary_roles_low_priority"]
    assert "Python Backend" in profile["skills"][:5]
    assert profile["strengths"][0].startswith("основной профиль - Python backend developer")
    assert profile["location"] == "Обнинск"
    assert profile["city"] == "Обнинск"
    assert profile["telegram"] == "@ne_stoit_togo"
    assert profile["age"] == 25
    assert profile["phone"] == "+79106053173"
    assert profile["min_monthly_salary"] == 100000
    assert profile["salary_expectations"]["critical_mode"] is True
    profile_text = json.dumps(profile, ensure_ascii=False)
    assert "300000-350000" not in profile_text
    assert profile["salary_positioning"]["active_hh_resume"] == "Python Backend / AI Backend Developer"
    assert "не позиционироваться architect-first" in profile["salary_strategy"]


def test_daily_auto_apply_queries_include_python_backend_without_generic_frontend_spread():
    script = (ROOT / "scripts/run_hh_auto_apply_daily.sh").read_text(encoding="utf-8")

    assert "Python Backend developer" in script
    assert "Junior Python Backend developer" in script
    assert "Senior Python Backend developer" in script
    assert "Team Lead Python" in script
    assert "FastAPI developer" in script
    assert "Backend Python developer" in script
    assert "AI agents developer" in script
    assert "LLM Backend Engineer" in script
    assert 'HH_AUTO_APPLY_DRAFT_THRESHOLD="${HH_AUTO_APPLY_DRAFT_THRESHOLD:-90}"' in script
    assert 'HH_AUTO_APPLY_MIN_SCORE="${HH_AUTO_APPLY_MIN_SCORE:-90}"' in script
    assert 'HH_AUTO_APPLY_LIMIT="${HH_AUTO_APPLY_LIMIT:-3}"' in script
    assert 'HH_AUTO_APPLY_DAILY_LIMIT="${HH_AUTO_APPLY_DAILY_LIMIT:-5}"' in script
    assert "React developer" not in script
    assert "Node.js developer" not in script
    assert "JavaScript developer" not in script


def test_hh_auto_apply_daily_runner_is_dry_run_by_default_and_double_gated():
    daily = (ROOT / "scripts/run_hh_auto_apply_daily.sh").read_text(encoding="utf-8")
    runner = (ROOT / "scripts/run_hh_auto_apply.sh").read_text(encoding="utf-8")

    assert 'HH_AUTO_APPLY_SEND="0"' in daily
    assert 'HH_AUTO_APPLY_ALLOW_LIVE_SEND="0"' in daily
    assert "permanently dry-run" in daily
    assert "HH_AUTO_APPLY_ALLOW_LIVE_SEND" in runner
    assert "live send blocked" in runner


def test_hh_chat_hourly_runner_is_dry_run_by_default_and_double_gated():
    hourly = (ROOT / "scripts/run_hh_chat_replies_hourly.sh").read_text(encoding="utf-8")
    runner = (ROOT / "scripts/run_hh_chat_replies.sh").read_text(encoding="utf-8")

    assert 'HH_CHAT_REPLY_SEND="${HH_CHAT_REPLY_SEND:-0}"' in hourly
    assert 'HH_CHAT_EXTERNAL_SUBMIT="${HH_CHAT_EXTERNAL_SUBMIT:-0}"' in hourly
    assert "HH_CHAT_REPLY_ALLOW_LIVE_SEND" in hourly
    assert "HH_CHAT_REPLY_ALLOW_LIVE_SEND" in runner
    assert "live send blocked" in runner
    assert "external submit blocked" in runner


def test_hh_chat_approved_live_runner_is_explicit_and_no_external_submit():
    live = (ROOT / "scripts/run_hh_chat_replies_live_approved.sh").read_text(encoding="utf-8")

    assert "Fail-closed lane" in live
    assert "run_hh_chat_replies_hourly.sh, which stays dry-run" in live
    assert 'export HH_CHAT_REPLY_SEND="${HH_CHAT_REPLY_SEND:-0}"' in live
    assert 'export HH_CHAT_REPLY_ALLOW_LIVE_SEND="${HH_CHAT_REPLY_ALLOW_LIVE_SEND:-0}"' in live
    assert 'export HH_CHAT_REPLY_ANSWER_LOW_FIT="${HH_CHAT_REPLY_ANSWER_LOW_FIT:-1}"' in live
    assert 'export HH_CHAT_REPLY_ACK_EXTERNAL_HANDOFF="${HH_CHAT_REPLY_ACK_EXTERNAL_HANDOFF:-0}"' in live
    assert "export HH_CHAT_EXTERNAL_SUBMIT=0" in live
    assert "exec ./scripts/run_hh_chat_replies.sh" in live


def test_aleksandr_profile_closes_open_project_periods_in_may_2026():
    profile = json.loads((ROOT / "data/profile.aleksandr.json").read_text(encoding="utf-8"))
    periods = [case.get("period", "") for case in profile["cases"]]

    assert any(period == "2025 - май 2026" for period in periods)
    assert not any("2025–2026" in period for period in periods)
    assert not any("2025-2026" in period for period in periods)


def test_aleksandr_profile_contains_new_employer_facing_cases():
    profile = json.loads((ROOT / "data/profile.aleksandr.json").read_text(encoding="utf-8"))
    titles = [case.get("title", "") for case in profile["cases"]]

    assert profile["cases_count"] == len(profile["cases"])
    assert "AI Dev Office - центр управления AI-агентами" in titles
    assert "whynotai Telegram Agents - платформа Telegram AI-агентов" in titles
    assert "AI-office X-ONE - платформа управления AI-офисом" in titles
    assert "Transoff AI Sales QA Platform - контроль качества звонков" in titles
    assert "HeadHunter CRM Agent - агент для поиска работы и откликов" in titles
    assert "Telethon" in profile["skills"]
    assert "Celery" in profile["skills"]
    assert "Qdrant" in profile["skills"]
    assert "Google Sheets API" in profile["skills"]
    assert "Playwright" in profile["skills"]
