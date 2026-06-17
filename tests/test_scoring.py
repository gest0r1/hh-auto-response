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


def test_stop_keywords_cap_keyword_stuffed_vacancy():
    profile = CandidateProfile(
        target_roles=["Python Backend Engineer", "AI Backend Engineer", "LLM Platform Engineer"],
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "LLM", "RAG", "AI"],
        preferred_keywords=["удаленно", "AI", "LLM", "backend", "platform"],
        stop_keywords=["computer vision", "data scientist"],
        min_monthly_salary=100000,
    )
    vacancy = Vacancy(
        external_id="hh-cv-ai-python",
        title="Senior Python разработчик для AI platform",
        company="Vision Lab",
        description=(
            "Удаленно. Python, FastAPI, PostgreSQL, Docker, LLM, RAG, backend platform. "
            "Основной фокус команды: computer vision и classical ML research."
        ),
        url="https://hh.ru/vacancy/cv-ai-python",
        salary_from=250000,
        salary_to=320000,
        currency="RUR",
        schedule="remote",
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "LLM"],
    )

    result = score_vacancy(vacancy, profile)

    assert result.score < 55
    assert result.decision == "archive"
    assert any("computer vision" in penalty for penalty in result.penalties)


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


def test_hard_title_mismatch_terms_prevent_auto_hot_scores():
    profile = CandidateProfile(
        target_roles=["Python Backend Engineer", "AI Agent Systems", "LLM Platform Engineer"],
        skills=["Python", "FastAPI", "LLM", "AI", "PostgreSQL", "Docker"],
        preferred_keywords=["удаленно", "AI", "LLM", "platform"],
        stop_keywords=[],
        min_monthly_salary=100000,
    )
    vacancy = Vacancy(
        external_id="hh-csharp-sber",
        title="C#/ .net разработчик",
        company="Сбер. IT",
        description="Удаленно. AI platform, LLM, Python integrations, PostgreSQL, Docker.",
        url="https://hh.ru/vacancy/csharp-sber",
        salary_from=250000,
        salary_to=320000,
        currency="RUR",
        schedule="remote",
        skills=["C#", ".NET", "Python", "LLM", "Docker"],
    )
    qa_vacancy = Vacancy(
        external_id="hh-qa-python",
        title="QA Automation Engineer (Python)",
        company="QAco",
        description="Удаленно. Python, pytest, Docker, API automation.",
        url="https://hh.ru/vacancy/qa-python",
        salary_from=250000,
        salary_to=320000,
        currency="RUR",
        schedule="remote",
        skills=["Python", "pytest", "Docker"],
    )
    qa_manual_backend_vacancy = Vacancy(
        external_id="hh-qa-auto-manual-backend",
        title="QA (auto/manual) backend",
        company="GS Labs",
        description="Удаленно. Python, REST API, PostgreSQL, Redis, Docker, CI/CD, SaaS.",
        url="https://hh.ru/vacancy/qa-auto-manual-backend",
        salary_from=250000,
        salary_to=320000,
        currency="RUR",
        schedule="remote",
        skills=["Python", "REST API", "PostgreSQL", "Redis", "Docker", "CI/CD"],
    )
    sdet_vacancy = Vacancy(
        external_id="hh-sdet-ai-python",
        title="Junior Software Development Engineer in Test (Quality & AI focus)",
        company="Gear Games",
        description="Remote. Python, AI tooling, backend integrations, Docker.",
        url="https://hh.ru/vacancy/sdet-ai-python",
        salary_from=180000,
        salary_to=260000,
        currency="RUR",
        schedule="remote",
        skills=["Python", "AI", "Docker"],
    )
    embedded_vacancy = Vacancy(
        external_id="hh-embedded-python",
        title="Senior Embedded Software Developer / Разработчик встроенного ПО",
        company="НПП ТехноЛаб",
        description="Python tooling, Linux, backend API, Docker.",
        url="https://hh.ru/vacancy/embedded-python",
        salary_from=220000,
        salary_to=300000,
        currency="RUR",
        schedule="remote",
        skills=["Python", "Linux", "Docker"],
    )
    ai_operator_vacancy = Vacancy(
        external_id="hh-ai-operator",
        title="ИИ-оператор",
        company="AI Ops",
        description="Работа с AI, LLM, промптами, Python будет плюсом.",
        url="https://hh.ru/vacancy/ai-operator",
        salary_from=120000,
        salary_to=180000,
        currency="RUR",
        schedule="remote",
        skills=["AI", "LLM", "Python"],
    )

    result = score_vacancy(vacancy, profile)
    qa_result = score_vacancy(qa_vacancy, profile)
    qa_manual_backend_result = score_vacancy(qa_manual_backend_vacancy, profile)
    sdet_result = score_vacancy(sdet_vacancy, profile)
    embedded_result = score_vacancy(embedded_vacancy, profile)
    ai_operator_result = score_vacancy(ai_operator_vacancy, profile)

    assert result.score < 70
    assert result.decision in {"maybe", "archive"}
    assert any("стоп в названии" in penalty for penalty in result.penalties)
    assert qa_result.score < 70
    assert qa_result.decision in {"maybe", "archive"}
    assert any("стоп в названии" in penalty for penalty in qa_result.penalties)
    assert qa_manual_backend_result.score < 70
    assert qa_manual_backend_result.decision in {"maybe", "archive"}
    assert any("стоп в названии" in penalty and "qa" in penalty for penalty in qa_manual_backend_result.penalties)
    assert sdet_result.score < 70
    assert any(
        "стоп в названии" in penalty and "software development engineer in test" in penalty
        for penalty in sdet_result.penalties
    )
    assert embedded_result.score < 70
    assert any("стоп в названии" in penalty and "embedded" in penalty for penalty in embedded_result.penalties)
    assert ai_operator_result.score < 70
    assert any("стоп в названии" in penalty and "ии оператор" in penalty for penalty in ai_operator_result.penalties)

    php_vacancy = Vacancy(
        external_id="hh-php-backend",
        title="Senior PHP/Symfony Backend Developer",
        company="LegacyCo",
        description="Удаленно. Backend integrations, PostgreSQL, Docker, API platform.",
        url="https://hh.ru/vacancy/php-backend",
        salary_from=250000,
        salary_to=320000,
        currency="RUR",
        schedule="remote",
        skills=["PHP", "Symfony", "PostgreSQL", "Docker"],
    )

    php_result = score_vacancy(php_vacancy, profile)

    assert php_result.score < 70
    assert any("php" in penalty or "symfony" in penalty for penalty in php_result.penalties)


