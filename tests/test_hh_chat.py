from app.hh_chat import (
    ExternalFormResult,
    HHChatReplyState,
    HHChatRunner,
    extract_external_targets,
    extract_google_form_links,
    format_external_handoff_alert,
    format_external_handoff_alert_messages,
    generate_hh_chat_reply,
    is_external_interview_link,
    is_google_form_url,
    is_reply_candidate,
    preview_from_raw,
)
from app.responses import ApplicantProfile, CaseStudy


class FakeLocator:
    def __init__(self, page, selector: str):
        self.page = page
        self.selector = selector

    def count(self):
        if self.selector == "body":
            return 1
        return 1 if self.selector in self.page.available_selectors else 0

    def fill(self, value: str):
        self.page.calls.append(("fill", self.selector, value))
        self.page.pending_message = value

    def click(self):
        self.page.calls.append(("click", self.selector))
        if self.selector == '[data-qa="chatik-do-send-message"]':
            self.page.sent_messages.append(self.page.pending_message)
            self.page.body_text = f"{self.page.body_text}\n{self.page.pending_message}"

    def is_visible(self):
        return self.selector in self.page.visible_selectors

    def inner_text(self):
        return self.page.body_text if self.selector == "body" else ""


class FakePage:
    def __init__(self):
        self.url = "https://hh.ru/chat"
        self.calls = []
        self.preview_rows = [
            {
                "href": "https://hh.ru/chat/abc",
                "dataQa": "chatik-open-chat-abc",
                "text": "AgentCo\nПодскажите, актуально ли предложение и какой опыт с Python?",
            }
        ]
        self.body_text = ""
        self.chat_body = "Работодатель\nПодскажите, актуально ли предложение и какой опыт с Python?"
        self.chat_messages = [
            {"text": "Подскажите, актуально ли предложение и какой опыт с Python?", "isMine": False}
        ]
        self.pending_message = ""
        self.sent_messages = []
        self.available_selectors = {
            '[data-qa="chatik-new-message-text"]',
            '[data-qa="chatik-do-send-message"]',
        }
        self.visible_selectors = set()

    def goto(self, url: str, wait_until: str = "domcontentloaded"):
        self.calls.append(("goto", url, wait_until))
        self.url = url
        if "/chat/abc" in url:
            self.body_text = self.chat_body

    def wait_for_load_state(self, state: str):
        self.calls.append(("wait", state))

    def wait_for_timeout(self, ms: int):
        self.calls.append(("pause", ms))

    def locator(self, selector: str):
        return FakeLocator(self, selector)

    def evaluate(self, expression: str):
        if "chatik-open-chat" in expression:
            return self.preview_rows
        if "chatik-chat-message-" in expression or "chat-bubble-text" in expression:
            return self.chat_messages
        if "message_my" in expression:
            return self.sent_messages
        return 0


class FakeFormHandler:
    def __init__(self, status: str = "filled_not_submitted"):
        self.status = status
        self.calls = []

    def handle_google_form(self, request, *, submit: bool = False):
        self.calls.append((request, submit))
        return ExternalFormResult(
            status=self.status,
            message=f"form {self.status}",
            url=request.form_url,
            filled_fields=2,
            submitted=self.status == "submitted",
        )


class FakeNotifier:
    def __init__(self):
        self.alerts = []

    def send_alert(self, alert):
        self.alerts.append(alert)


def _profile():
    return ApplicantProfile(
        headline="AI Agent Systems / AgentOps / Full-stack AI Infrastructure",
        strengths=["строю production-контуры для AI-агентов"],
        cases=[
            CaseStudy(
                title="Viably",
                stack=["Python", "FastAPI", "React", "Next.js", "PostgreSQL", "Docker", "LLM", "RAG"],
                result="AI platform",
            )
        ],
        portfolio_url="https://portfolio.viably.dev",
    )


