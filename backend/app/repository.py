from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.db import connect, initialize_database
from app.responses import sanitize_cover_letter
from app.scoring import ScoreResult, Vacancy


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _row_dict(row: Any) -> dict[str, Any]:
    return dict(row) if row is not None else {}


_ACTIVE_DUPLICATE_STATUSES = ("draft", "sent", "reply", "interview", "offer", "blocked", "rejected")
_COMPANY_GUARD_MODES = {"strict", "family", "off"}
_FAMILY_COMPANY_BUCKETS = {"sber"}
_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^a-zа-я0-9]+")
_LEGAL_PREFIX_RE = re.compile(r"^(ооо|ао|пао|зао|ип)\s+")
_LEGAL_SUFFIX_RE = re.compile(r"\s+(ооо|ао|пао|зао|ип)$")


def _canonical_key(value: str | None) -> str:
    normalized = (value or "").replace("ё", "е").lower().strip()
    normalized = _SPACE_RE.sub(" ", normalized)
    return normalized


def _company_bucket_key(company: str | None) -> str:
    """Normalize an employer to a safety bucket used for broad anti-spam guards.

    HH can expose large employers through multiple legal/brand names: for example
    `Сбер. IT`, `Сбер. Data Science` and `SberTech`.  Exact company matching would
    still spam the same employer family, so this bucket intentionally collapses
    obvious aliases and strips legal noise.
    """
    normalized = _canonical_key(company)
    normalized = _NON_WORD_RE.sub(" ", normalized)
    normalized = _SPACE_RE.sub(" ", normalized).strip()
    normalized = _LEGAL_PREFIX_RE.sub("", normalized)
    normalized = _LEGAL_SUFFIX_RE.sub("", normalized).strip()
    if normalized.startswith("сбер") or normalized.startswith("sber") or "sbertech" in normalized:
        return "sber"
    return normalized


def _company_title_key(company: str | None, title: str | None) -> tuple[str, str]:
    return (_company_bucket_key(company), _canonical_key(title))


def normalize_company_guard_mode(mode: str | None) -> str:
    normalized = (mode or "strict").strip().lower()
    return normalized if normalized in _COMPANY_GUARD_MODES else "strict"


def _company_guard_applies(company: str | None, mode: str | None) -> bool:
    normalized = normalize_company_guard_mode(mode)
    if normalized == "off":
        return False
    bucket = _company_bucket_key(company)
    if not bucket:
        return False
    if normalized == "family":
        return bucket in _FAMILY_COMPANY_BUCKETS
    return True


def _review_item_from_row(row: Any) -> dict[str, Any]:
    item = _row_dict(row)
    item["skills"] = _loads(item.pop("skills_json", "[]"), [])
    item["raw"] = _loads(item.pop("raw_json", "{}"), {})
    item["score_reasons"] = _loads(item.pop("score_reasons_json", "[]"), [])
    item["score_penalties"] = _loads(item.pop("score_penalties_json", "[]"), [])
    item["apply_url"] = item["raw"].get("apply_url") or item.get("url") or ""
    if "cover_letter" in item:
        item["cover_letter"] = sanitize_cover_letter(str(item.get("cover_letter") or ""))
    return item


class CRMRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_database(self.db_path)

    def upsert_vacancy(self, vacancy: Vacancy, score: ScoreResult) -> int:
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO vacancies (
                    external_id, title, company, description, url, salary_from, salary_to,
                    currency, schedule, employment, skills_json, raw_json, score, decision,
                    score_reasons_json, score_penalties_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(external_id) DO UPDATE SET
                    title=excluded.title,
                    company=excluded.company,
                    description=excluded.description,
                    url=excluded.url,
                    salary_from=excluded.salary_from,
                    salary_to=excluded.salary_to,
                    currency=excluded.currency,
                    schedule=excluded.schedule,
                    employment=excluded.employment,
                    skills_json=excluded.skills_json,
                    raw_json=excluded.raw_json,
                    score=excluded.score,
                    decision=excluded.decision,
                    score_reasons_json=excluded.score_reasons_json,
                    score_penalties_json=excluded.score_penalties_json,
                    status=CASE WHEN vacancies.status = 'new' THEN excluded.status ELSE vacancies.status END,
                    updated_at=datetime('now')
                """,
                (
                    vacancy.external_id,
                    vacancy.title,
                    vacancy.company,
                    vacancy.description,
                    vacancy.url,
                    vacancy.salary_from,
                    vacancy.salary_to,
                    vacancy.currency,
                    vacancy.schedule,
                    vacancy.employment,
                    _json(vacancy.skills),
                    _json(vacancy.raw),
                    score.score,
                    score.decision,
                    _json(score.reasons),
                    _json(score.penalties),
                    score.decision,
                ),
            )
            row = conn.execute("SELECT id FROM vacancies WHERE external_id = ?", (vacancy.external_id,)).fetchone()
            conn.commit()
            return int(row["id"])

    def has_company_title_application(
        self,
        *,
        company: str | None,
        title: str | None,
        exclude_vacancy_id: int | None = None,
        statuses: tuple[str, ...] = _ACTIVE_DUPLICATE_STATUSES,
    ) -> bool:
        """Return True when this employer/title already has an active application.

        HH sometimes publishes the same human vacancy under several vacancyId values.
        external_id dedupe is not enough; before drafting/sending, gate by company + title.
        """
        target = _company_title_key(company, title)
        if not all(target) or not statuses:
            return False
        placeholders = ", ".join("?" for _ in statuses)
        params: list[Any] = list(statuses)
        where = f"a.status IN ({placeholders})"
        if exclude_vacancy_id is not None:
            where += " AND v.id != ?"
            params.append(exclude_vacancy_id)
        with connect(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT v.company, v.title
                FROM applications a
                JOIN vacancies v ON v.id = a.vacancy_id
                WHERE {where}
                """,
                tuple(params),
            ).fetchall()
        return any(_company_title_key(row["company"], row["title"]) == target for row in rows)

    def has_company_application(
        self,
        *,
        company: str | None,
        exclude_vacancy_id: int | None = None,
        statuses: tuple[str, ...] = _ACTIVE_DUPLICATE_STATUSES,
        guard_mode: str = "strict",
    ) -> bool:
        """Return True when this employer bucket already has an active application.

        This is stricter than company+title dedupe. It prevents a noisy auto-apply
        loop from sending many different roles to the same employer family every
        day, which was observed with Sber/Сбер HH aliases.
        """
        if not _company_guard_applies(company, guard_mode):
            return False
        target = _company_bucket_key(company)
        if not target or not statuses:
            return False
        placeholders = ", ".join("?" for _ in statuses)
        params: list[Any] = list(statuses)
        where = f"a.status IN ({placeholders})"
        if exclude_vacancy_id is not None:
            where += " AND v.id != ?"
            params.append(exclude_vacancy_id)
        with connect(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT v.company
                FROM applications a
                JOIN vacancies v ON v.id = a.vacancy_id
                WHERE {where}
                """,
                tuple(params),
            ).fetchall()
        return any(_company_bucket_key(row["company"]) == target for row in rows)

    def create_or_update_application(
        self,
        vacancy_id: int,
        *,
        cover_letter: str,
        status: str = "draft",
        resume_id: str | None = None,
        score_at_apply: int | None = None,
    ) -> int:
        cover_letter = sanitize_cover_letter(cover_letter)
        with connect(self.db_path) as conn:
            existing = conn.execute("SELECT id, draft_version, status FROM applications WHERE vacancy_id = ?", (vacancy_id,)).fetchone()
            if existing:
                app_id = int(existing["id"])
                current_status = str(existing["status"])
                if status == "draft" and current_status != "draft":
                    # Search reruns must not resurrect already handled applications
                    # back into the review queue. Manual edits use
                    # update_application_cover_letter() instead.
                    return app_id
                conn.execute(
                    """
                    UPDATE applications
                    SET cover_letter = ?, status = ?, resume_id = COALESCE(?, resume_id),
                        score_at_apply = COALESCE(?, score_at_apply), draft_version = draft_version + 1,
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (cover_letter, status, resume_id, score_at_apply, app_id),
                )
            else:
                cur = conn.execute(
                    """
                    INSERT INTO applications (vacancy_id, cover_letter, status, resume_id, score_at_apply)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (vacancy_id, cover_letter, status, resume_id, score_at_apply),
                )
                app_id = int(cur.lastrowid)
            conn.commit()
            return app_id

    def update_application_cover_letter(
        self,
        application_id: int,
        *,
        cover_letter: str,
        status: str = "draft",
    ) -> bool:
        cover_letter = sanitize_cover_letter(cover_letter)
        with connect(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE applications
                SET cover_letter = ?, status = ?, draft_version = draft_version + 1,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (cover_letter, status, application_id),
            )
            conn.commit()
            return int(cur.rowcount) > 0

    def update_application_status(self, application_id: int, *, status: str) -> bool:
        sent_at_sql = "sent_at = COALESCE(sent_at, datetime('now'))," if status == "sent" else ""
        with connect(self.db_path) as conn:
            cur = conn.execute(
                f"""
                UPDATE applications
                SET status = ?, {sent_at_sql} updated_at = datetime('now')
                WHERE id = ?
                """,
                (status, application_id),
            )
            conn.commit()
            return int(cur.rowcount) > 0

    def archive_draft_application(self, vacancy_id: int) -> int:
        with connect(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE applications
                SET status = 'archived', updated_at = datetime('now')
                WHERE vacancy_id = ? AND status = 'draft'
                """,
                (vacancy_id,),
            )
            conn.commit()
            return int(cur.rowcount)

    def record_feedback(
        self,
        *,
        vacancy_id: int | None,
        application_id: int | None,
        event_type: str,
        rating: int | None = None,
        notes: str | None = None,
        edited_cover_letter: str | None = None,
    ) -> int:
        with connect(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO feedback_events (vacancy_id, application_id, event_type, rating, notes, edited_cover_letter)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (vacancy_id, application_id, event_type, rating, notes, edited_cover_letter),
            )
            if application_id and event_type in {"sent", "reply", "interview", "offer", "rejected", "archived"}:
                status = {
                    "sent": "sent",
                    "reply": "reply",
                    "interview": "interview",
                    "offer": "offer",
                    "rejected": "rejected",
                    "archived": "archived",
                }[event_type]
                sent_at_sql = "sent_at = COALESCE(sent_at, datetime('now'))," if status == "sent" else ""
                conn.execute(
                    f"""
                    UPDATE applications
                    SET status = ?, {sent_at_sql} updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (status, application_id),
                )
            conn.commit()
            return int(cur.lastrowid)

    def count_sent_today(self) -> int:
        with connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM applications
                WHERE status = 'sent'
                  AND date(COALESCE(sent_at, updated_at)) = date('now')
                """
            ).fetchone()
        return int(row["c"])

    def record_run_log(self, *, agent_name: str, status: str, details: dict[str, Any]) -> int:
        with connect(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO run_logs (agent_name, status, details_json)
                VALUES (?, ?, ?)
                """,
                (agent_name, status, _json(details)),
            )
            conn.commit()
            return int(cur.lastrowid)

    def update_learning_signal(self, key: str, weight: float, *, positive: bool | None = None) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO learning_signals (key, weight, positive_count, negative_count)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    weight=excluded.weight,
                    positive_count=learning_signals.positive_count + excluded.positive_count,
                    negative_count=learning_signals.negative_count + excluded.negative_count,
                    updated_at=datetime('now')
                """,
                (key, weight, 1 if positive is True else 0, 1 if positive is False else 0),
            )
            conn.commit()

    def get_learning_weights(self) -> dict[str, float]:
        with connect(self.db_path) as conn:
            rows = conn.execute("SELECT key, weight FROM learning_signals").fetchall()
        return {str(row["key"]): float(row["weight"]) for row in rows}

    def list_vacancies(self, *, limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
        where = "WHERE status = ?" if status else ""
        params: tuple[Any, ...] = (status, limit) if status else (limit,)
        with connect(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM vacancies
                {where}
                ORDER BY score DESC, updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        result = []
        for row in rows:
            item = _row_dict(row)
            item["skills"] = _loads(item.pop("skills_json", "[]"), [])
            item["raw"] = _loads(item.pop("raw_json", "{}"), {})
            item["score_reasons"] = _loads(item.pop("score_reasons_json", "[]"), [])
            item["score_penalties"] = _loads(item.pop("score_penalties_json", "[]"), [])
            result.append(item)
        return result

    def review_queue(
        self,
        *,
        min_score: int = 80,
        limit: int = 20,
        include_demo: bool = False,
        decisions: tuple[str, ...] = ("hot", "review"),
        company_guard: str = "strict",
    ) -> list[dict[str, Any]]:
        where = "a.status = 'draft' AND v.score >= ?"
        params: list[Any] = [min_score]
        if decisions:
            placeholders = ", ".join("?" for _ in decisions)
            where += f" AND v.decision IN ({placeholders})"
            params.extend(decisions)
        if not include_demo:
            where += " AND v.external_id NOT LIKE 'demo-%'"

        if limit <= 0:
            return []

        with connect(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT v.*, a.id AS application_id, a.status AS application_status,
                       a.cover_letter, a.score_at_apply, a.draft_version
                FROM vacancies v
                JOIN applications a ON a.vacancy_id = v.id
                WHERE {where}
                ORDER BY v.score DESC, v.updated_at DESC
                """,
                tuple(params),
            ).fetchall()
        queue: list[dict[str, Any]] = []
        seen_signatures: set[tuple[str, str]] = set()
        seen_company_buckets: set[str] = set()
        handled_statuses = tuple(status for status in _ACTIVE_DUPLICATE_STATUSES if status != "draft")
        for row in rows:
            item = _review_item_from_row(row)
            company = str(item.get("company") or "")
            title = str(item.get("title") or "")
            signature = _company_title_key(company, title)
            company_bucket = _company_bucket_key(company)
            if signature in seen_signatures:
                continue
            company_bucket_guarded = _company_guard_applies(company, company_guard)
            if company_bucket_guarded and company_bucket and company_bucket in seen_company_buckets:
                continue
            if self.has_company_title_application(
                company=company,
                title=title,
                exclude_vacancy_id=int(item["id"]),
                statuses=handled_statuses,
            ):
                continue
            if self.has_company_application(
                company=company,
                exclude_vacancy_id=int(item["id"]),
                statuses=handled_statuses,
                guard_mode=company_guard,
            ):
                continue
            seen_signatures.add(signature)
            if company_bucket_guarded and company_bucket:
                seen_company_buckets.add(company_bucket)
            queue.append(item)
            if len(queue) >= limit:
                break
        return queue

    def application_review_item(self, application_id: int) -> dict[str, Any] | None:
        with connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT v.*, a.id AS application_id, a.status AS application_status,
                       a.cover_letter, a.score_at_apply, a.draft_version
                FROM applications a
                JOIN vacancies v ON v.id = a.vacancy_id
                WHERE a.id = ?
                """,
                (application_id,),
            ).fetchone()
        return _review_item_from_row(row) if row is not None else None

    def dashboard_summary(self) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            metrics = {
                "vacancies_total": conn.execute("SELECT COUNT(*) AS c FROM vacancies").fetchone()["c"],
                "hot_total": conn.execute("SELECT COUNT(*) AS c FROM vacancies WHERE decision = 'hot'").fetchone()["c"],
                "drafts_total": conn.execute("SELECT COUNT(*) AS c FROM applications WHERE status = 'draft'").fetchone()["c"],
                "sent_total": conn.execute("SELECT COUNT(*) AS c FROM applications WHERE status = 'sent'").fetchone()["c"],
                "interviews_total": conn.execute("SELECT COUNT(*) AS c FROM applications WHERE status = 'interview'").fetchone()["c"],
            }
            pipeline_rows = conn.execute("SELECT status, COUNT(*) AS c FROM applications GROUP BY status").fetchall()
            top_rows = conn.execute(
                """
                SELECT v.*, a.status AS application_status, a.cover_letter
                FROM vacancies v
                LEFT JOIN applications a ON a.vacancy_id = v.id
                ORDER BY v.score DESC, v.updated_at DESC
                LIMIT 12
                """
            ).fetchall()
            feedback_rows = conn.execute(
                """
                SELECT f.*, v.title AS vacancy_title, v.company
                FROM feedback_events f
                LEFT JOIN vacancies v ON v.id = f.vacancy_id
                ORDER BY f.created_at DESC
                LIMIT 20
                """
            ).fetchall()
            learning_rows = conn.execute(
                "SELECT * FROM learning_signals ORDER BY ABS(weight) DESC, updated_at DESC LIMIT 20"
            ).fetchall()

        top_vacancies: list[dict[str, Any]] = []
        for row in top_rows:
            item = _row_dict(row)
            item["skills"] = _loads(item.pop("skills_json", "[]"), [])
            item["score_reasons"] = _loads(item.pop("score_reasons_json", "[]"), [])
            item["score_penalties"] = _loads(item.pop("score_penalties_json", "[]"), [])
            raw = _loads(item.pop("raw_json", "{}"), {})
            item["apply_url"] = raw.get("apply_url") or item.get("url") or ""
            if "cover_letter" in item:
                item["cover_letter"] = sanitize_cover_letter(str(item.get("cover_letter") or ""))
            top_vacancies.append(item)

        return {
            "metrics": metrics,
            "pipeline": {row["status"]: row["c"] for row in pipeline_rows},
            "top_vacancies": top_vacancies,
            "feedback_recent": [_row_dict(row) for row in feedback_rows],
            "learning_signals": [_row_dict(row) for row in learning_rows],
        }
