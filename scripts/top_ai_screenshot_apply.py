# pyright: reportMissingImports=false
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.auto_apply import _quality_checked_drafts  # noqa: E402
from app.config import default_applicant_profile, default_candidate_profile, get_settings  # noqa: E402
from app.db import initialize_database  # noqa: E402
from app.hh_browser import HHWebApplyRunner  # noqa: E402
from app.hh_vacancy import HHPublicVacancyClient  # noqa: E402
from app.repository import CRMRepository  # noqa: E402
from app.responses import ResponseContext, check_cover_letter_quality, generate_cover_letter  # noqa: E402
from app.scoring import score_vacancy  # noqa: E402

# Exact vacancies visible on Aleksandr's HH screenshots, resolved via public HH search.
TARGETS = [
    {"id": "133542116", "label": "Mad Devs: Middle AI Engineer (Fullstack)"},
    {"id": "133513192", "label": "Буров: AI Product CTO / Technical Co-founder"},
    {"id": "133536184", "label": "ВЛАДТРЕК: AI Solution Architect / Архитектор AI-автоматизации"},
    {"id": "133490153", "label": "Double-B Robotics: Full-stack разработчик AI агентов"},
    {"id": "133546154", "label": "Яндекс: Архитектор AI"},
]
MIN_SCORE = 80


def main() -> None:
    settings = get_settings()
    initialize_database(settings.db_path)
    repo = CRMRepository(settings.db_path)
    candidate = default_candidate_profile(repo.get_learning_weights())
    applicant = default_applicant_profile()
    vacancy_client = HHPublicVacancyClient(user_agent=settings.hh_user_agent)

    sent_today_before = repo.count_sent_today()
    daily_limit = 5
    daily_remaining = max(0, daily_limit - sent_today_before)

    prepared_rows = []
    target_results = []

    for target in TARGETS:
        item = {"target": target, "status": "new"}
        try:
            vacancy = vacancy_client.fetch_vacancy(f"https://hh.ru/vacancy/{target['id']}")
            score = score_vacancy(vacancy, candidate)
            vacancy_id = repo.upsert_vacancy(vacancy, score)
            item.update(
                {
                    "external_id": vacancy.external_id,
                    "title": vacancy.title,
                    "company": vacancy.company,
                    "score": score.score,
                    "decision": score.decision,
                    "url": vacancy.url,
                }
            )
            if score.score < MIN_SCORE or score.decision not in {"hot", "review", "maybe"}:
                item["status"] = "skipped_low_score"
                target_results.append(item)
                continue
            if repo.has_company_title_application(
                company=vacancy.company,
                title=vacancy.title,
                exclude_vacancy_id=vacancy_id,
            ):
                item["status"] = "skipped_company_title_duplicate"
                target_results.append(item)
                continue
            if repo.has_company_application(company=vacancy.company, exclude_vacancy_id=vacancy_id):
                item["status"] = "skipped_company_duplicate"
                target_results.append(item)
                continue
            generated = generate_cover_letter(ResponseContext(profile=applicant, vacancy=vacancy, score=score.score))
            if generated.risk_flags:
                item["status"] = "skipped_generation_quality"
                item["issues"] = generated.risk_flags
                target_results.append(item)
                continue
            quality = check_cover_letter_quality(
                generated.message,
                ResponseContext(profile=applicant, vacancy=vacancy, score=score.score),
            )
            if not quality.passed:
                item["status"] = "skipped_cover_quality"
                item["issues"] = quality.issues
                target_results.append(item)
                continue
            application_id = repo.create_or_update_application(
                vacancy_id,
                cover_letter=generated.message,
                status="draft",
                score_at_apply=score.score,
            )
            row = repo.application_review_item(application_id)
            if row:
                prepared_rows.append(row)
                item["status"] = "queued"
                item["application_id"] = application_id
            else:
                item["status"] = "queued_but_row_missing"
            target_results.append(item)
        except Exception as exc:  # live helper should report per-vacancy, not abort the batch
            item["status"] = "error"
            item["error"] = str(exc)
            target_results.append(item)

    rows_to_send = prepared_rows[:daily_remaining]
    drafts, quality_issues = _quality_checked_drafts(repo=repo, rows=rows_to_send, applicant_profile=applicant)

    browser_results = []
    if drafts and daily_remaining > 0:
        runner = HHWebApplyRunner.launch(user_data_dir=settings.hh_browser_user_data_dir, headless=True)
        try:
            browser_results = runner.run(drafts, send=True)
        finally:
            runner.close()

    sent = 0
    blocked = 0
    for result in browser_results:
        if result.status == "sent":
            sent += 1
            repo.record_feedback(
                vacancy_id=result.vacancy_id,
                application_id=result.application_id,
                event_type="sent",
                notes="Targeted top-AI screenshot apply",
            )
        else:
            blocked += 1
            repo.record_feedback(
                vacancy_id=result.vacancy_id,
                application_id=result.application_id,
                event_type="blocked",
                notes=f"Targeted top-AI apply blocked: {result.status}: {result.message}",
            )
            if result.application_id is not None:
                repo.update_application_status(result.application_id, status="blocked")

    summary = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "sent_today_before": sent_today_before,
        "daily_limit": daily_limit,
        "daily_remaining_before": daily_remaining,
        "targets": target_results,
        "queued": len(prepared_rows),
        "attempted": len(drafts),
        "sent": sent,
        "blocked": blocked,
        "quality_skipped_after_queue": len(quality_issues),
        "quality_issues_after_queue": quality_issues,
        "browser_statuses": [
            {
                "application_id": r.application_id,
                "vacancy_id": r.vacancy_id,
                "status": r.status,
                "message": r.message,
                "url": r.url,
            }
            for r in browser_results
        ],
        "sent_today_after": repo.count_sent_today(),
    }

    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"hh_top_ai_screenshot_apply_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    log_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["log_path"] = str(log_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
