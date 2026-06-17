from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.scoring import Vacancy


DEFAULT_COVER_LETTER_METHODOLOGY_PATH = Path(__file__).resolve().parents[2] / "docs" / "cover-letter-methodology.md"
BUILTIN_COVER_LETTER_METHODOLOGY = """# HH cover-letter methodology

Эта инструкция - fallback для генератора черновиков HH-отклика.

## Жесткие правила

1. Приветствие всегда отдельным первым абзацем: `Здравствуйте!`
2. Не обращаться к работодателю по названию компании, ИП, ООО или бренду из карточки HH.
3. Не начинать с факта, что вакансия найдена. Сразу переходить к задаче работодателя.
4. Не выдумывать опыт, цифры, компании, стек и результаты.
5. Не пересказывать карточку HH и резюме. Нужны 2-5 смысловых ожиданий из вакансии и 1-2 точных доказательства из профиля.
6. Не ставить название вакансии в кавычки. Чаще всего название вообще не нужно в тексте.
7. Не использовать длинные тире, елочки, эмодзи, жирные мини-заголовки и списки ради списков.
8. Не писать шаблонные заходы: `заинтересовала ваша вакансия`, `имею большой опыт`, `готов обсудить детали`, `качественно и в срок`, `все это знаю`, `хорошо знаю`.
9. Не делать механические связки по стеку вроде `LLM применял в Vibegent; FastAPI применял в Viably`.
10. Не использовать обороты `Для таких задач важно не просто ...`, `не только X, но и Y` как основу текста. Один острый контраст допустим только если он точно бьет в задачу.
11. Тон живой и конкретный: без канцелярита, рекламной пены, чатбот-обвязки и слишком гладкой симметрии.
12. Портфолио, если ссылки разрешены, идет последней строкой четвертого абзаца: `Портфолио: https://portfolio.viably.dev`
13. Если блок `Дополнительно`, `при отклике`, `в сопроводительном письме` или похожая секция прямо просит GitHub, кейсы, Telegram, AI-проекты, автоматизации, презентации или своих AI-агентов, последняя строка становится компактным proof pack: Portfolio/Telegram/GitHub/Yandex Disk только из известных полей и 1-3 релевантных кейса из профиля.
14. Legacy/internal cases with Wildberries, GPT-3.5/GPT-3.5-turbo or `Сервис генерации описаний` are historical only and must never be used in HH employer-facing drafts.
15. FPV40 не использовать как универсальный backend/CI/CD/Telegram кейс. Он подходит только под FPV/дроны/БАС, LMS, EdTech, курсы и обучающие платформы. Для обычного backend/SaaS/MVP/API/интеграций сначала выбирать более точные кейсы: Viably, HeadHunter CRM Agent, whynotai, Transoff, Vibegent, AI Dev Office или другие проекты из профиля.

## Принцип

Отклик пишется от задачи работодателя, а не от желания перечислить весь опыт Александра. Сначала читаем блоки `Чем предстоит заниматься`, `Что мы ждем`, `Кого ищем`, `Что важно`, `Будет плюсом`, `Требования`. Из них берем 2-5 ожиданий и формулируем своими словами.

Опыт нужен только как доказательство под эту задачу. Лучше один точный кейс и короткая польза для работодателя, чем длинный список проектов, технологий и ролей.

## 4-абзацный скелет

```text
Здравствуйте!

Задача, как я ее понял: {1-2 предложения про реальные ожидания работодателя, без переписывания карточки}.

{1 сильный абзац с доказательством: 1-2 релевантных кейса, стек и результат только если они бьют в задачу}.

{Короткая польза и спокойное закрытие.}
Портфолио: https://portfolio.viably.dev
```

## Что подставлять

- Стек: только пересечение вакансии с реальным профилем Александра.
- Кейс: только из профиля, портфолио или сохраненного owner context, без фантазии.
- Период и роль: использовать только когда это повышает доверие, не превращать абзац в резюме-таблицу.
- AI/AgentOps/LLMOps: выбирать 1-2 самых точных доказательства из Vibegent, Viably, Hermes Operator, Heisenberg Team, OpenClaw, AI Office или похожих кейсов.
- Kwork/freelance: можно писать острее, если объявление позволяет. Дерзость должна держаться на фактах: код, архитектура, деплой, бизнес-результат.
- Площадки без внешних ссылок: портфолио не добавлять, доверие усиливать через стек, кейс и рабочий результат.
- Proof pack: если работодатель отдельно просит ссылки или подтверждения в доп. блоке, не выдумывать GitHub и не писать `GitHub`, когда URL нет; использовать portfolio_url, telegram, proof_pack_url/Yandex Disk и выбранные кейсы.

## Humanizer-pass

Перед сохранением черновика проверь текст как редактор:

- нет чатбот-обвязки: `Отличный вопрос`, `Конечно`, `надеюсь, поможет`, `дайте знать`;
- нет пустых вводных: `стоит отметить`, `важно подчеркнуть`, `следует обратить внимание`, `в заключение`;
- нет канцелярита: `в рамках`, `осуществлять`, `данный`, `на данный момент`, `в целях`;
- нет рекламного тона: `уникальный`, `по-настоящему`, `раскрывает потенциал`, если за этим нет факта;
- нет фальшивых авторитетов и раздувания значимости;
- нет шаблонной симметрии, длинных красивых выводов без конкретики и механического форматирования.
"""


@dataclass(slots=True)
class CaseStudy:
    title: str
    stack: list[str] = field(default_factory=list)
    result: str = ""
    url: str | None = None
    role: str = ""
    period: str = ""
    description: str = ""


@dataclass(slots=True)
class ApplicantProfile:
    full_name: str = "Александр Олегович"
    headline: str = "Full-stack developer"
    strengths: list[str] = field(default_factory=list)
    cases: list[CaseStudy] = field(default_factory=list)
    portfolio_url: str | None = None
    website_url: str | None = None
    github_url: str | None = None
    proof_pack_url: str | None = None
    location: str | None = None
    telegram: str | None = None
    telegram_channel: str | None = None
    age: int | None = None
    phone: str | None = None


@dataclass(slots=True)
class ResponseContext:
    profile: ApplicantProfile
    vacancy: Vacancy
    score: int


@dataclass(slots=True)
class GeneratedResponse:
    message: str
    tone: str
    estimated_fit: int
    facts_used: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CoverLetterQualityCheck:
    passed: bool
    issues: list[str] = field(default_factory=list)


def load_cover_letter_methodology(path: str | Path | None = None) -> str:
    configured_path = path or os.getenv("HH_COVER_LETTER_METHODOLOGY_PATH")
    target = Path(configured_path) if configured_path else DEFAULT_COVER_LETTER_METHODOLOGY_PATH
    try:
        return target.read_text(encoding="utf-8")
    except OSError:
        return BUILTIN_COVER_LETTER_METHODOLOGY


GENERIC_PHRASES = [
    "заинтересовала ваша вакансия",
    "имею большой опыт",
    "готов обсудить детали",
    "качественно и в срок",
    "ответственно подхожу",
    "все это знаю",
    "всё это знаю",
    "хорошо знаю",
    "для таких задач важно не просто",
    "инженерный контур вокруг агентов",
    "отличный вопрос",
    "надеюсь, это поможет",
    "дайте знать",
    "если хотите, я могу",
    "важно отметить",
    "важно подчеркнуть",
    "стоит отметить",
    "следует обратить внимание",
    "нельзя не упомянуть",
    "по своей сути",
    "в заключение",
    "в рамках данного",
    "на данный момент времени",
    "по имеющимся данным",
    "на основе имеющейся информации",
    "будущее выглядит многообещающим",
    "впереди захватывающие времена",
]

LEGACY_REPEATED_TEMPLATE_PHRASES = [
    "По смыслу это близко к тому, чем я сейчас занимаюсь",
    "Могу быстро включиться: разобрать требования",
    "Готов подключиться и быстро разобрать",
    "Из похожего опыта:",
    "Ближайший похожий кейс у меня",
    "Это тот слой",
    "Тут нужен не пересказчик промптов, а человек, который быстро превращает идею в рабочий AI-продукт.",
    "Если нужен человек, который доводит AI-идею до рабочего продукта и спокойно режет лишнюю магию вокруг vibe coding, готов поговорить.",
]

ROBOTIC_COVER_LETTER_PHRASES = [
    "увидел вакансию",
    "по описанию",
    "держал бы фокус",
    "проверяемый контур",
    "по вашему контуру",
    "контур",
    "практичный план первых шагов",
    "понятный возврат результата владельцу",
    "owner-return",
]