def test_hh_chat_candidate_detection_skips_chips_and_closed_statuses():
    assert is_reply_candidate("Подскажите, готовы ли обсудить вакансию?") is True
    assert (
        is_reply_candidate(
            "Добрый день! Пожалуйста,укажите уровень дохода на который вы ориентируетесь.Спасибо!"
        )
        is True
    )
    assert is_reply_candidate("Какой график работы?") is False
    assert is_reply_candidate("Можно без опыта?") is False
    assert is_reply_candidate("У меня есть профильный опыт") is False
    assert is_reply_candidate("Могу работать в гибком графике") is False
    assert is_reply_candidate("Где находится место работы?") is False
    assert is_reply_candidate("BIM/Revit: production-опыта с Revit API не было") is False
    assert is_reply_candidate("По финтеху: делал платежные и биллинговые контуры") is False
    assert is_reply_candidate("Рассмотрим ваше резюме. Если навыки и опыт подойдут, мы свяжемся") is False
    assert is_reply_candidate("Всё зафиксировал, передаю информацию работодателю") is False
    assert is_reply_candidate("Спасибо, всё записал") is False
    assert is_reply_candidate("Спасибо за уделённое время") is False
    assert is_reply_candidate("Ваши ответы отправлены работодателю") is False
    assert is_reply_candidate("Представитель работодателя изучит резюме") is False
    assert is_reply_candidate("Если ваш отклик его заинтересует, он свяжется с вами") is False
    assert is_reply_candidate("• писать в сопроводительном сообщении, что сможете без проблем приезжать") is False


def test_hh_chat_preview_ignores_unread_badge_line():
    preview = preview_from_raw(
        {
            "href": "https://hh.ru/chat/5338812237",
            "dataQa": "chatik-open-chat-5338812237",
            "text": "Business Development Manager\n14:30\nAdSensor\nКакой у вас уровень англ?\n2",
        }
    )

    assert preview is not None
    assert preview.preview == "Какой у вас уровень англ?"
    assert is_reply_candidate(preview.preview) is True


def test_extracts_google_forms_and_external_targets_without_mixing_lanes():
    text = (
        "Заполните анкету https://forms.gle/abc и потом напишите в Telegram "
        "@mariahuntcode. Сайт компании https://example.com/interview"
    )

    assert extract_google_form_links(text) == ["https://forms.gle/abc"]
    assert is_google_form_url("https://docs.google.com/forms/d/e/abc/viewform") is True
    targets = extract_external_targets(text)

    assert [target.kind for target in targets] == ["external_url", "telegram_handle"]
    assert targets[0].value == "https://example.com/interview"
    assert targets[1].value == "@mariahuntcode"


def test_generate_hh_chat_reply_handles_language_salary_and_sales_honestly():
    english = generate_hh_chat_reply("Какой у вас уровень англ?", _profile())
    assert "отдельный уровень не указан" in english.message
    assert "english_honesty" in english.reasons

    salary = generate_hh_chat_reply("Какую заработную плату вы хотели бы иметь на данной должности?", _profile())
    assert "300-350" in salary.message
    assert "salary" in salary.reasons

    income = generate_hh_chat_reply(
        "Добрый день! Пожалуйста,укажите уровень дохода на который вы ориентируетесь.Спасибо!",
        _profile(),
    )
    assert "300-350" in income.message
    assert income.reasons == ["salary"]
    assert "generic" not in income.reasons

    sales = generate_hh_chat_reply(
        "Расскажите, пожалуйста, есть ли у вас опыт B2B-продаж в enterprise-сегменте и сколько лет вы этим занимаетесь?",
        _profile(),
    )
    assert "не буду придумывать" in sales.message
    assert "sales_honesty" in sales.reasons
    assert "salary" not in sales.reasons
    assert "stack_experience" not in sales.reasons

    b2b_contract = generate_hh_chat_reply(
        "У вас интересное резюме. Подскажите, где вы проживаете? "
        "Открыты ли вы к сотрудничеству через B2B контракт?",
        _profile(),
    )
    assert "Проживаю:" in b2b_contract.message
    assert "B2B-контракту открыт" in b2b_contract.message
    assert "B2B-продаж" not in b2b_contract.message
    assert "sales manager" not in b2b_contract.message
    assert "Python/FastAPI" not in b2b_contract.message
    assert b2b_contract.reasons == ["contract_logistics", "manual_required"]

    commercial_ai = generate_hh_chat_reply(
        "Расскажите, пожалуйста, сколько лет вы конкретно работали в коммерческих ML/AI проектах?",
        _profile(),
    )
    assert "с 2025 года" in commercial_ai.message
    assert "примерно 1,5 года" in commercial_ai.message
    assert "commercial_ai_years_honesty" in commercial_ai.reasons
    assert "generic" not in commercial_ai.reasons


