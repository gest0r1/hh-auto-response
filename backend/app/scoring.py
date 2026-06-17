from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CandidateProfile:
    target_roles: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    preferred_keywords: list[str] = field(default_factory=list)
    stop_keywords: list[str] = field(default_factory=list)
    min_monthly_salary: int | None = None
    learning_weights: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class Vacancy:
    external_id: str
    title: str
    company: str
    description: str
    url: str
    salary_from: int | None = None
    salary_to: int | None = None
    currency: str | None = None
    schedule: str | None = None
    employment: str | None = None
    skills: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScoreResult:
    score: int
    decision: str
    reasons: list[str] = field(default_factory=list)
    penalties: list[str] = field(default_factory=list)


def _norm(value: str | None) -> str:
    return (value or "").replace("ё", "е").lower()


def _vacancy_text(vacancy: Vacancy) -> str:
    chunks = [vacancy.title, vacancy.company, vacancy.description, vacancy.schedule or "", vacancy.employment or ""]
    chunks.extend(vacancy.skills)
    return _norm(" ".join(chunks))


def _contains(text: str, needle: str) -> bool:
    normalized = _norm(needle).replace("-", " ")
    return normalized in text.replace("-", " ")


def _salary_midpoint(vacancy: Vacancy) -> int | None:
    values = [v for v in [vacancy.salary_from, vacancy.salary_to] if isinstance(v, int) and v > 0]
    if not values:
        return None
    return round(sum(values) / len(values))


_NEGATIVE_REMOTE_PATTERNS = (
    re.compile(r"\bне\s+удаленно\b"),
    re.compile(r"\bбез\s+удаленки\b"),
    re.compile(r"\bудаленка\s+не\s+предусмотрена\b"),
    re.compile(r"\bудаленная\s+работа\s+не\s+предусмотрена\b"),
)


def _is_remote(vacancy: Vacancy, text: str) -> bool:
    normalized_text = _norm(text)
    if any(pattern.search(normalized_text) for pattern in _NEGATIVE_REMOTE_PATTERNS):
        return False
    return any(
        marker in normalized_text
        for marker in ["remote", "удаленно", "удаленная", "удаленка", "удалённо", "удалённая"]
    )


_HARD_TITLE_STOP_TERMS = (
    "c#",
    ".net",
    "dotnet",
    "qa engineer",
    "qa automation",
    "sdet",
    "software development engineer in test",
    "qa автоматизатор",
    "qa инженер",
    "aqa",
    "тестировщик",
    "quality assurance",
    "системный аналитик",
    "business analyst",
    "sales",
    "продаж",
    "маркетолог",
    "php",
    "symfony",
    "laravel",
    "bitrix",
    "bitrix24",
    "битрикс",
    "битрикс24",
    "odoo",
    "стажер",
    "intern",
    "internship",
    "head of it",
    "руководитель it",
    "appsec",
    "application security",
    "security",
    "data engineer",
    "data engineering",
    "etl developer",
    "bi developer",
    "mlops специалист",
    "mlops engineer",
    "инженер mlops",
    "technical writer",
    "технический писатель",
    "техписатель",
    "документатор",
    "documentation",
    "copywriter",
    "копирайтер",
    "редактор",
    "content writer",
    "recruiter",
    "it recruiter",
    "talent manager",
    "sourcer",
    "рекрутер",
    "ml engineer",
    "ml инженер",
    "ml developer",
    "ml разработчик",
    "machine learning engineer",
    "инженер машинного обучения",
    "embedded",
    "embedded software",
    "встроенного по",
    "встроенного программного обеспечения",
    "ии оператор",
    "ai operator",
    "оператор ии",
)


_HARD_TITLE_STOP_PATTERNS = (
    # HH sometimes writes QA roles as "QA (auto/manual) backend"; substring terms like
    # "qa automation" miss this, and it can look like a backend vacancy after keyword scoring.
    (re.compile(r"\bqa\b"), "qa"),
)


_GO_TITLE_STOP_PATTERNS = (
    (re.compile(r"\bgolang\b"), "golang"),
    (re.compile(r"\bgo\s+(?:developer|engineer|разработчик|программист|backend|бекенд)\b"), "go разработчик"),
    (re.compile(r"\b(?:developer|engineer|разработчик|программист|backend|бекенд)\s+(?:на\s+)?go\b"), "go разработчик"),
)


_OFFICE_ONLY_PATTERNS = (
    (re.compile(r"\bважно:\s*работа\s+в\s+офисе\b"), "работа в офисе"),
    (re.compile(r"\bработа\s+(?:в\s+офисе|из\s+офиса)\b"), "работа в офисе"),
    (re.compile(r"\bв\s+офис(?:е)?\b"), "в офис"),
)


