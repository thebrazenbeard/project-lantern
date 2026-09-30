from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "projects" / "lantern" / "CURRENTNESS_STATUS_V3.json"


def test_no_active_or_inferred_replacement_currentness_backend():
    data = json.loads(STATUS.read_text(encoding="utf-8"))
    assert data["schema"] == "PROJECT_LANTERN_CURRENTNESS_STATUS_V3"
    assert data["retired_currentness_provider"]["state"] == "RETIRED"
    assert data["active_currentness_backend"] is None
    assert data["replacement_currentness_backend"] == "NOT_ESTABLISHED"
    assert data["lantern_currentness"] == "UNKNOWN"
    assert data["fail_closed"]["query_retired_wowsql"] is False
    assert data["fail_closed"]["infer_candidate_as_active_backend"] is False


def test_candidate_source_is_not_runtime_currentness():
    data = json.loads(STATUS.read_text(encoding="utf-8"))
    assert data["source_candidates"] == [
        {"name": "POSTGRESQL_SQL_CONNECTOME_V4", "state": "SOURCE_CANDIDATE_ONLY"}
    ]
    assert data["evidence_ceiling"] == "SOURCE_STATUS_ONLY_NO_LIVE_RUNTIME_CURRENTNESS"
    assert all(
        data["fail_closed"][key] is False
        for key in (
            "fallback_to_supabase",
            "fallback_to_git_or_project_prose",
            "fallback_to_memory_or_chat",
        )
    )
