from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


@dataclass(slots=True)
class ApplyDraft:
    vacancy_id: int | None
    application_id: int | None
    resume_id: str | None
    title: str
    company: str
    apply_url: str
    cover_letter: str


@dataclass(slots=True)
class BrowserApplyResult:
    application_id: int | None
    vacancy_id: int | None
    status: str
    message: str
    url: str


class LocatorLike(Protocol):
    def count(self) -> int: ...
    def fill(self, value: str) -> None: ...
    def click(self) -> None: ...
    def is_visible(self) -> bool: ...


class PageLike(Protocol):
    url: str

    def goto(self, url: str, wait_until: str = "domcontentloaded") -> None: ...
    def wait_for_load_state(self, state: str) -> None: ...
    def locator(self, selector: str) -> LocatorLike: ...


LETTER_OPEN_SELECTORS = [
    '[data-qa="vacancy-response-letter-toggle"]',
    '[data-qa="vacancy-response-add-cover-letter"]',
    'button:has-text("Сопроводительное")',
    'button:has-text("Добавить сопроводительное")',
]

LETTER_INPUT_SELECTORS = [
    'textarea[name="letter"]',
    'textarea[data-qa="vacancy-response-popup-form-letter-input"]',
    '[data-qa="vacancy-response-popup-form-letter-input"] textarea',
    'textarea[data-qa="vacancy-response-letter-input"]',
    '[data-qa="vacancy-response-letter-input"] textarea',
    '[contenteditable="true"]',
]

SUBMIT_SELECTORS = [
    '[data-qa="vacancy-response-submit-popup"]',
    '[data-qa="vacancy-response-submit"]',
    'button:has-text("Откликнуться")',
    'button:has-text("Отправить")',
]

SENT_CONFIRMATION_MARKERS = [
    "Вы откликнулись",
    "Резюме доставлено",
    "Откликнуться повторно",
]

LOGIN_SELECTORS = [
    '[data-qa="login-input-username"]',
    'input[name="username"]',
    'input[name="login"]',
    'input[type="password"]',
]

RESUME_SELECTED_SELECTORS = [
    '[data-qa="resume-title"]',
    '[data-qa="resume-detail"]',
]


def _css_attr_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _resume_selectors(resume_id: str) -> list[str]:
    escaped = _css_attr_value(resume_id)
    return [
        f'input[name="resume"][value="{escaped}"]',
        f'input[type="radio"][value="{escaped}"]',
        f'input[value="{escaped}"]',
        f'label:has(input[value="{escaped}"])',
        f'[data-qa*="resume"]:has(input[value="{escaped}"])',
    ]


