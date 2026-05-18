from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.agent import JobSearchAgent, SearchClient
from app.hh_browser import BrowserApplyResult, row_to_apply_draft
from app.repository import CRMRepository
from app.responses import ApplicantProfile
from app.scoring import CandidateProfile


class ApplyRunner(Protocol):
    def run(self, drafts: list[Any], *, send: bool = False) -> list[BrowserApplyResult]: ...


@dataclass(slots=True)
class AutoApplySettings:
    queries: list[str]
    per_query: int = 20
    draft_threshold: int = 80
    min_score: int = 80
    limit: int = 5
    daily_limit: int | None = 5
    send: bool = False
    include_demo: bool = False


def _send_capacity(repo: CRMRepository, settings: AutoApplySettings) -> tuple[int, int | None, bool]:
    limit = max(0, settings.limit)
    if not settings.send or settings.daily_limit is None:
        return limit, None, False

    daily_limit = max(0, settings.daily_limit)
    sent_today = repo.count_sent_today()
    remaining = max(0, daily_limit - sent_today)
    return min(limit, remaining), remaining, remaining <= 0


def run_auto_apply_once(
    *,
    repo: CRMRepository,
    search_client: SearchClient,
    candidate_profile: CandidateProfile,
    applicant_profile: ApplicantProfile,
    apply_runner: ApplyRunner,
    settings: AutoApplySettings,
) -> dict[str, Any]:
    """Run the full HH loop once: search -> score -> draft -> browser apply.

    Real external sending still requires ``settings.send=True``. Without it the browser
    runner only prepares/fills drafts, which keeps the same code path testable and safe.
    """

    agent = JobSearchAgent(
        repo=repo,
        hh_client=search_client,
        candidate_profile=candidate_profile,
        applicant_profile=applicant_profile,
    )
    search_stats = agent.run_once(
        queries=settings.queries,
        per_query=settings.per_query,
        draft_threshold=settings.draft_threshold,
    )

    capacity, daily_remaining, daily_limit_reached = _send_capacity(repo, settings)
    if capacity <= 0:
        result: dict[str, Any] = {
            "search": search_stats,
            "queued": 0,
            "prepared": 0,
            "sent": 0,
            "blocked": 0,
            "send_enabled": settings.send,
            "daily_limit": settings.daily_limit,
            "daily_remaining": daily_remaining,
            "daily_limit_reached": daily_limit_reached,
            "statuses": [],
        }
        repo.record_run_log(agent_name="hh-auto-apply", status="skipped", details=result)
        return result

    rows = repo.review_queue(min_score=settings.min_score, limit=capacity, include_demo=settings.include_demo)
    drafts = [row_to_apply_draft(row) for row in rows]
    results = apply_runner.run(drafts, send=settings.send) if drafts else []

    sent = 0
    prepared = 0
    blocked = 0
    for item in results:
        if item.status == "sent" and settings.send:
            sent += 1
            repo.record_feedback(
                vacancy_id=item.vacancy_id,
                application_id=item.application_id,
                event_type="sent",
                notes="Auto-sent via HH browser auto-apply",
            )
        elif item.status == "prepared":
            prepared += 1
        else:
            blocked += 1
            repo.record_feedback(
                vacancy_id=item.vacancy_id,
                application_id=item.application_id,
                event_type="blocked",
                notes=f"HH browser auto-apply blocked: {item.status}: {item.message}",
            )
            if item.application_id is not None:
                repo.update_application_status(item.application_id, status="blocked")

    if settings.send and settings.daily_limit is not None:
        daily_remaining = max(0, max(0, settings.daily_limit) - repo.count_sent_today())
        daily_limit_reached = daily_remaining <= 0

    result = {
        "search": search_stats,
        "queued": len(drafts),
        "prepared": prepared,
        "sent": sent,
        "blocked": blocked,
        "send_enabled": settings.send,
        "daily_limit": settings.daily_limit,
        "daily_remaining": daily_remaining,
        "daily_limit_reached": daily_limit_reached,
        "statuses": [item.status for item in results],
    }
    repo.record_run_log(agent_name="hh-auto-apply", status="ok", details=result)
    return result
