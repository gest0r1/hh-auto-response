import re

from app.config import default_applicant_profile
from app.responses import (
    ApplicantProfile,
    CaseStudy,
    LEGACY_REPEATED_TEMPLATE_PHRASES,
    ResponseContext,
    _best_cases,
    check_cover_letter_quality,
    generate_cover_letter,
    load_cover_letter_methodology,
    sanitize_cover_letter_greeting,
    _important_requirements,
    _proof_case_titles,
    _requirement_focus_terms,
)
from app.scoring import Vacancy


def _deploy_word_count(message: str) -> int:
    return len(re.findall(r"\b(?:депло[а-яё]*|задепло[а-яё]*|deploy[a-z-]*)\b", message.lower()))


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

    paragraphs = [paragraph for paragraph in response.message.split("\n\n") if paragraph]
    assert paragraphs[0] == "Здравствуйте!"
    assert paragraphs[1].startswith("Задача, как я ее понял:")
    assert "Увидел вакансию" not in response.message
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
    lowered = methodology.lower().replace("ё", "е")

    assert "не обращаться к работодателю по названию компании" in lowered
    assert "Здравствуйте!" in methodology
    assert "Что важно" in methodology
    assert "Чем предстоит заниматься" in methodology
    assert "Что мы ждем" in methodology
    assert "стек" in lowered
    assert "кавычки" in lowered
    assert "для таких задач важно не просто" in lowered
    assert "живой" in lowered
    assert "внешних ссылок" in lowered
    assert "proof pack" in lowered
    assert "дополнительно" in lowered
    assert "github" in lowered
    assert "humanizer-pass" in lowered
    assert "чатбот" in lowered
    assert "канцелярит" in lowered
    assert "рекламного тона" in lowered
    assert "в рамках" in lowered


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

    paragraphs = [paragraph for paragraph in response.message.split("\n\n") if paragraph]
    assert len(paragraphs) == 4
    assert 650 <= len(response.message) <= 1000
    assert "Viably (2025-2026)" in response.message
    assert "Vibegent (2025-2026)" in response.message
    assert "2025–2026" not in response.message
    for forbidden_char in ["–", "—", "«", "»"]:
        assert forbidden_char not in response.message
    assert "FastAPI" in response.message
    assert "Next.js" in response.message
    assert "PostgreSQL" in response.message
    assert "Redis" in response.message
    assert "Docker" in response.message
    assert "RAG" in response.message
    assert "Задача, как я ее понял" in response.message
    assert "По описанию" not in response.message
    assert "Для таких задач важно не просто" not in response.message
    assert "инженерный контур вокруг агентов" not in response.message
    assert "По стеку из вакансии" not in response.message
    assert "Что у вас обозначено как важное" not in response.message
    assert "— применял" not in response.message
    assert "Увидел вакансию «" not in response.message
    assert "Увидел вакансию" not in response.message
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
    assert "Увидел вакансию" not in response.message
    assert "По стеку из вакансии" not in response.message
    assert "Что у вас обозначено как важное" not in response.message
    assert "Vibegent" in response.message or "OpenClaw" in response.message
    assert "Из похожего опыта" not in response.message
    assert "Это тот слой" not in response.message
    assert len([paragraph for paragraph in response.message.split("\n\n") if paragraph]) == 4
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
    assert "Задача, как я ее понял" in response.message
    assert "По описанию" not in response.message
    assert "агентная логика" in response.message
    assert "Из похожего опыта" not in response.message
    assert "Это тот слой" not in response.message
    assert "Сейчас много работаю" not in response.message
    assert "Что у вас обозначено как важное" not in response.message
    assert "По стеку из вакансии" not in response.message
    assert "Увидел вакансию" not in response.message
    lowered = response.message.lower().replace("ё", "е")
    assert "vibegent-proxy" not in lowered
    assert "credits" not in lowered
    assert "Портфолио: https://portfolio.viably.dev" in response.message
    assert 600 <= len(response.message) <= 1200
    assert len([paragraph for paragraph in response.message.split("\n\n") if paragraph]) == 4
    assert check.passed is True
    assert check.issues == []