ANTI_AI_CHATBOT_ARTIFACTS = [
    "отличный вопрос",
    "конечно!",
    "безусловно!",
    "вы абсолютно правы",
    "надеюсь, это поможет",
    "дайте знать",
    "если хотите, я могу",
]
ANTI_AI_INTRO_PHRASES = [
    "стоит отметить",
    "важно отметить",
    "важно подчеркнуть",
    "необходимо отметить",
    "следует обратить внимание",
    "нельзя не упомянуть",
    "по своей сути",
    "в заключение",
]
ANTI_AI_BUREAUCRATIC_PHRASES = [
    "в рамках данного",
    "в рамках этой",
    "осуществлять",
    "осуществлял",
    "осуществляю",
    "данный ",
    "данная ",
    "на данный момент времени",
    "в целях",
    "вышеупомянутый",
    "имеет место быть",
]
ANTI_AI_INFLATED_PHRASES = [
    "ключевой этап",
    "играет ключевую роль",
    "играет важную роль",
    "неоценимый вклад",
    "знаменует",
    "оставляет неизгладимый след",
    "краеугольным камнем",
    "масштабные тенденции",
]
ANTI_AI_PROMO_PHRASES = [
    "может похвастаться",
    "по-настоящему уник",
    "поистине",
    "в самом сердце",
    "захватывающ",
    "непревзойден",
    "непревзойдён",
    "раскрывает потенциал",
]
ANTI_AI_FAKE_AUTHORITY_PHRASES = [
    "по мнению экспертов",
    "эксперты считают",
    "эксперты полагают",
    "ведущие издания отмечают",
    "по имеющимся данным",
    "согласно различным источникам",
]
ANTI_AI_PARTICIPLE_RE = re.compile(
    r"\b(?:подч[её]ркивая|демонстрируя|обеспечивая|отражая|способствуя|формируя|воплощая|символизируя)\b",
    re.IGNORECASE,
)
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF]")
FORBIDDEN_COVER_LETTER_TYPOGRAPHY = {"—", "–", "«", "»"}
COVER_LETTER_TYPOGRAPHY_TRANSLATION = str.maketrans(
    {
        "—": "-",
        "–": "-",
        "«": '"',
        "»": '"',
    }
)
DEPLOY_WORD_RE = re.compile(r"\b(?:депло[а-яё]*|задепло[а-яё]*|deploy[a-z-]*)\b", re.IGNORECASE)
RUSSIAN_CONTOUR_RE = re.compile(r"\bконтур[а-яё]*\b", re.IGNORECASE)
AWKWARD_AROUND_RE = re.compile(r"\bвокруг\s+(?:продуктов\w+|самостоятельн\w+|[а-яё]+(?:\s+[а-яё]+){0,3})", re.IGNORECASE)
GENERATED_PHRASE_REPLACEMENTS = [
    (re.compile(r"\bчеловек\s+в\s+контуре\b", re.IGNORECASE), "human-in-the-loop"),
    (re.compile(r"\bпроверяем(?:ый|ого|ому|ым|ом)?\s+контур[а-яё]*\b", re.IGNORECASE), "проверяемую систему"),
    (re.compile(r"\bрабоч(?:ий|его|ему|им|ем)?\s+контур[а-яё]*\b", re.IGNORECASE), "рабочую систему"),
    (re.compile(r"\bproduction-контур[а-яё]*\b", re.IGNORECASE), "production-системы"),
    (re.compile(r"\bагентн(?:ый|ые|ых|ым|ыми|ом)?\s+контур[а-яё]*\b", re.IGNORECASE), "агентные системы"),
    (re.compile(r"\bконтур[а-яё]*\b", re.IGNORECASE), "система"),
]
URL_RE = re.compile(r"https?://[^\s),;]+", re.IGNORECASE)
GITHUB_URL_RE = re.compile(r"https?://(?:www\.)?github\.com/[^\s),;]+", re.IGNORECASE)
EXTRA_PROOF_SECTION_HEADING_RE = re.compile(
    r"^(?:"
    r"дополнительно|доп\.?\s*(?:информация|материалы|вопросы|пожелания)?|"
    r"дополнительн\w+\s+(?:информация|материалы|вопросы|пожелания|требования)|"
    r"при\s+отклике|в\s+отклике|к\s+отклику|"
    r"сопроводительн\w+\s+письм\w+|"
    r"что\s+(?:приложить|показать|добавить|указать)|"
    r"важно\s+в\s+отклике|как\s+откликнуться"
    r")\b.*:?$",
    re.IGNORECASE,
)
EXTRA_PROOF_INLINE_RE = re.compile(
    r"(?:дополнительно|при\s+отклике|в\s+отклике|к\s+отклику|"
    r"в\s+сопроводительном\s+письме|сопроводительное\s+письмо|"
    r"что\s+(?:приложить|показать|добавить|указать)|важно\s+в\s+отклике)"
    r"\s*[:\-]\s*.{0,360}",
    re.IGNORECASE | re.DOTALL,
)
PROOF_REQUEST_ACTION_MARKERS = [
    "покаж",
    "укаж",
    "прилож",
    "добав",
    "пришл",
    "отправ",
    "предостав",
    "прикреп",
    "дайте",
    "ссыл",
    "контакт",
    "связ",
    "аккаунт",
    "профил",
    "репозитор",
    "код",
    "show",
    "include",
    "attach",
    "send",
    "share",
    "link",
]
STALE_LEGACY_CASE_MARKERS = [
    "wildberries",
    "сервис генерации описаний",
]
INACTIVE_PUBLIC_CHANNEL_MARKERS = [
    "@techgenai",
    "techgenai",
]
LEGACY_MODEL_REFERENCE_RE = re.compile(
    r"\b(?:"
    r"gpt[\s._-]*3(?:[\s._-]*\.?[\s._-]*5(?:[\s._-]*turbo)?|\b)|"
    r"gpt[\s._-]*35(?:[\s._-]*turbo)?|"
    r"text[\s._-]*davinci(?:[\s._-]*(?:002|003))?|"
    r"davinci[\s._-]*(?:002|003)"
    r")\b",
    re.IGNORECASE,
)


_STOP_TOKENS = {
    "для",
    "это",
    "как",
    "или",
    "что",
    "the",
    "and",
    "with",
    "lead",
    "разработка",
    "разработки",
    "опыт",
    "проект",
    "продукт",
}

_WEAK_STACK_TERMS = {"backend", "frontend", "fullstack", "web", "mobile", "gate"}
REPEATED_FOCUS_EXEMPT_TERMS = {
    "telegram",
    "python",
    "react",
    "next.js",
    "fastapi",
    "django",
    "postgresql",
    "redis",
    "docker",
    "ci/cd",
    "web",
}


def _norm(value: str | None) -> str:
    return (value or "").replace("ё", "е").lower()


def _has_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _legacy_content_issues(text: str) -> list[str]:
    lowered = _norm(text)
    issues: list[str] = []
    if any(marker in lowered for marker in STALE_LEGACY_CASE_MARKERS):
        issues.append("stale_legacy_case")
    if any(marker in lowered for marker in INACTIVE_PUBLIC_CHANNEL_MARKERS):
        issues.append("inactive_public_channel_reference")
    if LEGACY_MODEL_REFERENCE_RE.search(text):
        issues.append("stale_model_reference")
    return issues


def _anti_ai_style_issues(text: str) -> list[str]:
    lowered = _norm(text)
    issues: list[str] = []

    if _has_any(lowered, ANTI_AI_CHATBOT_ARTIFACTS):
        issues.append("ai_style:chatbot_artifact")
    if _has_any(lowered, ANTI_AI_INTRO_PHRASES):
        issues.append("ai_style:empty_intro")
    if _has_any(lowered, ANTI_AI_BUREAUCRATIC_PHRASES):
        issues.append("ai_style:bureaucratic")
    if _has_any(lowered, ANTI_AI_INFLATED_PHRASES):
        issues.append("ai_style:inflated_significance")
    if _has_any(lowered, ANTI_AI_PROMO_PHRASES):
        issues.append("ai_style:promo_language")
    if _has_any(lowered, ANTI_AI_FAKE_AUTHORITY_PHRASES):
        issues.append("ai_style:fake_authority")
    if len(ANTI_AI_PARTICIPLE_RE.findall(text)) >= 2:
        issues.append("ai_style:participle_chain")

    negative_parallelisms = sum(
        len(re.findall(pattern, lowered))
        for pattern in [r"не\s+просто", r"не\s+только", r"дело\s+не\s+в"]
    )
    if negative_parallelisms > 1:
        issues.append("ai_style:negative_parallelism_overuse")

    dash_count = text.count("—")
    if dash_count > 5 or any(paragraph.count("—") > 2 for paragraph in text.split("\n\n")):
        issues.append("ai_style:dash_overuse")
    if re.search(r"(?m)^\s*[-*]\s+\*\*[^*]{2,60}\*\*\s*:", text):
        issues.append("ai_style:bold_inline_headers")
    if EMOJI_RE.search(text):
        issues.append("ai_style:emoji")
    if re.search(r"(?m)^#{1,4}\s+[А-ЯA-Z][^\n]{2,80}$", text) or re.search(r"(?m)^\s*[А-ЯA-Z][А-ЯA-Zа-яA-Za-z\s]{2,60}:\s*$", text):
        issues.append("ai_style:heading_artifact")

    return issues


def _contains_term(text: str, term: str) -> bool:
    needle = _norm(term).strip()
    if not needle:
        return False
    haystack = _norm(text)
    if len(needle) <= 4 or re.fullmatch(r"[a-zа-я0-9#+.]+", needle):
        return re.search(rf"(?<![a-zа-я0-9]){re.escape(needle)}(?![a-zа-я0-9])", haystack) is not None
    return needle in haystack


def _matched_skills(vacancy: Vacancy, case: CaseStudy | None = None) -> list[str]:
    vacancy_text = _norm(" ".join([vacancy.title, vacancy.description, *vacancy.skills]))
    source_skills = vacancy.skills if case is None else case.stack
    result: list[str] = []
    for skill in source_skills:
        if _contains_term(vacancy_text, skill) and skill not in result:
            result.append(skill)
    return result


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zа-я0-9]+", _norm(value))
        if len(token) >= 3 and token not in _STOP_TOKENS
    }


def _case_text(case: CaseStudy) -> str:
    return " ".join([case.title, case.role, case.period, case.description, case.result, *case.stack])


def _is_stale_legacy_case(case: CaseStudy) -> bool:
    return bool(_legacy_content_issues(_case_text(case)))


def _is_agentic_vacancy(vacancy: Vacancy) -> bool:
    text = _norm(" ".join([vacancy.title, vacancy.description, *vacancy.skills]))
    markers = [
        "agent",
        "агент",
        "agentops",
        "agentic",
        "multi-agent",
        "многоагент",
        "ai office",
        "ai-офис",
        "ai отдел",
        "ai-отдел",
        "бизнес-агент",
        "бизнес агент",
        "llm",
        "llmops",
        "rag",
        "cursor",
        "codex",
        "claude code",
        "openclaw",
        "hermes",
        "tool calling",
        "prompt architecture",
        "human-in-the-loop",
    ]
    return any(marker in text for marker in markers)