def test_generate_hh_chat_reply_acknowledges_questionnaire_without_claiming_completion():
    draft = generate_hh_chat_reply(
        "Перед встречей с руководителем заполните пожалуйста короткий опросник. "
        "Анкета https://forms.gle/example",
        _profile(),
    )

    assert draft.message == "Здравствуйте! Спасибо, получил анкету, посмотрю."
    assert draft.reasons == ["questionnaire_ack"]
    assert "заполнил" not in draft.message.lower()


def test_generate_hh_chat_reply_handles_sap_hana_checklist_honestly():
    draft = generate_hh_chat_reply(
        "Ответьте чек-листом плюс/минус: SAP HANA trace files, Python/Go/Java/C++/Rust "
        "парсинг, SAP HANA datasource, Iceberg/Paimon, Kafka, data engineering/"
        "observability/SRE, ИП/самозанятый, outstaff, salary, location, Telegram nick.",
        _profile(),
    )

    assert "[+] Python" in draft.message
    assert "[-] Go" in draft.message
    assert "[-] Java" in draft.message
    assert "[-] C++" in draft.message
    assert "[-] Rust" in draft.message
    assert "[+/-] Data engineering / observability / SRE" in draft.message
    assert "[-] SAP HANA diagnostic/trace files" in draft.message
    assert "[-] SAP HANA как источник данных" in draft.message
    assert "[-] Iceberg/Paimon" in draft.message
    assert "[-] Apache Kafka" in draft.message
    assert "1) ИП/СЗ" in draft.message
    assert "2) Аутстафф" in draft.message
    assert "3) ЗП" in draft.message
    assert "4) Локация - [указать город/часовой пояс]" in draft.message
    assert "5) Telegram - [указать Telegram-ник]" in draft.message
    assert "300-350" in draft.message
    assert "350-450" in draft.message
    assert "Telegram-ник в профиле не указан" not in draft.message
    assert "Локация: удаленно" not in draft.message
    assert "sap_hana_checklist_honesty" in draft.reasons
    assert "manual_required" in draft.reasons


def test_generate_hh_chat_reply_handles_engineering_discipline():
    draft = generate_hh_chat_reply("Что вы уже внедряли в инженерной дисциплине?", _profile())

    assert "CI/CD" in draft.message
    assert "release gates" in draft.message
    assert "engineering_discipline" in draft.reasons


def test_generate_hh_chat_reply_handles_db_fintech_and_load_questions():
    db = generate_hh_chat_reply(
        "С какими SQL, NoSQL или векторными базами данных вы работали и интегрировали их в продакшн?",
        _profile(),
    )
    assert "PostgreSQL" in db.message
    assert "Redis" in db.message
    assert "databases" in db.reasons

    fintech = generate_hh_chat_reply("Был ли у вас опыт работы в финтехе, эквайринге или банках?", _profile())
    assert "в банке или эквайринге" in fintech.message
    assert "YooKassa/Stripe" in fintech.message
    assert "fintech_honesty" in fintech.reasons

    load = generate_hh_chat_reply(
        "Какая максимальная нагрузка (RPS или количество подключений) была у ваших production-сервисов?",
        _profile(),
    )
    assert "точный RPS" in load.message
    assert "load_honesty" in load.reasons

    postgres = generate_hh_chat_reply(
        "Какой у вас опыт оптимизации PostgreSQL: индексы, EXPLAIN, partitioning?",
        _profile(),
    )
    assert "DBA-профиль" in postgres.message
    assert "postgres_optimization_honesty" in postgres.reasons
    assert "databases" not in postgres.reasons


def test_generate_hh_chat_reply_handles_financial_models_and_agent_routing():
    financial = generate_hh_chat_reply(
        "Делали ли вы расчёт и презентацию финмодели для клиента?",
        _profile(),
    )
    assert "finance analyst" in financial.message
    assert "financial_model_honesty" in financial.reasons

    routing = generate_hh_chat_reply(
        "Приходилось ли вам разрабатывать LLM Council или сложный маршрутизатор для агентов?",
        _profile(),
    )
    assert "маршрутизация" in routing.message
    assert "agent_routing" in routing.reasons
    assert "stack_experience" not in routing.reasons


