from __future__ import annotations

import json

import pytest

from lantern.canonical import CanonicalizationError, canonical_json, normalize_relative_posix_path
from lantern.contracts import build_record, parse_record
from lantern.ids import deterministic_uuid7


def test_canonical_json_is_stable_and_rejects_unsafe_numbers() -> None:
    assert canonical_json({"b": 1, "a": [True, None, "x"]}) == '{"a":[true,null,"x"],"b":1}'
    with pytest.raises(CanonicalizationError):
        canonical_json({"value": 0.5})
    with pytest.raises(CanonicalizationError):
        canonical_json({"value": float("nan")})


def test_paths_fail_closed() -> None:
    assert normalize_relative_posix_path("sources/abc") == "sources/abc"
    for value in ("/absolute", "../escape", "a/../b", "a\\b", ""):
        with pytest.raises(CanonicalizationError):
            normalize_relative_posix_path(value)


def test_record_hash_binds_complete_envelope() -> None:
    project_id = deterministic_uuid7("project", timestamp_ms=1785862800000)
    record_id = deterministic_uuid7("record", timestamp_ms=1785862801000)
    record = build_record(
        project_id=project_id,
        record_id=record_id,
        record_type="Claim",
        actor_id="tester",
        created_at="2026-08-04T12:00:00+00:00",
        provenance={"source": "test"},
        lineage_key="claim-a",
        payload={"claim_key": "claim-a", "text": "A", "epistemic_class": "TEST", "attributable_to": "tester"},
    )
    reparsed = parse_record(record.canonical_json)
    assert reparsed.record_sha256 == record.record_sha256
    tampered = json.loads(record.canonical_json)
    tampered["payload"]["text"] = "B"
    with pytest.raises(ValueError, match="hash"):
        parse_record(json.dumps(tampered, separators=(",", ":"), sort_keys=True))


def test_duplicate_json_keys_fail_closed() -> None:
    project_id = deterministic_uuid7("dup-project", timestamp_ms=1785862800000)
    record_id = deterministic_uuid7("dup-record", timestamp_ms=1785862801000)
    record = build_record(
        project_id=project_id,
        record_id=record_id,
        record_type="Claim",
        actor_id="tester",
        created_at="2026-08-04T12:00:00Z",
        provenance={"source": "test"},
        lineage_key="claim-dup",
        payload={"claim_key": "claim-dup", "text": "A", "epistemic_class": "TEST", "attributable_to": "tester"},
    )
    duplicate = record.canonical_json.replace('"actor_id":"tester"', '"actor_id":"tester","actor_id":"other"', 1)
    with pytest.raises(CanonicalizationError, match="Duplicate JSON key"):
        parse_record(duplicate)
