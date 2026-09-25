from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "projects" / "lantern" / "CURRENTNESS_STATUS_V1.md"
README = ROOT / "README.md"


def test_currentness_status_fails_closed_after_wowsql_retirement():
    text = STATUS.read_text(encoding="utf-8")

    assert "WoWSQL is retired" in text
    assert "LANTERN_CURRENTNESS = UNKNOWN" in text
    assert "does not currently establish a replacement live Lantern runtime" in text
    assert "Do not fall back to:" in text
    assert "- WoWSQL;" in text
    assert "- Supabase;" in text
    assert "- Git repository content;" in text
    assert "- ChatGPT conversation history;" in text


def test_successor_source_is_not_laundered_into_runtime_effect():
    text = STATUS.read_text(encoding="utf-8")

    assert "Build Team Two PR #49" in text
    assert "not an installed Project Lantern runtime" in text
    assert "source package readiness" in text
    assert "runtime qualification" in text
    assert "Project installation" in text
    assert "protected effects" in text


def test_readme_surfaces_current_fail_closed_state():
    text = README.read_text(encoding="utf-8")

    assert "# Project Lantern" in text
    assert "LANTERN_CURRENTNESS = UNKNOWN" in text
    assert "CURRENTNESS_STATUS_V1.md" in text