def _title_stop_penalties(title: str) -> list[str]:
    normalized_title = _norm(title).replace("-", " ")
    penalties = [term for term in _HARD_TITLE_STOP_TERMS if term in normalized_title]
    penalties.extend(label for pattern, label in _HARD_TITLE_STOP_PATTERNS if pattern.search(normalized_title))
    penalties.extend(label for pattern, label in _GO_TITLE_STOP_PATTERNS if pattern.search(normalized_title))
    return penalties


def _office_only_penalties(text: str, remote: bool) -> list[str]:
    if remote:
        return []
    for pattern, label in _OFFICE_ONLY_PATTERNS:
        if pattern.search(text):
            return [label]
    return []


def _decision(score: int) -> str:
    if score >= 85:
        return "hot"
    if score >= 70:
        return "review"
    if score >= 55:
        return "maybe"
    return "archive"


def score_vacancy(vacancy: Vacancy, profile: CandidateProfile) -> ScoreResult:
    """Score a vacancy for Aleksandr's HH CRM.

    The function is intentionally deterministic: it can run inside cron/scripts, be tested, and later
    be blended with LLM scoring without losing a stable baseline.
    """
    text = _vacancy_text(vacancy)
    score = 35
    reasons: list[str] = []
    penalties: list[str] = []

    matched_skills: list[str] = []
    for skill in profile.skills:
        if _contains(text, skill):
            matched_skills.append(skill)
            weight = profile.learning_weights.get(skill, profile.learning_weights.get(skill.lower(), 1.0))
            score += max(4, round(8 * weight))
            reasons.append(f"skill match: {skill}")
    if matched_skills:
        # Prevent huge keyword-stuffed descriptions from dominating the score.
        skill_bonus = min(32, len(matched_skills) * 8)
        score -= max(0, len(matched_skills) * 8 - skill_bonus)

    role_hits = 0
    for role in profile.target_roles:
        role_tokens = [token for token in _norm(role).replace("-", " ").split() if len(token) > 2]
        if role_tokens and all(token in text.replace("-", " ") for token in role_tokens[:2]):
            role_hits += 1
            reasons.append(f"role fit: {role}")
    score += min(15, role_hits * 5)

    preferred_hits = 0
    for keyword in profile.preferred_keywords:
        if _contains(text, keyword):
            preferred_hits += 1
            reasons.append(f"preferred keyword: {keyword}")
    score += min(15, preferred_hits * 5)

    remote = _is_remote(vacancy, text)
    if remote:
        score += 10
        reasons.append("remote/удалёнка")

    office_text = _norm(" ".join([vacancy.title, vacancy.description]))
    office_only_stops = _office_only_penalties(office_text, remote)
    for stop in office_only_stops:
        score -= 35
        stop_reason = f"офис без удаленки: {stop}"
        penalties.append(stop_reason)
        reasons.append(stop_reason)

    title_stops = _title_stop_penalties(vacancy.title)
    for stop in title_stops:
        score -= 35
        stop_reason = f"стоп в названии: {stop}"
        penalties.append(stop_reason)
        reasons.append(stop_reason)

    midpoint = _salary_midpoint(vacancy)
    if profile.min_monthly_salary and midpoint:
        if midpoint >= profile.min_monthly_salary:
            score += 10
            reasons.append(f"salary >= target: {midpoint}")
        elif remote and midpoint >= 100_000:
            reasons.append(f"salary flexible remote: {midpoint}")
        elif midpoint >= 100_000:
            score -= 5
            penalties.append(f"salary below comfort but workable: {midpoint}")
        elif midpoint < profile.min_monthly_salary * 0.8:
            score -= 15
            penalties.append(f"salary below target: {midpoint}")
        else:
            score -= 5
            penalties.append(f"salary slightly below target: {midpoint}")

    stop_keyword_matched = False
    for stop in profile.stop_keywords:
        if _contains(text, stop):
            stop_keyword_matched = True
            score -= 20
            stop_reason = f"стоп-слово: {stop}"
            penalties.append(stop_reason)
            reasons.append(stop_reason)

    for term, weight in profile.learning_weights.items():
        if term and _contains(text, term):
            learned_delta = round((weight - 1.0) * 6)
            if learned_delta:
                score += learned_delta
                if learned_delta > 0:
                    reasons.append(f"learned preference: {term} +{learned_delta}")
                else:
                    penalties.append(f"learned penalty: {term} {learned_delta}")

    if title_stops:
        # Hard title mismatches should stay out of the autonomous review/send path even when
        # the vacancy is keyword-stuffed with preferred tech, remote work, and high salary.
        score = min(score, 69)

    if office_only_stops:
        score = min(score, 69)

    if stop_keyword_matched:
        # Stop keywords are quality gates for autonomous outreach, not mild hints.
        # A keyword-stuffed vacancy must not stay hot just because it also mentions Python/LLM.
        score = min(score, 54)

    final_score = max(0, min(100, round(score)))
    return ScoreResult(score=final_score, decision=_decision(final_score), reasons=reasons, penalties=penalties)
