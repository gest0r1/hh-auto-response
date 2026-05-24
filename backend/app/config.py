from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path

from app.responses import ApplicantProfile, CaseStudy
from app.scoring import CandidateProfile


@dataclass(slots=True)
class Settings:
    db_path: Path
    hh_user_agent: str
    hh_access_token: str | None = None
    hh_resume_id: str | None = None
    profile_path: Path | None = None
    hh_browser_user_data_dir: Path = Path("./data/hh-browser-profile")


def get_settings() -> Settings:
    return Settings(
        db_path=Path(os.getenv("HH_CRM_DB_PATH", "./data/hh_crm.sqlite3")),
        hh_user_agent=os.getenv(
            "HH_USER_AGENT",
            "headhunter-crm-agent/0.1 (https://portfolio.viably.dev)",
        ),
        hh_access_token=os.getenv("HH_ACCESS_TOKEN") or None,
        hh_resume_id=os.getenv("HH_RESUME_ID") or None,
        profile_path=_default_profile_path(),
        hh_browser_user_data_dir=Path(os.getenv("HH_BROWSER_USER_DATA_DIR", "./data/hh-browser-profile")),
    )


def _default_profile_path() -> Path | None:
    explicit = os.getenv("HH_PROFILE_PATH")
    if explicit:
        return Path(explicit)
    candidate = Path(os.getenv("HH_PROFILE_PATH", "./data/profile.example.json"))
    return candidate if candidate.exists() else None


def _load_profile_data() -> dict:
    path = _default_profile_path()
    if not path or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def default_candidate_profile(learning_weights: dict[str, float] | None = None) -> CandidateProfile:
    data = _load_profile_data()
    if data:
        return CandidateProfile(
            target_roles=data.get("target_roles") or [],
            skills=data.get("skills") or [],
            preferred_keywords=data.get("preferred_keywords") or [],
            stop_keywords=data.get("stop_keywords") or [],
            min_monthly_salary=data.get("min_monthly_salary"),
            learning_weights=learning_weights or {},
        )
    return CandidateProfile(
        target_roles=[
            "full-stack",
            "backend",
            "telegram bots",
            "ai automation",
            "crm integrations",
            "парсинг",
            "интеграции",
        ],
        skills=[
            "React",
            "Next.js",
            "Node.js",
            "Python",
            "FastAPI",
            "Django",
            "Telegram",
            "CRM",
            "PostgreSQL",
            "SQLite",
            "LLM",
            "AI",
            "API",
        ],
        preferred_keywords=[
            "удаленно",
            "удалённо",
            "долгосрочно",
            "контракт",
            "part-time",
            "проектная работа",
            "автоматизация",
            "дашборд",
        ],
        stop_keywords=[
            "только офис",
            "холодные звонки",
            "1с",
            "bitrix24 внедренец",
            "битрикс без разработки",
        ],
        min_monthly_salary=180000,
        learning_weights=learning_weights or {},
    )


def default_applicant_profile() -> ApplicantProfile:
    data = _load_profile_data()
    if data:
        return ApplicantProfile(
            full_name=data.get("full_name") or "Александр Олегович",
            headline=data.get("headline") or "Full-stack developer / AI automation engineer",
            strengths=data.get("strengths") or [],
            cases=[
                CaseStudy(
                    title=case.get("title") or "Untitled case",
                    stack=case.get("stack") or case.get("skills") or [],
                    result=case.get("result")
                    or "; ".join((case.get("achievements") or [])[:2])
                    or case.get("description")
                    or "",
                    url=case.get("url") or None,
                    role=case.get("role") or "",
                    period=case.get("period") or "",
                    description=case.get("description") or "",
                )
                for case in data.get("cases", [])
            ],
            portfolio_url=data.get("portfolio_url") or None,
            website_url=data.get("website_url") or None,
        )

    # Safe placeholder until Aleksandr provides real resume/portfolio/cases.
    return ApplicantProfile(
        full_name="Александр Олегович",
        headline="Full-stack developer / AI automation engineer",
        strengths=[
            "быстро собираю рабочие MVP",
            "делаю интеграции и CRM под бизнес-процессы",
            "подключаю Telegram-ботов, API и визуальные дашборды",
        ],
        cases=[
            CaseStudy(
                title="CRM/дашборд для управления агентами и задачами",
                stack=["React", "Next.js", "Python", "SQLite", "Telegram"],
                result="собран визуальный контур управления, статусы и рабочие сценарии в одном интерфейсе",
            ),
            CaseStudy(
                title="Telegram automation pipeline",
                stack=["Python", "FastAPI", "Telegram", "API"],
                result="автоматизирован сбор данных, подготовка сообщений и контроль статусов",
            ),
        ],
        portfolio_url=None,
    )
