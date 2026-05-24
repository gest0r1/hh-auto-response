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
- Пишем не микроскопический, а содержательный отклик: обычно 4–6 коротких абзацев плюс портфолио.
- Не льём воду и не пишем «я это знаю». Каждый важный стек/требование связываем с конкретным проектом: где и когда применял, что именно делал, какой был контур.
- Отдельно отыгрываем блоки «Что важно», «Будет плюсом», «Требования»: если у Александра есть целевой опыт, сразу показываем его фактами.
- Привязываем текст к вакансии, стеку, релевантным кейсам и портфолио.
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
]


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
    return any(marker in text for marker in ["agent", "агент", "llm", "rag", "cursor", "codex", "claude code"])


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
        marker in case_text for marker in ["agent", "агент", "llm", "openclaw", "vibegent", "viably"]
    ):
        score += 10
    if _is_agentic_vacancy(vacancy):
        priority_boosts = {
            "openclaw": 52,
            "vibegent-proxy": 28,
            "vibegent": 50,
            "viably": 48,
            "llm infrastructure": 28,
            "agent cloud": 22,
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
        ("AI-агенты", ["ai-агент", "ai agents", "agent systems", "agentic"]),
        ("agentic SDLC", ["agentic sdlc"]),
        ("роли агентов", ["analyst agent", "architect agent", "reviewer agent", "qa agent", "security agent"]),
        ("human-in-the-loop", ["human-in-the-loop"]),
        ("Definition of Done", ["definition of done"]),
        ("CI/CD", ["ci/cd", "github", "gitlab"]),
        ("test automation", ["test automation", "тест"]),
        ("security checks", ["security checks", "security"]),
        ("release gates", ["release gates", "релиз"]),
        ("LLM/RAG", ["llm", "rag"]),
        ("production-инфраструктура", ["production", "инфраструктур"]),
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
    fragments = []
    for case in cases:
        matched_stack = _case_stack_terms(vacancy, case)
        stack = _join_ru(matched_stack, 6)
        label = _case_label(case)
        role = f", {case.role}" if case.role else ""
        detail = _truncate_sentence(case.description or case.result, 160, split_semicolon=True)
        if detail:
            fragments.append(f"{stack} — применял в {label}{role}: {detail}")
        else:
            fragments.append(f"{stack} — применял в {label}{role}")
    return "По стеку из вакансии: " + "; ".join(fragments) + "."


def _requirement_items(raw: str) -> list[str]:
    normalized = re.sub(r"\s+-\s+", "; ", raw)
    parts = [part.strip(" ;,.—-") for part in re.split(r";|•", normalized)]
    return [part for part in parts if len(part) >= 8]


def _important_requirements(vacancy: Vacancy) -> list[str]:
    description = re.sub(r"\s+", " ", vacancy.description or "").strip()
    if not description:
        return []
    result: list[str] = []
    patterns = [
        r"(?:что\s+важно|важно)\s*[:—-]\s*([^.]*)",
        r"(?:будет\s+плюсом|плюсом\s+будет)\s*[:—-]?\s*([^.]*)",
        r"(?:требования|ключевые\s+требования)\s*[:—-]\s*([^.]*)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, description, flags=re.IGNORECASE):
            for item in _requirement_items(match.group(1)):
                clean = _truncate_sentence(item, 135, split_semicolon=False)
                if clean and clean not in result:
                    result.append(clean)
    return result[:8]


def _requirement_relevance(requirement: str, cases: list[CaseStudy], vacancy: Vacancy) -> int:
    req_tokens = _tokens(requirement)
    case_tokens = _tokens(" ".join(_case_text(case) for case in cases))
    focus_tokens = _tokens(" ".join(_focus_terms(vacancy)[:5]))
    return len(req_tokens & case_tokens) * 2 + len(req_tokens & focus_tokens)


def _important_requirements_sentence(vacancy: Vacancy, cases: list[CaseStudy]) -> str:
    requirements = _important_requirements(vacancy)
    if not requirements:
        return ""
    ranked = sorted(requirements, key=lambda item: _requirement_relevance(item, cases, vacancy), reverse=True)
    selected = [item for item in ranked if _requirement_relevance(item, cases, vacancy) > 0][:4] or ranked[:3]
    anchors = _join_ru(_focus_terms(vacancy)[:5], 5)
    evidence_cases = ", ".join(_case_label(case) for case in cases[:2])
    evidence_tail = f"это закрывал в {evidence_cases}" if evidence_cases else "это закрывал в рабочих проектах"
    return (
        "Что у вас обозначено как важное: "
        + "; ".join(selected)
        + f". По этому блоку у меня прикладной опыт, не только теория: {anchors}; {evidence_tail}."
    )


def _delivery_sentence(vacancy: Vacancy) -> str:
    if _is_agentic_vacancy(vacancy):
        return (
            "В вашей задаче вижу не просто «поставить Cursor», а собрать управляемый delivery: "
            "роли агентов, human-in-the-loop, Definition of Done, code review, тесты, "
            "security checks и release gates."
        )
    return (
        "Могу быстро включиться: разобрать требования, предложить план реализации, "
        "собрать первый рабочий контур и дальше развивать систему итерациями."
    )


def _closing_sentence(vacancy: Vacancy) -> str:
    product = _product_label(vacancy)
    if product != "продукта" and _is_agentic_vacancy(vacancy):
        return f"Готов начать с аудита текущего backlog/архитектуры и предложить короткий план agentic SDLC для {product}."
    return "Готов начать с короткого аудита текущего контура и предложить понятный план следующих шагов."


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
    cases = _best_cases(profile, vacancy, limit=3 if _is_agentic_vacancy(vacancy) else 1)
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

    message_parts = [
        f"Здравствуйте! Увидел вакансию «{_clean_title(vacancy.title)}». "
        f"По описанию это близко к моему текущему профилю: {_join_ru(focus, 5)}.",
    ]
    case_sentence = _case_evidence_sentence(cases, vacancy)
    if case_sentence:
        message_parts.append(case_sentence)
    else:
        message_parts.append(f"Я {profile.headline}. Сильные стороны: {_join_ru(strengths, 2)}.")
    important_sentence = _important_requirements_sentence(vacancy, cases)
    if important_sentence:
        message_parts.append(important_sentence)
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

    selected_cases = _best_cases(context.profile, context.vacancy, limit=3 if _is_agentic_vacancy(context.vacancy) else 1)
    if selected_cases and not any(_short_case_title(case) in text or case.title in text for case in selected_cases):
        issues.append("missing_relevant_case")

    anchors = _focus_terms(context.vacancy)[:8] or context.vacancy.skills[:5]
    if anchors and not any(_norm(anchor) in lowered for anchor in anchors):
        issues.append("missing_vacancy_anchors")

    important_requirements = _important_requirements(context.vacancy)
    if important_requirements and "что у вас обозначено как важное" not in lowered:
        issues.append("missing_important_requirements")
    if selected_cases and context.vacancy.skills and "применял в" not in lowered:
        issues.append("missing_stack_evidence")
    if (important_requirements or len(anchors) >= 5) and len(text) < 650:
        issues.append("too_short_for_complex_vacancy")

    for phrase in GENERIC_PHRASES:
        if phrase in lowered:
            issues.append(f"generic_phrase:{phrase}")

    if len(text) > 2200:
        issues.append("too_long")
    if "[" in text or "]" in text or "{" in text or "}" in text:
        issues.append("template_artifact")

    return CoverLetterQualityCheck(passed=not issues, issues=issues)