def test_generate_hh_chat_reply_handles_negotiations_and_prompt_decomposition():
    negotiations = generate_hh_chat_reply(
        "Приходилось ли вам вести многоэтапные переговоры с руководителями уровня C-level?",
        _profile(),
    )
    assert "enterprise sales manager" in negotiations.message
    assert "clevel_negotiations_honesty" in negotiations.reasons

    prompt = generate_hh_chat_reply(
        "Расскажите, как вы обычно подходите к промпт-инжинирингу и декомпозиции задач для агентов?",
        _profile(),
    )
    assert "границ ответственности" in prompt.message
    assert "prompt_decomposition" in prompt.reasons


def test_generate_hh_chat_reply_is_honest_about_unverified_stack_and_salary():
    draft = generate_hh_chat_reply(
        "Подскажите, какой опыт с Kubernetes и какие ожидания по зарплате?",
        _profile(),
    )

    assert "300-350" in draft.message
    assert "Kubernetes" in draft.message
    assert "не буду придумывать" in draft.message
    assert "—" not in draft.message
    assert "«" not in draft.message


def test_generate_hh_chat_reply_is_honest_about_ansible_deployment_automation():
    draft = generate_hh_chat_reply(
        "Расскажите, пожалуйста, был ли у вас опыт использования Ansible "
        "для автоматизации развёртывания?",
        _profile(),
    )

    assert "Ansible" in draft.message
    assert "Глубокого production опыта" in draft.message
    assert "Docker/Docker Compose" in draft.message
    assert "CI/CD" in draft.message
    assert "scripts" in draft.message
    assert "health-checks/monitoring" in draft.message
    assert draft.reasons == ["ansible_honesty"]
    assert "generic" not in draft.reasons


def test_generate_hh_chat_reply_handles_vacancy_point_stack_fit_honestly():
    draft = generate_hh_chat_reply(
        "Насколько ваш стек технологий и опыта соответствует описанному "
        "в вакансии (по каждому из 21 пункта)?",
        _profile(),
    )

    assert "Python/backend" in draft.message
    assert "PostgreSQL/Redis/Docker" in draft.message
    assert "APIs/интеграции" in draft.message
    assert "LLM/agent-инфраструктура" in draft.message
    assert "Go/Kafka/Elastic/Geo" in draft.message
    assert "не буду ставить себе плюс" in draft.message
    assert "нет самих 21 пунктов" in draft.message
    assert "пришлите список в чат" in draft.message
    assert "построчно" in draft.message
    assert draft.reasons == ["vacancy_point_fit_honesty"]
    assert "stack_experience" not in draft.reasons
    assert "generic" not in draft.reasons


def test_generate_hh_chat_reply_answers_django_fastapi_screening_instead_of_point_template():
    draft = generate_hh_chat_reply(
        "Есть ли у вас коммерческий опыт одновременно с Django и FastAPI? "
        "Для Django: работа с моделями, миграциями в production, DRF? "
        "Для FastAPI: асинхронные эндпоинты, WebSockets, dependency injection? "
        "Как вы обычно оптимизируете медленный запрос в Django SQL или ORM? "
        "Насколько комфортен график МСК+2 с 09:00 до 18:00? "
        "Вилка по позиции 120 000 ₽. Подходит ли вам такой уровень?",
        _profile(),
    )

    assert "FastAPI" in draft.message
    assert "Django/DRF" in draft.message
    assert "dependency injection" in draft.message
    assert "EXPLAIN" in draft.message
    assert "select_related/prefetch_related" in draft.message
    assert "120 000" in draft.message
    assert "300-350" in draft.message
    assert "21 пункт" not in draft.message
    assert "Go/Kafka/Elastic/Geo" not in draft.message
    assert draft.reasons == ["django_fastapi_screening", "salary", "format"]
    assert "vacancy_point_fit_honesty" not in draft.reasons