def test_live_like_rag_llm_engineer_cover_letter_avoids_internal_proxy_jargon():
    profile = default_applicant_profile()
    vacancy = Vacancy(
        external_id="hh-133524120",
        title="RAG / LLM инженер",
        company="Example AI",
        description=(
            "Задачи:\n"
            "- построение корпоративной RAG-системы для интеллектуального поиска по документам\n"
            "- разработка ingestion / indexing pipeline: загрузка, парсинг, OCR, чанкинг, эмбеддинги\n"
            "- реализация retrieval / query pipeline: hybrid search, reranking, сборка контекста для LLM\n"
            "- работа с векторными БД, метаданными, ACL, версиями документов и SSO-доступом\n"
            "- разработка API для поиска, извлечения чанков / документов и интеграции с UI\n"
            "Требования:\n"
            "- практический опыт с RAG-системами и LLM в production\n"
            "- сильный Python и опыт backend-разработки API\n"
            "- опыт с embeddings, vector DB, BM25 / hybrid search, reranking\n"
            "- понимание парсинга документов: PDF, DOCX, таблицы, OCR, structured extraction\n"
            "- опыт с LangChain / LlamaIndex / Qdrant / Milvus / OpenSearch или аналогами\n"
            "- понимание безопасности данных: ACL, tenant isolation, JWT / SSO будет преимуществом"
        ),
        url="https://hh.ru/vacancy/133524120",
        skills=["LLM", "RAG", "backend"],
    )

    context = ResponseContext(profile=profile, vacancy=vacancy, score=97)
    response = generate_cover_letter(context)
    check = check_cover_letter_quality(response.message, context)
    lowered = response.message.lower().replace("ё", "е")

    assert "llm/rag" in lowered
    assert "vibegent-proxy" not in lowered
    assert "credits" not in lowered
    assert "ai backend" in lowered or "agentops" in lowered or "агент" in lowered
    assert check.passed is True
    assert check.issues == []


def test_ai_transformation_lead_cover_letter_sounds_like_internal_transformation_draft():
    profile = default_applicant_profile()
    vacancy = Vacancy(
        external_id="hh-133455243",
        title="AI Transformation Lead / AI Evangelist",
        company="Example Corp",
        description=(
            "Нужен AI Transformation Lead / AI Evangelist для внутренней AI-трансформации компании. "
            "Задача роли - находить процессы в отделах, анализировать бизнес-процессы, внедрять "
            "AI-инструменты и AI-агентов в ежедневную работу команд, обучать сотрудников и показывать быстрые эффекты.\n"
            "Что важно:\n"
            "- опыт внедрения AI в отделы продаж, поддержки, маркетинга, HR или операционные процессы;\n"
            "- умение проводить анализ бизнес-процессов и находить точки автоматизации;\n"
            "- практический опыт с AI-агентами, LLM/RAG и базовой архитектурой решений;\n"
            "- Telegram/Web-интерфейсы, workflow automation, интеграции с CRM и внутренними системами;\n"
            "- способность объяснять AI простым языком и быть евангелистом изменений внутри компании.\n"
            "Дополнительно\n\n"
            "Если у тебя есть:\n\n"
            "GitHub,\n"
            "кейсы,\n"
            "Telegram-канал,\n"
            "AI-проекты,\n"
            "автоматизации,\n"
            "презентации,\n"
            "свои AI-агенты — обязательно покажи их в отклике"
        ),
        url="https://hh.ru/vacancy/133455243",
        skills=[
            "AI transformation",
            "AI agents",
            "LLM",
            "RAG",
            "Workflow automation",
            "Business process analysis",
            "Telegram",
            "Web",
        ],
    )

    context = ResponseContext(profile=profile, vacancy=vacancy, score=96)
    response = generate_cover_letter(context)
    check = check_cover_letter_quality(response.message, context)

    paragraphs = [paragraph for paragraph in response.message.split("\n\n") if paragraph]
    body_start = paragraphs[1]
    lowered = response.message.lower().replace("ё", "е")

    assert response.message.startswith("Здравствуйте!")
    assert body_start.startswith("Главный фокус вижу так") or "вам нужен человек" in body_start.lower()
    assert not body_start.startswith("Задача, как я ее понял")
    assert "внедр" in lowered
    assert "отдел" in lowered
    assert "процесс" in lowered
    assert re.search(r"ai[-\s]?агент", lowered)
    assert "llm/rag" in lowered
    assert any(anchor in lowered for anchor in ["telegram/web", "telegram", "web", "workflow automation"])
    assert re.search(r"(анализ|разбор)[а-я\s-]{0,40}бизнес-процесс", lowered) or "business process analysis" in lowered
    assert "нужен ai backend/agentops" not in lowered
    assert "ai backend части" not in lowered
    assert "vibegent-proxy" not in lowered
    assert "credits" not in lowered
    for jargon in ["AI-офис", "agent dashboard", "frontend-preview"]:
        assert jargon.lower().replace("ё", "е") not in lowered
    proof_line = next(line for line in response.message.splitlines() if line.startswith("Portfolio:"))
    assert "Portfolio: https://portfolio.viably.dev" in proof_line
    assert "Telegram: @ne_stoit_togo" in proof_line
    assert "Telegram-channel/AI-project" not in proof_line
    assert "@techgenai" not in response.message
    assert "GitHub: https://github.com/Glour/dashboard-ai-office" in proof_line
    assert "Yandex Disk кейсы: https://disk.yandex.ru/d/TZHMyvaIDRYoeg" in proof_line
    assert "кейсы/AI-агенты/автоматизации:" in proof_line
    assert "AI-отделы и бизнес-агенты для компаний" in proof_line
    assert "Портфолио: https://portfolio.viably.dev" not in response.message
    assert len(paragraphs) == 4
    for forbidden_char in ["–", "—", "«", "»"]:
        assert forbidden_char not in response.message
    assert check.passed is True
    assert check.issues == []