def test_go_developer_title_stop_caps_keyword_stuffed_role_without_blocking_django():
    profile = CandidateProfile(
        target_roles=["Python Backend Engineer", "AI Backend Engineer", "LLM Platform Engineer"],
        skills=["Python", "Redis", "API", "FastAPI", "PostgreSQL", "Docker"],
        preferred_keywords=["remote", "Python", "backend", "API", "platform"],
        stop_keywords=[],
        min_monthly_salary=100000,
    )
    vacancy = Vacancy(
        external_id="hh-go-antifraud",
        title="Go разработчик in AntiFraud",
        company="Fraud Platform",
        description=(
            "Remote. Python services, Redis, API, FastAPI, PostgreSQL, Docker, backend platform. "
            "Нужен разработчик для antifraud integrations."
        ),
        url="https://hh.ru/vacancy/go-antifraud",
        salary_from=250000,
        salary_to=320000,
        currency="RUR",
        schedule="remote",
        employment="full",
        skills=["Go", "Python", "Redis", "API"],
    )
    django_vacancy = Vacancy(
        external_id="hh-django-backend",
        title="Django Backend разработчик",
        company="Python Product",
        description="Remote. Python backend, Django, Redis, API, PostgreSQL, Docker.",
        url="https://hh.ru/vacancy/django-backend",
        salary_from=250000,
        salary_to=320000,
        currency="RUR",
        schedule="remote",
        employment="full",
        skills=["Python", "Django", "Redis", "API", "PostgreSQL", "Docker"],
    )

    result = score_vacancy(vacancy, profile)
    django_result = score_vacancy(django_vacancy, profile)

    assert result.score < 70
    assert result.decision in {"maybe", "archive"}
    assert any("стоп в названии" in penalty and "go" in penalty for penalty in result.penalties)
    assert django_result.score >= 85
    assert not any("стоп в названии" in penalty for penalty in django_result.penalties)