def test_generate_hh_chat_reply_is_honest_about_kubernetes_and_openstack():
    draft = generate_hh_chat_reply(
        "Есть ли практический опыт работы с Kubernetes или OpenStack?",
        _profile(),
    )

    assert "Kubernetes" in draft.message
    assert "OpenStack" in draft.message
    assert "глубокий production опыт" in draft.message
    assert "honesty_unknown_stack" in draft.reasons
    assert "generic" not in draft.reasons


def test_generate_hh_chat_reply_is_honest_about_hadoop_experience():
    draft = generate_hh_chat_reply(
        "Есть ли у вас опыт работы с Hadoop и его компонентами?",
        _profile(),
    )

    assert "Hadoop" in draft.message
    assert "глубокий production опыт" in draft.message
    assert "honesty_unknown_stack" in draft.reasons
    assert "generic" not in draft.reasons


def test_hh_chat_external_telegram_handle_instruction_is_blocked(tmp_path):
    handoff = "Отправь пожалуйста мне в телеграм @mariahuntcode небольшую анкету для интервью"
    assert is_external_interview_link(handoff) is True
    assert is_reply_candidate(handoff) is True
    assert is_external_interview_link(
        "В портфолио есть Telegram bot и интеграция с @BotFather как технологический пример"
    ) is False

    page = FakePage()
    page.preview_rows = [
        {
            "href": "https://hh.ru/chat/telegram-handoff",
            "dataQa": "chatik-open-chat-telegram-handoff",
            "text": f"Recruiter\n{handoff}",
        }
    ]
    page.chat_body = f"Работодатель\n{handoff}"
    page.chat_messages = [{"text": handoff, "isMine": False}]
    state = HHChatReplyState(tmp_path / "state.json")
    runner = HHChatRunner(page=page, profile=_profile(), state=state)

    result = runner.run(send=False, limit=1)

    assert result.blocked == 1
    assert result.drafted == 0
    assert result.statuses == ["blocked_external_interview"]
    reply = result.replies[0]
    assert reply["reply"].startswith("Здравствуйте! Я Александр Олегович.")
    assert "Ответы по анкете:" not in reply["reply"]
    assert reply["external_targets"] == [
        {"kind": "telegram_handle", "value": "@mariahuntcode", "url": None}
    ]
    assert reply["external_result"]["prepared_answers"] == []
    assert not any(call[0] == "fill" for call in page.calls)


def test_hh_chat_runner_blocks_manual_required_draft_even_when_send_enabled(tmp_path):
    page = FakePage()
    checklist = (
        "Просьба ответить на полный чек-лист: SAP HANA trace files, Python/Go/Java/C++/Rust, "
        "Iceberg/Paimon, Kafka, data engineering/observability/SRE. "
        "Условия: ИП/СЗ, аутстафф, ЗП, локация, Telegram nick."
    )
    page.preview_rows = [
        {
            "href": "https://hh.ru/chat/sap",
            "dataQa": "chatik-open-chat-sap",
            "text": f"Recruiter\n{checklist}",
        }
    ]
    page.chat_body = f"Работодатель\n{checklist}"
    page.chat_messages = [{"text": checklist, "isMine": False}]
    state = HHChatReplyState(tmp_path / "state.json")
    runner = HHChatRunner(page=page, profile=_profile(), state=state)

    result = runner.run(send=True, limit=1)

    assert result.blocked == 1
    assert result.sent == 0
    assert result.statuses == ["blocked_manual_review"]
    assert "manual_required" in result.replies[0]["message"]
    assert "[указать Telegram-ник]" in result.replies[0]["reply"]
    assert not any(call[0] == "fill" for call in page.calls)


def test_hh_chat_runner_drafts_without_sending(tmp_path):
    page = FakePage()
    state = HHChatReplyState(tmp_path / "state.json")
    runner = HHChatRunner(page=page, profile=_profile(), state=state)

    result = runner.run(send=False, limit=1)

    assert result.scanned == 1
    assert result.candidates == 1
    assert result.drafted == 1
    assert result.sent == 0
    assert not any(call[0] == "fill" for call in page.calls)
    assert result.replies[0]["reply"].startswith("Здравствуйте!")