def test_extra_proof_pack_uses_known_github_case_url_when_requested():
    profile = ApplicantProfile(
        full_name="Александр Олегович",
        headline="AI automation engineer",
        cases=[
            CaseStudy(
                title="AI Automation Agent",
                stack=["Python", "AI agents", "Telegram", "Workflow automation"],
                result="собрал AI-агента для заявок, Telegram-уведомлений и CRM-автоматизации",
                url="https://github.com/aleksandr/ai-automation-agent",
            )
        ],
        portfolio_url="https://portfolio.viably.dev",
        proof_pack_url="https://disk.yandex.ru/d/TZHMyvaIDRYoeg",
        telegram="@ne_stoit_togo",
    )
    vacancy = Vacancy(
        external_id="hh-extra-proof-github",
        title="AI Automation Engineer",
        company="ProofCo",
        description=(
            "Нужен инженер для AI-агентов, Telegram и workflow automation.\n"
            "Дополнительно:\n"
            "- приложите GitHub, кейсы по AI-автоматизациям и Telegram для связи."
        ),
        url="https://hh.ru/vacancy/extra-proof-github",
        skills=["Python", "AI agents", "Telegram", "Workflow automation"],
    )

    context = ResponseContext(profile=profile, vacancy=vacancy, score=94)
    response = generate_cover_letter(context)
    check = check_cover_letter_quality(response.message, context)

    proof_line = next(line for line in response.message.splitlines() if line.startswith("Portfolio:"))
    assert "Portfolio: https://portfolio.viably.dev" in proof_line
    assert "Telegram: @ne_stoit_togo" in proof_line
    assert "GitHub: https://github.com/aleksandr/ai-automation-agent" in proof_line
    assert "Yandex Disk кейсы: https://disk.yandex.ru/d/TZHMyvaIDRYoeg" in proof_line
    assert "AI Automation Agent" in proof_line
    assert len([paragraph for paragraph in response.message.split("\n\n") if paragraph]) == 4
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
    assert "Задача, как я ее понял" in response.message
    assert "Тут нужен не пересказчик промптов" not in response.message
    assert "Если нужен человек, который доводит AI-идею" not in response.message
    assert "По описанию" not in response.message
    assert "Replit/Cursor" in response.message
    assert "MCP-серверы" in response.message
    assert "SaaS/MVP" in response.message
    assert "прикладной AI-продукт" in response.message
    assert "Из похожего опыта" not in response.message
    assert "Сейчас много работаю" not in response.message
    assert response.message.index("Задача, как я ее понял") < response.message.index("В ")
    assert len(response.message) <= 1600
    assert "Что у вас обозначено как важное" not in response.message
    assert "По стеку из вакансии" not in response.message
    assert check.passed is True
    assert check.issues == []