def test_office_only_without_remote_caps_keyword_stuffed_role():
    profile = CandidateProfile(
        target_roles=["Python Backend Engineer", "AI Backend Engineer", "LLM Platform Engineer"],
        skills=["Python", "FastAPI", "Redis", "PostgreSQL", "Docker", "AI", "LLM"],
        preferred_keywords=["Python", "AI", "LLM", "backend", "platform"],
        stop_keywords=[],
        min_monthly_salary=100000,
    )
    vacancy = Vacancy(
        external_id="hh-office-python-ai",
        title="Python Backend разработчик",
        company="Office Product",
        description=(
            "Важно: работа в офисе. Python, FastAPI, Redis, PostgreSQL, Docker, AI, LLM, "
            "backend platform integrations."
        ),
        url="https://hh.ru/vacancy/office-python-ai",
        salary_from=250000,
        salary_to=320000,
        currency="RUR",
        schedule="fullDay",
        employment="full",
        skills=["Python", "FastAPI", "Redis", "PostgreSQL", "Docker", "AI", "LLM"],
    )
    remote_vacancy = Vacancy(
        external_id="hh-remote-python-ai-office",
        title="Python Backend разработчик",
        company="Remote Product",
        description=(
            "Можно удаленно. Иногда встреча в офисе. Python, FastAPI, Redis, PostgreSQL, "
            "Docker, AI, LLM, backend platform integrations."
        ),
        url="https://hh.ru/vacancy/remote-python-ai-office",
        salary_from=250000,
        salary_to=320000,
        currency="RUR",
        schedule="remote",
        employment="full",
        skills=["Python", "FastAPI", "Redis", "PostgreSQL", "Docker", "AI", "LLM"],
    )
    negative_remote_vacancy = Vacancy(
        external_id="hh-not-remote-python-ai-office",
        title="Python Backend разработчик",
        company="Office Product",
        description=(
            "Не удаленно, работа в офисе. Python, FastAPI, Redis, PostgreSQL, Docker, AI, LLM, "
            "backend platform integrations."
        ),
        url="https://hh.ru/vacancy/not-remote-python-ai-office",
        salary_from=250000,
        salary_to=320000,
        currency="RUR",
        schedule="fullDay",
        employment="full",
        skills=["Python", "FastAPI", "Redis", "PostgreSQL", "Docker", "AI", "LLM"],
    )

    result = score_vacancy(vacancy, profile)
    remote_result = score_vacancy(remote_vacancy, profile)
    negative_remote_result = score_vacancy(negative_remote_vacancy, profile)

    assert result.score < 70
    assert result.decision in {"maybe", "archive"}
    assert any("офис без удаленки" in penalty for penalty in result.penalties)
    assert remote_result.score >= 85
    assert not any("офис без удаленки" in penalty for penalty in remote_result.penalties)
    assert negative_remote_result.score < 70
    assert any("офис без удаленки" in penalty for penalty in negative_remote_result.penalties)


def test_bitrix_developer_title_stop_caps_keyword_stuffed_remote_role():
    profile = CandidateProfile(
        target_roles=["Python Backend Engineer", "AI Backend Engineer", "LLM Platform Engineer"],
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "LLM", "RAG", "AI", "Automation"],
        preferred_keywords=["remote", "удаленно", "AI", "LLM", "backend", "automation", "platform"],
        stop_keywords=[],
        min_monthly_salary=100000,
    )
    vacancy = Vacancy(
        external_id="hh-bitrix24-automation",
        title="Разработчик Битрикс 24/Bitrix24 Developer / Automation Engineer",
        company="CRM Integrator",
        description=(
            "Удаленно. Python, FastAPI, PostgreSQL, Docker, LLM, RAG, AI backend automation platform. "
            "High-salary role with integrations, agents, API workflows and long-term product work."
        ),
        url="https://hh.ru/vacancy/bitrix24-automation",
        salary_from=250000,
        salary_to=320000,
        currency="RUR",
        schedule="remote",
        employment="full",
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "LLM", "Bitrix24"],
    )

    result = score_vacancy(vacancy, profile)

    assert result.score < 70
    assert result.decision in {"maybe", "archive"}
    assert any("стоп в названии" in penalty and "bitrix" in penalty for penalty in result.penalties)