def test_hh_chat_runner_deep_scans_interview_preview_and_uses_inside_question(tmp_path):
    page = FakePage()
    page.preview_rows = [
        {
            "href": "https://hh.ru/chat/tilda",
            "dataQa": "chatik-open-chat-tilda",
            "text": "Администратор сайта Tilda и Shopify\nСобеседование",
        }
    ]
    page.chat_body = (
        "Работодатель\nПеред встречей с руководителем заполните пожалуйста короткий "
        "опросник. Анкета https://forms.gle/example"
    )
    page.chat_messages = [
        {
            "text": (
                "Перед встречей с руководителем заполните пожалуйста короткий опросник. "
                "Анкета https://forms.gle/example"
            ),
            "isMine": False,
        }
    ]
    state = HHChatReplyState(tmp_path / "state.json")
    runner = HHChatRunner(page=page, profile=_profile(), state=state)

    result = runner.run(send=False, limit=1)

    assert result.scanned == 1
    assert result.candidates == 1
    assert result.drafted == 1
    assert any(call[0] == "goto" and "/chat/tilda" in call[1] for call in page.calls)
    assert result.replies[0]["question"].startswith("Перед встречей")
    assert result.statuses == ["google_form_draft"]
    assert result.replies[0]["reply"].startswith("Здравствуйте! Я Александр Олегович.")
    assert result.replies[0]["external_targets"] == [
        {
            "kind": "google_form",
            "value": "https://forms.gle/example",
            "url": "https://forms.gle/example",
        }
    ]
    assert result.replies[0]["external_result"] == {"prepared_answers": []}
    assert result.replies[0]["message"] == "external_copy_paste"


def test_hh_chat_external_alert_is_sent_with_notifier_and_deduplicated(tmp_path):
    handoff = "Отправь пожалуйста мне в телеграм @mariahuntcode небольшую анкету для интервью"
    page = FakePage()
    page.preview_rows = [
        {
            "href": "https://hh.ru/chat/telegram-handoff",
            "dataQa": "chatik-open-chat-telegram-handoff",
            "text": f"Recruiter\n{handoff}",
        }
    ]
    page.chat_body = f"Работодатель\n{handoff}"
    page.chat_messages = [{"text": handoff, "isMine": False}]
    state = HHChatReplyState(tmp_path / "state.json")
    notifier = FakeNotifier()
    runner = HHChatRunner(page=page, profile=_profile(), state=state, alert_notifier=notifier)

    result = runner.run(send=True, limit=1)

    assert result.statuses == ["external_alert_sent"]
    assert len(notifier.alerts) == 1
    alert_text = format_external_handoff_alert(notifier.alerts[0])
    alert_messages = format_external_handoff_alert_messages(notifier.alerts[0])
    assert len(alert_messages) == 3
    assert alert_messages[0].startswith("Внешний контакт из HH\n\nВакансия:")
    assert "\n\nКуда перейти:\n- Telegram: @mariahuntcode" in alert_messages[0]
    assert alert_messages[1].startswith("Сообщение работодателя:\n\n")
    assert alert_messages[2].startswith("Готовый текст для вставки:\n\n")
    assert "Внешний контакт из HH" in alert_text
    assert "@mariahuntcode" in alert_text
    assert handoff in alert_text
    assert "Ответы по анкете:" not in result.replies[0]["reply"]
    assert not any(call[0] == "fill" for call in page.calls)

    duplicate = runner.run(send=True, limit=1)

    assert duplicate.statuses == ["skipped_external_alert_duplicate"]
    assert duplicate.skipped == 1
    assert len(notifier.alerts) == 1


def test_hh_chat_external_alert_missing_notifier_does_not_crash(tmp_path):
    handoff = "Отправь пожалуйста мне в телеграм @mariahuntcode небольшую анкету для интервью"
    page = FakePage()
    page.preview_rows = [
        {
            "href": "https://hh.ru/chat/telegram-handoff",
            "dataQa": "chatik-open-chat-telegram-handoff",
            "text": f"Recruiter\n{handoff}",
        }
    ]
    page.chat_body = f"Работодатель\n{handoff}"
    page.chat_messages = [{"text": handoff, "isMine": False}]
    state = HHChatReplyState(tmp_path / "state.json")
    runner = HHChatRunner(page=page, profile=_profile(), state=state)

    result = runner.run(send=True, limit=1)

    assert result.statuses == ["external_alert_not_configured"]
    assert result.blocked == 1
    assert result.replies[0]["reply"].startswith("Здравствуйте! Я Александр Олегович.")
    assert state.data["external"] == {}


