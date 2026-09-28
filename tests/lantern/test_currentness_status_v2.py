from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "projects" / "lantern" / "CURRENTNESS_STATUS_V2.md"
README = ROOT / "README.md"


def test_currentness_status_fails_closed_after_wowsql_retirement():
    text = STATUS.read_text(encoding="utf-8")
    assert "WoWSQL is retired" in text
    assert "LANTERN_CURRENTNESS = UNKNOWN" in text
    assert "provider-neutral PostgreSQL / SQL Connectome V4" in text
    assert "Do not substitute any of these" in text
    assert "- WoWSQL;" in text
    assert "- Supabase;" in text
    assert "- Git repository content;" in text
    assert "- ChatGPT conversation history;" in text


def test_source_candidates_are_not_laundered_into_runtime_effect():
    text = STATUS.read_text(encoding="utf-8")
    assert "BT2 `main`" in text
    assert "SQL Connectome `main`" in text
    assert "source candidates and integration surfaces only" in text
    assert "Project installation" in text
    assert "fresh-chat behavioral consumption" in text
    assert "protected effects" in text


def test_readme_surfaces_current_fail_closed_state():
    text = README.read_text(encoding="utf-8")
    assert "## Lantern currentness" in text
    assert "LANTERN_CURRENTNESS = UNKNOWN" in text
    assert "CURRENTNESS_STATUS_V2.md" in text