def test_non_agentic_generation_avoids_awkward_around_focus_and_deploy_repetition():
    profile = ApplicantProfile(
        full_name="Александр Олегович",
        headline="Backend engineer",
        cases=[
            CaseStudy(
                title="Backend API platform",
                stack=["Python", "FastAPI", "PostgreSQL", "CI/CD"],
                result="строил API, интеграции, PostgreSQL, тесты и релизный процесс",
            )
        ],
        portfolio_url="https://portfolio.viably.dev",
    )
    vacancy = Vacancy(
        external_id="hh-non-agentic-product-ci",
        title="Backend Python Developer",
        company="ProductCo",
        description=(
            "Что важно: продуктовое мышление, CI/CD, самостоятельный запуск и деплой, "
            "API, интеграции, PostgreSQL и тесты."
        ),
        url="https://hh.ru/vacancy/non-agentic-product-ci",
        skills=["Python", "FastAPI", "PostgreSQL", "CI/CD"],
    )

    context = ResponseContext(profile=profile, vacancy=vacancy, score=91)
    response = generate_cover_letter(context)
    check = check_cover_letter_quality(response.message, context)
    lowered = response.message.lower()

    assert len([paragraph for paragraph in response.message.split("\n\n") if paragraph]) == 4
    assert "backend-разработка" in response.message
    assert "вокруг продуктовое мышление" not in lowered
    assert "вокруг самостоятельный" not in lowered
    assert not re.search(r"\bвокруг\s+[а-яё]", lowered)
    assert "Увидел вакансию" not in response.message
    assert "По описанию" not in response.message
    assert "контур" not in lowered
    assert "«" not in response.message and "»" not in response.message
    assert "—" not in response.message and "–" not in response.message
    assert _deploy_word_count(response.message) <= 2
    assert check.passed is True
    assert check.issues == []


def test_quality_gate_rejects_bad_around_focus_and_repeated_deploy_wording():
    profile = ApplicantProfile(
        headline="Backend engineer",
        cases=[CaseStudy(title="Backend API platform", stack=["Python", "CI/CD"], result="API and releases")],
        portfolio_url="https://portfolio.viably.dev",
    )
    vacancy = Vacancy(
        external_id="hh-bad-around-focus",
        title="Backend Python Developer",
        company="ProductCo",
        description="Что важно: продуктовое мышление, CI/CD, самостоятельный запуск и деплой.",
        url="https://hh.ru/vacancy/bad-around-focus",
        skills=["Python", "CI/CD"],
    )
    stale = (
        "Здравствуйте!\n\n"
        "Задача, как я ее понял: продуктовое мышление, CI/CD и деплой.\n\n"
        "В Backend API platform работал с Python и CI/CD: деплой, тесты и API.\n\n"
        "Здесь буду полезен на backend-части вокруг продуктовое мышление: "
        "вокруг самостоятельный запуск, деплой, продуктовое мышление, продуктовое мышление и продуктовое мышление.\n"
        "Портфолио: https://portfolio.viably.dev"
    )

    check = check_cover_letter_quality(stale, ResponseContext(profile=profile, vacancy=vacancy, score=90))

    assert check.passed is False
    assert "awkward_around_phrase" in check.issues
    assert "repeated_deploy_wording" in check.issues
    assert "repeated_focus_wording" in check.issues


