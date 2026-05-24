from __future__ import annotations

from typing import Any


def _bullets(values: list[str], *, fallback: str = "нет") -> str:
    if not values:
        return fallback
    return "\n".join(f"  - {value}" for value in values)


def render_markdown_review_queue(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# HH no-API review queue",
        "",
        "Черновики подготовлены из публичной выдачи HH без OAuth/API. Отклик — это ссылка на форму HH; текст ниже можно вставить и отредактировать.",
        "",
    ]
    if not rows:
        lines.extend(["Очередь пуста: подходящих draft-вакансий выше порога пока нет.", ""])
        return "\n".join(lines)

    for index, row in enumerate(rows, start=1):
        title = row.get("title") or "Без названия"
        company = row.get("company") or "Компания не указана"
        score = row.get("score")
        decision = row.get("decision") or "review"
        vacancy_url = row.get("url") or ""
        apply_url = row.get("apply_url") or vacancy_url
        cover_letter = row.get("cover_letter") or ""
        reasons = [str(value) for value in row.get("score_reasons") or []]
        penalties = [str(value) for value in row.get("score_penalties") or []]
        lines.extend(
            [
                f"## {index}. {title}",
                f"Company: {company}",
                f"Score: {score} / {decision}",
                f"Вакансия: {vacancy_url}",
                f"Отклик: {apply_url}",
                "Почему подходит:",
                _bullets(reasons),
            ]
        )
        if penalties:
            lines.extend(["Риски:", _bullets(penalties)])
        lines.extend(["Черновик:", "```text", cover_letter, "```", ""])
    return "\n".join(lines)
