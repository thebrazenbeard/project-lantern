import json

import pytest

from tools.source_currentness_status import summarize_source_status


def test_source_status_cannot_assert_live_provider_currentness(tmp_path):
    path = tmp_path / "source.json"
    path.write_text(json.dumps({
        "schema": "PROJECT_LANTERN_CURRENTNESS_STATUS_V3",
        "active_currentness_backend": "new-provider",
        "lantern_currentness": "CURRENT",
    }), encoding="utf-8")
    result = summarize_source_status(path)
    assert result["declared_backend"] == "new-provider"
    assert result["declared_source_currentness"] == "CURRENT"
    assert result["live_currentness"] == "UNKNOWN"
    assert result["live_provider_read"] is False


def test_canonical_lantern_source_status_is_unbound():
    result = summarize_source_status()
    assert result["evidence_class"] == "SOURCE_ONLY"
    assert result["declared_backend"] is None
    assert result["live_currentness"] == "UNKNOWN"


def test_malformed_source_status_fails_closed(tmp_path):
    path = tmp_path / "source.json"
    path.write_text('{"schema":"V2"}', encoding="utf-8")
    with pytest.raises(ValueError, match="unrecognized"):
        summarize_source_status(path)