def test_agentic_cover_letters_use_vacancy_specific_intro_and_closing():
    profile = default_applicant_profile()
    product_vacancy = Vacancy(
        external_id="hh-agentic-product",
        title="AI Product Engineer",
        company="Product AI",
        description=(
            "Что важно: быстрые SaaS/MVP-гипотезы, Replit, MCP, prompt engineering, тестирование, "
            "самостоятельный запуск и AI-агенты для внутренних продуктов."
        ),
        url="https://hh.ru/vacancy/agentic-product",
        skills=["AI agents", "MVP", "Replit", "MCP", "Prompt engineering"],
    )
    platform_vacancy = Vacancy(
        external_id="hh-agentic-platform",
        title="AI Platform Engineer / LLM Serving",
        company="Platform AI",
        description=(
            "Что важно: AI Platform, LLM serving, Kubernetes, GPU inference, observability, deploy, "
            "monitoring, RAG и AgentOps для production AI-сервисов."
        ),
        url="https://hh.ru/vacancy/agentic-platform",
        skills=["LLM", "RAG", "Kubernetes", "GPU", "AgentOps", "Monitoring"],
    )

    product_context = ResponseContext(profile=profile, vacancy=product_vacancy, score=94)
    platform_context = ResponseContext(profile=profile, vacancy=platform_vacancy, score=94)
    product_response = generate_cover_letter(product_context)
    platform_response = generate_cover_letter(platform_context)

    def first_and_closing(message: str) -> tuple[str, str]:
        paragraphs = [paragraph for paragraph in message.split("\n\n") if paragraph]
        closing = next(paragraph for paragraph in reversed(paragraphs) if not paragraph.startswith(("Портфолио:", "Сайт:")))
        return paragraphs[1], closing

    old_intro = "Тут нужен не пересказчик промптов, а человек, который быстро превращает идею в рабочий AI-продукт."
    old_closing = "Если нужен человек, который доводит AI-идею до рабочего продукта и спокойно режет лишнюю магию вокруг vibe coding, готов поговорить."
    product_first, product_closing = first_and_closing(product_response.message)
    platform_first, platform_closing = first_and_closing(platform_response.message)

    assert old_intro not in product_response.message
    assert old_intro not in platform_response.message
    assert old_closing not in product_response.message
    assert old_closing not in platform_response.message
    assert product_first != platform_first
    assert product_closing != platform_closing
    assert "глубокий GPU/model serving" in platform_response.message
    assert "не мой основной" in platform_response.message or "не выдаю за основной" in platform_response.message
    assert len([paragraph for paragraph in product_response.message.split("\n\n") if paragraph]) == 4
    assert len([paragraph for paragraph in platform_response.message.split("\n\n") if paragraph]) == 4
    assert check_cover_letter_quality(product_response.message, product_context).passed is True
    assert check_cover_letter_quality(platform_response.message, platform_context).passed is True


