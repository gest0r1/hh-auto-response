from app.agent import JobSearchAgent
from app.repository import CRMRepository
from app.responses import ApplicantProfile, CaseStudy
from app.scoring import CandidateProfile, Vacancy


class FakeHHClient:
    def search_vacancies(self, *, text: str, per_page: int = 20, page: int = 0):
        assert text
        return [
            Vacancy(
                external_id="hh-agent-1",
                title="React Python CRM developer",
                company="AgentCo",
                description="Удалённо. CRM, Telegram bot, FastAPI, React.",
                url="https://hh.ru/vacancy/agent-1",
                salary_from=230000,
                salary_to=280000,
                currency="RUR",
                schedule="remote",
                employment="part",
                skills=["React", "Python", "FastAPI", "Telegram", "CRM"],
            )
        ]


class DuplicateTitleHHClient:
    def search_vacancies(self, *, text: str, per_page: int = 20, page: int = 0):
        assert text
        return [
            Vacancy(
                external_id="hh-dup-agent-1",
                title="AI-разработчик (Python) Junior / Middle",
                company="Social Media Holding",
                description="Удалённо. Python, AI, FastAPI.",
                url="https://hh.ru/vacancy/dup-agent-1",
                salary_from=230000,
                salary_to=300000,
                currency="RUR",
                schedule="remote",
                skills=["Python", "FastAPI", "AI"],
            ),
            Vacancy(
                external_id="hh-dup-agent-2",
                title="AI-разработчик (Python) Junior / Middle",
                company="Social Media Holding",
                description="Удалённо. Python, AI, FastAPI. Duplicate vacancyId.",
                url="https://hh.ru/vacancy/dup-agent-2",
                salary_from=230000,
                salary_to=300000,
                currency="RUR",
                schedule="remote",
                skills=["Python", "FastAPI", "AI"],
            ),
        ]


class RescoreHHClient:
    def __init__(self, vacancy: Vacancy) -> None:
        self.vacancy = vacancy

    def search_vacancies(self, *, text: str, per_page: int = 20, page: int = 0):
        assert text
        return [self.vacancy]


def test_agent_search_scores_and_creates_drafts(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    candidate = CandidateProfile(
        target_roles=["full-stack", "crm integrations"],
        skills=["React", "Python", "FastAPI", "Telegram", "CRM"],
        preferred_keywords=["удалённо", "удаленно", "контракт"],
        stop_keywords=["только офис"],
        min_monthly_salary=180000,
    )
    applicant = ApplicantProfile(
        full_name="Александр Олегович",
        headline="Full-stack / AI automation engineer",
        strengths=["делаю CRM", "подключаю Telegram и API"],
        cases=[CaseStudy(title="AI CRM", stack=["React", "FastAPI", "Telegram"], result="запустил MVP и дашборд")],
    )
    agent = JobSearchAgent(repo=repo, hh_client=FakeHHClient(), candidate_profile=candidate, applicant_profile=applicant)

    result = agent.run_once(queries=["React Python CRM"], per_query=10, draft_threshold=80)
    summary = repo.dashboard_summary()

    assert result["vacancies_seen"] == 1
    assert result["drafts_created"] == 1
    assert summary["metrics"]["vacancies_total"] == 1
    assert summary["metrics"]["drafts_total"] == 1
    cover_letter = summary["top_vacancies"][0]["cover_letter"]
    assert cover_letter.startswith("Здравствуйте!")
    assert "Здравствуйте, AgentCo" not in cover_letter
    assert "React Python CRM developer" in cover_letter


def test_agent_skips_same_company_title_duplicates_even_with_different_hh_ids(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    candidate = CandidateProfile(
        target_roles=["ai backend"],
        skills=["Python", "FastAPI", "AI"],
        preferred_keywords=["удалённо", "удаленно"],
        min_monthly_salary=180000,
    )
    applicant = ApplicantProfile(full_name="Александр Олегович")
    agent = JobSearchAgent(
        repo=repo,
        hh_client=DuplicateTitleHHClient(),
        candidate_profile=candidate,
        applicant_profile=applicant,
    )

    result = agent.run_once(queries=["AI Python"], per_query=10, draft_threshold=80)

    assert result["vacancies_seen"] == 2
    assert result["drafts_created"] == 1
    assert result["semantic_duplicates_skipped"] == 1
    assert [row["external_id"] for row in repo.review_queue(min_score=80)] == ["hh-dup-agent-1"]


def test_agent_archives_stale_draft_when_rescore_drops_below_threshold(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    candidate = CandidateProfile(
        skills=["React", "Python", "CRM"],
        preferred_keywords=["удалённо", "удаленно"],
        min_monthly_salary=180000,
    )
    applicant = ApplicantProfile(full_name="Александр Олегович")
    hot_vacancy = Vacancy(
        external_id="hh-stale-1",
        title="React Python CRM developer",
        company="AgentCo",
        description="Удалённо. CRM, Python, React.",
        url="https://hh.ru/vacancy/stale-1",
        salary_from=230000,
        salary_to=280000,
        currency="RUR",
        schedule="remote",
    )
    low_fit_vacancy = Vacancy(
        external_id="hh-stale-1",
        title="QA engineer",
        company="AgentCo",
        description="Можно удалённо. Ручное тестирование web.",
        url="https://hh.ru/vacancy/stale-1",
        salary_from=120000,
        salary_to=150000,
        currency="RUR",
        schedule="remote",
    )

    JobSearchAgent(
        repo=repo,
        hh_client=RescoreHHClient(hot_vacancy),
        candidate_profile=candidate,
        applicant_profile=applicant,
    ).run_once(queries=["React Python CRM"], per_query=10, draft_threshold=80)
    assert len(repo.review_queue(min_score=80)) == 1

    result = JobSearchAgent(
        repo=repo,
        hh_client=RescoreHHClient(low_fit_vacancy),
        candidate_profile=candidate,
        applicant_profile=applicant,
    ).run_once(queries=["React Python CRM"], per_query=10, draft_threshold=80)

    assert result["drafts_created"] == 0
    assert repo.review_queue(min_score=80) == []
    assert repo.dashboard_summary()["pipeline"]["archived"] == 1
