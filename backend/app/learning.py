from __future__ import annotations

import re
from dataclasses import dataclass, field


POSITIVE_EVENTS = {"approved", "sent", "reply", "interview", "offer"}
NEGATIVE_EVENTS = {"rejected", "archived", "not_interested", "discard"}
CANONICAL_TERMS = [
    "CRM",
    "Telegram",
    "FastAPI",
    "React",
    "Python",
    "Node.js",
    "LLM",
    "AI",
    "интеграции",
    "дашборд",
    "удаленно",
    "удалённо",
    "офис",
    "Bitrix",
    "битрикс",
]


@dataclass(slots=True)
class LearningUpdate:
    weights: dict[str, float]
    extracted_preferences: list[str] = field(default_factory=list)
    negative_signals: list[str] = field(default_factory=list)
    delta: float = 0.0


class LearningEngine:
    def __init__(self, initial_weights: dict[str, float] | None = None) -> None:
        self.weights: dict[str, float] = dict(initial_weights or {})

    def learn_from_feedback(
        self,
        *,
        event_type: str,
        vacancy_keywords: list[str],
        rating: int | None = None,
        edited_cover_letter: str | None = None,
        notes: str | None = None,
    ) -> LearningUpdate:
        normalized_event = event_type.lower().strip()
        rating_value = max(1, min(5, rating or 3))
        if normalized_event in POSITIVE_EVENTS:
            delta = 0.12 + rating_value * 0.06
        elif normalized_event in NEGATIVE_EVENTS:
            delta = -(0.15 + (6 - rating_value) * 0.08)
        else:
            delta = 0.02 * (rating_value - 3)

        extracted = self._extract_terms(" ".join([edited_cover_letter or "", notes or ""]))
        terms = self._dedupe([*vacancy_keywords, *extracted])
        negative_signals: list[str] = []
        for term in terms:
            current = self.weights.get(term, 1.0 if delta >= 0 else 0.0)
            updated = round(current + delta, 3)
            self.weights[term] = updated
            if updated < 0:
                negative_signals.append(term)

        return LearningUpdate(
            weights=dict(self.weights),
            extracted_preferences=extracted,
            negative_signals=negative_signals,
            delta=delta,
        )

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if not value:
                continue
            key = value.casefold()
            if key not in seen:
                seen.add(key)
                result.append(value)
        return result

    @staticmethod
    def _extract_terms(text: str) -> list[str]:
        if not text:
            return []
        result: list[str] = []
        lowered = text.casefold()
        for term in CANONICAL_TERMS:
            if term.casefold() in lowered:
                result.append(term)
        # Capture short all-caps business nouns that often encode user preferences: CRM, ERP, LLM.
        for token in re.findall(r"\b[A-ZА-ЯЁ]{2,6}\b", text):
            if token not in result:
                result.append(token)
        return result