def test_lead_data_engineer_title_stop_keeps_keyword_stuffed_role_below_review():
    profile = CandidateProfile(
        target_roles=["Python Backend Engineer", "AI Backend Engineer", "LLM Platform Engineer"],
        skills=["Python", "Airflow", "Spark", "Kafka", "DWH", "LLM"],
        preferred_keywords=["remote", "Python", "LLM", "backend", "platform"],
        stop_keywords=["data scientist", "data analyst", "инженер данных"],
        min_monthly_salary=100000,
    )
    vacancy = Vacancy(
        external_id="hh-lead-data-engineer",
        title="Lead Data Engineer",
        company="Data Product",
        description=(
            "Remote high-salary role. Python, Airflow, Spark, Kafka, DWH pipelines. "
            "Build data platform integrations with occasional LLM use."
        ),
        url="https://hh.ru/vacancy/lead-data-engineer",
        salary_from=280000,
        salary_to=360000,
        currency="RUR",
        schedule="remote",
        employment="full",
        skills=["Python", "Airflow", "Spark", "Kafka", "DWH"],
    )

    result = score_vacancy(vacancy, profile)

    assert result.score < 70
    assert result.decision in {"maybe", "archive"}
    assert any("стоп в названии: data engineer" in penalty for penalty in result.penalties)


def test_technical_writer_title_stop_keeps_keyword_stuffed_role_below_review():
    profile = CandidateProfile(
        target_roles=["Python Backend Engineer", "AI Backend Engineer", "LLM Platform Engineer"],
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "LLM", "RAG", "AI"],
        preferred_keywords=["remote", "удаленно", "Python", "LLM", "backend", "platform"],
        stop_keywords=[],
        min_monthly_salary=100000,
    )
    vacancy = Vacancy(
        external_id="hh-technical-writer-middle-plus",
        title="Технический писатель (Middle+)",
        company="Docs AI",
        description=(
            "Удаленно. Python, FastAPI, PostgreSQL, Docker, LLM, RAG, AI backend platform. "
            "Нужно описывать API, developer experience и AI integrations."
        ),
        url="https://hh.ru/vacancy/technical-writer-middle-plus",
        salary_from=250000,
        salary_to=320000,
        currency="RUR",
        schedule="remote",
        employment="full",
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "LLM"],
    )

    result = score_vacancy(vacancy, profile)

    assert result.score < 70
    assert result.decision in {"maybe", "archive"}
    assert any("стоп в названии: технический писатель" in penalty for penalty in result.penalties)


def test_recruiter_and_talent_manager_titles_stay_out_of_auto_send_queue():
    profile = CandidateProfile(
        target_roles=["Python Backend Engineer", "AI Backend Engineer", "LLM Platform Engineer"],
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "LLM", "RAG", "AI"],
        preferred_keywords=["remote", "удаленно", "Python", "LLM", "backend", "platform"],
        stop_keywords=[],
        min_monthly_salary=100000,
    )
    vacancy = Vacancy(
        external_id="hh-senior-talent-manager-ai-keywords",
        title="Senior Talent Manager | Senior IT Recruiter | удалено",
        company="Recruiting AI",
        description=(
            "Удаленно. Нужно искать Python/FastAPI/LLM backend engineers, работать с AI platform "
            "и закрывать роли по RAG, PostgreSQL, Docker."
        ),
        url="https://hh.ru/vacancy/talent-manager",
        salary_from=250000,
        salary_to=320000,
        currency="RUR",
        schedule="remote",
        skills=["Python", "FastAPI", "LLM", "RAG", "Recruiting"],
    )

    result = score_vacancy(vacancy, profile)

    assert result.score < 70
    assert result.decision in {"maybe", "archive"}
    assert any("стоп в названии" in penalty and "recruiter" in penalty for penalty in result.penalties)


def test_ml_engineer_title_stays_below_review_for_agentops_search():
    profile = CandidateProfile(
        target_roles=["Python Backend Engineer", "AI Backend Engineer", "LLM Platform Engineer"],
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "LLM", "RAG", "AI"],
        preferred_keywords=["remote", "удаленно", "Python", "LLM", "backend", "platform"],
        stop_keywords=[],
        min_monthly_salary=100000,
    )
    vacancy = Vacancy(
        external_id="hh-ml-engineer-keyword-stuffed",
        title="ML-инженер",
        company="Model Lab",
        description=(
            "Удаленно. Python, FastAPI, Docker, LLM, RAG, AI backend platform. "
            "Основная роль - ML-инженер для моделей, экспериментов и machine learning pipeline."
        ),
        url="https://hh.ru/vacancy/ml-engineer",
        salary_from=250000,
        salary_to=320000,
        currency="RUR",
        schedule="remote",
        skills=["Python", "ML", "LLM", "Docker"],
    )

    result = score_vacancy(vacancy, profile)

    assert result.score < 70
    assert result.decision in {"maybe", "archive"}
    assert any("стоп в названии" in penalty and "ml" in penalty for penalty in result.penalties)
