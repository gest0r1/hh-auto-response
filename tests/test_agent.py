from app.agent import JobSearchAgent
from app.repository import CRMRepository
from app.responses import ApplicantProfile, CaseStudy, GeneratedResponse
from app.scoring import CandidateProfile, ScoreResult, Vacancy


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


class SameEmployerFamilyHHClient:
    def search_vacancies(self, *, text: str, per_page: int = 20, page: int = 0):
        assert text
        return [
            Vacancy(
                external_id="hh-sber-family-1",
                title="Python Backend Engineer",
                company="Сбер. IT",
                description="Удалённо. Python backend, LLM platform, FastAPI.",
                url="https://hh.ru/vacancy/sber-family-1",
                salary_from=230000,
                salary_to=300000,
                currency="RUR",
                schedule="remote",
                skills=["Python", "FastAPI", "LLM"],
            ),
            Vacancy(
                external_id="hh-sber-family-2",
                title="Lead AI Engineer",
                company="Сбер. Data Science",
                description="Удалённо. Python, AI, LLM platform, FastAPI.",
                url="https://hh.ru/vacancy/sber-family-2",
                salary_from=230000,
                salary_to=300000,
                currency="RUR",
                schedule="remote",
                skills=["Python", "FastAPI", "LLM", "AI"],
            ),
        ]


class SameOrdinaryEmployerDifferentTitlesHHClient:
    def search_vacancies(self, *, text: str, per_page: int = 20, page: int = 0):
        assert text
        return [
            Vacancy(
                external_id="hh-agentco-family-1",
                title="Python Backend Engineer",
                company="AgentCo",
                description="Удалённо. Python backend, FastAPI.",
                url="https://hh.ru/vacancy/agentco-family-1",
                salary_from=230000,
                salary_to=300000,
                currency="RUR",
                schedule="remote",
                skills=["Python", "FastAPI"],
            ),
            Vacancy(
                external_id="hh-agentco-family-2",
                title="LLM Platform Engineer",
                company="AgentCo",
                description="Удалённо. Python, AI, LLM platform, FastAPI.",
                url="https://hh.ru/vacancy/agentco-family-2",
                salary_from=230000,
                salary_to=300000,
                currency="RUR",
                schedule="remote",
                skills=["Python", "FastAPI", "LLM", "AI"],
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
    assert "Увидел вакансию" not in cover_letter
    assert "CRM/Telegram-интеграции" in cover_letter
    assert "API" in cover_letter


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


def test_agent_skips_same_employer_family_to_avoid_repeated_company_spam(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    candidate = CandidateProfile(
        target_roles=["mlops", "ai engineer"],
        skills=["Python", "FastAPI", "LLM", "AI"],
        preferred_keywords=["удалённо", "удаленно"],
        min_monthly_salary=180000,
    )
    applicant = ApplicantProfile(full_name="Александр Олегович")
    agent = JobSearchAgent(
        repo=repo,
        hh_client=SameEmployerFamilyHHClient(),
        candidate_profile=candidate,
        applicant_profile=applicant,
    )

    result = agent.run_once(queries=["Sber AI Python"], per_query=10, draft_threshold=80)

    assert result["vacancies_seen"] == 2
    assert result["drafts_created"] == 1
    assert result["company_duplicates_skipped"] == 1
    assert len(repo.review_queue(min_score=80)) == 1


def test_agent_family_company_guard_keeps_sber_guard_but_allows_ordinary_company_titles(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    candidate = CandidateProfile(
        target_roles=["python backend", "llm platform"],
        skills=["Python", "FastAPI", "LLM", "AI"],
        preferred_keywords=["удалённо", "удаленно"],
        min_monthly_salary=180000,
    )
    applicant = ApplicantProfile(full_name="Александр Олегович")

    ordinary_result = JobSearchAgent(
        repo=repo,
        hh_client=SameOrdinaryEmployerDifferentTitlesHHClient(),
        candidate_profile=candidate,
        applicant_profile=applicant,
        company_guard="family",
    ).run_once(queries=["AgentCo AI Python"], per_query=10, draft_threshold=80)

    assert ordinary_result["vacancies_seen"] == 2
    assert ordinary_result["drafts_created"] == 2
    assert ordinary_result["company_duplicates_skipped"] == 0
    assert [row["external_id"] for row in repo.review_queue(min_score=80, company_guard="family")] == [
        "hh-agentco-family-2",
        "hh-agentco-family-1",
    ]

    sber_repo = CRMRepository(tmp_path / "sber-crm.sqlite3")
    sber_result = JobSearchAgent(
        repo=sber_repo,
        hh_client=SameEmployerFamilyHHClient(),
        candidate_profile=candidate,
        applicant_profile=applicant,
        company_guard="family",
    ).run_once(queries=["Sber AI Python"], per_query=10, draft_threshold=80)

    assert sber_result["vacancies_seen"] == 2
    assert sber_result["drafts_created"] == 1
    assert sber_result["company_duplicates_skipped"] == 1


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


def test_agent_archives_existing_draft_when_generated_cover_letter_fails_quality(tmp_path, monkeypatch):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    candidate = CandidateProfile(
        skills=["React", "Python", "FastAPI", "Telegram", "CRM"],
        preferred_keywords=["удалённо", "удаленно"],
        min_monthly_salary=180000,
    )
    applicant = ApplicantProfile(full_name="Александр Олегович")
    vacancy = Vacancy(
        external_id="hh-quality-fail",
        title="React Python CRM developer",
        company="AgentCo",
        description="Удалённо. CRM, Telegram bot, FastAPI, React.",
        url="https://hh.ru/vacancy/quality-fail",
        salary_from=230000,
        salary_to=280000,
        currency="RUR",
        schedule="remote",
        skills=["React", "Python", "FastAPI", "Telegram", "CRM"],
    )
    vacancy_id = repo.upsert_vacancy(vacancy, ScoreResult(score=91, decision="hot"))
    repo.create_or_update_application(
        vacancy_id,
        cover_letter="Здравствуйте! Старый черновик.",
        status="draft",
        score_at_apply=91,
    )

    def fake_generate_cover_letter(context):
        return GeneratedResponse(
            message="Здравствуйте! Шаблонный текст.",
            tone="direct_business",
            estimated_fit=context.score,
            risk_flags=["generic_repeated_template"],
        )

    monkeypatch.setattr("app.agent.generate_cover_letter", fake_generate_cover_letter)
    agent = JobSearchAgent(
        repo=repo,
        hh_client=RescoreHHClient(vacancy),
        candidate_profile=candidate,
        applicant_profile=applicant,
    )

    result = agent.run_once(queries=["React Python CRM"], per_query=10, draft_threshold=80)

    assert result["drafts_created"] == 0
    assert result["quality_failed"] == 1
    assert result["drafts_archived"] == 1
    assert result["quality_issues"] == ["hh-quality-fail: generic_repeated_template"]
    assert repo.review_queue(min_score=80) == []
    assert repo.dashboard_summary()["pipeline"]["archived"] == 1
