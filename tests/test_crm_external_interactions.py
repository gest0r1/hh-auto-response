from app.repository import CRMRepository
from app.scoring import ScoreResult, Vacancy


def _create_application(repo: CRMRepository, *, resume_id: str = "resume-300k") -> int:
    vacancy_id = repo.upsert_vacancy(
        Vacancy(
            external_id="hh-134258608",
            title="Python Developer (AD Robot)",
            company="Интерактивное агентство Это Легко",
            description="Python, AI, AD Robot",
            url="https://hh.ru/vacancy/134258608",
            skills=["Python", "LLM"],
            raw={"apply_url": "https://hh.ru/applicant/vacancy_response?vacancyId=134258608"},
        ),
        ScoreResult(score=100, decision="hot", reasons=["python"], penalties=[]),
    )
    return repo.create_or_update_application(
        vacancy_id,
        cover_letter="Здравствуйте!",
        status="sent",
        resume_id=resume_id,
        score_at_apply=100,
    )


def test_external_interaction_records_application_resume_and_payload(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    application_id = _create_application(repo, resume_id="resume-300k")

    interaction_id = repo.record_external_interaction(
        application_id=application_id,
        kind="google_form",
        target_url="https://forms.gle/PYbfwCLBmnnje6iBA",
        status="dry_run_prepared",
        payload={
            "answers": {
                "resume": "https://hh.ru/resume/resume-300k",
                "grade": "Middle",
            },
            "required_fields": 21,
        },
        notes="Prepared form from CRM application row, not inferred from form grade.",
    )

    rows = repo.list_external_interactions(application_id=application_id)

    assert interaction_id > 0
    assert len(rows) == 1
    assert rows[0]["application_id"] == application_id
    assert rows[0]["vacancy_id"] is not None
    assert rows[0]["resume_id"] == "resume-300k"
    assert rows[0]["kind"] == "google_form"
    assert rows[0]["status"] == "dry_run_prepared"
    assert rows[0]["target_url"] == "https://forms.gle/PYbfwCLBmnnje6iBA"
    assert rows[0]["payload"]["answers"]["grade"] == "Middle"


def test_external_interaction_requires_existing_application(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")

    try:
        repo.record_external_interaction(
            application_id=999,
            kind="google_form",
            target_url="https://forms.gle/missing",
            status="dry_run_prepared",
            payload={},
        )
    except ValueError as exc:
        assert "application_id=999" in str(exc)
    else:
        raise AssertionError("missing application_id should fail closed")