def test_devops_ai_cover_letter_excludes_wildberries_gpt35_legacy_case_and_template_phrases():
    legacy_case = CaseStudy(
        title="Сервис генерации описаний для Wildberries",
        role="Backend Developer / DevOps",
        period="2024",
        description="Автоматическая генерация описаний товаров с использованием GPT-3.5-turbo",
        stack=["Python", "FastAPI", "Docker", "DevOps", "GPT"],
        result="миграция API, оптимизация расходов и решение блокировок",
    )
    current_case = CaseStudy(
        title="Hermes Operator Contour — AgentOps Runtime",
        role="AI Infrastructure Engineer",
        period="2025-2026",
        description=(
            "AgentOps runtime: Telegram gateway, memory, retrieval, cron health checks, "
            "reports, Docker deploy и recovery после сбоев"
        ),
        stack=["Python", "Docker", "LLM", "RAG", "AgentOps", "CI/CD"],
        result="рабочий операторский процесс для AI-агентов с мониторингом и безопасными релизами",
    )
    profile = ApplicantProfile(
        headline="Python backend / AI Platform / DevOps engineer",
        strengths=["строю backend и AI-инфраструктуру", "довожу сервисы до production-support"],
        cases=[
            legacy_case,
            current_case,
            CaseStudy(
                title="Viably — AI Product Platform",
                role="Backend Engineer",
                period="2025-2026",
                description="AI generation pipeline, FastAPI backend, PostgreSQL, Redis, Docker и production-инфраструктура",
                stack=["FastAPI", "PostgreSQL", "Redis", "Docker", "LLM"],
                result="production AI product platform",
            ),
        ],
        portfolio_url="https://portfolio.viably.dev",
        proof_pack_url="https://disk.yandex.ru/d/example",
    )
    vacancy = Vacancy(
        external_id="hh-devops-ai-legacy-regression",
        title="DevOps / Backend Engineer for GPT AI Platform",
        company="AI Infra",
        description=(
            "Нужен DevOps/backend инженер для AI-платформы: Python, FastAPI, Docker, CI/CD, LLM/GPT, "
            "RAG, мониторинг и production support. При отклике покажите кейсы AI-проектов и автоматизаций."
        ),
        url="https://hh.ru/vacancy/devops-ai-legacy-regression",
        skills=["Python", "FastAPI", "Docker", "CI/CD", "LLM", "GPT", "DevOps"],
    )

    selected_cases = _best_cases(profile, vacancy, limit=5)
    proof_titles = _proof_case_titles([legacy_case, current_case], {"cases", "ai_projects"})
    context = ResponseContext(profile=profile, vacancy=vacancy, score=94)
    response = generate_cover_letter(context)
    check = check_cover_letter_quality(response.message, context)
    combined = "\n".join([response.message, *response.facts_used, ", ".join(proof_titles)]).lower()

    assert legacy_case not in selected_cases
    assert "wildberries" not in combined
    assert "gpt-3.5" not in combined
    assert "сервис генерации описаний" not in combined
    assert "Hermes" in response.message or "Viably" in response.message
    assert "кейсы/AI-агенты/автоматизации" in response.message
    for phrase in LEGACY_REPEATED_TEMPLATE_PHRASES:
        assert phrase not in response.message
    assert check.passed is True
    assert check.issues == []


def test_cover_letter_quality_gate_rejects_wildberries_gpt35_legacy_case_reference():
    profile = ApplicantProfile(
        headline="Python backend / AI Platform engineer",
        cases=[
            CaseStudy(
                title="Hermes Operator Contour",
                stack=["Python", "Docker", "LLM"],
                result="AgentOps runtime and production support",
            )
        ],
        portfolio_url="https://portfolio.viably.dev",
    )
    vacancy = Vacancy(
        external_id="hh-devops-ai-bad-legacy-template",
        title="DevOps / Backend Engineer for GPT AI Platform",
        company="AI Infra",
        description="Нужны Python, Docker, LLM/GPT, RAG, мониторинг и production support.",
        url="https://hh.ru/vacancy/devops-ai-bad-legacy-template",
        skills=["Python", "Docker", "LLM", "GPT"],
    )
    bad_template = (
        "Здравствуйте!\n\n"
        "Задача, как я ее понял: DevOps/backend для GPT AI Platform, Python, Docker и production support.\n\n"
        "В Сервис генерации описаний для Wildberries делал генерацию описаний товаров с использованием GPT-3.5-turbo.\n\n"
        "Здесь буду полезен на AI backend части: LLM/RAG, интеграции, проверки и поддержка после запуска.\n"
        "Портфолио: https://portfolio.viably.dev"
    )

    check = check_cover_letter_quality(bad_template, ResponseContext(profile=profile, vacancy=vacancy, score=90))

    assert check.passed is False
    assert "stale_legacy_case" in check.issues
    assert "stale_model_reference" in check.issues


def test_cover_letter_quality_gate_rejects_inactive_public_channel_reference():
    profile = ApplicantProfile(
        headline="AI automation engineer",
        cases=[CaseStudy(title="AI agents", stack=["Python", "Telegram"], result="AI automation")],
        portfolio_url="https://portfolio.viably.dev",
        telegram="@ne_stoit_togo",
    )
    vacancy = Vacancy(
        external_id="hh-ai-proof-pack-inactive-channel",
        title="AI Automation Engineer",
        company="AI Infra",
        description="При отклике покажите Telegram-канал, AI-проекты и автоматизации.",
        url="https://hh.ru/vacancy/ai-proof-pack-inactive-channel",
        skills=["Python", "Telegram", "AI agents"],
    )
    bad_template = (
        "Здравствуйте!\n\n"
        "Задача, как я ее понял: AI-автоматизации и Telegram.\n\n"
        "В AI agents работал с Python и Telegram: делал AI automation.\n\n"
        "Portfolio: https://portfolio.viably.dev; Telegram: @ne_stoit_togo; "
        "Telegram-channel/AI-project: @techgenai"
    )

    check = check_cover_letter_quality(bad_template, ResponseContext(profile=profile, vacancy=vacancy, score=90))

    assert check.passed is False
    assert "inactive_public_channel_reference" in check.issues