def _is_ai_transformation_vacancy(vacancy: Vacancy) -> bool:
    text = _norm(" ".join([vacancy.title, vacancy.description, *vacancy.skills]))
    if any(
        marker in text
        for marker in [
            "ai transformation",
            "ai-трансформац",
            "ai трансформац",
            "ai evangelist",
            "ai-евангел",
            "евангелист",
        ]
    ):
        return True

    has_ai = "ai" in text or "llm" in text or "агент" in text
    has_implementation = any(marker in text for marker in ["внедр", "implementation", "adoption"])
    has_department_scope = any(marker in text for marker in ["отдел", "sales", "support", "marketing", "hr"])
    has_adoption_scope = any(
        marker in text
        for marker in [
            "employee adoption",
            "обучать сотруд",
            "обучение сотруд",
            "сотрудник",
            "в ежедневную работу команд",
            "изменений внутри",
        ]
    )
    has_process_analysis = any(
        marker in text
        for marker in [
            "business process analysis",
            "анализ бизнес-процесс",
            "разбор бизнес-процесс",
            "находить процессы",
            "точки автоматизации",
            "workflow automation",
        ]
    )

    if has_ai and has_implementation and (has_department_scope or has_adoption_scope):
        return True
    return has_ai and has_process_analysis and (
        has_department_scope or has_adoption_scope or "workflow automation" in text
    )


def _is_infra_heavy_ai_platform_vacancy(vacancy: Vacancy) -> bool:
    text = _norm(" ".join([vacancy.title, vacancy.description, *vacancy.skills]))
    infra_markers = [
        "ai platform",
        "llm platform",
        "llm serving",
        "model serving",
        "kubernetes",
        "k8s",
        "gpu",
        "cuda",
        "inference",
        "инференс",
        "mlops",
    ]
    return _is_agentic_vacancy(vacancy) and any(marker in text for marker in infra_markers)


def _is_data_engineering_vacancy(vacancy: Vacancy) -> bool:
    text = _norm(" ".join([vacancy.title, vacancy.description, *vacancy.skills]))
    if any(marker in text for marker in ["data engineer", "data engineering", "дата инженер", "инженер данных"]):
        return True
    return "data" in text and any(
        marker in text
        for marker in ["dwh", "airflow", "spark", "kafka", "etl", "elt", "pipeline", "пайплайн", "качество данных"]
    )


def _is_fpv40_case(case: CaseStudy) -> bool:
    case_text = _norm(_case_text(case))
    return any(marker in case_text for marker in ["fpv40", "fpv-пилот", "fpv пилот", "бпла", "беспилот", "операторов бас"])


def _is_fpv40_domain_vacancy(vacancy: Vacancy) -> bool:
    text = _norm(" ".join([vacancy.title, vacancy.description, *vacancy.skills]))
    return any(
        marker in text
        for marker in [
            "fpv",
            "дрон",
            "бпла",
            "беспилот",
            "оператор бас",
            "операторов бас",
            "uav",
            "lms",
            "edtech",
            "образовательная платформа",
            "учебная платформа",
            "онлайн-обуч",
            "онлайн обуч",
            "курс",
            "урок",
            "квиз",
            "сертификат",
            "школа пилот",
            "ученик",
            "инструктор",
        ]
    )


def _is_irrelevant_fpv40_case(case: CaseStudy, vacancy: Vacancy) -> bool:
    return _is_fpv40_case(case) and not _is_fpv40_domain_vacancy(vacancy)


def _is_irrelevant_fpv40_data_case(case: CaseStudy, vacancy: Vacancy) -> bool:
    if not _is_data_engineering_vacancy(vacancy):
        return False
    case_text = _norm(_case_text(case))
    if "fpv40" not in case_text:
        return False
    return not any(marker in case_text for marker in ["data", "dwh", "airflow", "spark", "kafka", "etl", "elt"])


def _is_backend_product_vacancy(vacancy: Vacancy) -> bool:
    text = _norm(" ".join([vacancy.title, vacancy.description, *vacancy.skills]))
    return any(
        marker in text
        for marker in [
            "backend",
            "бекенд",
            "api",
            "интеграц",
            "данные",
            "postgres",
            "redis",
            "fastapi",
            "django",
            "worker",
            "воркер",
            "релиз",
            "release",
            "production",
            "prod",
            "поддержк",
            "saas",
            "mvp",
            "самостоятельный запуск",
            "самостоятельн",
        ]
    )


def _case_relevance(case: CaseStudy, vacancy: Vacancy) -> int:
    vacancy_text = _norm(" ".join([vacancy.title, vacancy.description, *vacancy.skills]))
    case_text = _norm(_case_text(case))
    score = 0
    for skill in vacancy.skills:
        if _contains_term(case_text, skill):
            score += 8
    shared_tokens = _tokens(vacancy.title + " " + " ".join(vacancy.skills)) & _tokens(_case_text(case))
    score += min(12, len(shared_tokens) * 2)
    if _is_irrelevant_fpv40_case(case, vacancy):
        score -= 70
    if _is_backend_product_vacancy(vacancy):
        backend_product_boosts = {
            "viably": 34,
            "headhunter crm agent": 32,
            "whynotai telegram agents": 30,
            "transoff ai sales qa": 26,
            "ai dev office": 24,
            "ai-office x-one": 22,
            "vibegent": 18,
            "crm-интеграции": 18,
            "magnet": 14,
        }
        for marker, boost in backend_product_boosts.items():
            if marker in case_text:
                score += boost
                break
        if any(marker in case_text for marker in ["fastapi", "django", "postgresql", "redis", "api", "интеграц", "worker", "воркер"]):
            score += 8
        if any(marker in vacancy_text for marker in ["saas", "mvp", "самостоятельн", "релиз", "release"]):
            if any(marker in case_text for marker in ["product platform", "production", "pipeline", "deployment", "деплой", "релиз"]):
                score += 6
    if _is_agentic_vacancy(vacancy) and any(
        marker in case_text
        for marker in [
            "agent",
            "агент",
            "llm",
            "openclaw",
            "hermes",
            "vibegent",
            "viably",
            "ai office",
            "ai-офис",
            "ai-отдел",
            "многоагент",
            "business agents",
            "agentops",
        ]
    ):
        score += 10
    if _is_ai_transformation_vacancy(vacancy):
        transformation_boosts = {
            "ai-отделы": 95,
            "ai-отдел": 95,
            "business agents": 95,
            "ai departments": 95,
            "support automation": 78,
            "sales ops": 78,
            "ai office": 56,
            "agent command center": 56,
            "heisenberg team": 48,
            "многоагентная рабочая команда": 48,
            "viably": 34,
            "hermes operator": 30,
        }
        for marker, boost in transformation_boosts.items():
            if marker in case_text:
                score += boost
                break
        if any(marker in case_text for marker in ["vibegent-proxy", "llm infrastructure layer", "credits"]):
            score -= 90
    if _is_agentic_vacancy(vacancy):
        priority_boosts = {
            "heisenberg team": 62,
            "многоагентная рабочая команда": 62,
            "hermes operator contour": 60,
            "ai office": 58,
            "agent command center": 58,
            "ai-отделы": 56,
            "business agents": 56,
            "openclaw": 54,
            "vibegent-proxy": 52,
            "vibegent": 50,
            "agent cloud": 48,
            "viably": 46,
            "llm infrastructure": 44,
            "media-capable": 38,
            "telegram chat analyzer": 30,
            "gostassistent": 28,
        }
        for marker, boost in priority_boosts.items():
            if marker in case_text:
                score += boost
                break
    if any(marker in vacancy_text for marker in ["ci/cd", "release", "security", "definition of done"]):
        if any(marker in case_text for marker in ["ci/cd", "production", "deploy", "инфраструктур"]):
            score += 5
    return score


def _best_cases(profile: ApplicantProfile, vacancy: Vacancy, *, limit: int = 3) -> list[CaseStudy]:
    ranked = sorted(
        ((case, _case_relevance(case, vacancy)) for case in profile.cases),
        key=lambda item: item[1],
        reverse=True,
    )
    min_score = 1 if _is_agentic_vacancy(vacancy) else 8
    relevant = [
        case
        for case, score in ranked
        if score >= min_score
        and not _is_stale_legacy_case(case)
        and not _is_irrelevant_fpv40_case(case, vacancy)
        and not _is_irrelevant_fpv40_data_case(case, vacancy)
    ]
    return relevant[:limit]


def _response_case_limit(vacancy: Vacancy) -> int:
    """Select from a broad agentic pool; the final letter still mentions only 1–2 proof points."""
    return 7 if _is_agentic_vacancy(vacancy) else 1


def _best_case(profile: ApplicantProfile, vacancy: Vacancy) -> CaseStudy | None:
    cases = _best_cases(profile, vacancy, limit=1)
    return cases[0] if cases else None


def _join_ru(items: list[str], limit: int = 3) -> str:
    clean = [item for item in items if item]
    if not clean:
        return "релевантный стек"
    limited = clean[:limit]
    if len(limited) == 1:
        return limited[0]
    return ", ".join(limited[:-1]) + " и " + limited[-1]


def _clean_title(title: str) -> str:
    return (title or "вакансию").strip().rstrip(".!?")


def _short_case_title(case: CaseStudy) -> str:
    return re.split(r"\s+[—–-]\s+", case.title, maxsplit=1)[0].strip() or case.title.strip()


def _case_label(case: CaseStudy) -> str:
    title = _short_case_title(case)
    return f"{title} ({case.period})" if case.period else title


def _truncate_sentence(value: str, limit: int = 135, *, split_semicolon: bool = True) -> str:
    clean = re.sub(r"\s+", " ", (value or "")).strip().rstrip(".;")
    if split_semicolon:
        for separator in ["; ", ". "]:
            if separator in clean:
                clean = clean.split(separator, 1)[0].strip().rstrip(".;")
                break
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)].rsplit(" ", 1)[0].rstrip(" ,.;")


