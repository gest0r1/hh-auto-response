from app.auto_apply import AutoApplySettings, run_auto_apply_once
from app.hh_browser import BrowserApplyResult
from app.repository import CRMRepository
from app.responses import ApplicantProfile, CaseStudy
from app.scoring import CandidateProfile, ScoreResult, Vacancy


class FakeHHClient:
    def search_vacancies(self, *, text: str, per_page: int = 20, page: int = 0):
        assert text
        return [
            Vacancy(
                external_id="hh-auto-1",
                title="Python React AI automation developer",
                company="AgentCo",
                description="Удалённо. Python, React, FastAPI, Telegram, CRM, AI automation.",
                url="https://hh.ru/vacancy/auto-1",
                salary_from=240000,
                salary_to=320000,
                currency="RUR",
                schedule="remote",
                employment="part",
                skills=["Python", "React", "FastAPI", "Telegram", "CRM", "AI"],
                raw={"apply_url": "https://hh.ru/applicant/vacancy_response?vacancyId=auto-1"},
            )
        ]


class FakeApplyRunner:
    def __init__(self, *, status: str) -> None:
        self.status = status
        self.calls = []

    def run(self, drafts, *, send: bool = False):
        self.calls.append({"send": send, "drafts": drafts})
        return [
            BrowserApplyResult(
                application_id=draft.application_id,
                vacancy_id=draft.vacancy_id,
                status=self.status,
                message=f"fake {self.status}",
                url=draft.apply_url,
            )
            for draft in drafts
        ]


class EmptyHHClient:
    def search_vacancies(self, *, text: str, per_page: int = 20, page: int = 0):
        return []


def candidate_profile() -> CandidateProfile:
    return CandidateProfile(
        target_roles=["full-stack", "ai automation", "crm integrations"],
        skills=["Python", "React", "FastAPI", "Telegram", "CRM", "AI"],
        preferred_keywords=["удалённо", "удаленно", "автоматизация"],
        stop_keywords=["только офис"],
        min_monthly_salary=180000,
    )


def applicant_profile() -> ApplicantProfile:
    return ApplicantProfile(
        full_name="Александр Олегович",
        headline="Full-stack / AI automation engineer",
        strengths=["делаю CRM", "подключаю Telegram и API"],
        cases=[CaseStudy(title="AI CRM", stack=["React", "FastAPI", "Telegram"], result="запустил MVP и дашборд")],
        portfolio_url="https://portfolio.viably.dev",
    )


def test_auto_apply_searches_creates_draft_and_sends_when_enabled(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    runner = FakeApplyRunner(status="sent")

    result = run_auto_apply_once(
        repo=repo,
        search_client=FakeHHClient(),
        candidate_profile=candidate_profile(),
        applicant_profile=applicant_profile(),
        apply_runner=runner,
        settings=AutoApplySettings(
            queries=["Python React AI automation"],
            per_query=10,
            draft_threshold=80,
            min_score=80,
            limit=5,
            daily_limit=1,
            send=True,
        ),
    )

    assert result["search"]["vacancies_seen"] == 1
    assert result["queued"] == 1
    assert result["sent"] == 1
    assert result["daily_remaining"] == 0
    assert result["daily_limit_reached"] is True
    assert result["prepared"] == 0
    assert result["blocked"] == 0
    assert runner.calls[0]["send"] is True
    assert runner.calls[0]["drafts"][0].cover_letter.startswith("Здравствуйте!")
    assert repo.dashboard_summary()["metrics"]["sent_total"] == 1
    assert repo.count_sent_today() == 1


def test_auto_apply_dry_run_prepares_without_marking_sent(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    runner = FakeApplyRunner(status="prepared")

    result = run_auto_apply_once(
        repo=repo,
        search_client=FakeHHClient(),
        candidate_profile=candidate_profile(),
        applicant_profile=applicant_profile(),
        apply_runner=runner,
        settings=AutoApplySettings(
            queries=["Python React AI automation"],
            min_score=80,
            limit=5,
            daily_limit=3,
            send=False,
        ),
    )

    assert result["queued"] == 1
    assert result["prepared"] == 1
    assert result["sent"] == 0
    assert runner.calls[0]["send"] is False
    assert repo.dashboard_summary()["metrics"]["drafts_total"] == 1
    assert repo.dashboard_summary()["metrics"]["sent_total"] == 0


def test_auto_apply_respects_daily_limit_before_opening_browser(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    sent_runner = FakeApplyRunner(status="sent")
    first = run_auto_apply_once(
        repo=repo,
        search_client=FakeHHClient(),
        candidate_profile=candidate_profile(),
        applicant_profile=applicant_profile(),
        apply_runner=sent_runner,
        settings=AutoApplySettings(queries=["Python React AI automation"], min_score=80, daily_limit=1, send=True),
    )
    assert first["sent"] == 1

    blocked_runner = FakeApplyRunner(status="sent")
    second = run_auto_apply_once(
        repo=repo,
        search_client=EmptyHHClient(),
        candidate_profile=candidate_profile(),
        applicant_profile=applicant_profile(),
        apply_runner=blocked_runner,
        settings=AutoApplySettings(queries=["Python React AI automation"], min_score=80, daily_limit=1, send=True),
    )

    assert second["daily_limit_reached"] is True
    assert second["queued"] == 0
    assert blocked_runner.calls == []


def test_auto_apply_archives_stale_bad_draft_before_browser_send(tmp_path):
    repo = CRMRepository(tmp_path / "crm.sqlite3")
    vacancy = Vacancy(
        external_id="hh-stale-bad-draft",
        title="React Python CRM developer",
        company="AgentCo",
        description="Удалённо. CRM, Telegram bot, FastAPI, React.",
        url="https://hh.ru/vacancy/stale-bad-draft",
        salary_from=230000,
        salary_to=280000,
        currency="RUR",
        schedule="remote",
        skills=["React", "Python", "FastAPI", "Telegram", "CRM"],
        raw={"apply_url": "https://hh.ru/applicant/vacancy_response?vacancyId=stale-bad-draft"},
    )
    vacancy_id = repo.upsert_vacancy(vacancy, ScoreResult(score=91, decision="hot"))
    repo.create_or_update_application(
        vacancy_id,
        cover_letter=(
            "Здравствуйте! По смыслу это близко к тому, чем я сейчас занимаюсь: CRM, Telegram bot, "
            "FastAPI и React.\n\n"
            "Могу быстро включиться: разобрать требования, предложить план реализации и собрать "
            "первый рабочий контур.\n\n"
            "Портфолио: https://portfolio.viably.dev"
        ),
        status="draft",
        score_at_apply=91,
    )
    runner = FakeApplyRunner(status="sent")

    result = run_auto_apply_once(
        repo=repo,
        search_client=EmptyHHClient(),
        candidate_profile=candidate_profile(),
        applicant_profile=applicant_profile(),
        apply_runner=runner,
        settings=AutoApplySettings(
            queries=["Python React AI automation"],
            min_score=80,
            limit=5,
            daily_limit=5,
            send=True,
        ),
    )

    assert runner.calls == []
    assert result["queue_candidates"] == 1
    assert result["queued"] == 0
    assert result["quality_skipped"] == 1
    assert result["quality_issues"][0]["external_id"] == "hh-stale-bad-draft"
    assert "generic_repeated_template" in result["quality_issues"][0]["issues"]
    assert repo.review_queue(min_score=80) == []
    assert repo.dashboard_summary()["pipeline"]["archived"] == 1
