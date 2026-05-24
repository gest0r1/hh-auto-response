from __future__ import annotations

from typing import Any

import httpx

from app.scoring import Vacancy


class HHClient:
    def __init__(
        self,
        *,
        user_agent: str,
        access_token: str | None = None,
        base_url: str = "https://api.hh.ru",
        timeout: float = 20.0,
    ) -> None:
        self.user_agent = user_agent
        self.access_token = access_token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "HH-User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def search_vacancies(self, *, text: str, per_page: int = 20, page: int = 0) -> list[Vacancy]:
        params = {
            "text": text,
            "per_page": max(1, min(per_page, 100)),
            "page": max(0, page),
            "order_by": "publication_time",
            "search_field": "name",
        }
        with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
            response = client.get(f"{self.base_url}/vacancies", params=params)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = response.text[:600]
                raise RuntimeError(f"HH API {response.status_code}: {detail}") from exc
            payload = response.json()
        return [self._parse_vacancy(item) for item in payload.get("items", [])]

    @staticmethod
    def _parse_vacancy(item: dict[str, Any]) -> Vacancy:
        salary = item.get("salary") or {}
        employer = item.get("employer") or {}
        snippet = item.get("snippet") or {}
        schedule = item.get("schedule") or {}
        employment = item.get("employment") or {}
        description_parts = [
            snippet.get("requirement") or "",
            snippet.get("responsibility") or "",
            item.get("professional_roles", [{}])[0].get("name", "") if item.get("professional_roles") else "",
        ]
        skills: list[str] = []
        for raw_skill in item.get("key_skills") or []:
            name = raw_skill.get("name") if isinstance(raw_skill, dict) else str(raw_skill)
            if name:
                skills.append(name)
        # Search endpoint rarely returns key_skills; keep title/snippet scoring as baseline.
        return Vacancy(
            external_id=f"hh-{item.get('id')}",
            title=item.get("name") or "Без названия",
            company=employer.get("name") or "Компания не указана",
            description="\n".join(part for part in description_parts if part),
            url=item.get("alternate_url") or item.get("url") or "",
            salary_from=salary.get("from"),
            salary_to=salary.get("to"),
            currency=salary.get("currency"),
            schedule=schedule.get("id") or schedule.get("name"),
            employment=employment.get("id") or employment.get("name"),
            skills=skills,
            raw=item,
        )
