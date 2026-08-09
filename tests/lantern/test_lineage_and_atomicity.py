from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lantern.canonical import canonical_json_bytes, sha256_hex
from lantern.store import LanternStore, ValidationError


def test_stale_competing_successor_has_no_partial_database_or_source_effects(seeded_store, fixture_data: dict) -> None:
    source_ops = [op for op in fixture_data["operations"] if op["operation"] == "source.observe"]
    source_a = source_ops[0]["args"]["record_id"]
    before_records = seeded_store._connection.execute("select count(*) from records").fetchone()[0]
    before_events = seeded_store._connection.execute("select count(*) from state_events").fetchone()[0]
    before_files = sorted(path.name for path in seeded_store.sources_path.iterdir())
    result = seeded_store.observe_source(
        actor_id="operator-1",
        source_key="fixture-source",
        locator="fixture/source.md",
        retrieval_route="TEST",
        media_type="text/markdown",
        custody_mode="CAPTURED",
        retention_status="RETAINED",
        observed_at="2026-08-04T12:20:00Z",
        content=b"Competing successor",
        predecessor_record_id=source_a,
    )
    assert result.outcome == "CONFLICT"
    assert seeded_store._connection.execute("select count(*) from records").fetchone()[0] == before_records
    assert seeded_store._connection.execute("select count(*) from state_events").fetchone()[0] == before_events
    assert sorted(path.name for path in seeded_store.sources_path.iterdir()) == before_files


def test_invalid_timestamp_fails_before_source_staging(seeded_store) -> None:
    before = sorted(path.name for path in seeded_store.sources_path.iterdir())
    with pytest.raises(ValueError):
        seeded_store.observe_source(
            actor_id="operator-1", source_key="bad-time", locator="bad", retrieval_route="TEST",
            media_type="text/plain", custody_mode="CAPTURED", retention_status="RETAINED",
            observed_at="not-a-time", content=b"bytes",
        )
    assert sorted(path.name for path in seeded_store.sources_path.iterdir()) == before


def test_successor_projection_and_events_commit_together(seeded_store, fixture_data: dict) -> None:
    source_ops = [op for op in fixture_data["operations"] if op["operation"] == "source.observe"]
    source_a = source_ops[0]["args"]["record_id"]
    source_b = source_ops[1]["args"]["record_id"]
    head = seeded_store._connection.execute(
        "select record_id from lineage_heads where record_type='SourceSnapshot' and lineage_key='fixture-source'"
    ).fetchone()[0]
    assert head == source_b
    assert seeded_store._connection.execute(
        "select count(*) from state_events where subject_record_id=? and event_type='SUPERSEDED'", (source_a,)
    ).fetchone()[0] == 1
    assert seeded_store._connection.execute(
        "select count(*) from state_events where event_type='REVIEW_REQUIRED'"
    ).fetchone()[0] == 2


def _journal_paths(root: Path, operation_id: str) -> tuple[Path, Path]:
    token = sha256_hex(operation_id)[:32]
    stage = root / ".lantern-staging" / token
    journal = root / ".lantern-operations" / f"{token}.json"
    stage.mkdir(parents=True, exist_ok=True)
    journal.parent.mkdir(parents=True, exist_ok=True)
    return stage, journal


def _write_journal(journal: Path, operation_id: str, stage: Path, root: Path, targets: list[str]) -> None:
    journal.write_bytes(canonical_json_bytes({
        "schema": "LANTERN_FILE_OPERATION_V1",
        "operation_id": operation_id,
        "stage_dir": stage.relative_to(root).as_posix(),
        "new_targets": targets,
    }) + b"\n")


@pytest.mark.parametrize("case", ["absolute", "traversal", "malformed", "noncanonical", "operation_mismatch"])
def test_hostile_recovery_journal_blocks_open_without_external_deletion(tmp_path: Path, case: str) -> None:
    root = tmp_path / "store"
    with LanternStore.initialize(root):
        pass
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")
    operation_id = "hostile-recovery"
    stage, journal = _journal_paths(root, operation_id)
    digest = sha256_hex(b"safe")
    if case == "absolute":
        _write_journal(journal, operation_id, stage, root, [outside.as_posix()])
    elif case == "traversal":
        _write_journal(journal, operation_id, stage, root, ["sources/../outside.txt"])
    elif case == "malformed":
        journal.write_text("{", encoding="utf-8")
    elif case == "noncanonical":
        payload = {"schema": "LANTERN_FILE_OPERATION_V1", "operation_id": operation_id,
                   "stage_dir": stage.relative_to(root).as_posix(), "new_targets": [f"sources/{digest}"]}
        journal.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    else:
        _write_journal(journal, "different-operation", stage, root, [f"sources/{digest}"])
    with pytest.raises(ValidationError):
        LanternStore.open(root)
    assert outside.read_text(encoding="utf-8") == "keep"
    assert journal.exists()


def test_symlinked_recovery_stage_blocks_open(tmp_path: Path) -> None:
    root = tmp_path / "store"
    with LanternStore.initialize(root):
        pass
    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (outside_dir / "keep.txt").write_text("keep", encoding="utf-8")
    operation_id = "symlink-recovery"
    token = sha256_hex(operation_id)[:32]
    stage_parent = root / ".lantern-staging"
    stage_parent.mkdir(exist_ok=True)
    stage = stage_parent / token
    try:
        os.symlink(outside_dir, stage, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    journal = root / ".lantern-operations" / f"{token}.json"
    journal.parent.mkdir(exist_ok=True)
    _write_journal(journal, operation_id, stage, root, [])
    with pytest.raises(ValidationError, match="symlink"):
        LanternStore.open(root)
    assert (outside_dir / "keep.txt").read_text(encoding="utf-8") == "keep"
