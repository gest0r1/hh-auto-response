from __future__ import annotations

import html as html_lib
import re
from typing import Iterable
from urllib.parse import urljoin

import httpx

from app.hh_vacancy import parse_hh_vacancy_html
from app.scoring import Vacancy

HH_WEB_BASE_URL = "https://hh.ru"

_CARD_MARKER_RE = re.compile(r"data-qa=[\"']vacancy-serp__vacancy[\"']")
_TAG_RE = re.compile(r"<[^>]+>")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_SPACE_RE = re.compile(r"\s+")
_NUMBER_RE = re.compile(r"\d[\d\s\u00a0\u202f]*")
_SALARY_RE = re.compile(
    r"(?P<salary_from>\d[\d\s\u00a0\u202f]*)"
    r"(?:\s*[–—-]\s*(?P<salary_to>\d[\d\s\u00a0\u202f]*))?"
    r"\s*(?P<currency>₽|руб\.?|RUR)",
    re.IGNORECASE,
)
_VACANCY_ID_RE = re.compile(r"/vacancy/(\d+)")
_CARD_ID_RE = re.compile(r"<div\s+id=[\"'](\d+)[\"'][^>]*class=[\"'][^\"']*vacancy-card", re.IGNORECASE)
_DATA_QA_TEXT_RE = re.compile(
    r"<(?P<tag>span|div)[^>]*data-qa=[\"'](?P<qa>[^\"']+)[\"'][^>]*>(?P<body>.*?)</(?P=tag)>",
    re.DOTALL | re.IGNORECASE,
)
_ANCHOR_RE = re.compile(r"<a\b(?P<attrs>[^>]*)>(?P<body>.*?)</a>", re.DOTALL | re.IGNORECASE)
_ATTR_RE = re.compile(r"(?P<name>[\w:-]+)\s*=\s*(?P<quote>[\"'])(?P<value>.*?)(?P=quote)", re.DOTALL)


def _clean_text(value: str) -> str:
    without_comments = _COMMENT_RE.sub(" ", value)
    without_tags = _TAG_RE.sub(" ", without_comments)
    unescaped = html_lib.unescape(without_tags)
    normalized = unescaped.replace("\xa0", " ").replace("\u202f", " ")
    return _SPACE_RE.sub(" ", normalized).strip()


def _attrs(attr_text: str) -> dict[str, str]:
    return {match.group("name").lower(): html_lib.unescape(match.group("value")) for match in _ATTR_RE.finditer(attr_text)}


def _absolute_url(href: str | None, *, base_url: str = HH_WEB_BASE_URL) -> str:
    if not href:
        return ""
    return urljoin(base_url, html_lib.unescape(href))


def _balanced_element_end(source: str, *, start: int, tag: str) -> int | None:
    tag_re = re.compile(rf"</?{re.escape(tag)}\b[^>]*>", re.IGNORECASE)
    depth = 0
    for match in tag_re.finditer(source, start):
        token = match.group(0)
        if token.startswith("</"):
            depth -= 1
            if depth == 0:
                return match.end()
        elif not token.endswith("/>"):
            depth += 1
    return None


def _card_chunks(html: str) -> Iterable[str]:
    matches = list(_CARD_MARKER_RE.finditer(html))
    for index, match in enumerate(matches):
        tag_start = html.rfind("<", 0, match.start())
        tag_match = re.match(r"<(?P<tag>[a-zA-Z][\w:-]*)\b", html[tag_start:]) if tag_start >= 0 else None
        if tag_start >= 0 and tag_match:
            end = _balanced_element_end(html, start=tag_start, tag=tag_match.group("tag"))
            if end is not None:
                yield html[tag_start:end]
                continue

        # Fallback for malformed/partial HTML: keep the old marker-to-marker behavior.
        fallback_end = matches[index + 1].start() if index + 1 < len(matches) else len(html)
        yield html[match.start() : fallback_end]


