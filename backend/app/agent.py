from __future__ import annotations

from typing import Protocol

from app.learning import LearningEngine
from app.repository import CRMRepository
from app.responses import ApplicantProfile, generate_cover_letter, ResponseContext
from app.scoring import CandidateProfile, Vacancy, score_vacancy


class SearchClient(Protocol):
    def search_vacancies(self, *, text: str, per_page: int = 20, page: int = 0) -> list[Vacancy]: ...


class JobSearchAgent:
    def __init__(
        self,
        *,
        repo: CRMRepository,
        hh_client: SearchClient,
        candidate_profile: CandidateProfile,
        applicant_profile: ApplicantProfile,
        company_guard: str = "strict",
    ) -> None:
        self.repo = repo
        self.hh_client = hh_client
        self.candidate_profile = candidate_profile
        self.applicant_profile = applicant_profile
        self.company_guard = company_guard

    def run_once(
        self,
        *,
        queries: list[str],
        per_query: int = 20,
        pages: int = 1,
        draft_threshold: int = 80,
        resume_id: str | None = None,
    ) -> dict[str, int | list[str]]:
        seen: set[str] = set()
        stats = {
            "queries": len(queries),
            "pages": max(1, pages),
            "vacancies_seen": 0,
            "vacancies_saved": 0,
            "drafts_created": 0,
            "drafts_archived": 0,
            "quality_failed": 0,
            "duplicates_skipped": 0,
            "semantic_duplicates_skipped": 0,
            "company_duplicates_skipped": 0,
            "quality_issues": [],
            "errors": [],
        }
        learning_weights = self.repo.get_learning_weights()
        if learning_weights:
            self.candidate_profile.learning_weights = learning_weights

        for query in queries:
            for page in range(max(1, pages)):
                try:
                    vacancies = self.hh_client.search_vacancies(text=query, per_page=per_query, page=page)
                except Exception as exc:  # pragma: no cover - exercised in live smoke, not unit tests
                    stats["errors"].append(f"{query} page {page}: {exc}")
                    continue
                if not vacancies:
                    continue
                for vacancy in vacancies:
                    if vacancy.external_id in seen:
                        stats["duplicates_skipped"] += 1
                        continue
                    seen.add(vacancy.external_id)
                    stats["vacancies_seen"] += 1
                    score = score_vacancy(vacancy, self.candidate_profile)
                    vacancy_id = self.repo.upsert_vacancy(vacancy, score)
                    stats["vacancies_saved"] += 1
                    if score.score >= draft_threshold and score.decision in {"hot", "review", "maybe"}:
                        if self.repo.has_company_title_application(
                            company=vacancy.company,
                            title=vacancy.title,
                            exclude_vacancy_id=vacancy_id,
                        ):
                            stats["semantic_duplicates_skipped"] += 1
                            stats["drafts_archived"] += self.repo.archive_draft_application(vacancy_id)
                            continue
                        if self.repo.has_company_application(
                            company=vacancy.company,
                            exclude_vacancy_id=vacancy_id,
                            guard_mode=self.company_guard,
                        ):
                            stats["company_duplicates_skipped"] += 1
                            stats["drafts_archived"] += self.repo.archive_draft_application(vacancy_id)
                            continue
                        generated = generate_cover_letter(
                            ResponseContext(profile=self.applicant_profile, vacancy=vacancy, score=score.score)
                        )
                        if generated.risk_flags:
                            stats["quality_failed"] += 1
                            stats["drafts_archived"] += self.repo.archive_draft_application(vacancy_id)
                            stats["quality_issues"].append(
                                f"{vacancy.external_id}: {', '.join(generated.risk_flags)}"
                            )
                            continue
                        application_id = self.repo.create_or_update_application(
                            vacancy_id,
                            cover_letter=generated.message,
                            status="draft",
                            resume_id=resume_id,
                            score_at_apply=score.score,
                        )
                        application = self.repo.application_review_item(application_id)
                        if application and application.get("application_status") == "draft":
                            stats["drafts_created"] += 1
                    else:
                        stats["drafts_archived"] += self.repo.archive_draft_application(vacancy_id)
        return stats

    def learn_from_feedback(
        self,
        *,
        event_type: str,
        vacancy_keywords: list[str],
        rating: int | None = None,
        notes: str | None = None,
        edited_cover_letter: str | None = None,
    ) -> dict[str, float]:
        engine = LearningEngine(initial_weights=self.repo.get_learning_weights())
        update = engine.learn_from_feedback(
            event_type=event_type,
            vacancy_keywords=vacancy_keywords,
            rating=rating,
            notes=notes,
            edited_cover_letter=edited_cover_letter,
        )
        positive = event_type in {"approved", "sent", "reply", "interview", "offer"}
        negative = event_type in {"rejected", "archived", "discard", "not_interested"}
        for key, weight in update.weights.items():
            self.repo.update_learning_signal(key, weight, positive=True if positive else False if negative else None)
        return update.weights
