from __future__ import annotations

import html as html_lib
import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.scoring import Vacancy

HH_WEB_BASE_URL = "https://hh.ru"

_HH_VACANCY_ID_RE = re.compile(
    r"(?:hh\.ru/(?:vacancy|applicant/vacancy_response)[^\s<>]*?(?:vacancyId=)?|"
    r"dreamjob\.ru/employers/\d+/vakansii/)"
    r"(?P<id>\d{5,})",
    re.IGNORECASE,
)
_QUERY_VACANCY_ID_RE = re.compile(r"[?&]vacancyId=(?P<id>\d{5,})", re.IGNORECASE)
_JSON_LD_RE = re.compile(
    r"<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>(?P<body>.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_ATTR_RE = re.compile(r"(?P<name>[\w:-]+)\s*=\s*(?P<quote>[\"'])(?P<value>.*?)(?P=quote)", re.DOTALL)
_META_RE = re.compile(r"<meta\b(?P<attrs>[^>]*)>", re.IGNORECASE | re.DOTALL)
_SALARY_RE = re.compile(
    r"(?:от\s*)?(?P<salary_from>\d[\d\s\u00a0\u202f]*)"
    r"(?:\s*(?:до|[–—-])\s*(?P<salary_to>\d[\d\s\u00a0\u202f]*))?"
    r"\s*(?P<currency>₽|руб\.?|RUR)",
    re.IGNORECASE,
)

KNOWN_SKILLS = [
    "AI agents",
    "AI-агенты",
    "agentic SDLC",
    "agentic workflow",
    "planner",
    "executor",
    "reviewer",
    "evaluator",
    "human-in-the-loop",
    "Cursor",
    "Claude Code",
    "Codex",
    "GitHub Copilot",
    "GitHub",
    "GitLab",
    "CI/CD",
    "test automation",
    "security checks",
    "release gates",
    "Definition of Done",
    "LLM",
    "RAG",
    "agent systems",
    "React Native",
    "Expo",
    "Supabase",
    "backend",
    "web",
    "mobile",
]


def extract_hh_vacancy_id(text: str) -> str | None:
    """Extract HH vacancy id from a pasted HH/DreamJob vacancy or response URL."""
    value = (text or "").strip()
    if value.isdigit() and len(value) >= 5:
        return value
    match = _QUERY_VACANCY_ID_RE.search(value)
    if match:
        return match.group("id")
    match = _HH_VACANCY_ID_RE.search(value)
    return match.group("id") if match else None


def _attrs(attr_text: str) -> dict[str, str]:
    return {match.group("name").lower(): html_lib.unescape(match.group("value")) for match in _ATTR_RE.finditer(attr_text)}


def _meta_content(source: str, *, name: str | None = None, property_name: str | None = None) -> str:
    for match in _META_RE.finditer(source):
        attrs = _attrs(match.group("attrs"))
        if name and attrs.get("name", "").lower() == name.lower():
            return attrs.get("content", "")
        if property_name and attrs.get("property", "").lower() == property_name.lower():
            return attrs.get("content", "")
    return ""


def _clean_html_text(value: str) -> str:
    text = value or ""
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<\s*/\s*(p|div|li|ul|ol|h\d)\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<\s*li\b[^>]*>", "\n- ", text, flags=re.IGNORECASE)
    text = _TAG_RE.sub(" ", text)
    text = html_lib.unescape(text)
    text = text.replace("\xa0", " ").replace("\u202f", " ")
    text = "\n".join(_SPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def _json_ld_objects(source: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for match in _JSON_LD_RE.finditer(source):
        body = match.group("body").strip()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            continue
        items = parsed if isinstance(parsed, list) else [parsed]
        result.extend(item for item in items if isinstance(item, dict))
    return result


def _job_posting(source: str) -> dict[str, Any]:
    for item in _json_ld_objects(source):
        item_type = item.get("@type")
        if item_type == "JobPosting" or (isinstance(item_type, list) and "JobPosting" in item_type):
            return item
    return {}


def _parse_number(value: str | None) -> int | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return int(digits) if digits else None


def _parse_salary(text: str) -> tuple[int | None, int | None, str | None]:
    match = _SALARY_RE.search(text or "")
    if not match:
        return None, None, None
    currency_raw = (match.group("currency") or "").lower()
    currency = "RUR" if currency_raw in {"₽", "руб", "руб.", "rur"} else currency_raw.upper()
    return _parse_number(match.group("salary_from")), _parse_number(match.group("salary_to")), currency


def _schedule_from(text: str) -> str | None:
    lowered = (text or "").replace("ё", "е").lower()
    if any(marker in lowered for marker in ["удаленный", "удаленная", "удаленно", "удаленка", "можно удаленно"]):
        return "remote"
    if "гибрид" in lowered:
        return "hybrid"
    if "полный день" in lowered:
        return "fullDay"
    if "свободный" in lowered:
        return "flexible"
    return None


def _employment_from(text: str) -> str | None:
    lowered = (text or "").replace("ё", "е").lower()
    if "занятость: полная" in lowered or re.search(r"\bполная\b", lowered):
        return "full"
    if "частичная" in lowered or "part-time" in lowered:
        return "part"
    return None


def _skills_from(text: str) -> list[str]:
    lowered = (text or "").replace("ё", "е").lower()
    skills: list[str] = []
    for skill in KNOWN_SKILLS:
        normalized = skill.replace("ё", "е").lower()
        if normalized in lowered and skill not in skills:
            skills.append(skill)
    return skills


def _title_from_meta_title(source: str) -> str:
    match = re.search(r"<title[^>]*>(?P<title>.*?)</title>", source, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    title = _clean_html_text(match.group("title"))
    title = re.sub(r"^Вакансия\s+", "", title, flags=re.IGNORECASE).strip()
    title = re.sub(r"\s+в\s+[^,]+,\s+работа\s+в\s+компании\s+.+$", "", title, flags=re.IGNORECASE)
    return title.strip()


def _company_from_meta_title(source: str) -> str:
    meta_title = _clean_html_text(re.search(r"<title[^>]*>(.*?)</title>", source, re.IGNORECASE | re.DOTALL).group(1)) if re.search(r"<title[^>]*>(.*?)</title>", source, re.IGNORECASE | re.DOTALL) else ""
    match = re.search(r"работа\s+в\s+компании\s+(.+)$", meta_title, re.IGNORECASE)
    return match.group(1).strip() if match else "Компания не указана"


def _location_from_job(job: dict[str, Any]) -> str:
    location = job.get("jobLocation") or {}
    if isinstance(location, list):
        location = location[0] if location else {}
    address = location.get("address") if isinstance(location, dict) else {}
    if not isinstance(address, dict):
        return ""
    return str(address.get("addressLocality") or address.get("addressRegion") or "").strip()


def parse_hh_vacancy_html(source: str, *, source_url: str = "", vacancy_id: str | None = None) -> Vacancy:
    """Parse a public HH vacancy page into the CRM Vacancy model.

    HH exposes the actual vacancy body as schema.org JobPosting JSON-LD inside the public HTML.
    This parser reads that public payload and does not use private applicant actions.
    """
    job = _job_posting(source)
    title = str(job.get("title") or "").strip() or _title_from_meta_title(source)
    organization = job.get("hiringOrganization") or {}
    company = ""
    if isinstance(organization, dict):
        company = str(organization.get("name") or "").strip()
    company = company or _company_from_meta_title(source)

    description_html = str(job.get("description") or "")
    description = _clean_html_text(description_html)
    meta_description = _meta_content(source, name="description") or _meta_content(source, property_name="og:description")
    combined_text = "\n".join(part for part in [description, meta_description, _location_from_job(job)] if part)

    external_id = extract_hh_vacancy_id(source_url) or vacancy_id or ""
    if not external_id:
        identifier = job.get("identifier") or {}
        if isinstance(identifier, dict):
            external_id = str(identifier.get("value") or "").strip()
    if not external_id:
        raise RuntimeError("HH vacancy id was not found in the vacancy page")
    if not title or not description:
        raise RuntimeError("HH vacancy page did not contain enough public vacancy text")

    salary_from, salary_to, currency = _parse_salary("\n".join([meta_description, description]))
    url = source_url if source_url else f"{HH_WEB_BASE_URL}/vacancy/{external_id}"
    if url and url.startswith("/"):
        url = f"{HH_WEB_BASE_URL}{url}"

    return Vacancy(
        external_id=f"hh-{external_id}",
        title=title,
        company=company or "Компания не указана",
        description=combined_text,
        url=url,
        salary_from=salary_from,
        salary_to=salary_to,
        currency=currency,
        schedule=_schedule_from(combined_text),
        employment=_employment_from(meta_description),
        skills=_skills_from(combined_text),
        raw={
            "source": "hh_public_vacancy_html",
            "source_url": source_url,
            "vacancy_id": external_id,
            "apply_url": f"{HH_WEB_BASE_URL}/applicant/vacancy_response?vacancyId={external_id}",
            "area": _location_from_job(job),
        },
    )


class HHPublicVacancyClient:
    """No-OAuth client for one public HH vacancy page.

    It reads only the public vacancy HTML/JSON-LD. If HH returns CAPTCHA/403/429, this is a stop
    signal: the caller should ask the user for the vacancy text rather than trying to bypass it.
    """

    def __init__(
        self,
        *,
        user_agent: str,
        base_url: str = HH_WEB_BASE_URL,
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    @property
    def headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.6",
        }

    def fetch_vacancy(self, url_or_text: str) -> Vacancy:
        vacancy_id = extract_hh_vacancy_id(url_or_text)
        if not vacancy_id:
            raise RuntimeError("Не нашёл ID вакансии HH в сообщении")
        source_url = self._url_for(url_or_text, vacancy_id)
        with httpx.Client(
            timeout=self.timeout,
            headers=self.headers,
            follow_redirects=True,
            transport=self.transport,
        ) as client:
            response = client.get(source_url)
        if response.status_code in {403, 429}:
            raise RuntimeError(f"HH vacancy stop signal: HTTP {response.status_code}")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"HH vacancy HTTP {response.status_code}") from exc

        lower_text = response.text.lower()
        captcha_stop = any(marker in lower_text for marker in ["/account/captcha", "data-qa=\"captcha", "captcha__"])
        if captcha_stop and not _job_posting(response.text):
            raise RuntimeError("HH vacancy returned CAPTCHA/anti-bot page; stop, do not bypass")
        return parse_hh_vacancy_html(response.text, source_url=str(response.url), vacancy_id=vacancy_id)

    def _url_for(self, url_or_text: str, vacancy_id: str) -> str:
        for token in re.split(r"\s+", url_or_text.strip()):
            if not token:
                continue
            cleaned = token.strip("<>()[]{}.,;!\"'")
            if extract_hh_vacancy_id(cleaned):
                parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned}")
                if parsed.netloc.endswith("hh.ru"):
                    return cleaned if "://" in cleaned else f"https://{cleaned}"
        return f"{self.base_url}/vacancy/{vacancy_id}"
