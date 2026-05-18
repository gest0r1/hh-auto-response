from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.hh_chat import (
    ExternalFormResult,
    GoogleFormRequest,
    answer_google_form_question,
    is_google_form_url,
    normalize_text,
)
from app.responses import ApplicantProfile


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


@dataclass(slots=True)
class GoogleFormField:
    label: str
    selector: str
    required: bool
    kind: str


LOGIN_URL_MARKERS = [
    "accounts.google.com",
    "/signin",
    "/servicelogin",
]
LOGIN_SELECTORS = [
    'input[type="password"]',
    'input[type="email"]',
    '#identifierId',
]
CAPTCHA_SELECTORS = [
    'iframe[src*="recaptcha"]',
    ".g-recaptcha",
    '[data-sitekey]',
]
BLOCKED_BODY_MARKERS = [
    "captcha",
    "recaptcha",
    "подтвердите, что вы не робот",
    "i'm not a robot",
]
PAYMENT_BODY_MARKERS = [
    "payment",
    "оплата",
    "платеж",
    "платёж",
    "карта",
    "card number",
]
SUBMIT_SELECTORS = [
    'div[role="button"]:has-text("Отправить")',
    'div[role="button"]:has-text("Submit")',
    'span:has-text("Отправить")',
    'span:has-text("Submit")',
]
SUBMIT_CONFIRMATION_MARKERS = [
    "Ответ записан",
    "Ваш ответ записан",
    "Your response has been recorded",
    "Thanks for filling out",
]