def test_non_agentic_cover_letter_does_not_use_repeated_generic_template_or_random_fpv_case():
    profile = default_applicant_profile()
    vacancy = Vacancy(
        external_id="hh-lead-data-engineer",
        title="Lead Data Engineer",
        company="DataCo",
        description=(
            "Нужен Lead Data Engineer: построение DWH, Airflow, Spark, Kafka, data pipelines, "
            "качество данных и управление командой data engineering."
        ),
        url="https://hh.ru/vacancy/lead-data-engineer",
        skills=["Python", "Airflow", "Spark", "Kafka", "DWH"],
    )

    context = ResponseContext(profile=profile, vacancy=vacancy, score=92)
    response = generate_cover_letter(context)
    bad_template = (
        "Здравствуйте! Увидел вакансию Lead Data Engineer. По смыслу это близко к тому, чем я сейчас занимаюсь: "
        "быстрые SaaS/MVP-гипотезы, memory/retrieval, CI/CD, production-инфраструктура и SaaS.\n\n"
        "Ближайший похожий кейс у меня FPV40 Campus (2025–2026). Там работал с CI/CD: делал "
        "Полноценная LMS-платформа с микросервисной архитектурой для онлайн-обучения управлению FPV-дронами.\n\n"
        "Могу быстро включиться: разобрать требования, предложить план реализации, собрать первый рабочий контур "
        "и дальше развивать систему итерациями.\n\n"
        "Готов подключиться и быстро разобрать, что у вас сейчас есть, а что лучше усилить первым.\n\n"
        "Портфолио: https://portfolio.viably.dev"
    )
    bad_check = check_cover_letter_quality(bad_template, context)

    assert "По смыслу это близко к тому, чем я сейчас занимаюсь" not in response.message
    assert "Могу быстро включиться: разобрать требования" not in response.message
    assert "Готов подключиться и быстро разобрать" not in response.message
    assert "Ближайший похожий кейс у меня FPV40 Campus" not in response.message
    assert bad_check.passed is False
    assert "generic_repeated_template" in bad_check.issues
    assert "irrelevant_fpv40_case" in bad_check.issues
    assert "forbidden_typography" in bad_check.issues


def test_generic_backend_cover_letter_uses_stronger_product_case_instead_of_fpv40_stack_match():
    profile = default_applicant_profile()
    vacancy = Vacancy(
        external_id="hh-generic-backend-fpv40-regression",
        title="Python Backend Developer",
        company="BackendCo",
        description=(
            "Нужна backend-разработка: API, интеграции, данные, тесты, релизы и поддержка. "
            "В требованиях отдельно: самостоятельный запуск проектов, быстрые SaaS/MVP-гипотезы, "
            "React, Docker, GitHub Actions, CI/CD и Telegram Bots."
        ),
        url="https://hh.ru/vacancy/generic-backend-fpv40-regression",
        skills=["React", "Docker", "GitHub Actions", "CI/CD", "Telegram Bots"],
    )

    selected_cases = _best_cases(profile, vacancy, limit=3)
    context = ResponseContext(profile=profile, vacancy=vacancy, score=91)
    response = generate_cover_letter(context)
    check = check_cover_letter_quality(response.message, context)
    combined = "\n".join([response.message, *response.facts_used]).lower()

    assert selected_cases
    assert not selected_cases[0].title.startswith("FPV40")
    assert "fpv40" not in combined
    assert any(title in response.message for title in ["Viably", "HeadHunter CRM Agent", "whynotai", "Transoff"])
    assert "FastAPI" in response.message
    assert "PostgreSQL" in response.message
    assert check.passed is True
    assert check.issues == []


