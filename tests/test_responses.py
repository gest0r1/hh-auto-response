from app.responses import (
    ApplicantProfile,
    CaseStudy,
    ResponseContext,
    check_cover_letter_quality,
    generate_cover_letter,
    load_cover_letter_methodology,
    sanitize_cover_letter_greeting,
)
from app.scoring import Vacancy


def test_generate_cover_letter_uses_vacancy_context_and_cases():
    profile = ApplicantProfile(
        full_name="Александр Олегович",
        headline="Full-stack developer / AI automation engineer",
        strengths=["быстро собираю MVP", "делаю интеграции под бизнес-процессы", "умею доводить до продакшена"],
        cases=[
            CaseStudy(
                title="CRM для обработки заявок",
                stack=["React", "FastAPI", "PostgreSQL", "Telegram"],
                result="сократил ручную обработку заявок и вывел статусы в дашборд",
            )
        ],
        portfolio_url="https://example.com/portfolio",
    )
    vacancy = Vacancy(
        external_id="hh-3",
        title="Разработчик CRM и Telegram-бота",
        company="SalesOps",
        description="Нужно сделать CRM, Telegram-бота, визуальный дашборд и интеграции.",
        url="https://hh.ru/vacancy/3",
        skills=["React", "FastAPI", "Telegram", "CRM"],
    )

    response = generate_cover_letter(ResponseContext(profile=profile, vacancy=vacancy, score=91))

    assert response.message.startswith("Здравствуйте!")
    assert "Здравствуйте, SalesOps" not in response.message
    assert "CRM" in response.message
    assert "Telegram" in response.message
    assert "сократил ручную обработку" in response.message
    assert "https://example.com/portfolio" in response.message
    assert "[" not in response.message
    assert response.tone == "direct_business"
    assert response.estimated_fit >= 90


def test_generate_cover_letter_never_uses_employer_name_as_greeting():
    profile = ApplicantProfile(
        headline="AI automation engineer",
        strengths=["делаю AI-агентов", "автоматизирую CRM"],
        portfolio_url="https://portfolio.viably.dev",
    )
    vacancy = Vacancy(
        external_id="hh-ip-1",
        title="Python-разработчик AI-агентов",
        company="ИП Иванов Иван Иванович",
        description="Нужен Python, LLM, Telegram-боты и автоматизация откликов.",
        url="https://hh.ru/vacancy/ip-1",
        skills=["Python", "LLM", "Telegram"],
    )

    response = generate_cover_letter(ResponseContext(profile=profile, vacancy=vacancy, score=90))

    first_sentence = response.message.split(".", 1)[0]
    assert first_sentence == "Здравствуйте! Увидел вакансию «Python-разработчик AI-агентов»"
    assert "Здравствуйте, ИП" not in response.message
    assert "ИП Иванов" not in response.message
    assert "https://portfolio.viably.dev" in response.message


def test_sanitize_cover_letter_greeting_removes_legacy_employer_addressing():
    legacy = (
        "Здравствуйте, ИП Москвина Наталья Александровна! "
        "Увидел вакансию «Python AI Engineer». По описанию это мой профиль."
    )

    sanitized = sanitize_cover_letter_greeting(legacy)

    assert sanitized.startswith("Здравствуйте! Увидел вакансию")
    assert "Здравствуйте, ИП" not in sanitized
    assert "ИП Москвина" not in sanitized


def test_cover_letter_methodology_contains_employer_greeting_rule():
    methodology = load_cover_letter_methodology()

    assert "не обращаемся к работодателю по названию компании" in methodology.lower()
    assert "Здравствуйте!" in methodology
    assert "Что важно" in methodology
    assert "стек" in methodology.lower()
    assert "где и когда применял" in methodology.lower()


def test_generate_cover_letter_maps_vacancy_stack_and_important_block_to_concrete_project_evidence():
    profile = ApplicantProfile(
        full_name="Александр Олегович",
        headline="Full-stack / Backend / AI Infrastructure",
        cases=[
            CaseStudy(
                title="Viably — AI Product Platform",
                role="Backend Engineer / Platform Architect",
                period="2025–2026",
                stack=["FastAPI", "Next.js", "PostgreSQL", "Redis", "Docker", "RAG"],
                result="строил AI generation pipeline, preview/runtime, OAuth, billing и production-инфраструктуру",
            ),
            CaseStudy(
                title="Vibegent — AI-агент платформа",
                role="AI Infrastructure Engineer",
                period="2025–2026",
                stack=["LLM", "Telegram Bots", "Docker", "Hetzner"],
                result="делал LLM-прокси, Telegram-интерфейсы, воркер-ноды и деплой пользовательских AI-агентов",
            ),
        ],
        portfolio_url="https://portfolio.viably.dev",
    )
    vacancy = Vacancy(
        external_id="hh-stack-important",
        title="AI Fullstack Engineer / RAG Developer",
        company="Example AI",
        description=(
            "Стек: Python/FastAPI, React/Next.js, PostgreSQL, Redis, Docker, LLM, RAG. "
            "Что важно: применение RAG-систем в реальных проектах лучше академических знаний; "
            "умение запускать сервисы в production; интеграция LLM и Telegram."
        ),
        url="https://hh.ru/vacancy/stack-important",
        skills=["FastAPI", "Next.js", "PostgreSQL", "Redis", "Docker", "LLM", "RAG", "Telegram Bots"],
    )

    response = generate_cover_letter(ResponseContext(profile=profile, vacancy=vacancy, score=96))
    check = check_cover_letter_quality(response.message, ResponseContext(profile=profile, vacancy=vacancy, score=96))

    assert len(response.message) >= 900
    assert "Viably (2025–2026)" in response.message
    assert "Vibegent (2025–2026)" in response.message
    assert "FastAPI" in response.message
    assert "Next.js" in response.message
    assert "PostgreSQL" in response.message
    assert "Redis" in response.message
    assert "Docker" in response.message
    assert "RAG" in response.message
    assert "Что у вас обозначено как важное" in response.message
    assert "реальных проектах" in response.message
    assert "академических знаний" in response.message
    assert "production" in response.message
    assert "Портфолио: https://portfolio.viably.dev" in response.message
    assert check.passed is True
    assert check.issues == []