def _focus_terms(vacancy: Vacancy) -> list[str]:
    text = _norm(" ".join([vacancy.title, vacancy.description, *vacancy.skills]))
    checks = [
        ("AI-внедрение в отделы", ["ai transformation", "ai-трансформац", "ai evangelist", "ai-евангел", "ai-внедр", "ai внедр"]),
        ("анализ бизнес-процессов", ["business process analysis", "анализ бизнес-процесс", "разбор бизнес-процесс"]),
        ("workflow automation", ["workflow automation", "точки автоматизации", "рабочие процессы"]),
        ("обучение сотрудников", ["employee adoption", "обучать сотруд", "обучение сотруд", "евангелист"]),
        ("AI-агенты", ["ai-агент", "ai agents", "agent systems", "agentic", "ассистент"]),
        ("быстрые SaaS/MVP-гипотезы", ["saas", "mvp", "прототип", "гипотез", "time-to-market"]),
        ("Replit/Cursor", ["replit", "cursor"]),
        ("MCP-серверы", ["mcp", "model context protocol"]),
        ("prompt engineering", ["промпт", "prompt"]),
        ("самостоятельный запуск проектов", ["под ключ", "самостоятельн", "задепло", "без помощи devops"]),
        ("продуктовое мышление", ["продуктовое мышление", "баланс между", "коммерчески успеш"]),
        ("AgentOps", ["agentops", "agent operations", "операторск"]),
        ("agentic SDLC", ["agentic sdlc"]),
        ("многоагентные команды", ["multi-agent", "многоагент", "agent team", "команда агентов", "команды агентов"]),
        ("AI-отделы для бизнеса", ["ai отдел", "ai-отдел", "business agents", "бизнес-агент", "sales ops", "support automation"]),
        ("Hermes/OpenClaw runtime", ["hermes", "openclaw", "runtime", "gateway", "model auth"]),
        ("AI Office / agent UX", ["ai office", "ai-офис", "agent ux", "dashboard", "кабинет"]),
        ("memory/retrieval", ["memory", "retrieval", "knowledge base", "база знаний", "persistent"]),
        ("роли агентов", ["analyst agent", "architect agent", "reviewer agent", "qa agent", "security agent", "роли агент"]),
        ("human-in-the-loop", ["human-in-the-loop", "человек в контуре"]),
        ("передача результата в рабочий процесс", ["owner-return", "возврат результата"]),
        ("Definition of Done", ["definition of done"]),
        ("CI/CD", ["ci/cd", "github", "gitlab"]),
        ("test automation", ["test automation", "тестирован", "тесты"]),
        ("security checks", ["security checks", "security", "секрет"]),
        ("release gates", ["release gates", "релиз"]),
        ("LLM/RAG", ["llm", "rag", "llmops"]),
        ("production-инфраструктура", ["production", "инфраструктур", "deploy", "monitoring"]),
    ]
    result: list[str] = []
    for label, markers in checks:
        if any(marker in text for marker in markers) and label not in result:
            result.append(label)
    for skill in vacancy.skills:
        normalized_skill = _norm(skill)
        if not skill:
            continue
        if any(
            normalized_skill == _norm(item)
            or (normalized_skill in {"llm", "rag"} and "llm/rag" in _norm(item))
            or (normalized_skill == "mvp" and "mvp" in _norm(item))
            or (normalized_skill == "mcp" and "mcp" in _norm(item))
            for item in result
        ):
            continue
        if skill not in result:
            result.append(skill)
    return result


def _product_label(vacancy: Vacancy) -> str:
    description = vacancy.description or ""
    match = re.search(r"LandComp\s*2\.0", description, flags=re.IGNORECASE)
    if match:
        return "LandComp 2.0"
    return "продукта"


def _matched_case_skills(vacancy: Vacancy, case: CaseStudy) -> list[str]:
    case_text = _norm(_case_text(case))
    result: list[str] = []
    for skill in vacancy.skills:
        if _norm(skill) in _WEAK_STACK_TERMS:
            continue
        if skill and _contains_term(case_text, skill) and skill not in result:
            result.append(skill)
    return result


def _case_stack_terms(vacancy: Vacancy, case: CaseStudy) -> list[str]:
    matched = _matched_case_skills(vacancy, case)
    if _is_backend_product_vacancy(vacancy):
        backend_terms = []
        for term in case.stack:
            normalized = _norm(term)
            if normalized in {
                "python",
                "fastapi",
                "django",
                "django framework",
                "postgresql",
                "redis",
                "celery",
                "sqlalchemy",
                "alembic",
                "rest api",
                "docker",
                "docker compose",
                "ci/cd",
                "github actions",
                "telegram bots",
                "playwright",
            }:
                backend_terms.append(term)
        if backend_terms:
            combined: list[str] = []
            for term in [*matched, *backend_terms]:
                if term and term not in combined and _norm(term) not in _WEAK_STACK_TERMS:
                    combined.append(term)
            return combined[:6]
    if matched:
        return matched
    fallback = [term for term in case.stack if _norm(term) not in _WEAK_STACK_TERMS]
    if fallback:
        return fallback[:5]
    if _is_agentic_vacancy(vacancy):
        return ["AI-agent operations"]
    return ["релевантный стек"]


def _case_evidence_sentence(cases: list[CaseStudy], vacancy: Vacancy) -> str:
    if not cases:
        return ""

    def detail_for(case: CaseStudy, limit: int = 155) -> str:
        return _truncate_sentence(case.description or case.result, limit, split_semicolon=True)

    def case_kind(case: CaseStudy) -> str:
        key = _norm(_case_text(case))
        if "viably" in key:
            return "product"
        if any(marker in key for marker in ["hermes operator", "openclaw", "agent runtime"]):
            return "runtime"
        if any(
            marker in key
            for marker in [
                "heisenberg",
                "многоагентная рабочая команда",
                "ai office",
                "agent command center",
                "ai-отдел",
                "ai отдел",
                "business agents",
            ]
        ):
            return "team"
        if any(marker in key for marker in ["vibegent", "vibegent-proxy", "agent cloud", "media-capable"]):
            return "platform"
        return "other"

    def sentence_for(case: CaseStudy, *, first: bool = False) -> str:
        label = _case_label(case)
        short_title = _short_case_title(case)
        case_key = _norm(short_title)
        full_key = _norm(_case_text(case))
        stack = _join_ru(_case_stack_terms(vacancy, case), 6)
        detail = detail_for(case)

        if "vibegent-proxy" in full_key:
            return (
                "В Vibegent делал LLM-инфраструктуру для AI-агентов: маршрутизация запросов к моделям, "
                "retry/fallback, контроль ошибок и устойчивые интеграции."
            )

        if "agent cloud" in full_key:
            return f"В {label} собирал deploy-инфраструктуру для пользовательских агентов: Hetzner worker nodes, remote Docker, scheduling и DB-трекинг."

        if "media-capable" in full_key:
            return f"В {label} добавлял Telegram media-flow для агентов: text, voice/audio, vision, STT и per-user memory."

        if "vibegent" in case_key:
            if detail:
                detail = re.sub(r"^делал\s+", "", detail, flags=re.IGNORECASE)
                if _norm(detail).startswith("production-платформа"):
                    return f"В {label} делал production-платформу пользовательских AI-агентов: LLM-прокси, биллинг, Telegram-интерфейсы, воркер-ноды и инфраструктуру."
                return f"В {label} делал {detail}."
            return f"В {label} работал с AI-агентами, LLM и Telegram-интерфейсами."

        if "hermes operator" in full_key:
            return f"В {label} настраивал Hermes как рабочий AgentOps-процесс: Telegram gateway, memory, skills, knowledge base, retrieval, cron health checks и reports."

        if "openclaw" in case_key:
            if detail:
                detail = re.sub(r"^production-стабилизаци[яю]\s*", "", detail, flags=re.IGNORECASE)
                return f"В {label} стабилизировал агентную среду: {detail}."
            return f"В {label} стабилизировал агентную среду и runtime-часть."

        if "heisenberg" in full_key:
            return f"В {label} собирал многоагентную команду с ролями, координатором, Board-First workflow, handoff и quality gates."

        if "ai office" in full_key or "agent command center" in full_key:
            if _is_ai_transformation_vacancy(vacancy) or any(
                marker in full_key for marker in ["business agents", "workflow automation", "sales ops", "support automation"]
            ):
                return (
                    f"В {label} проектировал AI-внедрение для бизнеса: роли агентов, "
                    "разбор процессов, workflow automation, CRM/коммуникации и понятный контроль результата."
                )
            return f"В {label} делал AI-офис/agent dashboard: роли, кабинеты, статусы, задачи и проверяемый frontend-preview."

        if "ai-отдел" in full_key or "business agents" in full_key:
            if _is_ai_transformation_vacancy(vacancy):
                return (
                    f"В {label} проектировал AI-внедрение для отделов: разбор бизнес-процессов, "
                    "AI-агенты как рабочие роли, CRM/таблицы, Telegram/Web, human-in-the-loop "
                    "и передачу результата в рабочий процесс."
                )
            return f"В {label} делал бизнес-агентов: sales/support ops, лиды, CRM/таблицы, Telegram/Web, ручную проверку и передачу результата в рабочий процесс."

        if "viably" in case_key:
            base = f"В {label} закрывал backend и продуктовую часть. Там работал с {stack}"
            return f"{base}: {detail}." if detail else f"{base}."

        base = f"В {label} работал с {stack}"
        if detail:
            detail_has_action = re.match(
                r"^(делал|строил|занимался|собирал|разв[её]ртывал|настраивал|запустил|подключал)\b",
                _norm(detail),
            )
            return f"{base}: {detail}." if detail_has_action else f"{base}: делал {detail}."
        return f"{base}."

    if _is_agentic_vacancy(vacancy):
        if _is_ai_transformation_vacancy(vacancy):
            selected: list[str] = []
            selected_cases: list[CaseStudy] = []
            preferred_marker_groups = [
                ["ai-отдел", "ai отдел", "business agents", "ai departments"],
                ["heisenberg", "многоагентная рабочая команда"],
                ["viably"],
                ["hermes operator"],
            ]
            for marker_group in preferred_marker_groups:
                for case in cases:
                    if case in selected_cases:
                        continue
                    key = _norm(_case_text(case))
                    if any(marker in key for marker in ["vibegent-proxy", "llm infrastructure layer", "credits"]):
                        continue
                    if any(marker in key for marker in marker_group):
                        selected.append(sentence_for(case))
                        selected_cases.append(case)
                        break
                if selected:
                    break

            if selected:
                return selected[0]

        grouped: dict[str, list[str]] = {"platform": [], "runtime": [], "team": [], "product": [], "other": []}
        for case in cases:
            grouped[case_kind(case)].append(sentence_for(case))

        selected: list[str] = []
        for bucket in ["platform", "runtime", "team", "product", "other"]:
            if grouped[bucket]:
                selected.append(grouped[bucket][0])
            if len(selected) >= 2:
                break

        if selected:
            return " ".join(selected[:2])

    return "\n\n".join(sentence_for(case, first=index == 0) for index, case in enumerate(cases[:2]))