def _text_by_qa(chunk: str, qa: str) -> str:
    pattern = re.compile(
        rf"<(?P<tag>span|div)[^>]*data-qa=[\"']{re.escape(qa)}[\"'][^>]*>(?P<body>.*?)</(?P=tag)>",
        re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(chunk)
    return _clean_text(match.group("body")) if match else ""


def _anchor_by_qa(chunk: str, qa: str) -> tuple[dict[str, str], str] | None:
    for match in _ANCHOR_RE.finditer(chunk):
        attrs = _attrs(match.group("attrs"))
        if attrs.get("data-qa") == qa:
            return attrs, match.group("body")
    return None


def _first_salary(text: str) -> tuple[int | None, int | None, str | None]:
    match = _SALARY_RE.search(text)
    if not match:
        return None, None, None
    salary_from = _parse_number(match.group("salary_from"))
    salary_to = _parse_number(match.group("salary_to")) if match.group("salary_to") else None
    currency_raw = (match.group("currency") or "").lower()
    currency = "RUR" if currency_raw in {"₽", "руб", "руб.", "rur"} else currency_raw.upper()
    return salary_from, salary_to, currency


def _parse_number(value: str | None) -> int | None:
    if not value:
        return None
    digits = "".join(_NUMBER_RE.search(value).group(0).split()) if _NUMBER_RE.search(value) else ""
    return int(digits) if digits else None


def _vacancy_id_from(chunk: str, title_url: str) -> str | None:
    url_match = _VACANCY_ID_RE.search(title_url)
    if url_match:
        return url_match.group(1)
    card_match = _CARD_ID_RE.search(chunk)
    if card_match:
        return card_match.group(1)
    return None


def _schedule_from(text: str, chunk: str) -> str | None:
    lowered = text.lower().replace("ё", "е")
    if "vacancy-label-work-schedule-remote" in chunk or "можно удаленно" in lowered or "удаленно" in lowered:
        return "remote"
    if "гибрид" in lowered:
        return "hybrid"
    if "полный день" in lowered:
        return "fullDay"
    return None


def _apply_url_from(chunk: str) -> str:
    response_anchor = _anchor_by_qa(chunk, "vacancy-serp__vacancy_response")
    if not response_anchor:
        return ""
    attrs, _body = response_anchor
    return _absolute_url(attrs.get("href"))


def parse_hh_search_html(html: str, *, source_url: str = "") -> list[Vacancy]:
    """Parse HH.ru public search-result HTML into CRM vacancies.

    This intentionally uses the web search page, not api.hh.ru. If HH changes markup,
    tests should be updated around the public contract we rely on: title link, company,
    salary, schedule labels, and response link.
    """
    vacancies: list[Vacancy] = []
    for chunk in _card_chunks(html):
        title_anchor = _anchor_by_qa(chunk, "serp-item__title")
        if not title_anchor:
            continue
        title_attrs, title_body = title_anchor
        title = _text_by_qa(title_body, "serp-item__title-text") or _clean_text(title_body)
        title_url = _absolute_url(title_attrs.get("href"))
        vacancy_id = _vacancy_id_from(chunk, title_url)
        if not vacancy_id or not title or not title_url:
            continue

        company = _text_by_qa(chunk, "vacancy-serp__vacancy-employer-text") or "Компания не указана"
        address = _text_by_qa(chunk, "vacancy-serp__vacancy-address")
        full_text = _clean_text(chunk)
        salary_from, salary_to, currency = _first_salary(full_text)
        schedule = _schedule_from(full_text, chunk)
        apply_url = _apply_url_from(chunk)
        description_parts = [title, company, address, full_text]
        description = "\n".join(part for part in description_parts if part)
        vacancies.append(
            Vacancy(
                external_id=f"hh-{vacancy_id}",
                title=title,
                company=company,
                description=description,
                url=title_url,
                salary_from=salary_from,
                salary_to=salary_to,
                currency=currency,
                schedule=schedule,
                employment=None,
                skills=[],
                raw={
                    "source": "hh_public_html",
                    "source_url": source_url,
                    "vacancy_id": vacancy_id,
                    "apply_url": apply_url,
                },
            )
        )
    return vacancies


class HHPublicSearchClient:
    """No-OAuth HH.ru client based on public web search pages.

    It does not use api.hh.ru and it does not bypass CAPTCHA or anti-bot controls.
    If HH blocks the request, the caller gets a clear stop-signal exception.
    """

    def __init__(
        self,
        *,
        user_agent: str,
        base_url: str = HH_WEB_BASE_URL,
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
        fetch_details: bool = False,
        require_details: bool = False,
    ) -> None:
        self.user_agent = user_agent
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport
        self.fetch_details = fetch_details
        self.require_details = require_details

    @property
    def headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.6",
        }

    def search_vacancies(self, *, text: str, per_page: int = 20, page: int = 0) -> list[Vacancy]:
        params = {
            "text": text,
            "per_page": max(1, min(per_page, 50)),
            "page": max(0, page),
            "order_by": "publication_time",
        }
        with httpx.Client(
            timeout=self.timeout,
            headers=self.headers,
            follow_redirects=True,
            transport=self.transport,
        ) as client:
            response = client.get(f"{self.base_url}/search/vacancy", params=params)
            if response.status_code in {403, 429}:
                raise RuntimeError(f"HH public search stop signal: HTTP {response.status_code}")
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f"HH public search HTTP {response.status_code}") from exc

            vacancies = parse_hh_search_html(response.text, source_url=str(response.url))
            lower_text = response.text.lower()
            captcha_stop = any(marker in lower_text for marker in ["/account/captcha", "data-qa=\"captcha", "captcha__"])
            if not vacancies and captcha_stop:
                raise RuntimeError("HH public search returned CAPTCHA/anti-bot page; stop, do not bypass")
            vacancies = vacancies[: params["per_page"]]
            if self.fetch_details:
                vacancies = self._fetch_public_details(client, vacancies)
            return vacancies

    def _fetch_public_details(self, client: httpx.Client, vacancies: list[Vacancy]) -> list[Vacancy]:
        enriched: list[Vacancy] = []
        for vacancy in vacancies:
            try:
                response = client.get(vacancy.url)
                if response.status_code in {403, 429}:
                    raise RuntimeError(f"HTTP {response.status_code}")
                response.raise_for_status()
                lower_text = response.text.lower()
                captcha_stop = any(marker in lower_text for marker in ["/account/captcha", "data-qa=\"captcha", "captcha__"])
                if captcha_stop and "application/ld+json" not in lower_text:
                    raise RuntimeError("CAPTCHA/anti-bot page")
                detailed = parse_hh_vacancy_html(response.text, source_url=str(response.url), vacancy_id=vacancy.raw.get("vacancy_id"))
                raw = dict(detailed.raw)
                raw.update(
                    {
                        "source": "hh_public_search_with_detail_html",
                        "search_apply_url": vacancy.raw.get("apply_url") or "",
                        "apply_url": vacancy.raw.get("apply_url") or raw.get("apply_url") or "",
                        "search_source_url": vacancy.raw.get("source_url") or "",
                    }
                )
                detailed.raw = raw
                enriched.append(detailed)
            except Exception as exc:
                if self.require_details:
                    continue
                raw = dict(vacancy.raw)
                raw["detail_fetch_error"] = str(exc)
                vacancy.raw = raw
                enriched.append(vacancy)
        return enriched
