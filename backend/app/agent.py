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
    ) -> None:
        self.repo = repo
        self.hh_client = hh_client
        self.candidate_profile = candidate_profile
        self.applicant_profile = applicant_profile

    def run_once(
        self,
        *,
        queries: list[str],
        per_query: int = 20,
        draft_threshold: int = 80,
    ) -> dict[str, int | list[str]]:
        seen: set[str] = set()
        stats = {
            "queries": len(queries),
            "vacancies_seen": 0,
            "vacancies_saved": 0,
            "drafts_created": 0,
            "drafts_archived": 0,
            "duplicates_skipped": 0,
            "semantic_duplicates_skipped": 0,
            "errors": [],
        }
        learning_weights = self.repo.get_learning_weights()
        if learning_weights:
            self.candidate_profile.learning_weights = learning_weights

        for query in queries:
            try:
                vacancies = self.hh_client.search_vacancies(text=query, per_page=per_query, page=0)
            except Exception as exc:  # pragma: no cover - exercised in live smoke, not unit tests
                stats["errors"].append(f"{query}: {exc}")
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
                    generated = generate_cover_letter(
                        ResponseContext(profile=self.applicant_profile, vacancy=vacancy, score=score.score)
                    )
                    self.repo.create_or_update_application(
                        vacancy_id,
                        cover_letter=generated.message,
                        status="draft",
                        score_at_apply=score.score,
                    )
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