_RELEVANT_REQUIREMENT_HEADING_RE = re.compile(
    r"^(?:"
    r"что\s+(?:мы\s+)?(?:жд[её]м|важно)|"
    r"кого\s+ищем|"
    r"требования|ключевые\s+требования|"
    r"чем\s+предстоит\s+заниматься|задачи|"
    r"будет\s+(?:круто|плюсом)|плюсом\s+будет|"
    r"важно"
    r")\b.*:?$",
    re.IGNORECASE,
)
_STOP_REQUIREMENT_HEADING_RE = re.compile(
    r"^(?:что\s+мы\s+предлагаем|условия|о\s+компании|мы\s+предлагаем|график|зарплата|вакансия)\b.*:?$",
    re.IGNORECASE,
)
_GENERIC_HEADING_RE = re.compile(r"^[A-ZА-ЯЁ][^.!?]{2,90}:$")
EXTRA_PROOF_CONTINUATION_HEADING_RE = re.compile(
    r"^(?:если\s+(?:у\s+(?:тебя|вас)\s+)?есть|если\s+можете|можно\s+приложить|будет\s+плюсом)\b.*:$",
    re.IGNORECASE,
)


def _dedupe_append(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _clean_requirement_item(raw: str) -> str:
    item = re.sub(r"^\s*(?:[-–—•▪*]|\d+[.)])\s*", "", raw or "").strip(" ;,.—-")
    if not item:
        return ""
    lowered = _norm(item)
    if any(marker in lowered for marker in ["уважаемые соискатели", "мошен", "не присылайте", "не сообщайте код"]):
        return ""
    if lowered.rstrip(" :") in {"если ты", "от тебя"}:
        return ""
    if _STOP_REQUIREMENT_HEADING_RE.match(item) or _GENERIC_HEADING_RE.match(item):
        return ""
    return _truncate_sentence(item, 160, split_semicolon=False)


def _requirement_items(raw: str) -> list[str]:
    normalized = re.sub(r"\s+(?:[-–—•▪*])\s+", "; ", raw or "")
    parts = [part.strip(" ;,.—-") for part in re.split(r";|•|▪|\n", normalized)]
    result: list[str] = []
    for part in parts:
        clean = _clean_requirement_item(part)
        if len(clean) >= 8 and clean not in result:
            result.append(clean)
    return result


def _important_requirements(vacancy: Vacancy) -> list[str]:
    raw_description = (vacancy.description or "").strip()
    if not raw_description:
        return []

    result: list[str] = []
    in_relevant_section = False
    lines = [line.strip() for line in raw_description.splitlines()]
    for line in lines:
        if not line:
            continue
        if _STOP_REQUIREMENT_HEADING_RE.match(line):
            in_relevant_section = False
            continue
        heading_match = _RELEVANT_REQUIREMENT_HEADING_RE.match(line)
        if heading_match:
            in_relevant_section = True
            after_colon = line.split(":", 1)[1] if ":" in line else ""
            for item in _requirement_items(after_colon):
                _dedupe_append(result, item)
            continue
        if in_relevant_section:
            if _GENERIC_HEADING_RE.match(line) and not line.startswith(("-", "–", "—", "•", "▪", "*")):
                in_relevant_section = False
                continue
            clean = _clean_requirement_item(line)
            if len(clean) >= 8:
                _dedupe_append(result, clean)

    # Inline fallback for compact pasted descriptions without line breaks.
    flattened = re.sub(r"\s+", " ", raw_description)
    inline_patterns = [
        r"(?:что\s+(?:мы\s+)?(?:жд[её]м|важно)|важно|кого\s+ищем|требования|ключевые\s+требования)\s*[:—-]\s*([^.]*)",
        r"(?:будет\s+(?:круто|плюсом)|плюсом\s+будет)\s*[:—-]?\s*([^.]*)",
    ]
    for pattern in inline_patterns:
        for match in re.finditer(pattern, flattened, flags=re.IGNORECASE):
            for item in _requirement_items(match.group(1)):
                _dedupe_append(result, item)
    return result[:14]


def _requirement_relevance(requirement: str, cases: list[CaseStudy], vacancy: Vacancy) -> int:
    req_tokens = _tokens(requirement)
    case_tokens = _tokens(" ".join(_case_text(case) for case in cases))
    focus_tokens = _tokens(" ".join(_focus_terms(vacancy)[:5]))
    return len(req_tokens & case_tokens) * 2 + len(req_tokens & focus_tokens)


def _requirement_focus_terms(requirements: list[str], vacancy: Vacancy) -> list[str]:
    requirement_text = _norm(" ".join(requirements))
    full_text = _norm(vacancy.description or "")
    result: list[str] = []

    def add(label: str, markers: list[str], *, include_full_text: bool = False) -> None:
        haystacks = [requirement_text]
        if include_full_text:
            haystacks.append(full_text)
        if any(marker in haystack for marker in markers for haystack in haystacks):
            _dedupe_append(result, label)

    add("AI-внедрение в отделы", ["ai transformation", "ai-трансформац", "ai evangelist", "ai-евангел", "внедр"], include_full_text=True)
    add("анализ бизнес-процессов", ["business process analysis", "анализ бизнес-процесс", "разбор бизнес-процесс"], include_full_text=True)
    add("workflow automation", ["workflow automation", "точки автоматизации", "рабочие процессы"], include_full_text=True)
    add("обучение сотрудников", ["employee adoption", "обучать сотруд", "обучение сотруд", "евангелист"], include_full_text=True)
    add("Replit/Cursor", ["replit", "cursor"])
    add("MCP-серверы", ["mcp", "model context protocol"])
    add("быстрые SaaS/MVP-гипотезы", ["saas", "mvp", "прототип", "гипотез", "time-to-market"], include_full_text=True)
    add("AI-агенты/ассистенты", ["ai-агент", "ai агент", "агент", "ассистент"])
    add("самостоятельный запуск проектов", ["под ключ", "самостоятельн", "без помощи devops", "задепло"])
    add("качество LLM-ответов", ["промпт", "prompt", "качество ответ"])
    add("тестирование и быстрый релиз", ["тест", "релиз", "release"])
    add("продуктовое мышление", ["продуктовое мышление", "баланс между", "точки роста", "фидбек"])
    add("общение с заказчиками и защита идей", ["заказчик", "защищать", "презентац", "показывать результат"])

    for focus in _focus_terms(vacancy):
        if len(result) >= 6:
            break
        if _norm(focus) not in {_norm(item) for item in result}:
            result.append(focus)
    return result[:6]


def _important_requirements_sentence(vacancy: Vacancy, cases: list[CaseStudy]) -> str:
    requirements = _important_requirements(vacancy)
    if not requirements:
        return ""
    ranked = sorted(requirements, key=lambda item: _requirement_relevance(item, cases, vacancy), reverse=True)
    anchors = _join_ru(_requirement_focus_terms(ranked, vacancy)[:5], 5)
    vacancy_text = _norm(vacancy.description)
    product = _product_label(vacancy)
    product_prefix = f"для {product} - " if product != "продукта" else ""
    if _is_agentic_vacancy(vacancy):
        if _is_ai_transformation_vacancy(vacancy):
            return (
                "Главный фокус вижу так: внутреннее AI-внедрение в отделы - сначала анализ бизнес-процессов "
                "и точек автоматизации, затем AI-агенты в ежедневной работе команд. Важны LLM/RAG, "
                "Telegram/Web или workflow automation, интеграции с CRM/внутренними системами "
                "и обучение сотрудников на практических кейсах."
            )
        if _is_infra_heavy_ai_platform_vacancy(vacancy):
            return (
                f"Задача, как я ее понял: {product_prefix}нужна backend-часть AI-платформы: {anchors}. "
                "Сильнее всего здесь AI backend, AgentOps, LLM/RAG-интеграции, сервисная логика, мониторинг, тесты и production-запуск; "
                "глубокий GPU/model serving не выдаю за основной опыт."
            )
        if "не обучаем модели" in vacancy_text or "pytorch" in vacancy_text:
            return (
                f"Задача, как я ее понял: {product_prefix}быстро делать прикладной AI-продукт: {anchors}. "
                "Не обучение моделей, а MVP, LLM/MCP-интеграции, тесты, самостоятельный запуск и понятный показ результата."
            )
        return (
            f"Задача, как я ее понял: {product_prefix}нужен AI backend/AgentOps. "
            f"Важные акценты вакансии: {anchors}; дальше - LLM/RAG-интеграции, агентная логика, memory/routing, тесты и поддержка после запуска."
        )
    return (
        "Задача, как я ее понял: здесь нужна backend-разработка: "
        f"API, интеграции, данные, тесты, релизы и поддержка. В требованиях отдельно вижу: {anchors}."
    )


def _plain_vacancy_description(vacancy: Vacancy) -> str:
    text = vacancy.description or ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(?:p|li|ul|ol|div|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return text


def _extra_proof_request_snippets(vacancy: Vacancy) -> list[str]:
    raw_description = _plain_vacancy_description(vacancy)
    snippets: list[str] = []
    active: list[str] = []

    def flush() -> None:
        nonlocal active
        if active:
            snippets.append(" ".join(active))
            active = []

    for line in [line.strip() for line in raw_description.splitlines()]:
        if not line:
            continue
        if EXTRA_PROOF_SECTION_HEADING_RE.match(line):
            flush()
            active = [line]
            after_colon = line.split(":", 1)[1].strip() if ":" in line else ""
            if after_colon:
                active.append(after_colon)
            continue
        if active:
            is_new_heading = (
                _GENERIC_HEADING_RE.match(line)
                and not EXTRA_PROOF_CONTINUATION_HEADING_RE.match(line)
                and not line.startswith(("-", "*", "•", "▪"))
            )
            if is_new_heading and not EXTRA_PROOF_SECTION_HEADING_RE.match(line):
                flush()
                continue
            active.append(line)
    flush()

    flattened = re.sub(r"\s+", " ", raw_description).strip()
    for match in EXTRA_PROOF_INLINE_RE.finditer(flattened):
        snippets.append(match.group(0))

    lowered = _norm(flattened)
    for marker in [
        "в сопроводительном письме",
        "при отклике",
        "в отклике",
        "к отклику",
        "как откликнуться",
    ]:
        index = lowered.find(marker)
        if index >= 0:
            snippets.append(flattened[index : index + 380])

    return list(dict.fromkeys(snippet for snippet in snippets if snippet.strip()))


def _proof_request_tags_from_text(text: str) -> set[str]:
    lowered = _norm(text)
    tags: set[str] = set()

    github_text = re.sub(r"github\s+actions?", "", lowered)
    if "github" in github_text or "гитхаб" in lowered:
        tags.add("github")
    if any(marker in lowered for marker in ["портфолио", "portfolio"]):
        tags.add("portfolio")
    if any(
        marker in lowered
        for marker in [
            "кейс",
            "case",
            "пример работ",
            "примеры работ",
            "пример проект",
            "яндекс диск",
            "yandex disk",
            "disk.yandex",
            "yadi.sk",
        ]
    ):
        tags.add("cases")
    if any(marker in lowered for marker in ["telegram", "телеграм", " t.me/", " tg", "канал", "контакт"]):
        tags.add("telegram")
    if any(
        marker in lowered
        for marker in ["ai-проект", "ai проект", "ai projects", "проекты с ai", "проекты на ai", "ии-проект"]
    ):
        tags.add("ai_projects")
    if any(marker in lowered for marker in ["автоматизац", "automation", "workflow"]):
        tags.add("automations")
    if any(marker in lowered for marker in ["презентац", "presentation", "deck"]):
        tags.add("presentations")
    if re.search(r"(?:сво|собственн|own).{0,28}(?:ai[-\s]?агент|агент|agent)", lowered):
        tags.add("own_agents")
    elif any(marker in lowered for marker in ["ai-агент", "ai агент", "ai agents", "агент"]):
        tags.add("agents")
    return tags


def _proof_request_tags(vacancy: Vacancy) -> set[str]:
    result: set[str] = set()
    for snippet in _extra_proof_request_snippets(vacancy):
        lowered = _norm(snippet)
        tags = _proof_request_tags_from_text(snippet)
        if not tags:
            continue
        has_action = any(marker in lowered for marker in PROOF_REQUEST_ACTION_MARKERS)
        is_extra_section = any(
            marker in lowered
            for marker in [
                "дополнительно",
                "доп.",
                "при отклике",
                "в отклике",
                "к отклику",
                "сопроводитель",
                "что приложить",
                "что показать",
                "важно в отклике",
            ]
        )
        if has_action or (is_extra_section and len(tags) >= 2):
            result.update(tags)
    return result


def _clean_known_url(value: str | None) -> str | None:
    if not value:
        return None
    match = URL_RE.search(value.strip())
    return match.group(0).rstrip(".,;:!?") if match else None


def _known_proof_pack_url(profile: ApplicantProfile) -> str | None:
    return _clean_known_url(getattr(profile, "proof_pack_url", None))


def _known_github_url(profile: ApplicantProfile, cases: list[CaseStudy]) -> str | None:
    for value in [
        getattr(profile, "github_url", None),
        profile.website_url,
        profile.portfolio_url,
        *(case.url for case in cases),
    ]:
        url = _clean_known_url(value)
        if url and GITHUB_URL_RE.match(url):
            return url
    return None


def _proof_case_titles(cases: list[CaseStudy], tags: set[str], *, limit: int = 3) -> list[str]:
    safe_cases = [case for case in cases if not _is_stale_legacy_case(case)]
    if not safe_cases:
        return []

    def score(case: CaseStudy) -> int:
        text = _norm(_case_text(case))
        value = 0
        if tags & {"ai_projects", "agents", "own_agents", "automations"} and any(
            marker in text for marker in ["ai-отдел", "ai отдел", "business agents", "ai departments", "бизнес-агент"]
        ):
            value += 6
        if tags & {"ai_projects", "agents", "own_agents"} and any(
            marker in text for marker in ["ai", "агент", "agent", "llm", "rag", "hermes", "openclaw", "ai office", "ai-отдел"]
        ):
            value += 4
        if "automations" in tags and any(
            marker in text for marker in ["автоматизац", "automation", "workflow", "sales ops", "support automation", "crm"]
        ):
            value += 4
        if "presentations" in tags and any(marker in text for marker in ["презентац", "presentation", "dashboard", "preview"]):
            value += 3
        if "cases" in tags:
            value += 2
        return value

    ranked = sorted(safe_cases, key=score, reverse=True)
    result: list[str] = []
    for case in ranked:
        title = _short_case_title(case).translate(COVER_LETTER_TYPOGRAPHY_TRANSLATION).strip()
        if title and title not in result:
            result.append(title)
        if len(result) >= limit:
            break
    return result


def _proof_case_label(tags: set[str]) -> str:
    if tags & {"ai_projects", "agents", "own_agents", "automations"}:
        return "кейсы/AI-агенты/автоматизации"
    if "presentations" in tags:
        return "кейсы/презентации"
    return "кейсы"


def _profile_link_sentence(profile: ApplicantProfile, *, english_label: bool = False) -> str:
    if profile.portfolio_url:
        label = "Portfolio" if english_label else "Портфолио"
        return f"{label}: {profile.portfolio_url}"
    if profile.website_url:
        label = "Website" if english_label else "Сайт"
        return f"{label}: {profile.website_url}"
    return ""


def _proof_pack_sentence(profile: ApplicantProfile, vacancy: Vacancy, cases: list[CaseStudy], tags: set[str]) -> str:
    safe_cases = [case for case in cases if not _is_stale_legacy_case(case)]
    if not tags:
        return _profile_link_sentence(profile)

    parts: list[str] = []
    profile_link = _profile_link_sentence(profile, english_label=True)
    if profile_link:
        parts.append(profile_link)
    if profile.telegram:
        parts.append(f"Telegram: {profile.telegram}")
    if profile.telegram_channel:
        parts.append(f"Telegram-channel/AI-project: {profile.telegram_channel}")
    github_url = _known_github_url(profile, safe_cases)
    if github_url:
        parts.append(f"GitHub: {github_url}")
    proof_pack_url = _known_proof_pack_url(profile)
    if proof_pack_url and tags & {
        "cases",
        "ai_projects",
        "agents",
        "own_agents",
        "automations",
        "presentations",
    }:
        parts.append(f"Yandex Disk кейсы: {proof_pack_url}")
    proof_titles = _proof_case_titles(safe_cases, tags)
    if proof_titles:
        parts.append(f"{_proof_case_label(tags)}: {', '.join(proof_titles)}")
    return "; ".join(parts)


def _agentic_intro_sentence(vacancy: Vacancy, focus: list[str]) -> str:
    title = _clean_title(vacancy.title)
    focus_text = _join_ru(focus, 5)
    vacancy_text = _norm(" ".join([vacancy.title, vacancy.description, *vacancy.skills]))

    if _is_ai_transformation_vacancy(vacancy):
        return (
            "Главный фокус вижу так: внутреннее AI-внедрение в отделы - сначала анализ бизнес-процессов "
            "и точек автоматизации, затем AI-агенты в ежедневной работе команд. Важны LLM/RAG, "
            f"Telegram/Web или workflow automation, интеграции с CRM и понятное обучение сотрудников. Фокус вакансии: {focus_text}."
        )
    if _is_infra_heavy_ai_platform_vacancy(vacancy):
        return (
            f"Задача, как я ее понял: AI platform/LLM-infra: {focus_text}. "
            "Мой честный сильный опыт - AI backend, AgentOps, monitoring, production-запуск и LLM/RAG-интеграции; "
            "глубокий Kubernetes/GPU model serving не мой основной профиль."
        )
    if any(marker in vacancy_text for marker in ["agentic sdlc", "definition of done", "release gates", "security checks", "reviewer agent", "qa agent"]):
        return (
            f"Задача, как я ее понял: agentic SDLC для {title}. "
            f"Нужны роли агентов, review/QA/security checks, CI/CD и release gates. Фокус вакансии: {focus_text}."
        )
    if any(marker in vacancy_text for marker in ["replit", "mcp", "mvp", "гипотез", "saas", "прототип", "не обучаем модели"]):
        return (
            f"Задача, как я ее понял: быстро собирать AI-продукты и MVP: {focus_text}. "
            "Здесь важны Replit/Cursor, MCP, промпты, тесты и самостоятельный запуск."
        )
    if any(marker in vacancy_text for marker in ["sales", "support", "crm", "telegram", "b2b", "бизнес-процесс"]):
        return (
            f"Задача, как я ее понял: business-agent backend: {focus_text}. "
            "Нужны Telegram/Web, CRM, LLM-интеграции и контроль результата в рабочем процессе."
        )
    if any(marker in vacancy_text for marker in ["agentops", "memory", "retrieval", "tool calling", "human-in-the-loop", "monitoring", "многоагент"]):
        return (
            f"Задача, как я ее понял: AgentOps: {focus_text}. "
            "Нужны memory/retrieval, tool calling, routing, проверки и эксплуатация после запуска."
        )
    return (
        f"Задача, как я ее понял: AI backend: {focus_text}. "
        "Нужны LLM/RAG-интеграции, tools, тесты, production-запуск и поддержка."
    )


def _non_agentic_intro_sentence(vacancy: Vacancy, focus: list[str]) -> str:
    focus_text = _join_ru(focus, 5)
    vacancy_text = _norm(" ".join([vacancy.title, vacancy.description, *vacancy.skills]))
    if _is_data_engineering_vacancy(vacancy):
        return (
            f"Задача, как я ее понял: data engineering: {focus_text}. "
            "Нужны пайплайны, качество данных, API/интеграции, тесты и надежные релизы."
        )
    if any(marker in vacancy_text for marker in ["crm", "amo", "bitrix", "битрикс", "telegram", "телеграм"]):
        return (
            f"Задача, как я ее понял: CRM/Telegram-интеграции и backend: {focus_text}. "
            "Важны API, данные, пользовательские сценарии, тесты и релизы."
        )
    if any(marker in vacancy_text for marker in ["backend", "api", "fastapi", "django", "postgres", "redis"]):
        return (
            f"Задача, как я ее понял: backend-разработка: {focus_text}. "
            "Нужны API, интеграции, данные, фоновые задачи, тесты и релизы."
        )
    if any(marker in vacancy_text for marker in ["devops", "platform", "docker", "kubernetes", "ci/cd", "инфраструктур"]):
        return (
            f"Задача, как я ее понял: platform/backend: {focus_text}. "
            "Нужны сервисы, надежность, мониторинг и понятный релизный процесс."
        )
    return (
        f"Задача, как я ее понял: практичная разработка под требования вакансии: {focus_text}. "
        "Важны быстрый разбор задачи, рабочая версия, тесты и релизы."
    )


def _profile_fallback_sentence(profile: ApplicantProfile, vacancy: Vacancy, strengths: list[str], focus: list[str]) -> str:
    focus_text = _join_ru(focus, 5)
    clean_strengths = [
        re.sub(
            RUSSIAN_CONTOUR_RE,
            "системы",
            re.sub(r"\bowner-return\b", "передача результата в рабочий процесс", item, flags=re.IGNORECASE),
        )
        for item in strengths
    ]
    strengths_text = _join_ru([_truncate_sentence(item, 115) for item in clean_strengths], 2)
    if _is_data_engineering_vacancy(vacancy):
        return (
            f"Из моего профиля сюда ближе backend/platform часть: {profile.headline}. "
            f"Сильнее всего могу быть полезен там, где data-задача пересекается с backend-разработкой: {strengths_text}, "
            "интеграции, фоновые процессы, API, PostgreSQL/Redis, Docker, мониторинг и аккуратный production-support. "
            f"По требованиям вроде {focus_text} быстро отделю обязательную часть от лишней и доведу ее до понятных проверок результата."
        )
    return (
        f"Мой основной профиль - {profile.headline}. "
        f"Сильные стороны: {strengths_text}; обычно беру задачи, где нужно быстро понять бизнес-задачу, "
        f"собрать рабочую backend/full-stack основу под требования вроде {focus_text} и довести ее до поддержки в проде."
    )


def _delivery_sentence(vacancy: Vacancy) -> str:
    if _is_agentic_vacancy(vacancy):
        return ""
    vacancy_text = _norm(" ".join([vacancy.title, vacancy.description, *vacancy.skills]))
    if _is_data_engineering_vacancy(vacancy):
        return (
            "Начал бы с карты источников и потоков данных, критичных SLA, проверок качества и короткого плана, "
            "где сначала закрывать надежность пайплайнов, а где можно двигаться итерациями."
        )
    if any(marker in vacancy_text for marker in ["crm", "amo", "bitrix", "битрикс", "telegram", "телеграм"]):
        return (
            "На старте разобрал бы пользовательские сценарии, API/Telegram-интеграции, модель данных и места, "
            "где ручная операционная работа должна превращаться в понятный автоматизированный поток. "
            "Для CRM отдельно проверил бы входящие заявки, ответственных, статусы, уведомления, права доступа "
            "и точки контроля, чтобы автоматизация не жила отдельно от реального процесса."
        )
    if any(marker in vacancy_text for marker in ["backend", "api", "fastapi", "django", "postgres", "redis"]):
        return (
            "На старте проверил бы границы сервисов, API-контракты, схему данных, фоновые задачи и риски деплоя, "
            "после чего собрал бы первую рабочую версию без лишнего усложнения."
        )
    return (
        "На старте разобрал бы текущую систему, пользовательский сценарий, ограничения по срокам и риски, "
        "а затем предложил бы короткий план первых изменений с проверяемым результатом."
    )


def _agentic_closing_sentence(vacancy: Vacancy, focus: list[str]) -> str:
    product = _product_label(vacancy)
    focus_text = _join_ru(focus, 3)
    vacancy_text = _norm(" ".join([vacancy.title, vacancy.description, *vacancy.skills]))
    if _is_infra_heavy_ai_platform_vacancy(vacancy):
        return (
            f"Готов обсудить, где полезнее мой опыт в {focus_text}: "
            "AI backend/platform, AgentOps, deploy/monitoring или интеграции LLM в существующую систему."
        )
    if any(marker in vacancy_text for marker in ["agentic sdlc", "definition of done", "release gates", "security checks", "reviewer agent", "qa agent"]):
        target = f" по {product}" if product != "продукта" else ""
        return (
            "Готов начать с карты ролей, DoD, review/security gates "
            f"и короткого плана первого production-релиза{target}. Фокус на {focus_text}."
        )
    if any(marker in vacancy_text for marker in ["replit", "mcp", "mvp", "гипотез", "saas", "прототип", "не обучаем модели"]):
        return (
            "Готов начать с короткой ревизии гипотезы, "
            f"MCP/Replit-связки и плана первого MVP. Фокус на {focus_text}."
        )
    if any(marker in vacancy_text for marker in ["sales", "support", "crm", "telegram", "b2b", "бизнес-процесс"]):
        return (
            "Готов разобрать текущие процессы, где агент реально экономит время, "
            f"и собрать первую рабочую версию под {focus_text}, каналы и CRM."
        )
    if product != "продукта":
        return (
            f"Готов подключиться: сначала разобрал бы текущее состояние {product} "
            f"и набросал короткий план по {focus_text}."
        )
    return (
        f"Готов созвониться и пройтись по первому релизу: {focus_text}, "
        "границы задачи, риски, интеграции и проверки результата."
    )


def _closing_sentence(vacancy: Vacancy, focus: list[str] | None = None) -> str:
    if _is_agentic_vacancy(vacancy):
        return _agentic_closing_sentence(vacancy, focus or _focus_terms(vacancy))
    if _is_data_engineering_vacancy(vacancy):
        return "Готов обсудить, где у вас сейчас главный риск: архитектура данных, надежность пайплайнов, качество данных или командный процесс."
    return "Готов обсудить задачу, быстро уточнить ограничения и предложить первые изменения с понятным результатом."


def _usefulness_sentence(vacancy: Vacancy, focus: list[str], portfolio_sentence: str = "") -> str:
    if _is_agentic_vacancy(vacancy):
        if _is_ai_transformation_vacancy(vacancy):
            base = (
                "Начал бы с карты процессов по отделам, выбора 2-3 пилотных workflow "
                "и короткой проверки, где AI-агент реально снижает ручную работу. "
                "Дальше - LLM/RAG, Telegram/Web, CRM-интеграции и обучение команды на рабочих примерах."
            )
        elif _is_infra_heavy_ai_platform_vacancy(vacancy):
            base = (
                "Здесь буду полезен на backend-части AI-платформы: "
                "связать модельные интеграции и RAG с сервисной логикой, мониторингом, тестами и production-запуском. "
                "Глубокий GPU/model serving - не мой основной опыт."
            )
        else:
            base = (
                "Здесь буду полезен на AI backend части: "
                "LLM/RAG, агентная логика, Telegram/Web-интеграции, проверки и поддержка после запуска."
            )
    elif _is_data_engineering_vacancy(vacancy):
        base = (
            "Здесь буду полезен там, где data engineering упирается в backend: "
            "API, интеграции, данные, проверки качества, тесты, релизы и поддержка."
        )
    else:
        base = (
            "Здесь буду полезен в backend-разработке: "
            "API, интеграции, данные, тесты, релизы и поддержка в проде. "
            "Могу быстро войти в существующий код и довести изменения до рабочего состояния."
        )
    return f"{base}\n{portfolio_sentence}" if portfolio_sentence else base


_LEGACY_GREETING_WITH_ADDRESSEE_RE = re.compile(r"^\s*Здравствуйте\s*,\s*.{1,180}?[!.]\s*", re.IGNORECASE | re.DOTALL)


def sanitize_cover_letter_greeting(message: str) -> str:
    """Enforce the HH rule: greet with plain `Здравствуйте!`, never with employer/company names."""
    text = (message or "").strip()
    if not text:
        return ""
    if text.startswith("Здравствуйте!"):
        return text

    match = _LEGACY_GREETING_WITH_ADDRESSEE_RE.match(text)
    if match:
        rest = text[match.end() :].lstrip()
        return ("Здравствуйте!" + (f" {rest}" if rest else "")).strip()

    if re.match(r"^\s*Здравствуйте\b", text, flags=re.IGNORECASE):
        rest = re.sub(r"^\s*Здравствуйте\b[\s,!.:;—-]*", "", text, count=1, flags=re.IGNORECASE).lstrip()
        return ("Здравствуйте!" + (f" {rest}" if rest else "")).strip()

    return text


def sanitize_cover_letter(message: str) -> str:
    text = sanitize_cover_letter_greeting(message)
    text = text.translate(COVER_LETTER_TYPOGRAPHY_TRANSLATION)
    for pattern, replacement in GENERATED_PHRASE_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text


def generate_cover_letter(context: ResponseContext) -> GeneratedResponse:
    profile = context.profile
    vacancy = context.vacancy
    methodology = load_cover_letter_methodology()
    skills = _matched_skills(vacancy) or _focus_terms(vacancy)[:5]
    cases = _best_cases(profile, vacancy, limit=_response_case_limit(vacancy))
    strengths = profile.strengths[:2] or ["быстро разбираюсь в бизнес-задаче", "довожу решение до продакшена"]
    focus = _focus_terms(vacancy) or skills

    facts_used: list[str] = []
    if skills:
        facts_used.append("skills:" + ",".join(skills[:5]))
    for case in cases:
        facts_used.append(f"case:{case.title}")
    if methodology:
        facts_used.append("methodology:cover-letter")

    proof_request_tags = _proof_request_tags(vacancy)
    if proof_request_tags:
        facts_used.append("extra-proof-request:" + ",".join(sorted(proof_request_tags)))
    portfolio_sentence = _proof_pack_sentence(profile, vacancy, cases, proof_request_tags)

    important_sentence = _important_requirements_sentence(vacancy, cases)
    if important_sentence:
        vacancy_sentence = important_sentence
    elif _is_agentic_vacancy(vacancy):
        vacancy_sentence = _agentic_intro_sentence(vacancy, focus)
    else:
        vacancy_sentence = _non_agentic_intro_sentence(vacancy, focus)

    message_parts = ["Здравствуйте!", vacancy_sentence]
    case_sentence = _case_evidence_sentence(cases, vacancy)
    if case_sentence:
        message_parts.append(case_sentence)
    else:
        message_parts.append(_profile_fallback_sentence(profile, vacancy, strengths, focus))
    message_parts.append(_usefulness_sentence(vacancy, focus, portfolio_sentence))

    message = sanitize_cover_letter("\n\n".join(part for part in message_parts if part))
    risk_flags = []
    if context.score < 70:
        risk_flags.append("fit_below_review_threshold")
    quality = check_cover_letter_quality(message, context)
    risk_flags.extend(quality.issues)

    return GeneratedResponse(
        message=message,
        tone="direct_business",
        estimated_fit=max(0, min(100, context.score)),
        facts_used=facts_used,
        risk_flags=risk_flags,
    )


def check_cover_letter_quality(message: str, context: ResponseContext) -> CoverLetterQualityCheck:
    text = (message or "").strip()
    lowered = _norm(text)
    issues: list[str] = []
    issues.extend(_legacy_content_issues(text))

    if not text.startswith("Здравствуйте!"):
        issues.append("bad_greeting")
    first_sentence = text.split(".", 1)[0]
    if re.match(r"^\s*Здравствуйте\s*,", first_sentence, flags=re.IGNORECASE):
        issues.append("employer_in_greeting")
    company = (context.vacancy.company or "").strip()
    if company and company != "Компания не указана" and company.lower() in first_sentence.lower().replace("ё", "е"):
        issues.append("company_in_first_sentence")
    if any(char in text for char in FORBIDDEN_COVER_LETTER_TYPOGRAPHY):
        issues.append("forbidden_typography")

    portfolio_url = context.profile.portfolio_url or context.profile.website_url
    if portfolio_url:
        expected_label = "Портфолио:" if context.profile.portfolio_url else "Сайт:"
        expected_line = f"{expected_label} {portfolio_url}"
        accepted_labels = [expected_label, "Portfolio:" if context.profile.portfolio_url else "Website:"]
        if expected_line not in text.splitlines() and not any(
            portfolio_url in line and any(label in line for label in accepted_labels)
            for line in text.splitlines()
        ):
            issues.append("missing_portfolio")

    proof_request_tags = _proof_request_tags(context.vacancy)
    if proof_request_tags:
        proof_lines = [
            line
            for line in text.splitlines()
            if any(
                label in line
                for label in [
                    "Portfolio:",
                    "Website:",
                    "Портфолио:",
                    "Сайт:",
                    "Telegram:",
                    "GitHub:",
                    "Yandex Disk",
                    "Яндекс",
                    "кейсы",
                    "Кейсы",
                ]
            )
        ]
        proof_text = "\n".join(proof_lines)
        if not proof_lines or (context.profile.telegram and "Telegram:" not in proof_text):
            issues.append("missing_requested_proof_pack")
        github_url = _known_github_url(
            context.profile,
            _best_cases(context.profile, context.vacancy, limit=_response_case_limit(context.vacancy)),
        )
        if "github" in proof_request_tags and github_url and "GitHub:" not in proof_text:
            issues.append("missing_requested_github")
        proof_pack_url = _known_proof_pack_url(context.profile)
        if (
            proof_pack_url
            and proof_request_tags & {"cases", "ai_projects", "agents", "own_agents", "automations", "presentations"}
            and proof_pack_url not in proof_text
        ):
            issues.append("missing_requested_yandex_case_pack")

    selected_cases = _best_cases(context.profile, context.vacancy, limit=_response_case_limit(context.vacancy))
    mentioned_cases = [case for case in selected_cases if _short_case_title(case) in text or case.title in text]
    if selected_cases and not mentioned_cases:
        issues.append("missing_relevant_case")
    if _is_agentic_vacancy(context.vacancy) and len(mentioned_cases) > 3:
        issues.append("resume_recap_dump")

    anchors = _focus_terms(context.vacancy)[:8] or context.vacancy.skills[:5]
    if anchors and not any(_norm(anchor) in lowered for anchor in anchors):
        issues.append("missing_vacancy_anchors")

    important_requirements = _important_requirements(context.vacancy)
    if important_requirements and not any(
        marker in lowered
        for marker in [
            "мне близко",
            "мне близок",
            "акцент",
            "упор",
            "практика",
            "прикладную часть",
            "главный фокус",
            "задача",
            "нужны",
        ]
    ):
        issues.append("missing_important_requirements")
    requirement_terms = _requirement_focus_terms(important_requirements, context.vacancy) if important_requirements else []
    if requirement_terms and not any(_norm(term) in lowered for term in requirement_terms[:4]):
        issues.append("missing_specific_requirement_terms")
    if selected_cases and context.vacancy.skills and not any(
        marker in lowered
        for marker in ["работал с", "делал", "строил", "занимался", "настраивал", "собирал", "проектировал"]
    ):
        issues.append("missing_stack_evidence")
    if (
        "по стеку из вакансии" in lowered
        or "что у вас обозначено как важное" in lowered
        or "— применял" in lowered
        or "для таких задач важно не просто" in lowered
    ):
        issues.append("robotic_structure")
    if AWKWARD_AROUND_RE.search(lowered):
        issues.append("awkward_around_phrase")
    if RUSSIAN_CONTOUR_RE.search(lowered):
        issues.append("banned_phrase:контур")
    if len(DEPLOY_WORD_RE.findall(lowered)) > 2:
        issues.append("repeated_deploy_wording")
    repetition_text = "\n".join(
        line
        for line in text.splitlines()
        if not any(
            label in line
            for label in [
                "Portfolio:",
                "Website:",
                "Портфолио:",
                "Сайт:",
                "Telegram:",
                "GitHub:",
                "Yandex Disk",
                "Яндекс",
                "кейсы",
                "Кейсы",
            ]
        )
    )
    repetition_lowered = _norm(repetition_text)
    for focus in _focus_terms(context.vacancy):
        normalized_focus = _norm(focus)
        if normalized_focus in REPEATED_FOCUS_EXEMPT_TERMS:
            continue
        if len(normalized_focus) >= 6 and repetition_lowered.count(normalized_focus) > 3:
            issues.append("repeated_focus_wording")
            break
    for phrase in ROBOTIC_COVER_LETTER_PHRASES:
        if phrase in lowered:
            issues.append(f"robotic_phrase:{phrase}")
    if any(phrase in text for phrase in LEGACY_REPEATED_TEMPLATE_PHRASES):
        issues.append("generic_repeated_template")
    if "fpv40" in lowered and (
        not _is_fpv40_domain_vacancy(context.vacancy) or _is_data_engineering_vacancy(context.vacancy)
    ):
        issues.append("irrelevant_fpv40_case")
    if re.search(r'увидел вакансию\s+[«"]', lowered):
        issues.append("quoted_vacancy_title")
    if (important_requirements or len(anchors) >= 5) and len(text) < 380:
        issues.append("too_short_for_complex_vacancy")

    for phrase in GENERIC_PHRASES:
        if phrase in lowered:
            issues.append(f"generic_phrase:{phrase}")

    issues.extend(_anti_ai_style_issues(text))

    paragraphs = [paragraph for paragraph in text.split("\n\n") if paragraph.strip()]
    if len(paragraphs) > 4:
        issues.append("too_many_paragraphs")

    if len(text) > 1700:
        issues.append("too_long")
    if "[" in text or "]" in text or "{" in text or "}" in text:
        issues.append("template_artifact")

    # Keep order stable but avoid duplicate flags when phrase lists overlap.
    issues = list(dict.fromkeys(issues))
    return CoverLetterQualityCheck(passed=not issues, issues=issues)
