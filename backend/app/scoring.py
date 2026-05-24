from __future__ import annotations

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

    if any(marker in text for marker in ["remote", "удаленно", "удаленная", "удаленка", "удалённо", "удалённая"]):
        score += 10
        reasons.append("remote/удалёнка")

    midpoint = _salary_midpoint(vacancy)
    if profile.min_monthly_salary and midpoint:
        if midpoint >= profile.min_monthly_salary:
            score += 10
            reasons.append(f"salary >= target: {midpoint}")
        elif midpoint < profile.min_monthly_salary * 0.8:
            score -= 20
            penalties.append(f"salary below target: {midpoint}")
        else:
            score -= 8
            penalties.append(f"salary slightly below target: {midpoint}")

    for stop in profile.stop_keywords:
        if _contains(text, stop):
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

    final_score = max(0, min(100, round(score)))
    return ScoreResult(score=final_score, decision=_decision(final_score), reasons=reasons, penalties=penalties)
