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


def test_record_feedback_sent_sets_sent_at_and_counts_today(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    vacancy = Vacancy(
        external_id="hh-sent-today",
        title="Python automation engineer",
        company="AgentCo",
        description="Удалённая CRM автоматизация",
        url="https://hh.ru/vacancy/sent-today",
        raw={"apply_url": "https://hh.ru/applicant/vacancy_response?vacancyId=sent-today"},
    )
    vacancy_id = repo.upsert_vacancy(vacancy, ScoreResult(score=91, decision="hot", reasons=["remote"]))
    app_id = repo.create_or_update_application(
        vacancy_id,
        cover_letter="Здравствуйте! Готов обсудить автоматизацию CRM.",
        status="draft",
        score_at_apply=91,
    )

    repo.record_feedback(vacancy_id=vacancy_id, application_id=app_id, event_type="sent", notes="auto-send")

    assert repo.dashboard_summary()["metrics"]["sent_total"] == 1
    assert repo.count_sent_today() == 1


def test_create_or_update_application_does_not_resurrect_sent_draft(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    vacancy = Vacancy(
        external_id="hh-no-resurrect",
        title="AI automation engineer",
        company="AgentCo",
        description="Удалённая AI automation вакансия",
        url="https://hh.ru/vacancy/no-resurrect",
        raw={"apply_url": "https://hh.ru/applicant/vacancy_response?vacancyId=no-resurrect"},
    )
    vacancy_id = repo.upsert_vacancy(vacancy, ScoreResult(score=91, decision="hot", reasons=["remote"]))
    app_id = repo.create_or_update_application(
        vacancy_id,
        cover_letter="Здравствуйте! Первый черновик.",
        status="draft",
        score_at_apply=91,
    )
    repo.record_feedback(vacancy_id=vacancy_id, application_id=app_id, event_type="sent", notes="manual send")

    same_app_id = repo.create_or_update_application(
        vacancy_id,
        cover_letter="Здравствуйте! Новый черновик после повторного поиска.",
        status="draft",
        score_at_apply=91,
    )

    assert same_app_id == app_id
    assert repo.review_queue(min_score=80) == []
    summary = repo.dashboard_summary()
    assert summary["metrics"]["sent_total"] == 1
    assert summary["top_vacancies"][0]["application_status"] == "sent"
    assert "Первый черновик" in summary["top_vacancies"][0]["cover_letter"]


def test_repository_review_queue_hides_semantic_duplicate_drafts(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    first_id = repo.upsert_vacancy(
        Vacancy(
            external_id="hh-dup-1",
            title="AI-разработчик (Python) Junior / Middle",
            company="Social Media Holding",
            description="Python AI",
            url="https://hh.ru/vacancy/dup-1",
        ),
        ScoreResult(score=91, decision="hot", reasons=["python"]),
    )
    second_id = repo.upsert_vacancy(
        Vacancy(
            external_id="hh-dup-2",
            title="AI-разработчик (Python) Junior / Middle",
            company="Social Media Holding",
            description="Python AI duplicate",
            url="https://hh.ru/vacancy/dup-2",
        ),
        ScoreResult(score=90, decision="hot", reasons=["python"]),
    )
    repo.create_or_update_application(first_id, cover_letter="Здравствуйте! 1", status="draft", score_at_apply=91)
    repo.create_or_update_application(second_id, cover_letter="Здравствуйте! 2", status="draft", score_at_apply=90)

    queue = repo.review_queue(min_score=80, limit=10)

    assert len(queue) == 1
    assert queue[0]["external_id"] == "hh-dup-1"


def test_repository_review_queue_duplicate_filtering_does_not_starve_later_valid_rows(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    first_id = repo.upsert_vacancy(
        Vacancy(
            external_id="hh-starve-dup-1",
            title="Python Backend Engineer",
            company="DuplicateCo",
            description="Python backend",
            url="https://hh.ru/vacancy/starve-dup-1",
        ),
        ScoreResult(score=100, decision="hot", reasons=["python"]),
    )
    second_id = repo.upsert_vacancy(
        Vacancy(
            external_id="hh-starve-dup-2",
            title="Python Backend Engineer",
            company="DuplicateCo",
            description="Python backend duplicate",
            url="https://hh.ru/vacancy/starve-dup-2",
        ),
        ScoreResult(score=99, decision="hot", reasons=["python"]),
    )
    valid_id = repo.upsert_vacancy(
        Vacancy(
            external_id="hh-starve-valid",
            title="FastAPI Platform Engineer",
            company="ValidCo",
            description="FastAPI backend",
            url="https://hh.ru/vacancy/starve-valid",
        ),
        ScoreResult(score=98, decision="hot", reasons=["fastapi"]),
    )
    repo.create_or_update_application(first_id, cover_letter="Здравствуйте! 1", status="draft", score_at_apply=100)
    repo.create_or_update_application(second_id, cover_letter="Здравствуйте! 2", status="draft", score_at_apply=99)
    repo.create_or_update_application(valid_id, cover_letter="Здравствуйте! 3", status="draft", score_at_apply=98)

    queue = repo.review_queue(min_score=80, limit=2)

    assert [row["external_id"] for row in queue] == ["hh-starve-dup-1", "hh-starve-valid"]


def test_repository_review_queue_hides_draft_when_same_company_title_was_sent(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    sent_id = repo.upsert_vacancy(
        Vacancy(
            external_id="hh-dup-sent-1",
            title="Full-Stack разработчик",
            company="Kahrs Logistic and Sales LLC",
            description="Fullstack",
            url="https://hh.ru/vacancy/dup-sent-1",
        ),
        ScoreResult(score=91, decision="hot", reasons=["fullstack"]),
    )
    draft_id = repo.upsert_vacancy(
        Vacancy(
            external_id="hh-dup-sent-2",
            title="Full-Stack разработчик",
            company="Kahrs Logistic and Sales LLC",
            description="Fullstack duplicate",
            url="https://hh.ru/vacancy/dup-sent-2",
        ),
        ScoreResult(score=90, decision="hot", reasons=["fullstack"]),
    )
    repo.create_or_update_application(sent_id, cover_letter="Здравствуйте!", status="sent", score_at_apply=91)
    repo.create_or_update_application(draft_id, cover_letter="Здравствуйте!", status="draft", score_at_apply=90)

    assert repo.has_company_title_application(
        company="Kahrs Logistic and Sales LLC",
        title="Full-Stack разработчик",
        exclude_vacancy_id=draft_id,
    ) is True
    assert repo.review_queue(min_score=80, limit=10) == []


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


def test_repository_review_queue_excludes_maybe_and_archive_decisions_by_default(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")

    hot_id = repo.upsert_vacancy(
        Vacancy(
            external_id="hh-hot-fit",
            title="AI Agent Systems Engineer",
            company="AgentCo",
            description="LLM platform and AgentOps",
            url="https://hh.ru/vacancy/hot-fit",
        ),
        ScoreResult(score=91, decision="hot", reasons=["agentops"]),
    )
    repo.create_or_update_application(hot_id, cover_letter="Здравствуйте!", status="draft", score_at_apply=91)

    maybe_id = repo.upsert_vacancy(
        Vacancy(
            external_id="hh-maybe-wide",
            title="Generic Fullstack Developer",
            company="WideCo",
            description="React and backend tasks",
            url="https://hh.ru/vacancy/maybe-wide",
        ),
        ScoreResult(score=67, decision="maybe", reasons=["generic"]),
    )
    repo.create_or_update_application(maybe_id, cover_letter="Здравствуйте!", status="draft", score_at_apply=67)

    archive_id = repo.upsert_vacancy(
        Vacancy(
            external_id="hh-archive-old-draft",
            title="Frontend internship",
            company="ArchiveCo",
            description="Junior frontend role",
            url="https://hh.ru/vacancy/archive-old-draft",
        ),
        ScoreResult(score=60, decision="archive", reasons=["old draft downgraded"]),
    )
    repo.create_or_update_application(archive_id, cover_letter="Здравствуйте!", status="draft", score_at_apply=60)

    default_queue = repo.review_queue(min_score=45, limit=10)
    permissive_queue = repo.review_queue(min_score=45, limit=10, decisions=("hot", "review", "maybe", "archive"))

    assert [row["external_id"] for row in default_queue] == ["hh-hot-fit"]
    assert {row["external_id"] for row in permissive_queue} == {
        "hh-hot-fit",
        "hh-maybe-wide",
        "hh-archive-old-draft",
    }