def _apply_url_with_resume(apply_url: str, resume_id: str | None) -> str:
    if not resume_id:
        return apply_url
    parts = urlsplit(apply_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("resume", resume_id)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _url_has_resume(url: str, resume_id: str) -> bool:
    query = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
    return query.get("resume") == resume_id or query.get("resumeId") == resume_id


def row_to_apply_draft(row: dict[str, Any]) -> ApplyDraft:
    return ApplyDraft(
        vacancy_id=int(row["id"]) if row.get("id") is not None else None,
        application_id=int(row["application_id"]) if row.get("application_id") is not None else None,
        resume_id=str(row.get("resume_id") or "").strip() or None,
        title=str(row.get("title") or "Без названия"),
        company=str(row.get("company") or "Компания не указана"),
        apply_url=str(row.get("apply_url") or row.get("url") or ""),
        cover_letter=str(row.get("cover_letter") or ""),
    )


class HHWebApplyRunner:
    """Fill HH response forms through a real browser session, without HH API/OAuth.

    The runner intentionally does not bypass login, CAPTCHA, or anti-bot screens. It uses
    a persistent browser profile so the user can log in once and reuse cookies. By default
    it fills the draft and stops before clicking submit; sending requires `send=True`.
    """

    def __init__(self, *, page: PageLike, close_handles: list[Any] | None = None) -> None:
        self.page = page
        self._close_handles = close_handles or []

    @classmethod
    def launch(
        cls,
        *,
        user_data_dir: str | Path = "./data/hh-browser-profile",
        headless: bool = False,
    ) -> "HHWebApplyRunner":
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - depends on optional browser extra
            raise RuntimeError(
                "Playwright is not installed. Install browser mode with: "
                "pip install -e '.[browser]' && python -m playwright install chromium"
            ) from exc

        path = Path(user_data_dir)
        path.mkdir(parents=True, exist_ok=True)
        playwright = sync_playwright().start()
        context = playwright.chromium.launch_persistent_context(
            str(path),
            headless=headless,
            viewport={"width": 1440, "height": 1000},
            locale="ru-RU",
        )
        page = context.pages[0] if context.pages else context.new_page()
        context.set_default_timeout(20_000)
        context.set_default_navigation_timeout(30_000)
        return cls(page=page, close_handles=[context, playwright])

    def close(self) -> None:
        for handle in self._close_handles:
            close = getattr(handle, "close", None)
            stop = getattr(handle, "stop", None)
            if callable(close):
                close()
            elif callable(stop):
                stop()

    def prepare_one(self, draft: ApplyDraft, *, send: bool = False) -> BrowserApplyResult:
        if not draft.apply_url:
            return BrowserApplyResult(
                application_id=draft.application_id,
                vacancy_id=draft.vacancy_id,
                status="missing_apply_url",
                message="No HH apply URL in CRM row",
                url="",
            )
        if not draft.cover_letter.strip():
            return BrowserApplyResult(
                application_id=draft.application_id,
                vacancy_id=draft.vacancy_id,
                status="missing_cover_letter",
                message="No cover letter draft in CRM row",
                url=draft.apply_url,
            )

        target_url = _apply_url_with_resume(draft.apply_url, draft.resume_id)
        try:
            self.page.goto(target_url, wait_until="domcontentloaded", timeout=30_000)  # type: ignore[call-arg]
        except TypeError:  # fake/protocol pages in tests may not accept timeout
            self.page.goto(target_url, wait_until="domcontentloaded")
        except Exception as exc:
            return BrowserApplyResult(
                application_id=draft.application_id,
                vacancy_id=draft.vacancy_id,
                status="navigation_timeout",
                message=f"HH apply page navigation failed: {type(exc).__name__}: {exc}",
                url=getattr(self.page, "url", draft.apply_url),
            )
        self._safe_wait("domcontentloaded")
        if self._login_required():
            return BrowserApplyResult(
                application_id=draft.application_id,
                vacancy_id=draft.vacancy_id,
                status="needs_login",
                message="HH login is required in the browser profile",
                url=getattr(self.page, "url", draft.apply_url),
            )

        selected_resume = self._select_resume_if_requested(draft.resume_id)
        if draft.resume_id and not selected_resume:
            return BrowserApplyResult(
                application_id=draft.application_id,
                vacancy_id=draft.vacancy_id,
                status="resume_not_found",
                message=f"Requested HH resume_id was not found on the apply form: {draft.resume_id}",
                url=getattr(self.page, "url", draft.apply_url),
            )

        self._open_cover_letter_if_needed()
        filled_selector = self._fill_first_available(LETTER_INPUT_SELECTORS, draft.cover_letter)
        if not filled_selector:
            return BrowserApplyResult(
                application_id=draft.application_id,
                vacancy_id=draft.vacancy_id,
                status="form_not_found",
                message="Could not find HH cover-letter input; markup may have changed",
                url=getattr(self.page, "url", draft.apply_url),
            )

        if not send:
            return BrowserApplyResult(
                application_id=draft.application_id,
                vacancy_id=draft.vacancy_id,
                status="prepared",
                message=f"Draft inserted via {filled_selector}; submit not clicked",
                url=getattr(self.page, "url", draft.apply_url),
            )

        clicked_selector = self._click_first_available(SUBMIT_SELECTORS)
        if not clicked_selector:
            return BrowserApplyResult(
                application_id=draft.application_id,
                vacancy_id=draft.vacancy_id,
                status="submit_not_found",
                message="Cover letter filled, but submit button was not found",
                url=getattr(self.page, "url", draft.apply_url),
            )
        self._safe_wait("domcontentloaded")
        self._safe_wait("networkidle")
        self._safe_pause(3000)
        if self._sent_confirmed():
            return BrowserApplyResult(
                application_id=draft.application_id,
                vacancy_id=draft.vacancy_id,
                status="sent",
                message=f"Submit confirmed after clicking {clicked_selector}",
                url=getattr(self.page, "url", draft.apply_url),
            )
        return BrowserApplyResult(
            application_id=draft.application_id,
            vacancy_id=draft.vacancy_id,
            status="submit_unverified",
            message=(
                f"Submit clicked via {clicked_selector}, but HH did not show a delivered/answered confirmation. "
                "The page may require extra questionnaire answers or async confirmation."
            ),
            url=getattr(self.page, "url", draft.apply_url),
        )

    def run(self, drafts: list[ApplyDraft], *, send: bool = False) -> list[BrowserApplyResult]:
        return [self.prepare_one(draft, send=send) for draft in drafts]

    def _safe_wait(self, state: str) -> None:
        try:
            self.page.wait_for_load_state(state)
        except Exception:
            return

    def _safe_pause(self, ms: int) -> None:
        wait_for_timeout = getattr(self.page, "wait_for_timeout", None)
        if callable(wait_for_timeout):
            try:
                wait_for_timeout(ms)
            except Exception:
                return

    def _sent_confirmed(self) -> bool:
        text = ""
        locator = self._safe_locator("body")
        if locator:
            inner_text = getattr(locator, "inner_text", None)
            if callable(inner_text):
                try:
                    text = str(inner_text())
                except Exception:
                    text = ""
        return any(marker in text for marker in SENT_CONFIRMATION_MARKERS)

    def _login_required(self) -> bool:
        current_url = getattr(self.page, "url", "").lower()
        if any(marker in current_url for marker in ["/account/login", "/account/signup", "/login"]):
            return True
        for selector in LOGIN_SELECTORS:
            locator = self._safe_locator(selector)
            if locator and self._safe_count(locator) > 0 and self._safe_visible(locator):
                return True
        return False

    def _open_cover_letter_if_needed(self) -> None:
        for selector in LETTER_OPEN_SELECTORS:
            locator = self._safe_locator(selector)
            if locator and self._safe_count(locator) > 0:
                try:
                    locator.click()
                    self._safe_wait("domcontentloaded")
                    return
                except Exception:
                    continue

    def _select_resume_if_requested(self, resume_id: str | None) -> str | None:
        if not resume_id:
            return None
        for selector in _resume_selectors(resume_id):
            locator = self._safe_locator(selector)
            if locator and self._safe_count(locator) > 0:
                try:
                    locator.click()
                    self._safe_wait("domcontentloaded")
                    return selector
                except Exception:
                    continue
        current_url = getattr(self.page, "url", "")
        if _url_has_resume(current_url, resume_id):
            for selector in RESUME_SELECTED_SELECTORS:
                locator = self._safe_locator(selector)
                if locator and self._safe_count(locator) > 0:
                    return "query:resume"
        return None

    def _fill_first_available(self, selectors: list[str], value: str) -> str | None:
        for selector in selectors:
            locator = self._safe_locator(selector)
            if locator and self._safe_count(locator) > 0:
                try:
                    locator.fill(value)
                    return selector
                except Exception:
                    continue
        return None

    def _click_first_available(self, selectors: list[str]) -> str | None:
        for selector in selectors:
            locator = self._safe_locator(selector)
            if locator and self._safe_count(locator) > 0:
                try:
                    locator.click()
                    self._safe_wait("domcontentloaded")
                    return selector
                except Exception:
                    continue
        return None

    def _safe_locator(self, selector: str) -> LocatorLike | None:
        try:
            return self.page.locator(selector)
        except Exception:
            return None

    @staticmethod
    def _safe_count(locator: LocatorLike) -> int:
        try:
            return locator.count()
        except Exception:
            return 0

    @staticmethod
    def _safe_visible(locator: LocatorLike) -> bool:
        try:
            return locator.is_visible()
        except Exception:
            return False
