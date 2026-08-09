from __future__ import annotations

import json
from pathlib import Path

import pytest

from lantern.canonical import canonical_json_bytes, sha256_hex
from lantern.contracts import build_record, parse_record
from lantern.ids import deterministic_uuid7
from lantern.store import LanternStore, ValidationError


def _count(store) -> int:
    return store._connection.execute("select count(*) from records").fetchone()[0]


def test_direct_insert_rejects_validly_hashed_invalid_domain_records_without_effects(seeded_store) -> None:
    project_id = seeded_store.project_id
    before = _count(seeded_store)
    records = [
        build_record(
            project_id=project_id, record_id=deterministic_uuid7("bad-source", timestamp_ms=1785867000000),
            record_type="SourceSnapshot", actor_id="tester", created_at="2026-08-04T13:10:00Z",
            observed_at="2026-08-04T13:10:00Z", provenance={"source_locator": "x", "retrieval_route": "TEST"},
            lineage_key="bad-source", payload={"source_key": "bad-source", "locator": "x", "retrieval_route": "TEST",
            "media_type": "text/plain", "custody_mode": "CAPTURED", "retention_status": "RETAINED", "content_sha256": None},
        ),
        build_record(
            project_id=project_id, record_id=deterministic_uuid7("bad-assessment", timestamp_ms=1785867001000),
            record_type="Assessment", actor_id="tester", created_at="2026-08-04T13:10:01Z",
            provenance={"assessor_id": "tester", "scope_id": "scope"}, lineage_key="unknown|tester|scope",
            payload={"claim_id": deterministic_uuid7("unknown", timestamp_ms=1785866000000), "assessor_id": "tester",
            "scope_id": "scope", "disposition": "MAYBE", "rationale": "bad"},
        ),
        build_record(
            project_id=project_id, record_id=deterministic_uuid7("bad-decision", timestamp_ms=1785867002000),
            record_type="Decision", actor_id="tester", created_at="2026-08-04T13:10:02Z",
            provenance={"authority": "tester"}, lineage_key="bad-decision",
            payload={"decision_key": "bad-decision", "authority": "tester", "conclusion": "bad",
            "evidence": [deterministic_uuid7("unknown-evidence", timestamp_ms=1785866001000)],
            "assumptions": [], "alternatives": []},
        ),
    ]
    for record in records:
        with pytest.raises(ValidationError):
            seeded_store.insert_record(record)
        assert _count(seeded_store) == before


def test_import_preflight_rejects_validly_hashed_invalid_assessment_before_any_effect(seeded_store, tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    seeded_store.export_bundle(bundle)
    lines = (bundle / "records.ndjson").read_text(encoding="utf-8").splitlines()
    index = next(i for i, line in enumerate(lines) if parse_record(line).record_type == "Assessment")
    original = parse_record(lines[index])
    invalid = build_record(
        project_id=original.project_id, record_id=original.record_id, record_type="Assessment",
        actor_id=original.actor_id, created_at=original.created_at, provenance=original.provenance,
        lineage_key=original.lineage_key, predecessor_record_id=original.predecessor_record_id,
        payload={**original.payload, "disposition": "MAYBE"},
    )
    lines[index] = invalid.canonical_json
    records_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    (bundle / "records.ndjson").write_bytes(records_bytes)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    manifest["records_sha256"] = sha256_hex(records_bytes)
    (bundle / "manifest.json").write_bytes(canonical_json_bytes(manifest) + b"\n")
    target = LanternStore.initialize(tmp_path / "target", manifest=seeded_store.manifest())
    try:
        with pytest.raises(ValidationError, match="disposition"):
            target.import_bundle(bundle)
        assert _count(target) == 0
        assert list(target.sources_path.iterdir()) == []
    finally:
        target.close()


def test_projection_rebuild_reuses_authoritative_semantic_validator(seeded_store) -> None:
    row = seeded_store._connection.execute(
        "select record_id,payload_json from records where record_type='Assessment' limit 1"
    ).fetchone()
    payload = json.loads(row["payload_json"])
    payload["disposition"] = "MAYBE"
    seeded_store._connection.execute(
        "update records set payload_json=? where record_id=?",
        (json.dumps(payload, separators=(",", ":"), sort_keys=True), row["record_id"]),
    )
    with pytest.raises(ValidationError, match="disposition"):
        with seeded_store.transaction():
            seeded_store._rebuild_projections()


def test_direct_insert_rejects_retained_custody_without_blob_and_has_zero_effects(seeded_store) -> None:
    fake_digest = "a" * 64
    record = build_record(
        project_id=seeded_store.project_id,
        record_id=deterministic_uuid7("retained-without-bytes", timestamp_ms=1785867010000),
        record_type="SourceSnapshot", actor_id="tester", created_at="2026-08-04T13:10:10Z",
        observed_at="2026-08-04T13:10:10Z", provenance={"source_locator": "x", "retrieval_route": "TEST"},
        lineage_key="retained-without-bytes",
        payload={"source_key": "retained-without-bytes", "locator": "x", "retrieval_route": "TEST",
                 "media_type": "text/plain", "custody_mode": "CAPTURED",
                 "retention_status": "RETAINED", "content_sha256": fake_digest},
    )
    before_records = _count(seeded_store)
    before_manifest = (seeded_store.root / seeded_store.MANIFEST_NAME).read_bytes()
    before_sources = sorted(path.name for path in seeded_store.sources_path.iterdir())
    with pytest.raises(ValidationError, match="missing|retained source bytes"):
        seeded_store.insert_record(record)
    assert _count(seeded_store) == before_records
    assert (seeded_store.root / seeded_store.MANIFEST_NAME).read_bytes() == before_manifest
    assert sorted(path.name for path in seeded_store.sources_path.iterdir()) == before_sources
    assert not (seeded_store.root / ".lantern-staging").exists() or not any((seeded_store.root / ".lantern-staging").iterdir())
    assert not (seeded_store.root / ".lantern-operations").exists() or not any((seeded_store.root / ".lantern-operations").iterdir())
