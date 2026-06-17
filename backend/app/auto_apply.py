from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.agent import JobSearchAgent, SearchClient
from app.hh_browser import BrowserApplyResult, row_to_apply_draft
from app.repository import CRMRepository
from app.responses import ApplicantProfile, ResponseContext, check_cover_letter_quality
from app.scoring import CandidateProfile, Vacancy


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
    company_guard: str = "strict"


def _send_capacity(repo: CRMRepository, settings: AutoApplySettings) -> tuple[int, int | None, bool]:
    limit = max(0, settings.limit)
    if not settings.send or settings.daily_limit is None:
        return limit, None, False

    daily_limit = max(0, settings.daily_limit)
    sent_today = repo.count_sent_today()
    remaining = max(0, daily_limit - sent_today)
    return min(limit, remaining), remaining, remaining <= 0


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _review_row_score(row: dict[str, Any]) -> int:
    return _optional_int(row.get("score_at_apply")) or _optional_int(row.get("score")) or 0


def _vacancy_from_review_row(row: dict[str, Any]) -> Vacancy:
    raw = row.get("raw")
    skills = row.get("skills")
    return Vacancy(
        external_id=str(row.get("external_id") or ""),
        title=str(row.get("title") or ""),
        company=str(row.get("company") or ""),
        description=str(row.get("description") or ""),
        url=str(row.get("url") or ""),
        salary_from=_optional_int(row.get("salary_from")),
        salary_to=_optional_int(row.get("salary_to")),
        currency=str(row["currency"]) if row.get("currency") is not None else None,
        schedule=str(row["schedule"]) if row.get("schedule") is not None else None,
        employment=str(row["employment"]) if row.get("employment") is not None else None,
        skills=[str(skill) for skill in skills] if isinstance(skills, list) else [],
        raw=raw if isinstance(raw, dict) else {},
    )


def _archive_quality_failed_draft(
    repo: CRMRepository,
    *,
    row: dict[str, Any],
    issues: list[str],
) -> None:
    vacancy_id = _optional_int(row.get("id"))
    application_id = _optional_int(row.get("application_id"))
    notes = "HH browser auto-apply quality gate archived stale draft: " + ", ".join(issues)
    if application_id is not None:
        repo.record_feedback(
            vacancy_id=vacancy_id,
            application_id=application_id,
            event_type="archived",
            notes=notes,
        )
    elif vacancy_id is not None:
        repo.archive_draft_application(vacancy_id)


def _quality_checked_drafts(
    *,
    repo: CRMRepository,
    rows: list[dict[str, Any]],
    applicant_profile: ApplicantProfile,
) -> tuple[list[Any], list[dict[str, Any]]]:
    drafts: list[Any] = []
    quality_issues: list[dict[str, Any]] = []
    for row in rows:
        vacancy = _vacancy_from_review_row(row)
        quality = check_cover_letter_quality(
            str(row.get("cover_letter") or ""),
            ResponseContext(profile=applicant_profile, vacancy=vacancy, score=_review_row_score(row)),
        )
        if not quality.passed:
            issues = list(quality.issues)
            _archive_quality_failed_draft(repo, row=row, issues=issues)
            quality_issues.append(
                {
                    "external_id": vacancy.external_id,
                    "application_id": _optional_int(row.get("application_id")),
                    "vacancy_id": _optional_int(row.get("id")),
                    "issues": issues,
                }
            )
            continue
        drafts.append(row_to_apply_draft(row))
    return drafts, quality_issues


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
        company_guard=settings.company_guard,
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
            "queue_candidates": 0,
            "prepared": 0,
            "sent": 0,
            "blocked": 0,
            "quality_skipped": 0,
            "quality_issues": [],
            "send_enabled": settings.send,
            "daily_limit": settings.daily_limit,
            "daily_remaining": daily_remaining,
            "daily_limit_reached": daily_limit_reached,
            "statuses": [],
        }
        repo.record_run_log(agent_name="hh-auto-apply", status="skipped", details=result)
        return result

    rows = repo.review_queue(
        min_score=settings.min_score,
        limit=capacity,
        include_demo=settings.include_demo,
        company_guard=settings.company_guard,
    )
    drafts, quality_issues = _quality_checked_drafts(
        repo=repo,
        rows=rows,
        applicant_profile=applicant_profile,
    )
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
        "queue_candidates": len(rows),
        "prepared": prepared,
        "sent": sent,
        "blocked": blocked,
        "quality_skipped": len(quality_issues),
        "quality_issues": quality_issues,
        "send_enabled": settings.send,
        "daily_limit": settings.daily_limit,
        "daily_remaining": daily_remaining,
        "daily_limit_reached": daily_limit_reached,
        "statuses": [item.status for item in results],
    }
    repo.record_run_log(agent_name="hh-auto-apply", status="ok", details=result)
    return result
