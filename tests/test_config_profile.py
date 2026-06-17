import json

from app.config import default_applicant_profile, default_candidate_profile, get_settings


def test_profile_loader_uses_json_profile(monkeypatch, tmp_path):
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "full_name": "Александр Олегович",
                "headline": "Platform Architect",
                "portfolio_url": "https://portfolio.viably.dev",
                "github_url": "https://github.com/Glour/dashboard-ai-office",
                "proof_pack_url": "https://disk.yandex.ru/d/TZHMyvaIDRYoeg",
                "location": "Обнинск",
                "telegram": "@ne_stoit_togo",
                "telegram_channel": None,
                "age": 25,
                "phone": "+79106053173",
                "skills": ["FastAPI", "React", "Telegram"],
                "target_roles": ["Backend Engineer"],
                "preferred_keywords": ["удалённо"],
                "stop_keywords": ["только офис"],
                "min_monthly_salary": 250000,
                "strengths": ["строю платформы"],
                "cases": [
                    {
                        "title": "Viably",
                        "stack": ["FastAPI", "Next.js"],
                        "result": "production AI product platform",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HH_PROFILE_PATH", str(profile_path))

    candidate = default_candidate_profile()
    applicant = default_applicant_profile()

    assert candidate.skills == ["FastAPI", "React", "Telegram"]
    assert candidate.target_roles == ["Backend Engineer"]
    assert candidate.min_monthly_salary == 250000
    assert applicant.portfolio_url == "https://portfolio.viably.dev"
    assert applicant.github_url == "https://github.com/Glour/dashboard-ai-office"
    assert applicant.proof_pack_url == "https://disk.yandex.ru/d/TZHMyvaIDRYoeg"
    assert applicant.location == "Обнинск"
    assert applicant.telegram == "@ne_stoit_togo"
    assert applicant.telegram_channel is None
    assert applicant.age == 25
    assert applicant.phone == "+79106053173"
    assert applicant.cases[0].title == "Viably"
    assert applicant.cases[0].result == "production AI product platform"


def test_profile_age_env_override_is_parsed(monkeypatch, tmp_path):
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps({"full_name": "Александр Олегович", "age": 25}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setenv("HH_PROFILE_PATH", str(profile_path))
    monkeypatch.setenv("HH_PROFILE_AGE", "26")

    applicant = default_applicant_profile()

    assert applicant.age == 26


def test_profile_age_ignores_invalid_env_and_json_values(monkeypatch, tmp_path):
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps({"full_name": "Александр Олегович", "age": "not-a-number"}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setenv("HH_PROFILE_PATH", str(profile_path))
    monkeypatch.setenv("HH_PROFILE_AGE", "invalid")

    applicant = default_applicant_profile()

    assert applicant.age is None


def test_settings_include_no_api_browser_profile_path(monkeypatch, tmp_path):
    browser_dir = tmp_path / "hh-browser-profile"
    monkeypatch.setenv("HH_BROWSER_USER_DATA_DIR", str(browser_dir))

    settings = get_settings()

    assert settings.hh_browser_user_data_dir == browser_dir
