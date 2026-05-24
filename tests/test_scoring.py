from app.scoring import CandidateProfile, Vacancy, score_vacancy


def test_scores_remote_fullstack_vacancy_high():
    profile = CandidateProfile(
        target_roles=["full-stack", "backend", "telegram bots", "ai automation", "crm integrations"],
        skills=["React", "Node.js", "Python", "FastAPI", "Telegram", "CRM", "LLM", "PostgreSQL"],
        preferred_keywords=["удаленно", "удалённо", "долгосрочно", "контракт", "part-time"],
        stop_keywords=["только офис", "1с", "холодные звонки"],
        min_monthly_salary=180000,
    )
    vacancy = Vacancy(
        external_id="hh-1",
        title="Full-stack разработчик React + Python для AI CRM",
        company="Product Lab",
        description=(
            "Ищем разработчика на удаленно, долгосрочный контракт. Нужно развивать CRM, "
            "интеграции, Telegram-ботов и AI automation. Стек: React, Python, FastAPI, PostgreSQL."
        ),
        url="https://hh.ru/vacancy/1",
        salary_from=220000,
        salary_to=300000,
        currency="RUR",
        schedule="remote",
        employment="part",
        skills=["React", "Python", "FastAPI", "Telegram", "CRM"],
    )

    result = score_vacancy(vacancy, profile)

    assert result.score >= 85
    assert any("React" in reason for reason in result.reasons)
    assert any("удал" in reason.lower() or "remote" in reason.lower() for reason in result.reasons)
    assert result.decision == "hot"


def test_stop_keywords_and_low_salary_reduce_score():
    profile = CandidateProfile(
        target_roles=["full-stack"],
        skills=["React", "Python"],
        preferred_keywords=["удаленно"],
        stop_keywords=["только офис", "битрикс"],
        min_monthly_salary=180000,
    )
    vacancy = Vacancy(
        external_id="hh-2",
        title="Разработчик Bitrix",
        company="Legacy Office",
        description="Только офис, поддержка битрикс. Зарплата ниже рынка.",
        url="https://hh.ru/vacancy/2",
        salary_from=90000,
        salary_to=120000,
        currency="RUR",
        schedule="fullDay",
        employment="full",
        skills=["PHP", "Bitrix"],
    )

    result = score_vacancy(vacancy, profile)

    assert result.score < 55
    assert result.decision == "archive"
    assert any("стоп" in reason.lower() for reason in result.reasons)


def test_remote_100_200_salary_is_not_hard_rejected_when_job_is_relevant():
    profile = CandidateProfile(
        target_roles=["backend"],
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "API"],
        preferred_keywords=["удаленно"],
        stop_keywords=[],
        min_monthly_salary=300000,
    )
    vacancy = Vacancy(
        external_id="hh-flex-salary",
        title="Python Backend разработчик",
        company="Remote Product",
        description="Удаленно. Backend API, FastAPI, PostgreSQL, Docker. Возможен рост по роли и оплате.",
        url="https://hh.ru/vacancy/flex",
        salary_from=100000,
        salary_to=200000,
        currency="RUR",
        schedule="remote",
        employment="full",
        skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
    )

    result = score_vacancy(vacancy, profile)

    assert result.decision != "archive"
    assert any("salary flexible remote" in reason for reason in result.reasons)
    assert not any("salary below target" in penalty for penalty in result.penalties)
