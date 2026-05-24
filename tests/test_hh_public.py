from __future__ import annotations

import httpx

from app.hh_public import HHPublicSearchClient, parse_hh_search_html


SAMPLE_SEARCH_HTML = """
<html><body>
  <div data-qa="vacancy-serp__vacancy" tabindex="0">
    <div id="132703070" class="vacancy-card--sample">
      <a data-qa="serp-item__title"
         href="https://hh.ru/vacancy/132703070?query=React+Python+CRM&amp;hhtmFrom=vacancy_search_list">
        <span data-qa="serp-item__title-text">Full-stack разработчик / AI-first engineer</span>
      </a>
      <span>250&nbsp;000 – 350&nbsp;000 <!-- -->₽<!-- --> за месяц</span>
      <span data-qa="vacancy-label-work-schedule-remote">Можно удалённо</span>
      <span data-qa="vacancy-serp__vacancy-employer-text">ООО&nbsp;<!-- -->AgentCo</span>
      <span data-qa="vacancy-serp__vacancy-address">Москва</span>
      <a data-qa="vacancy-serp__vacancy_response"
         href="/applicant/vacancy_response?vacancyId=132703070&amp;employerId=5354525&amp;hhtmFrom=vacancy_search_list">
        Откликнуться
      </a>
    </div>
  </div>
</body></html>
"""


def test_parse_hh_public_search_html_extracts_vacancy_and_apply_link():
    vacancies = parse_hh_search_html(SAMPLE_SEARCH_HTML, source_url="https://hh.ru/search/vacancy?text=React")

    assert len(vacancies) == 1
    vacancy = vacancies[0]
    assert vacancy.external_id == "hh-132703070"
    assert vacancy.title == "Full-stack разработчик / AI-first engineer"
    assert vacancy.company == "ООО AgentCo"
    assert vacancy.url == "https://hh.ru/vacancy/132703070?query=React+Python+CRM&hhtmFrom=vacancy_search_list"
    assert vacancy.salary_from == 250000
    assert vacancy.salary_to == 350000
    assert vacancy.currency == "RUR"
    assert vacancy.schedule == "remote"
    assert "Можно удалённо" in vacancy.description
    assert vacancy.raw["source"] == "hh_public_html"
    assert vacancy.raw["apply_url"] == "https://hh.ru/applicant/vacancy_response?vacancyId=132703070&employerId=5354525&hhtmFrom=vacancy_search_list"


def test_parse_hh_public_search_html_does_not_pull_trailing_page_noise_into_last_card():
    html = (
        SAMPLE_SEARCH_HTML
        + """
        <section data-qa="serp-subscription">
          По вашему запросу ещё будут появляться новые вакансии.
          React Python CRM Ключевые слова в названии вакансии
        </section>
        """
    )

    vacancies = parse_hh_search_html(html, source_url="https://hh.ru/search/vacancy?text=React")

    assert len(vacancies) == 1
    assert "React Python CRM Ключевые слова" not in vacancies[0].description


def test_public_client_uses_hh_search_page_not_api_endpoint():
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        assert request.url.path == "/search/vacancy"
        assert "api.hh.ru" not in str(request.url)
        return httpx.Response(200, text=SAMPLE_SEARCH_HTML, headers={"content-type": "text/html; charset=utf-8"})

    client = HHPublicSearchClient(
        user_agent="headhunter-crm-agent/0.1 (https://portfolio.viably.dev)",
        transport=httpx.MockTransport(handler),
    )

    vacancies = client.search_vacancies(text="React Python CRM", per_page=10, page=2)

    assert requested_urls
    assert "text=React+Python+CRM" in requested_urls[0]
    assert "per_page=10" in requested_urls[0]
    assert "page=2" in requested_urls[0]
    assert "search_field" not in requested_urls[0]
    assert vacancies[0].external_id == "hh-132703070"