def test_hh_chat_google_form_handler_submit_is_gated_by_external_submit(tmp_path):
    question = (
        "Перед встречей с руководителем заполните пожалуйста короткий опросник. "
        "Анкета https://forms.gle/example"
    )
    page = FakePage()
    page.preview_rows = [
        {
            "href": "https://hh.ru/chat/google-form",
            "dataQa": "chatik-open-chat-google-form",
            "text": "Recruiter\nСобеседование",
        }
    ]
    page.chat_body = f"Работодатель\n{question}"
    page.chat_messages = [{"text": question, "isMine": False}]
    state = HHChatReplyState(tmp_path / "prepare-state.json")
    handler = FakeFormHandler(status="filled_not_submitted")
    runner = HHChatRunner(
        page=page,
        profile=_profile(),
        state=state,
        external_form_handler=handler,
    )

    result = runner.run(send=True, limit=1)

    assert result.statuses == ["google_form_filled_not_submitted"]
    assert len(handler.calls) == 1
    request, submit = handler.calls[0]
    assert request.form_url == "https://forms.gle/example"
    assert submit is False
    assert result.external_submit_enabled is False

    submit_page = FakePage()
    submit_page.preview_rows = page.preview_rows
    submit_page.chat_body = page.chat_body
    submit_page.chat_messages = page.chat_messages
    submit_state = HHChatReplyState(tmp_path / "submit-state.json")
    submit_handler = FakeFormHandler(status="submitted")
    submit_runner = HHChatRunner(
        page=submit_page,
        profile=_profile(),
        state=submit_state,
        external_form_handler=submit_handler,
    )

    submit_result = submit_runner.run(send=True, limit=1, external_submit=True)

    assert submit_result.statuses == ["google_form_submitted"]
    assert len(submit_handler.calls) == 1
    submit_request, submit = submit_handler.calls[0]
    assert submit_request.form_url == "https://forms.gle/example"
    assert submit is True
    assert submit_result.external_submit_enabled is True
    assert submit_result.replies[0]["external_result"]["submitted"] is True


def test_hh_chat_runner_uses_latest_incoming_dom_message_not_outgoing(tmp_path):
    page = FakePage()
    page.preview_rows = [
        {
            "href": "https://hh.ru/chat/sap",
            "dataQa": "chatik-open-chat-sap",
            "text": "SAP HANA разработчик\nСобеседование",
        }
    ]
    incoming = (
        "Ответьте чек-листом плюс/минус: SAP HANA trace files, Python/Go/Java/C++/Rust "
        "парсинг, SAP HANA datasource, Iceberg/Paimon, Kafka, data engineering/"
        "observability/SRE, ИП/самозанятый, outstaff, salary, location, Telegram nick."
    )
    page.chat_body = f"{incoming}\nКакой у вас опыт с Kafka?"
    page.chat_messages = [
        {"text": incoming, "isMine": False},
        {"text": "Какой у вас опыт с Kafka?", "isMine": True},
    ]
    state = HHChatReplyState(tmp_path / "state.json")
    runner = HHChatRunner(page=page, profile=_profile(), state=state)

    result = runner.run(send=False, limit=1)

    assert result.blocked == 1
    assert result.drafted == 0
    assert result.replies[0]["question"] == incoming
    assert result.statuses == ["blocked_manual_review"]
    assert "sap_hana_checklist_honesty" in result.replies[0]["message"]
    assert "[-] Apache Kafka - production опыт не заявляю" in result.replies[0]["reply"]


def test_hh_chat_runner_sends_once_and_marks_state(tmp_path):
    page = FakePage()
    state = HHChatReplyState(tmp_path / "state.json")
    runner = HHChatRunner(page=page, profile=_profile(), state=state)

    result = runner.run(send=True, limit=1)

    assert result.sent == 1
    assert any(call[0] == "fill" for call in page.calls)
    assert ("click", '[data-qa="chatik-do-send-message"]') in page.calls
    assert state.data["answered"]

    second = runner.run(send=True, limit=1)

    assert second.sent == 0
    assert second.skipped == 1
    assert second.statuses == ["skipped_duplicate"]