def test_generate_cover_letter_for_agentic_lead_uses_multiple_portfolio_cases_and_passes_quality_gate():
    profile = ApplicantProfile(
        full_name="Александр Олегович",
        headline="AI Infrastructure Engineer / Platform Architect",
        strengths=[
            "строю production-контуры для AI-агентов",
            "настраиваю agentic workflows, review и release gates",
        ],
        cases=[
            CaseStudy(
                title="FPV40 Campus — LMS-платформа для FPV-пилотов",
                stack=["React", "Docker", "GitHub Actions", "CI/CD", "Telegram Bots"],
                result="4 микросервиса, интерактивные React-компоненты, платежи, сертификаты и CI/CD",
            ),
            CaseStudy(
                title="Viably — AI Product Platform",
                stack=["FastAPI", "Next.js", "PostgreSQL", "Redis", "Docker", "LLM", "CI/CD"],
                result="AI generation pipeline, preview/deploy runtime, OAuth, billing и production-инфраструктура",
            ),
            CaseStudy(
                title="Vibegent — Мультитенантная AI-агент платформа",
                stack=["AI agents", "LLM", "Telegram Bots", "Docker", "Hetzner"],
                result="платформа пользовательских AI-агентов с LLM-прокси, Telegram-интерфейсами и воркер-нодами",
            ),
            CaseStudy(
                title="OpenClaw — Agent Runtime Operations",
                stack=["AI agents", "gateway", "memory", "persistent sessions"],
                result="production-стабилизация runtime, gateway, browser, messaging, memory и model auth",
            ),
        ],
        portfolio_url="https://portfolio.viably.dev",
    )
    vacancy = Vacancy(
        external_id="hh-132885649",
        title="AI Delivery Lead / Архитектор разработки на AI-агентах",
        company="Фордевинд",
        description=(
            "LandComp 2.0, AI-дизайнер сада, B2B-ассистент, генерация изображений. "
            "Нужно спроектировать agentic SDLC, роли analyst/architect/code/reviewer/QA/security agents, "
            "Definition of Done, CI/CD, test automation, security checks и release gates. "
            "Будет плюсом опыт LLM/RAG/agent systems, crisis delivery и engineering playbooks. Удаленный формат."
        ),
        url="https://hh.ru/vacancy/132885649",
        salary_from=270000,
        salary_to=420000,
        currency="RUR",
        schedule="remote",
        skills=["AI agents", "agentic SDLC", "CI/CD", "LLM", "RAG", "security checks", "release gates"],
    )

    response = generate_cover_letter(ResponseContext(profile=profile, vacancy=vacancy, score=97))
    check = check_cover_letter_quality(response.message, ResponseContext(profile=profile, vacancy=vacancy, score=97))

    assert response.message.startswith("Здравствуйте!")
    assert "Здравствуйте, Фордевинд" not in response.message
    assert "LandComp 2.0" in response.message
    assert "agentic SDLC" in response.message
    assert "Definition of Done" in response.message
    assert "Vibegent" in response.message
    assert "Viably" in response.message
    assert "OpenClaw" in response.message
    assert "FPV40" not in response.message
    assert "\nПортфолио: https://portfolio.viably.dev" in response.message
    assert check.passed is True
    assert check.issues == []


def test_cover_letter_quality_gate_rejects_generic_text_without_cases_or_portfolio():
    profile = ApplicantProfile(
        headline="AI Infrastructure Engineer",
        cases=[CaseStudy(title="Vibegent", stack=["AI agents"], result="AI-agent platform")],
        portfolio_url="https://portfolio.viably.dev",
    )
    vacancy = Vacancy(
        external_id="hh-1",
        title="AI Delivery Lead",
        company="Фордевинд",
        description="Нужно построить agentic SDLC, CI/CD и release gates.",
        url="https://hh.ru/vacancy/1",
        skills=["AI agents", "CI/CD"],
    )

    generic = "Здравствуйте! Имею большой опыт, готов обсудить детали и выполнить качественно и в срок."

    check = check_cover_letter_quality(generic, ResponseContext(profile=profile, vacancy=vacancy, score=90))

    assert check.passed is False
    assert "missing_portfolio" in check.issues
    assert "missing_relevant_case" in check.issues
    assert "generic_phrase:имею большой опыт" in check.issues
