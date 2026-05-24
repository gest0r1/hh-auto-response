from app.db import initialize_database
from app.repository import CRMRepository
from app.scoring import ScoreResult, Vacancy


def test_repository_upserts_vacancies_and_builds_dashboard_summary(tmp_path):
    db_path = tmp_path / "crm.sqlite3"
    initialize_database(db_path)
    repo = CRMRepository(db_path)
    vacancy = Vacancy(
        external_id="hh-42",
        title="Full-stack React Python",
        company="Acme",
        description="Remote CRM project",
        url="https://hh.ru/vacancy/42",
        salary_from=200000,
        salary_to=260000,
        currency="RUR",
        schedule="remote",
        employment="part",
        skills=["React", "Python", "CRM"],
    )
    score = ScoreResult(score=88, decision="hot", reasons=["skill match: React", "remote"] )

    first_id = repo.upsert_vacancy(vacancy, score)
    second_id = repo.upsert_vacancy(vacancy, score)
    app_id = repo.create_or_update_application(first_id, cover_letter="Здравствуйте!", status="draft")
    repo.record_feedback(vacancy_id=first_id, application_id=app_id, event_type="approved", rating=5, notes="Ок")

    summary = repo.dashboard_summary()

    assert first_id == second_id
    assert summary["metrics"]["vacancies_total"] == 1
    assert summary["metrics"]["drafts_total"] == 1
    assert summary["pipeline"]["draft"] == 1
    assert summary["top_vacancies"][0]["score"] == 88
    assert summary["feedback_recent"][0]["event_type"] == "approved"


def test_dashboard_summary_exposes_no_api_apply_url(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    vacancy = Vacancy(
        external_id="hh-778",
        title="Python automation engineer",
        company="AgentCo",
        description="Удалённая CRM автоматизация",
        url="https://hh.ru/vacancy/778",
        raw={"apply_url": "https://hh.ru/applicant/vacancy_response?vacancyId=778"},
    )
    vacancy_id = repo.upsert_vacancy(vacancy, ScoreResult(score=89, decision="hot", reasons=["remote"]))
    repo.create_or_update_application(vacancy_id, cover_letter="Здравствуйте!", status="draft", score_at_apply=89)

    summary = repo.dashboard_summary()

    assert summary["top_vacancies"][0]["apply_url"] == "https://hh.ru/applicant/vacancy_response?vacancyId=778"


def test_repository_review_queue_excludes_demo_drafts_by_default(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    demo_vacancy = Vacancy(
        external_id="demo-hh-1",
        title="Demo vacancy",
        company="Demo",
        description="Удалённая демо-вакансия",
        url="https://hh.ru/vacancy/demo-1",
        raw={"apply_url": "https://hh.ru/vacancy/demo-1"},
    )
    demo_id = repo.upsert_vacancy(demo_vacancy, ScoreResult(score=99, decision="hot", reasons=["demo"]))
    repo.create_or_update_application(demo_id, cover_letter="Демо", status="draft", score_at_apply=99)

    real_vacancy = Vacancy(
        external_id="hh-777",
        title="Python React automation engineer",
        company="AgentCo",
        description="Удалённый проект по CRM и автоматизации",
        url="https://hh.ru/vacancy/777",
        raw={"apply_url": "https://hh.ru/applicant/vacancy_response?vacancyId=777"},
    )
    real_id = repo.upsert_vacancy(real_vacancy, ScoreResult(score=91, decision="hot", reasons=["remote"]))
    repo.create_or_update_application(real_id, cover_letter="Здравствуйте!", status="draft", score_at_apply=91)

    queue = repo.review_queue(min_score=80, limit=5)

    assert [row["external_id"] for row in queue] == ["hh-777"]


def test_repository_review_queue_can_include_demo_drafts_when_requested(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    demo_vacancy = Vacancy(
        external_id="demo-hh-1",
        title="Demo vacancy",
        company="Demo",
        description="Удалённая демо-вакансия",
        url="https://hh.ru/vacancy/demo-1",
        raw={"apply_url": "https://hh.ru/vacancy/demo-1"},
    )
    demo_id = repo.upsert_vacancy(demo_vacancy, ScoreResult(score=99, decision="hot", reasons=["demo"]))
    repo.create_or_update_application(demo_id, cover_letter="Демо", status="draft", score_at_apply=99)

    queue = repo.review_queue(min_score=80, limit=5, include_demo=True)

    assert [row["external_id"] for row in queue] == ["demo-hh-1"]


def test_repository_sanitizes_legacy_employer_greeting_in_review_queue(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    vacancy = Vacancy(
        external_id="hh-ip-legacy",
        title="Python AI Engineer",
        company="ИП Москвина Наталья Александровна",
        description="Удалённый проект по LLM и browser automation",
        url="https://hh.ru/vacancy/ip-legacy",
        raw={"apply_url": "https://hh.ru/applicant/vacancy_response?vacancyId=ip-legacy"},
    )
    vacancy_id = repo.upsert_vacancy(vacancy, ScoreResult(score=91, decision="hot", reasons=["remote"]))
    app_id = repo.create_or_update_application(
        vacancy_id,
        cover_letter=(
            "Здравствуйте, ИП Москвина Наталья Александровна! "
            "Увидел вакансию «Python AI Engineer». По описанию это мой профиль."
        ),
        status="draft",
        score_at_apply=91,
    )

    queue_item = repo.review_queue(min_score=80, limit=5)[0]
    direct_item = repo.application_review_item(app_id)

    assert queue_item["cover_letter"].startswith("Здравствуйте! Увидел вакансию")
    assert "Здравствуйте, ИП" not in queue_item["cover_letter"]
    assert "ИП Москвина" not in queue_item["cover_letter"]
    assert direct_item is not None
    assert direct_item["cover_letter"] == queue_item["cover_letter"]


def test_repository_review_queue_includes_draft_and_no_api_apply_url(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    vacancy = Vacancy(
        external_id="hh-777",
        title="Python React automation engineer",
        company="AgentCo",
        description="Удалённый проект по CRM и автоматизации",
        url="https://hh.ru/vacancy/777",
        salary_from=250000,
        salary_to=320000,
        currency="RUR",
        schedule="remote",
        skills=["Python", "React", "CRM"],
        raw={"apply_url": "https://hh.ru/applicant/vacancy_response?vacancyId=777"},
    )
    vacancy_id = repo.upsert_vacancy(vacancy, ScoreResult(score=91, decision="hot", reasons=["remote"]))
    repo.create_or_update_application(
        vacancy_id,
        cover_letter="Здравствуйте! Готов обсудить автоматизацию CRM.",
        status="draft",
        score_at_apply=91,
    )

    queue = repo.review_queue(min_score=80, limit=5)

    assert len(queue) == 1
    assert queue[0]["title"] == "Python React automation engineer"
    assert queue[0]["application_status"] == "draft"
    assert queue[0]["apply_url"] == "https://hh.ru/applicant/vacancy_response?vacancyId=777"
    assert "Готов обсудить" in queue[0]["cover_letter"]