def test_cover_letter_quality_gate_rejects_legacy_agentic_template_phrases():
    profile = ApplicantProfile(
        headline="AI Infrastructure Engineer",
        cases=[CaseStudy(title="Vibegent", stack=["AI agents", "LLM"], result="AI-agent platform")],
        portfolio_url="https://portfolio.viably.dev",
    )
    vacancy = Vacancy(
        external_id="hh-agentic-legacy-template",
        title="AI Agent Engineer",
        company="Example AI",
        description="Нужно строить AI-агентов, LLM-интеграции, RAG и AgentOps.",
        url="https://hh.ru/vacancy/agentic-legacy-template",
        skills=["AI agents", "LLM", "RAG", "AgentOps"],
    )
    stale = (
        "Здравствуйте! Увидел вакансию AI Agent Engineer. "
        "Тут нужен не пересказчик промптов, а человек, который быстро превращает идею в рабочий AI-продукт.\n\n"
        "В Vibegent делал LLM-инфраструктуру и AI-agent platform.\n\n"
        "Если нужен человек, который доводит AI-идею до рабочего продукта и спокойно режет лишнюю магию вокруг vibe coding, готов поговорить.\n\n"
        "Портфолио: https://portfolio.viably.dev"
    )

    check = check_cover_letter_quality(stale, ResponseContext(profile=profile, vacancy=vacancy, score=90))

    assert check.passed is False
    assert "generic_repeated_template" in check.issues


def test_cover_letter_quality_gate_rejects_robotic_phrases_requested_for_regression():
    profile = ApplicantProfile(
        headline="AI Infrastructure Engineer",
        cases=[CaseStudy(title="Vibegent", stack=["AI agents", "LLM"], result="AI-agent platform")],
        portfolio_url="https://portfolio.viably.dev",
    )
    vacancy = Vacancy(
        external_id="hh-robotic-requested",
        title="AI Backend Engineer",
        company="Example AI",
        description="Нужны LLM-интеграции, RAG, API, тесты и деплой.",
        url="https://hh.ru/vacancy/robotic-requested",
        skills=["LLM", "RAG", "API"],
    )
    stale = (
        "Здравствуйте! Увидел вакансию AI Backend Engineer. По описанию держал бы фокус на AgentOps.\n\n"
        "В Vibegent делал LLM-интеграции.\n\n"
        "Дальше собрал бы проверяемый контур по вашему контуру, практичный план первых шагов "
        "и понятный возврат результата владельцу.\n\n"
        "Портфолио: https://portfolio.viably.dev"
    )

    check = check_cover_letter_quality(stale, ResponseContext(profile=profile, vacancy=vacancy, score=90))

    assert check.passed is False
    for phrase in [
        "увидел вакансию",
        "по описанию",
        "держал бы фокус",
        "проверяемый контур",
        "по вашему контуру",
        "практичный план первых шагов",
        "понятный возврат результата владельцу",
    ]:
        assert f"robotic_phrase:{phrase}" in check.issues


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


def test_cover_letter_quality_gate_rejects_forbidden_typography():
    profile = ApplicantProfile(
        headline="AI Infrastructure Engineer",
        cases=[CaseStudy(title="Vibegent", stack=["LLM"], result="LLM-инфраструктура")],
        portfolio_url="https://portfolio.viably.dev",
    )
    vacancy = Vacancy(
        external_id="hh-forbidden-typography",
        title="AI Engineer",
        company="Example",
        description="Нужно интегрировать LLM в продукт.",
        url="https://hh.ru/vacancy/forbidden-typography",
        skills=["LLM"],
    )
    bad_letter = (
        "Здравствуйте! Увидел вакансию «AI Engineer». "
        "В Vibegent (2025–2026) делал LLM — инфраструктуру.\n\n"
        "Портфолио: https://portfolio.viably.dev"
    )

    check = check_cover_letter_quality(bad_letter, ResponseContext(profile=profile, vacancy=vacancy, score=90))

    assert check.passed is False
    assert "forbidden_typography" in check.issues


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