class ConservativeGoogleFormRunner:
    """Open and fill only simple Google Forms text fields.

    The runner intentionally fails closed on login, CAPTCHA, payment wording, file upload,
    required choices and required text fields that cannot be answered from Aleksandr's
    profile. Submitting is controlled only by the caller's explicit `submit` flag.
    """

    def __init__(
        self,
        *,
        page: PageLike,
        profile: ApplicantProfile,
        close_handles: list[Any] | None = None,
    ) -> None:
        self.page = page
        self.profile = profile
        self._close_handles = close_handles or []

    @classmethod
    def launch(
        cls,
        *,
        profile: ApplicantProfile,
        user_data_dir: str | Path = "./data/hh-browser-profile",
        headless: bool = False,
    ) -> "ConservativeGoogleFormRunner":
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
        return cls(profile=profile, page=page, close_handles=[context, playwright])

    def close(self) -> None:
        for handle in self._close_handles:
            close = getattr(handle, "close", None)
            stop = getattr(handle, "stop", None)
            if callable(close):
                close()
            elif callable(stop):
                stop()

    def handle_google_form(
        self,
        request: GoogleFormRequest,
        *,
        submit: bool = False,
    ) -> ExternalFormResult:
        if not is_google_form_url(request.form_url):
            return ExternalFormResult(
                status="non_google_url",
                message="External form URL is not a Google Form",
                url=request.form_url,
            )

        self.page.goto(request.form_url, wait_until="domcontentloaded")
        self._safe_wait("domcontentloaded")
        self._safe_wait("networkidle")

        current_url = getattr(self.page, "url", request.form_url)
        if self._login_required():
            return ExternalFormResult(
                status="needs_login",
                message="Google login is required in the persistent browser profile",
                url=current_url,
            )

        body_text = self._body_text()
        if self._captcha_present(body_text):
            return ExternalFormResult(
                status="captcha",
                message="Google Form shows a CAPTCHA or bot check",
                url=current_url,
            )
        if self._payment_present(body_text):
            return ExternalFormResult(
                status="payment",
                message="Google Form contains payment wording; stopped",
                url=current_url,
            )
        if self._has_file_upload():
            return ExternalFormResult(
                status="file_upload",
                message="Google Form contains a file upload; stopped",
                url=current_url,
            )

        fields = self._extract_fields()
        if not fields:
            return ExternalFormResult(
                status="no_fields",
                message="Google Form has no simple text fields to fill",
                url=current_url,
            )

        filled = 0
        for field in fields:
            if field.kind != "text":
                if field.required:
                    return ExternalFormResult(
                        status="ambiguous_fields",
                        message=f"Required non-text field is not safe to answer: {field.label}",
                        url=current_url,
                        filled_fields=filled,
                    )
                continue

            answer = answer_google_form_question(field.label, self.profile)
            if not answer:
                if field.required:
                    return ExternalFormResult(
                        status="unknown_required",
                        message=f"Unknown required field: {field.label}",
                        url=current_url,
                        filled_fields=filled,
                    )
                continue

            locator = self._safe_locator(field.selector)
            if not locator or self._safe_count(locator) <= 0:
                if field.required:
                    return ExternalFormResult(
                        status="ambiguous_fields",
                        message=f"Required field selector is not available: {field.label}",
                        url=current_url,
                        filled_fields=filled,
                    )
                continue
            try:
                locator.fill(answer)
                filled += 1
            except Exception:
                if field.required:
                    return ExternalFormResult(
                        status="ambiguous_fields",
                        message=f"Could not fill required field: {field.label}",
                        url=current_url,
                        filled_fields=filled,
                    )

        if not submit:
            return ExternalFormResult(
                status="filled_not_submitted",
                message="Google Form filled where safe; submit not clicked",
                url=current_url,
                filled_fields=filled,
            )

        clicked_selector = self._click_first_available(SUBMIT_SELECTORS)
        if not clicked_selector:
            return ExternalFormResult(
                status="submit_not_found",
                message="Google Form filled, but submit button was not found",
                url=current_url,
                filled_fields=filled,
            )
        self._safe_wait("domcontentloaded")
        self._safe_wait("networkidle")
        self._safe_pause(1500)
        if self._submit_confirmed():
            return ExternalFormResult(
                status="submitted",
                message=f"Google Form submit confirmed after clicking {clicked_selector}",
                url=getattr(self.page, "url", current_url),
                filled_fields=filled,
                submitted=True,
            )
        return ExternalFormResult(
            status="submit_unverified",
            message=f"Submit clicked via {clicked_selector}, but confirmation was not detected",
            url=getattr(self.page, "url", current_url),
            filled_fields=filled,
        )

    def _extract_fields(self) -> list[GoogleFormField]:
        script = """
        () => {
          const rows = Array.from(document.querySelectorAll('div[role="listitem"]'));
          const fields = [];
          rows.forEach((row, rowIndex) => {
            const text = (row.innerText || row.textContent || '').trim();
            const label = text
              .split('\\n')
              .map((line) => line.trim())
              .filter(Boolean)
              .filter((line) => !/^(Обязательный вопрос|Required|Ваш ответ|Your answer)$/i.test(line))
              .slice(0, 4)
              .join(' ');
            const inputs = Array.from(row.querySelectorAll(
              'input:not([type="hidden"]), textarea, select'
            ));
            const fileInput = inputs.some((node) => (node.type || '').toLowerCase() === 'file');
            const textInputs = inputs.filter((node) => {
              const tag = (node.tagName || '').toLowerCase();
              const type = (node.type || 'text').toLowerCase();
              return tag === 'textarea' || ['text', 'email', 'url', 'tel'].includes(type);
            });
            const required = /\\*|Обязательный вопрос|Required/i.test(text)
              || inputs.some((node) => node.required || node.getAttribute('aria-required') === 'true');
            let kind = 'unsupported';
            let selector = '';
            if (fileInput) {
              kind = 'file_upload';
            } else if (textInputs.length === 1) {
              kind = 'text';
              selector = `data-hh-crm-google-field-${rowIndex}`;
              textInputs[0].setAttribute('data-hh-crm-google-field', selector);
              selector = `[data-hh-crm-google-field="${selector}"]`;
            } else if (textInputs.length > 1) {
              kind = 'ambiguous_text';
            }
            fields.push({label, selector, required, kind});
          });
          return fields;
        }
        """
        rows = self._safe_evaluate(script, fallback=[])
        fields: list[GoogleFormField] = []
        if not isinstance(rows, list):
            return fields
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            label = normalize_text(str(raw.get("label") or ""))
            kind = normalize_text(str(raw.get("kind") or "unsupported"))
            selector = str(raw.get("selector") or "")
            required = bool(raw.get("required"))
            if kind == "file_upload":
                fields.append(GoogleFormField(label=label or "file upload", selector="", required=True, kind=kind))
            elif kind == "text" and selector:
                fields.append(GoogleFormField(label=label, selector=selector, required=required, kind=kind))
            elif required:
                fields.append(GoogleFormField(label=label or "required field", selector="", required=True, kind=kind))
        return fields

    def _login_required(self) -> bool:
        current_url = getattr(self.page, "url", "").lower()
        if any(marker in current_url for marker in LOGIN_URL_MARKERS):
            return True
        for selector in LOGIN_SELECTORS:
            locator = self._safe_locator(selector)
            if locator and self._safe_count(locator) > 0 and self._safe_visible(locator):
                return True
        return False

    def _captcha_present(self, body_text: str) -> bool:
        lowered = body_text.lower()
        if any(marker in lowered for marker in BLOCKED_BODY_MARKERS):
            return True
        for selector in CAPTCHA_SELECTORS:
            locator = self._safe_locator(selector)
            if locator and self._safe_count(locator) > 0:
                return True
        return False

    @staticmethod
    def _payment_present(body_text: str) -> bool:
        lowered = body_text.lower()
        return any(marker in lowered for marker in PAYMENT_BODY_MARKERS)

    def _has_file_upload(self) -> bool:
        locator = self._safe_locator('input[type="file"]')
        return bool(locator and self._safe_count(locator) > 0)

    def _body_text(self) -> str:
        locator = self._safe_locator("body")
        if not locator:
            return ""
        inner_text = getattr(locator, "inner_text", None)
        if callable(inner_text):
            try:
                return str(inner_text())
            except Exception:
                return ""
        return ""

    def _click_first_available(self, selectors: list[str]) -> str | None:
        for selector in selectors:
            locator = self._safe_locator(selector)
            if locator and self._safe_count(locator) > 0:
                try:
                    locator.click()
                    return selector
                except Exception:
                    continue
        return None

    def _submit_confirmed(self) -> bool:
        text = self._body_text()
        return any(marker in text for marker in SUBMIT_CONFIRMATION_MARKERS)

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

    def _safe_locator(self, selector: str) -> LocatorLike | None:
        try:
            return self.page.locator(selector)
        except Exception:
            return None

    def _safe_evaluate(self, expression: str, *, fallback: Any) -> Any:
        evaluate = getattr(self.page, "evaluate", None)
        if not callable(evaluate):
            return fallback
        try:
            return evaluate(expression)
        except Exception:
            return fallback

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
