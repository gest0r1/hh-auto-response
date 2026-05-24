from __future__ import annotations

import httpx

from app.hh_vacancy import HHPublicVacancyClient, extract_hh_vacancy_id, parse_hh_vacancy_html


SAMPLE_HH_VACANCY_HTML = """
<html>
<head>
<title>Вакансия AI Delivery Lead / Архитектор разработки на AI-агентах в Москве, работа в компании Фордевинд</title>
<meta name="description" content="Вакансия AI Delivery Lead / Архитектор разработки на AI-агентах в компании Фордевинд. Зарплата: от 270000 до 420000 ₽ за месяц. Москва. Требуемый опыт: 1–3 года. Занятость: полная.">
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "JobPosting",
  "title": "AI Delivery Lead / Архитектор разработки на AI-агентах",
  "hiringOrganization": {"@type": "Organization", "name": "Фордевинд"},
  "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": "Москва"}},
  "description": "<p>Ищем технического лидера, который умеет строить полный цикл разработки на AI-агентах: от анализа требований и архитектуры до генерации кода, ревью, тестирования, security checks и релизного контроля.</p><p>Проект LandComp 2.0: AI-дизайнер сада, B2B-ассистент, генерация изображений, маркетплейс и Supabase-инфраструктура.</p><p><strong>Задачи:</strong></p><ul><li>спроектировать agentic SDLC для продукта: discovery, analysis, architecture, implementation, review, QA, security, release;</li><li>организовать работу команды с Cursor, GitHub/GitLab, CI/CD, тестами и документацией;</li></ul><p><strong>Будет плюсом:</strong> опыт с LLM/RAG/agent systems, React Native / Expo / Supabase.</p>"
}
</script>
</head>
<body></body>
</html>
"""


def test_extract_hh_vacancy_id_from_vacancy_and_response_links() -> None:
    assert extract_hh_vacancy_id("https://hh.ru/vacancy/132885649") == "132885649"
    assert (
        extract_hh_vacancy_id("https://hh.ru/applicant/vacancy_response?vacancyId=132885649")
        == "132885649"
    )
    assert extract_hh_vacancy_id("132885649") == "132885649"


def test_parse_hh_vacancy_html_reads_public_jobposting_json_ld() -> None:
    vacancy = parse_hh_vacancy_html(
        SAMPLE_HH_VACANCY_HTML,
        source_url="https://hh.ru/vacancy/132885649",
        vacancy_id="132885649",
    )

    assert vacancy.external_id == "hh-132885649"
    assert vacancy.title == "AI Delivery Lead / Архитектор разработки на AI-агентах"
    assert vacancy.company == "Фордевинд"
    assert vacancy.salary_from == 270000
    assert vacancy.salary_to == 420000
    assert vacancy.currency == "RUR"
    assert vacancy.employment == "full"
    assert "LandComp 2.0" in vacancy.description
    assert "agentic SDLC" in vacancy.description
    assert "Cursor" in vacancy.skills
    assert "LLM" in vacancy.skills
    assert vacancy.raw["apply_url"] == "https://hh.ru/applicant/vacancy_response?vacancyId=132885649"


def test_public_vacancy_client_fetches_and_parses_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/vacancy/132885649"
        return httpx.Response(200, text=SAMPLE_HH_VACANCY_HTML, request=request)

    client = HHPublicVacancyClient(
        user_agent="headhunter-crm-agent-test/1.0",
        transport=httpx.MockTransport(handler),
    )

    vacancy = client.fetch_vacancy("https://hh.ru/vacancy/132885649")

    assert vacancy.title.startswith("AI Delivery Lead")
    assert vacancy.raw["vacancy_id"] == "132885649"


def test_public_vacancy_client_treats_403_as_stop_signal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden", request=request)

    client = HHPublicVacancyClient(
        user_agent="headhunter-crm-agent-test/1.0",
        transport=httpx.MockTransport(handler),
    )

    try:
        client.fetch_vacancy("https://hh.ru/vacancy/132885649")
    except RuntimeError as exc:
        assert "stop signal" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("403 should be reported as a stop signal")
