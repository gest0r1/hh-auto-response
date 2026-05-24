from app.review_export import render_markdown_review_queue


def test_render_markdown_review_queue_contains_apply_link_and_draft():
    markdown = render_markdown_review_queue(
        [
            {
                "title": "Python React automation engineer",
                "company": "AgentCo",
                "score": 91,
                "decision": "hot",
                "url": "https://hh.ru/vacancy/777",
                "apply_url": "https://hh.ru/applicant/vacancy_response?vacancyId=777",
                "cover_letter": "Здравствуйте! Готов обсудить автоматизацию CRM.",
                "score_reasons": ["remote/удалёнка", "skill match: Python"],
                "score_penalties": [],
            }
        ]
    )

    assert "# HH no-API review queue" in markdown
    assert "Python React automation engineer" in markdown
    assert "Score: 91 / hot" in markdown
    assert "Отклик: https://hh.ru/applicant/vacancy_response?vacancyId=777" in markdown
    assert "Готов обсудить автоматизацию CRM" in markdown
