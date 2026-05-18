from app.config import default_applicant_profile
from app.responses import (
    ApplicantProfile,
    CaseStudy,
    ResponseContext,
    check_cover_letter_quality,
    generate_cover_letter,
    load_cover_letter_methodology,
    sanitize_cover_letter_greeting,
    _important_requirements,
    _requirement_focus_terms,
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
    assert first_sentence == "Здравствуйте! Увидел вакансию Python-разработчик AI-агентов"
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
    assert "Чем предстоит заниматься" in methodology
    assert "Что мы ждём" in methodology
    assert "стек" in methodology.lower()
    assert "без кавычек" in methodology.lower()
    assert "по стеку из вакансии" in methodology.lower()
    assert "для таких задач важно не просто" in methodology.lower()
    assert "не вылизываем" in methodology.lower()
    assert "живой" in methodology.lower()
    assert "не очередной вайбкодер" in methodology.lower()
    assert "по умолчанию" in methodology.lower()
    assert "лёгкая высокомерность" in methodology.lower()
    assert "не про красивые демки" in methodology.lower()
    assert "внешние ссылки" in methodology.lower()
    assert "humanizer-pass" in methodology.lower()
    assert "чатбот" in methodology.lower()
    assert "канцелярит" in methodology.lower()
    assert "рекламный тон" in methodology.lower()
    assert "в рамках" in methodology.lower()


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
    assert "По описанию вижу главный фокус" in response.message
    assert "Для таких задач важно не просто" not in response.message
    assert "инженерный контур вокруг агентов" not in response.message
    assert "По стеку из вакансии" not in response.message
    assert "Что у вас обозначено как важное" not in response.message
    assert "— применял" not in response.message
    assert "Увидел вакансию «" not in response.message
    assert "работал с FastAPI" in response.message
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
    assert "Увидел вакансию «" not in response.message
    assert "По стеку из вакансии" not in response.message
    assert "Что у вас обозначено как важное" not in response.message
    assert "Vibegent" in response.message or "OpenClaw" in response.message
    assert "Из похожего опыта" in response.message
    assert "Это тот слой" in response.message
    assert "FPV40" not in response.message
    assert "\nПортфолио: https://portfolio.viably.dev" in response.message
    assert len(response.message) <= 1600
    assert check.passed is True
    assert check.issues == []


def test_default_profile_agentic_cover_letter_uses_broad_agentops_experience_and_important_block():
    profile = default_applicant_profile()
    vacancy = Vacancy(
        external_id="hh-broad-agentops",
        title="AI Agent Systems Architect / AgentOps Engineer",
        company="Example AI",
        description=(
            "Что важно: production AI agents, AgentOps, многоагентные команды, RAG, tool calling, memory, "
            "Telegram/Web-интеграции, human-in-the-loop, мониторинг, тесты и внедрение AI-агентов в бизнес-процессы."
        ),
        url="https://hh.ru/vacancy/broad-agentops",
        skills=[
            "AI agents",
            "AgentOps",
            "Multi-agent systems",
            "RAG",
            "Tool calling",
            "Agent memory",
            "Telegram Bots",
            "human-in-the-loop",
        ],
    )

    context = ResponseContext(profile=profile, vacancy=vacancy, score=98)
    response = generate_cover_letter(context)
    check = check_cover_letter_quality(response.message, context)

    assert "Vibegent" in response.message or "Hermes Operator Contour" in response.message or "Heisenberg Team" in response.message
    assert "По описанию вижу главный фокус" in response.message
    assert "агентная логика" in response.message
    assert "Из похожего опыта" in response.message
    assert "Это тот слой" in response.message
    assert "Сейчас много работаю" not in response.message
    assert "Что у вас обозначено как важное" not in response.message
    assert "По стеку из вакансии" not in response.message
    assert "Увидел вакансию «" not in response.message
    assert "Портфолио: https://portfolio.viably.dev" in response.message
    assert 700 <= len(response.message) <= 1600
    assert check.passed is True
    assert check.issues == []


def test_live_like_ai_product_engineer_response_anchors_to_expectation_sections():
    profile = default_applicant_profile()
    vacancy = Vacancy(
        external_id="hh-130517394",
        title="AI Product Engineer",
        company="Lofty.",
        description=(
            "Мы развиваем внутреннюю лабораторию по созданию AI-агентов и ассистентов. "
            "В портфеле — 4 действующих проекта в нишах Crypto и AI Tools с бизнес-моделью по подписке (SaaS).\n"
            "Наша цель: Быстрая проверка гипотез и превращение концептов в коммерчески успешные продукты на базе SOTA-моделей (GPT-5, Claude) и инфраструктуры Replit/MCP.\n"
            "Мы не обучаем модели, не крутим веса и не пишем архитектуры нейросетей на PyTorch.\n"
            "Чем предстоит заниматься:\n"
            "- Создавать AI-продукты под ключ: Проходить путь от идеи и гипотезы до работающего прототипа (MVP);\n"
            "- Вайбкодинг в Replit: Активно использовать платформу и AI-агентов для быстрой сборки и внедрения решений;\n"
            "- Работа с MCP: Поднимать и интегрировать MCP-серверы (Model Context Protocol) для расширения возможностей моделей;\n"
            "- Промпт-инжиниринг: Писать и тестировать системные промпты, анализировать поведение моделей и добиваться нужного качества ответов;\n"
            "- Автономный запуск: Самостоятельно разворачивать проекты (без помощи DevOps) и проводить тестирование;\n"
            "Что мы ждем от тебя:\n"
            "- Техническая база: Ты понимаешь принципы работы AI и умеешь использовать MCP-серверы на практике;\n"
            "- Навыки мейкера: Можешь полностью собрать и запустить проект самостоятельно, используя современные No-code/Low-code и AI инструменты;\n"
            "- Продуктовое мышление: Способность находить баланс между красивым кодом и скоростью проверки гипотезы;\n"
            "Будет круто, если ты:\n"
            "- Уже прописан в Replit и знаешь все возможности этой платформы.\n"
            "Что мы предлагаем:\n"
            "- Конкурентоспособную заработную плату."
        ),
        url="https://hh.ru/vacancy/130517394",
        skills=["Cursor", "Replit", "MCP", "Claude", "MVP"],
    )

    context = ResponseContext(profile=profile, vacancy=vacancy, score=92)
    requirements = _important_requirements(vacancy)
    requirement_terms = _requirement_focus_terms(requirements, vacancy)
    response = generate_cover_letter(context)
    check = check_cover_letter_quality(response.message, context)

    assert any("MCP-серверы" in item for item in requirements)
    assert any("Replit" in item for item in requirements)
    assert "Replit/Cursor" in requirement_terms
    assert "MCP-серверы" in requirement_terms
    assert "быстрые SaaS/MVP-гипотезы" in requirement_terms
    assert "Тут нужен не пересказчик промптов" in response.message
    assert "По описанию вижу главный фокус" in response.message
    assert "Replit/Cursor" in response.message
    assert "MCP-серверы" in response.message
    assert "SaaS/MVP" in response.message
    assert "прикладному AI-продукту" in response.message
    assert "Из похожего опыта" in response.message
    assert "Сейчас много работаю" not in response.message
    assert response.message.index("По описанию вижу главный фокус") < response.message.index("Из похожего опыта")
    assert len(response.message) <= 1600
    assert "Что у вас обозначено как важное" not in response.message
    assert "По стеку из вакансии" not in response.message
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


def test_cover_letter_quality_gate_rejects_robotic_hh_structure():
    profile = ApplicantProfile(
        headline="AI Infrastructure Engineer",
        cases=[CaseStudy(title="Vibegent", stack=["LLM"], result="LLM-инфраструктура")],
        portfolio_url="https://portfolio.viably.dev",
    )
    vacancy = Vacancy(
        external_id="hh-robotic",
        title="Senior AI Platform Engineer",
        company="Example",
        description="Что важно: production backend, LLM/RAG и CI/CD.",
        url="https://hh.ru/vacancy/robotic",
        skills=["LLM", "RAG", "CI/CD"],
    )
    robotic = (
        "Здравствуйте! Увидел вакансию «Senior AI Platform Engineer».\n\n"
        "По стеку из вакансии: LLM — применял в Vibegent.\n\n"
        "Что у вас обозначено как важное: production backend.\n\n"
        "Для таких задач важно не просто подключить LLM API.\n\n"
        "Портфолио: https://portfolio.viably.dev"
    )

    check = check_cover_letter_quality(robotic, ResponseContext(profile=profile, vacancy=vacancy, score=90))

    assert check.passed is False
    assert "robotic_structure" in check.issues
    assert "quoted_vacancy_title" in check.issues


def test_cover_letter_quality_gate_rejects_ai_slop_and_bureaucratic_style():
    profile = ApplicantProfile(
        headline="AI Infrastructure Engineer",
        cases=[CaseStudy(title="Vibegent", stack=["LLM"], result="LLM-инфраструктура")],
        portfolio_url="https://portfolio.viably.dev",
    )
    vacancy = Vacancy(
        external_id="hh-ai-style",
        title="AI Engineer",
        company="Example",
        description="Нужно интегрировать LLM в продукт.",
        url="https://hh.ru/vacancy/ai-style",
        skills=["LLM"],
    )
    ai_slop = (
        "Здравствуйте! Увидел вакансию AI Engineer. Конечно! Важно отметить, что в рамках данного проекта "
        "я осуществлял работу, обеспечивая качество и демонстрируя подход. "
        "В Vibegent делал LLM-инфраструктуру.\n\n"
        "Портфолио: https://portfolio.viably.dev"
    )

    check = check_cover_letter_quality(ai_slop, ResponseContext(profile=profile, vacancy=vacancy, score=90))

    assert check.passed is False
    assert "ai_style:chatbot_artifact" in check.issues
    assert "ai_style:empty_intro" in check.issues
    assert "ai_style:bureaucratic" in check.issues
    assert "ai_style:participle_chain" in check.issues
