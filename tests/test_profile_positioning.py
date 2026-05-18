import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_aleksandr_profile_keeps_python_backend_as_primary_axis():
    profile = json.loads((ROOT / "data/profile.aleksandr.json").read_text(encoding="utf-8"))

    assert profile["headline"].startswith("Python Backend Engineer")
    assert profile["target_roles"][:3] == [
        "Python Backend Engineer",
        "Python Backend Developer",
        "Backend Python Developer",
    ]
    assert "Python Backend" in profile["skills"][:5]
    assert profile["strengths"][0].startswith("основной профиль - Python backend")


def test_daily_auto_apply_queries_include_python_backend_without_generic_frontend_spread():
    script = (ROOT / "scripts/run_hh_auto_apply_daily.sh").read_text(encoding="utf-8")

    assert "Python Backend developer" in script
    assert "FastAPI developer" in script
    assert "Backend Python developer" in script
    assert "AI agents developer" in script
    assert "LLM Backend Engineer" in script
    assert "React developer" not in script
    assert "Node.js developer" not in script
    assert "JavaScript developer" not in script
