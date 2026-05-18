from app.hh_browser import HHWebApplyRunner, row_to_apply_draft


class FakeLocator:
    def __init__(self, page, selector: str):
        self.page = page
        self.selector = selector

    def count(self):
        return 1 if self.selector in self.page.available_selectors else 0

    def fill(self, value: str):
        self.page.calls.append(("fill", self.selector, value))

    def click(self):
        self.page.calls.append(("click", self.selector))
        if "submit" in self.selector and self.page.confirm_on_submit:
            self.page.body_text = "Вы откликнулись\nРезюме доставлено"

    def is_visible(self):
        return self.selector in self.page.visible_selectors

    def inner_text(self):
        return self.page.body_text if self.selector == "body" else ""


class FakePage:
    def __init__(self, *, url: str = "https://hh.ru/applicant/vacancy_response?vacancyId=777"):
        self.url = url
        self.calls = []
        self.body_text = ""
        self.confirm_on_submit = True
        self.available_selectors = {
            'textarea[name="letter"]',
            '[data-qa="vacancy-response-submit-popup"]',
        }
        self.visible_selectors = set()

    def goto(self, url: str, wait_until: str = "domcontentloaded"):
        self.calls.append(("goto", url, wait_until))
        self.url = url

    def wait_for_load_state(self, state: str):
        self.calls.append(("wait", state))

    def wait_for_timeout(self, ms: int):
        self.calls.append(("pause", ms))

    def locator(self, selector: str):
        return FakeLocator(self, selector)


def test_row_to_apply_draft_uses_apply_url_and_cover_letter():
    draft = row_to_apply_draft(
        {
            "id": 777,
            "application_id": 12,
            "title": "Python React automation engineer",
            "company": "AgentCo",
            "apply_url": "https://hh.ru/applicant/vacancy_response?vacancyId=777",
            "cover_letter": "Здравствуйте! Готов обсудить CRM.",
        }
    )

    assert draft.vacancy_id == 777
    assert draft.application_id == 12
    assert draft.apply_url.endswith("vacancyId=777")
    assert "CRM" in draft.cover_letter


def test_browser_runner_fills_cover_letter_without_sending():
    page = FakePage()
    runner = HHWebApplyRunner(page=page)
    draft = row_to_apply_draft(
        {
            "id": 777,
            "application_id": 12,
            "title": "Python React automation engineer",
            "company": "AgentCo",
            "apply_url": "https://hh.ru/applicant/vacancy_response?vacancyId=777",
            "cover_letter": "Здравствуйте! Готов обсудить CRM.",
        }
    )

    result = runner.prepare_one(draft, send=False)

    assert result.status == "prepared"
    assert ("goto", draft.apply_url, "domcontentloaded") in page.calls
    assert ("fill", 'textarea[name="letter"]', draft.cover_letter) in page.calls
    assert not any(call[0] == "click" and "submit" in call[1] for call in page.calls)


def test_browser_runner_can_click_submit_when_send_is_explicit():
    page = FakePage()
    runner = HHWebApplyRunner(page=page)
    draft = row_to_apply_draft(
        {
            "id": 777,
            "application_id": 12,
            "title": "Python React automation engineer",
            "company": "AgentCo",
            "apply_url": "https://hh.ru/applicant/vacancy_response?vacancyId=777",
            "cover_letter": "Здравствуйте! Готов обсудить CRM.",
        }
    )

    result = runner.prepare_one(draft, send=True)

    assert result.status == "sent"
    assert ("click", '[data-qa="vacancy-response-submit-popup"]') in page.calls
    assert ("pause", 3000) in page.calls


def test_browser_runner_does_not_mark_sent_without_hh_confirmation():
    page = FakePage()
    page.confirm_on_submit = False
    runner = HHWebApplyRunner(page=page)
    draft = row_to_apply_draft(
        {
            "id": 777,
            "application_id": 12,
            "title": "Python React automation engineer",
            "company": "AgentCo",
            "apply_url": "https://hh.ru/applicant/vacancy_response?vacancyId=777",
            "cover_letter": "Здравствуйте! Готов обсудить CRM.",
        }
    )

    result = runner.prepare_one(draft, send=True)

    assert result.status == "submit_unverified"
    assert ("click", '[data-qa="vacancy-response-submit-popup"]') in page.calls


def test_browser_runner_stops_if_login_is_required():
    page = FakePage(url="https://hh.ru/account/login")
    page.available_selectors = set()
    runner = HHWebApplyRunner(page=page)
    draft = row_to_apply_draft(
        {
            "id": 777,
            "application_id": 12,
            "title": "Python React automation engineer",
            "company": "AgentCo",
            "apply_url": "https://hh.ru/account/login",
            "cover_letter": "Здравствуйте!",
        }
    )

    result = runner.prepare_one(draft, send=False)

    assert result.status == "needs_login"
    assert "login" in result.message.lower()
