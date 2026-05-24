from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.scoring import Vacancy


DEFAULT_COVER_LETTER_METHODOLOGY_PATH = Path(__file__).resolve().parents[2] / "docs" / "cover-letter-methodology.md"
BUILTIN_COVER_LETTER_METHODOLOGY = """# HH cover-letter methodology

- Начинаем с «Здравствуйте!» без обращения по имени/названию работодателя.
- Не обращаемся к работодателю по названию компании: не пишем «Здравствуйте, ИП ...», «Здравствуйте, ООО ...» или «Здравствуйте, CompanyName».
- Пишем живым человеческим plain-text стилем Александра: спокойно, конкретно, без AI-глянца и канцелярита.
- Не ставим название вакансии в кавычки и не строим текст как переписанную вакансию.
- Не используем роботные блоки вроде «По стеку из вакансии» и «Что у вас обозначено как важное».
- Не пишем через тире-связки вида «LLM — применял в ...». Лучше обычные фразы: «В Vibegent делал...», «В Viably работал с...».
- Запрещён AI-оборот «Для таких задач важно не просто ...». Он звучит как сгенерированный ответ.
- Текст не должен быть слишком вылизанным: лучше чуть разговорнее, короче, с естественной шероховатостью, но без намеренных грубых ошибок.
- Стек и требования связываем с конкретными проектами, но естественно, без длинных перечислений из карточки HH и без пересказа резюме.
- Отклик должен быть vacancy-first: сначала что работодатель ждёт/где боль, потом 1–2 сильных доказательства под эту задачу.
- Перед выбором кейсов обязательно читаем смысловые блоки вакансии: «Чем предстоит заниматься», «Что мы ждём», «Кого ищем», «Что важно», «Будет плюсом/круто». В отклике должен быть один живой абзац, который прямо отыгрывает 2–5 конкретных ожиданий из этих блоков.
- Для agentic/AgentOps/LLMOps вакансий не ограничиваемся Vibegent/Viably при выборе доказательств, но в финальный текст не вываливаем весь список: выбираем 1–2 самых точных попадания.
- Блок «Что важно» по AI-agent вакансиям отыгрываем прямо: «Это как раз мой профиль: не отдельный чат-бот, а рабочий агентный контур...».
- Для Kwork/коротких one-sentence откликов во многих случаях по умолчанию нужен зуб: «не очередной вайбкодер», реальный прикладной опыт в коде и архитектуре, AI-софт под прибыль бизнеса.
- Допускается лёгкая высокомерность, если она опирается на факты и цепляет: «не про красивые демки», «тут нужен не парсер ради парсера», «AI как ускоритель, не замена голове».
- Если площадка запрещает внешние ссылки, не добавляем портфолио силой; усиливаем привязку к стеку, кейсу и бизнес-результату.
- Портфолио отдельной строкой, когда ссылки разрешены.
- Перед финалом делаем humanizer-pass: убираем чатбот-обвязку, пустые вводные, канцелярит, рекламный тон, раздувание значимости, фальшивые авторитеты, деепричастные хвосты и механическое форматирование.
- Один острый контраст допустим, если он бьёт в вакансию; повторяющиеся «не просто X, а Y» / «не только X, но и Y» выглядят как AI-slop.
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
    location: str | None = None
    telegram: str | None = None
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


def _norm(value: str | None) -> str:
    return (value or "").replace("ё", "е").lower()


def _has_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


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


def _case_relevance(case: CaseStudy, vacancy: Vacancy) -> int:
    vacancy_text = _norm(" ".join([vacancy.title, vacancy.description, *vacancy.skills]))
    case_text = _norm(_case_text(case))
    score = 0
    for skill in vacancy.skills:
        if _contains_term(case_text, skill):
            score += 8
    shared_tokens = _tokens(vacancy.title + " " + " ".join(vacancy.skills)) & _tokens(_case_text(case))
    score += min(12, len(shared_tokens) * 2)
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
    relevant = [case for case, score in ranked if score > 0]
    if relevant:
        return relevant[:limit]
    return profile.cases[:1]


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
        ("AI-агенты", ["ai-агент", "ai agents", "agent systems", "agentic", "ассистент"]),
        ("быстрые SaaS/MVP-гипотезы", ["saas", "mvp", "прототип", "гипотез", "time-to-market"]),
        ("Replit/Cursor", ["replit", "cursor"]),
        ("MCP-серверы", ["mcp", "model context protocol"]),
        ("prompt engineering", ["промпт", "prompt"]),
        ("самостоятельный запуск и деплой", ["под ключ", "самостоятельно", "задепло", "deploy", "без помощи devops"]),
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
        ("owner-return", ["owner-return", "возврат результата"]),
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
        if skill and skill not in result:
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
            return f"В {label} делал LLM-proxy слой: ротация токенов, backoff, retry/fallback и контроль credits."

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
            return f"В {label} настраивал Hermes как рабочий AgentOps-контур: Telegram gateway, memory, skills, knowledge base, retrieval, cron health checks и reports."

        if "openclaw" in case_key:
            if detail:
                detail = re.sub(r"^production-стабилизаци[яю]\s*", "", detail, flags=re.IGNORECASE)
                return f"В {label} стабилизировал агентную среду: {detail}."
            return f"В {label} стабилизировал агентную среду и runtime-контур."

        if "heisenberg" in full_key:
            return f"В {label} собирал многоагентную команду с ролями, координатором, Board-First workflow, handoff и quality gates."

        if "ai office" in full_key or "agent command center" in full_key:
            return f"В {label} делал AI-офис/agent dashboard: роли, кабинеты, статусы, задачи и проверяемый frontend-preview."

        if "ai-отдел" in full_key or "business agents" in full_key:
            return f"По бизнес-агентам у меня есть {label}: sales/support ops, лиды, CRM/таблицы, Telegram/Web, human-in-the-loop и owner-return."

        if "viably" in case_key:
            base = f"По backend и продуктовой части у меня есть {label}. Там работал с {stack}"
            return f"{base}: {detail}." if detail else f"{base}."

        prefix = "Ближайший похожий кейс у меня" if first else "Ещё релевантный опыт есть в"
        base = f"{prefix} {label}. Там работал с {stack}"
        if detail:
            detail_has_action = re.match(r"^(делал|строил|занимался|собирал|разв[её]ртывал|настраивал)\b", _norm(detail))
            return f"{base}: {detail}." if detail_has_action else f"{base}: делал {detail}."
        return f"{base}."

    if _is_agentic_vacancy(vacancy):
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
            return (
                "Из похожего опыта: "
                + " ".join(selected[:2])
                + " Это тот слой, где прототип приходится проверять, деплоить и развивать после первого красивого показа."
            )

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

    add("Replit/Cursor", ["replit", "cursor"])
    add("MCP-серверы", ["mcp", "model context protocol"])
    add("быстрые SaaS/MVP-гипотезы", ["saas", "mvp", "прототип", "гипотез", "time-to-market"], include_full_text=True)
    add("AI-агенты/ассистенты", ["ai-агент", "ai агент", "агент", "ассистент"])
    add("самостоятельный запуск под ключ", ["под ключ", "самостоятельно", "без помощи devops", "задепло", "деплой", "deploy"])
    add("prompt engineering и качество ответов", ["промпт", "prompt", "качество ответ"])
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
    if _is_agentic_vacancy(vacancy):
        if "не обучаем модели" in vacancy_text or "pytorch" in vacancy_text:
            return (
                f"По описанию вижу главный фокус: {anchors}. "
                "Мой опыт ближе к прикладному AI-продукту: быстро собрать, проверить, задеплоить и показать бизнесу."
            )
        return (
            f"По описанию вижу главный фокус: {anchors}. "
            "Я работаю с таким слоем: агентная логика, интеграции, память/routing, тесты, деплой и понятный возврат результата владельцу."
        )
    return (
        f"Мне близко, что у вас в описании упор на {anchors}. "
        "Я больше про практику: быстро разобраться в требованиях, собрать рабочий контур, "
        "закрыть интеграции и довести до нормального релиза."
    )


def _delivery_sentence(vacancy: Vacancy) -> str:
    if _is_agentic_vacancy(vacancy):
        return ""
    return (
        "Могу быстро включиться: разобрать требования, предложить план реализации, "
        "собрать первый рабочий контур и дальше развивать систему итерациями."
    )


def _closing_sentence(vacancy: Vacancy) -> str:
    product = _product_label(vacancy)
    if _is_agentic_vacancy(vacancy):
        if product != "продукта":
            return f"Готов подключиться: сначала разобрал бы текущий контур и набросал короткий практичный план по {product}."
        return "Если нужен человек, который доводит AI-идею до рабочего продукта и спокойно режет лишнюю магию вокруг vibe coding, готов поговорить."
    return "Готов подключиться и быстро разобрать, что у вас сейчас есть, а что лучше усилить первым."


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

    portfolio_sentence = ""
    if profile.portfolio_url:
        portfolio_sentence = f"Портфолио: {profile.portfolio_url}"
    elif profile.website_url:
        portfolio_sentence = f"Сайт: {profile.website_url}"

    if _is_agentic_vacancy(vacancy):
        message_parts = [
            f"Здравствуйте! Увидел вакансию {_clean_title(vacancy.title)}. "
            "Тут нужен не пересказчик промптов, а человек, который быстро превращает идею в рабочий AI-продукт."
        ]
    else:
        message_parts = [
            f"Здравствуйте! Увидел вакансию {_clean_title(vacancy.title)}. "
            f"По смыслу это близко к тому, чем я сейчас занимаюсь: {_join_ru(focus, 5)}."
        ]
    important_sentence = _important_requirements_sentence(vacancy, cases)
    if important_sentence:
        message_parts.append(important_sentence)
    case_sentence = _case_evidence_sentence(cases, vacancy)
    if case_sentence:
        message_parts.append(case_sentence)
    else:
        message_parts.append(f"Я {profile.headline}. Сильные стороны: {_join_ru(strengths, 2)}.")
    message_parts.append(_delivery_sentence(vacancy))
    message_parts.append(_closing_sentence(vacancy))
    if portfolio_sentence:
        message_parts.append(portfolio_sentence)

    message = sanitize_cover_letter_greeting("\n\n".join(part for part in message_parts if part))
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

    if not text.startswith("Здравствуйте!"):
        issues.append("bad_greeting")
    first_sentence = text.split(".", 1)[0]
    if re.match(r"^\s*Здравствуйте\s*,", first_sentence, flags=re.IGNORECASE):
        issues.append("employer_in_greeting")
    company = (context.vacancy.company or "").strip()
    if company and company != "Компания не указана" and company.lower() in first_sentence.lower().replace("ё", "е"):
        issues.append("company_in_first_sentence")

    portfolio_url = context.profile.portfolio_url or context.profile.website_url
    if portfolio_url:
        expected_label = "Портфолио:" if context.profile.portfolio_url else "Сайт:"
        expected_line = f"{expected_label} {portfolio_url}"
        if expected_line not in text.splitlines():
            issues.append("missing_portfolio")

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
        for marker in ["мне близко", "мне близок", "акцент", "упор", "практика", "прикладную часть", "главный фокус"]
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
    if re.search(r'увидел вакансию\s+[«"]', lowered):
        issues.append("quoted_vacancy_title")
    if (important_requirements or len(anchors) >= 5) and len(text) < 650:
        issues.append("too_short_for_complex_vacancy")

    for phrase in GENERIC_PHRASES:
        if phrase in lowered:
            issues.append(f"generic_phrase:{phrase}")

    issues.extend(_anti_ai_style_issues(text))

    if len(text) > 2200:
        issues.append("too_long")
    if "[" in text or "]" in text or "{" in text or "}" in text:
        issues.append("template_artifact")

    # Keep order stable but avoid duplicate flags when phrase lists overlap.
    issues = list(dict.fromkeys(issues))
    return CoverLetterQualityCheck(passed=not issues, issues=issues)
