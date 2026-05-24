from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agent import JobSearchAgent
from app.config import default_applicant_profile, default_candidate_profile, get_settings
from app.db import initialize_database
from app.hh_client import HHClient
from app.hh_public import HHPublicSearchClient
from app.repository import CRMRepository

settings = get_settings()
initialize_database(settings.db_path)
repo = CRMRepository(settings.db_path)

app = FastAPI(title="HeadHunter CRM Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AgentRunRequest(BaseModel):
    queries: list[str] = Field(default_factory=lambda: ["React Python CRM", "Telegram bot Python", "AI automation developer"])
    per_query: int = 20
    draft_threshold: int = 80
    mode: str = "public"


class FeedbackRequest(BaseModel):
    vacancy_id: int | None = None
    application_id: int | None = None
    event_type: str
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None
    edited_cover_letter: str | None = None
    vacancy_keywords: list[str] = Field(default_factory=list)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "db_path": str(settings.db_path)}


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    return repo.dashboard_summary()


@app.get("/api/vacancies")
def vacancies(limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
    return repo.list_vacancies(limit=limit, status=status)


@app.post("/api/agent/run")
def run_agent(payload: AgentRunRequest) -> dict[str, Any]:
    if not payload.queries:
        raise HTTPException(status_code=400, detail="queries must not be empty")
    if payload.mode == "public":
        search_client = HHPublicSearchClient(user_agent=settings.hh_user_agent)
    elif payload.mode == "api":
        search_client = HHClient(user_agent=settings.hh_user_agent, access_token=settings.hh_access_token)
    else:
        raise HTTPException(status_code=400, detail="mode must be 'public' or 'api'")
    agent = JobSearchAgent(
        repo=repo,
        hh_client=search_client,
        candidate_profile=default_candidate_profile(repo.get_learning_weights()),
        applicant_profile=default_applicant_profile(),
    )
    return agent.run_once(
        queries=payload.queries,
        per_query=payload.per_query,
        draft_threshold=payload.draft_threshold,
    )


@app.post("/api/feedback")
def feedback(payload: FeedbackRequest) -> dict[str, Any]:
    feedback_id = repo.record_feedback(
        vacancy_id=payload.vacancy_id,
        application_id=payload.application_id,
        event_type=payload.event_type,
        rating=payload.rating,
        notes=payload.notes,
        edited_cover_letter=payload.edited_cover_letter,
    )
    agent = JobSearchAgent(
        repo=repo,
        hh_client=HHClient(user_agent=settings.hh_user_agent, access_token=settings.hh_access_token),
        candidate_profile=default_candidate_profile(repo.get_learning_weights()),
        applicant_profile=default_applicant_profile(),
    )
    weights = agent.learn_from_feedback(
        event_type=payload.event_type,
        vacancy_keywords=payload.vacancy_keywords,
        rating=payload.rating,
        notes=payload.notes,
        edited_cover_letter=payload.edited_cover_letter,
    )
    return {"feedback_id": feedback_id, "learning_weights": weights}
