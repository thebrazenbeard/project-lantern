from __future__ import annotations

import json
from pathlib import Path

import pytest

from lantern.canonical import canonical_json_bytes, sha256_hex
from lantern.contracts import build_record, parse_record
from lantern.store import ConflictError, LanternStore, ValidationError


def _rewrite_records(bundle: Path, lines: list[str]) -> None:
    records_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    (bundle / "records.ndjson").write_bytes(records_bytes)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    manifest["records_sha256"] = sha256_hex(records_bytes)
    (bundle / "manifest.json").write_bytes(canonical_json_bytes(manifest) + b"\n")


def _empty_compatible_store(root: Path, source_store) -> LanternStore:
    return LanternStore.initialize(root, manifest=source_store.manifest())


def test_clean_export_import_preserves_exact_manifest_records_and_queries(seeded_store, tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    seeded_store.export_bundle(bundle)
    target_root = tmp_path / "target"
    receipt = LanternStore.import_bundle_new(target_root, bundle)
    assert receipt["summary"] == {"CREATED": len(receipt["results"])}
    assert (target_root / "project-manifest.json").read_bytes() == (seeded_store.root / "project-manifest.json").read_bytes()
    with LanternStore.open(target_root) as target:
        assert target.manifest() == seeded_store.manifest()
        assert target.status() == seeded_store.status()
        second = target.import_bundle(bundle)
        assert second["summary"] == {"VERIFIED": len(second["results"])}
        roundtrip = tmp_path / "roundtrip"
        target.export_bundle(roundtrip)
        assert (bundle / "records.ndjson").read_bytes() == (roundtrip / "records.ndjson").read_bytes()
        assert (bundle / "manifest.json").read_bytes() == (roundtrip / "manifest.json").read_bytes()


def test_divergent_same_id_import_never_overwrites(seeded_store, tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    seeded_store.export_bundle(bundle)
    lines = (bundle / "records.ndjson").read_text(encoding="utf-8").splitlines()
    original = parse_record(lines[0])
    divergent = build_record(
        project_id=original.project_id,
        record_id=original.record_id,
        record_type=original.record_type,
        actor_id=original.actor_id,
        created_at=original.created_at,
        observed_at=original.observed_at,
        provenance=original.provenance,
        lineage_key=original.lineage_key,
        predecessor_record_id=original.predecessor_record_id,
        payload={**original.payload, "retention_status": "DIVERGENT_LOCAL_COPY"},
    )
    lines[0] = divergent.canonical_json
    _rewrite_records(bundle, lines)
    before = seeded_store.get_record(original.record_id).canonical_json
    receipt = seeded_store.import_bundle(bundle)
    result = next(item for item in receipt["results"] if item["record_id"] == original.record_id)
    assert result["outcome"] == "CONFLICT"
    assert seeded_store.get_record(original.record_id).canonical_json == before


def test_import_skips_records_that_depend_on_a_conflicting_id_and_does_not_promote_their_blob(
    seeded_store, tmp_path: Path
) -> None:
    bundle = tmp_path / "bundle"
    seeded_store.export_bundle(bundle)
    source = next(
        seeded_store._row_to_record(row)
        for row in seeded_store._connection.execute(
            "select * from records where record_type='SourceSnapshot' order by created_at"
        )
    )
    original_digest = source.payload["content_sha256"]
    target = _empty_compatible_store(tmp_path / "target", seeded_store)
    try:
        divergent_content = b"target-local-divergent-source"
        divergent_digest = sha256_hex(divergent_content)
        divergent = build_record(
            project_id=source.project_id,
            record_id=source.record_id,
            record_type="SourceSnapshot",
            actor_id=source.actor_id,
            created_at=source.created_at,
            observed_at=source.observed_at,
            provenance=source.provenance,
            lineage_key=source.lineage_key,
            payload={**source.payload, "retention_status": "DIVERGENT_LOCAL_COPY",
                     "content_sha256": divergent_digest},
        )
        (target.sources_path / divergent_digest).write_bytes(divergent_content)
        assert target.insert_record(divergent).outcome == "CREATED"
        receipt = target.import_bundle(bundle)
        outcomes = {item["record_id"]: item["outcome"] for item in receipt["results"]}
        assert outcomes[source.record_id] == "CONFLICT"
        assert "SKIPPED" in outcomes.values()
        assert not (target.sources_path / original_digest).exists()
        assert (target.sources_path / divergent_digest).read_bytes() == divergent_content
    finally:
        target.close()


@pytest.mark.parametrize("failure", ["missing", "wrong_size", "divergent", "undeclared"])
def test_source_preflight_failure_leaves_database_and_source_directory_unchanged(
    seeded_store, tmp_path: Path, failure: str
) -> None:
    bundle = tmp_path / "bundle"
    seeded_store.export_bundle(bundle)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = manifest["sources"][0]["sha256"]
    source_path = bundle / "sources" / digest
    if failure == "missing":
        source_path.unlink()
    elif failure == "wrong_size":
        manifest["sources"][0]["size"] += 1
        manifest_path.write_bytes(canonical_json_bytes(manifest) + b"\n")
    elif failure == "divergent":
        source_path.write_bytes(b"divergent")
    else:
        extra = b"undeclared"
        extra_digest = sha256_hex(extra)
        (bundle / "sources" / extra_digest).write_bytes(extra)
        manifest["sources"].append({"sha256": extra_digest, "size": len(extra)})
        manifest["sources"].sort(key=lambda item: item["sha256"])
        manifest_path.write_bytes(canonical_json_bytes(manifest) + b"\n")
    target = _empty_compatible_store(tmp_path / "target", seeded_store)
    try:
        before_records = target._connection.execute("select count(*) from records").fetchone()[0]
        before_files = sorted(path.name for path in target.sources_path.iterdir())
        with pytest.raises((ValidationError, ConflictError)):
            target.import_bundle(bundle)
        assert target._connection.execute("select count(*) from records").fetchone()[0] == before_records
        assert sorted(path.name for path in target.sources_path.iterdir()) == before_files
    finally:
        target.close()


def test_failure_after_blob_promotion_rolls_back_database_and_files_then_retry_is_idempotent(
    seeded_store, tmp_path: Path
) -> None:
    bundle = tmp_path / "bundle"
    seeded_store.export_bundle(bundle)
    target = _empty_compatible_store(tmp_path / "target", seeded_store)
    try:
        target._import_failure_hook = lambda: (_ for _ in ()).throw(RuntimeError("injected"))
        with pytest.raises(RuntimeError, match="injected"):
            target.import_bundle(bundle)
        assert target._connection.execute("select count(*) from records").fetchone()[0] == 0
        assert list(target.sources_path.iterdir()) == []
        del target._import_failure_hook
        receipt = target.import_bundle(bundle)
        assert receipt["summary"] == {"CREATED": len(receipt["results"])}
        second = target.import_bundle(bundle)
        assert second["summary"] == {"VERIFIED": len(second["results"])}
        assert len(list(target.sources_path.iterdir())) == len(json.loads((bundle / "manifest.json").read_text())["sources"])
    finally:
        target.close()


def test_existing_store_manifest_incompatibility_and_bundle_manifest_tampering_fail_before_mutation(
    seeded_store, tmp_path: Path
) -> None:
    bundle = tmp_path / "bundle"
    seeded_store.export_bundle(bundle)
    incompatible = LanternStore.initialize(tmp_path / "incompatible", project_id=seeded_store.project_id)
    try:
        with pytest.raises(ConflictError, match="ProjectManifest"):
            incompatible.import_bundle(bundle)
        assert incompatible._connection.execute("select count(*) from records").fetchone()[0] == 0
    finally:
        incompatible.close()

    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["project_manifest"]["custody_policy"] = "MUTATED"
    manifest_path.write_bytes(canonical_json_bytes(manifest) + b"\n")
    target = _empty_compatible_store(tmp_path / "target", seeded_store)
    try:
        with pytest.raises(ValidationError, match="custody"):
            target.import_bundle(bundle)
        assert target._connection.execute("select count(*) from records").fetchone()[0] == 0
    finally:
        target.close()

# W7 fresh recovery hostile acceptance. This revision starts from accepted legacy bytes.
import errno
import os
import shutil
import threading

from lantern._store_portability import PortabilityMixin
from lantern.ids import uuid7


def _w7_project_manifest() -> dict:
    return {
        "schema": "LANTERN_PROJECT_MANIFEST_V1",
        "project_id": uuid7(timestamp_ms=1_700_000_000_000, random_bits=1),
        "project_name": "w7-portability-hostile",
        "schema_version": "1.0",
        "interchange_version": "1.0",
        "created_at": "2026-08-08T00:00:00Z",
        "created_by": "w7-test",
        "custody_policy": "LOCAL_FIRST",
        "export_policy": "EXPLICIT_ONLY",
        "path_rules": "PROJECT_ROOT_RELATIVE_POSIX",
    }


def _rewrite_w7_manifest(bundle: Path, **updates) -> None:
    manifest = json.loads((bundle / "manifest.json").read_text())
    manifest.update(updates)
    (bundle / "manifest.json").write_bytes(canonical_json_bytes(manifest) + b"\n")


def _write_w7_empty_bundle(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "sources").mkdir()
    records = b""
    manifest = {
        "schema": "LANTERN_EXPORT_MANIFEST_V1",
        "project_manifest": _w7_project_manifest(),
        "record_count": 0,
        "records_path": "records.ndjson",
        "records_sha256": sha256_hex(records),
        "sources": [],
    }
    (root / "records.ndjson").write_bytes(records)
    (root / "manifest.json").write_bytes(canonical_json_bytes(manifest) + b"\n")
    return root


def _write_w7_source_bundle(root: Path, content: bytes = b"source") -> tuple[Path, str]:
    bundle = _write_w7_empty_bundle(root)
    digest = sha256_hex(content)
    (bundle / "sources" / digest).write_bytes(content)
    _rewrite_w7_manifest(bundle, sources=[{"sha256": digest, "size": len(content)}])
    return bundle, digest


def test_w7_hv_001_bundle_root_symlink_rejected(tmp_path: Path) -> None:
    real = _write_w7_empty_bundle(tmp_path / "real")
    alias = tmp_path / "bundle"
    alias.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValidationError):
        PortabilityMixin._read_bundle(alias)


def test_w7_hv_002_manifest_symlink_rejected(tmp_path: Path) -> None:
    bundle = _write_w7_empty_bundle(tmp_path / "bundle")
    outside = tmp_path / "outside-manifest.json"
    outside.write_bytes((bundle / "manifest.json").read_bytes())
    (bundle / "manifest.json").unlink()
    (bundle / "manifest.json").symlink_to(outside)
    with pytest.raises(ValidationError, match="manifest"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_003_records_symlink_rejected(tmp_path: Path) -> None:
    bundle = _write_w7_empty_bundle(tmp_path / "bundle")
    outside = tmp_path / "outside-records"
    outside.write_bytes(b"")
    (bundle / "records.ndjson").unlink()
    (bundle / "records.ndjson").symlink_to(outside)
    with pytest.raises(ValidationError, match="records"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_004_sources_directory_symlink_rejected(tmp_path: Path) -> None:
    bundle = _write_w7_empty_bundle(tmp_path / "bundle")
    outside = tmp_path / "outside-sources"; outside.mkdir()
    (bundle / "sources").rmdir(); (bundle / "sources").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValidationError, match="sources"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_005_undeclared_physical_source_entry_rejected(tmp_path: Path) -> None:
    bundle = _write_w7_empty_bundle(tmp_path / "bundle")
    (bundle / "sources" / ("a" * 64)).write_bytes(b"undeclared")
    with pytest.raises(ValidationError, match="undeclared"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_006_manifest_read_is_bounded_before_parse(tmp_path: Path) -> None:
    bundle = _write_w7_empty_bundle(tmp_path / "bundle")
    (bundle / "manifest.json").write_bytes(b"{" + b"x" * ((1 << 20) + 1))
    with pytest.raises(ValidationError, match="maximum size"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_007_records_read_is_bounded_before_digest(tmp_path: Path) -> None:
    bundle = _write_w7_empty_bundle(tmp_path / "bundle")
    p = bundle / "records.ndjson"
    with p.open("r+b") as f: f.truncate((64 << 20) + 1)
    with pytest.raises(ValidationError, match="maximum size"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_008_source_digest_must_be_lowercase_hex_before_open(tmp_path: Path) -> None:
    bundle = _write_w7_empty_bundle(tmp_path / "bundle")
    digest = "A" * 64
    _rewrite_w7_manifest(bundle, sources=[{"sha256": digest, "size": 1}])
    with pytest.raises(ValidationError, match="digest"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_009_source_declared_size_over_limit_fails_before_source_open(tmp_path: Path) -> None:
    bundle = _write_w7_empty_bundle(tmp_path / "bundle")
    _rewrite_w7_manifest(bundle, sources=[{"sha256": "a" * 64, "size": (64 << 20) + 1}])
    with pytest.raises(ValidationError, match="maximum size"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_010_aggregate_source_limit_preflights_before_any_source_open(tmp_path: Path) -> None:
    bundle = _write_w7_empty_bundle(tmp_path / "bundle")
    entries=[{"sha256": f"{i:064x}", "size": 64 << 20} for i in range(1,10)]
    _rewrite_w7_manifest(bundle, sources=entries)
    with pytest.raises(ValidationError, match="Aggregate"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_011_source_blob_symlink_rejected(tmp_path: Path) -> None:
    bundle,digest=_write_w7_source_bundle(tmp_path/"bundle")
    outside=tmp_path/"outside"; outside.write_bytes(b"source")
    (bundle/"sources"/digest).unlink(); (bundle/"sources"/digest).symlink_to(outside)
    with pytest.raises(ValidationError, match="source blob"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_012_source_blob_directory_rejected(tmp_path: Path) -> None:
    bundle,digest=_write_w7_source_bundle(tmp_path/"bundle")
    (bundle/"sources"/digest).unlink(); (bundle/"sources"/digest).mkdir()
    with pytest.raises(ValidationError, match="source blob"):
        PortabilityMixin._read_bundle(bundle)


@pytest.mark.parametrize("digest", ["g"*64, "."*64])
def test_w7_hv_013_source_digest_nonhex_rejected(tmp_path: Path, digest: str) -> None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle")
    (bundle/"sources"/digest).write_bytes(b"x")
    _rewrite_w7_manifest(bundle,sources=[{"sha256":digest,"size":1}])
    with pytest.raises(ValidationError, match="digest"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_014_source_size_boolean_rejected(tmp_path: Path) -> None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle"); digest=sha256_hex(b"x")
    (bundle/"sources"/digest).write_bytes(b"x")
    _rewrite_w7_manifest(bundle,sources=[{"sha256":digest,"size":True}])
    with pytest.raises(ValidationError, match="size"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_015_duplicate_source_manifest_entry_rejected(tmp_path: Path) -> None:
    bundle,digest=_write_w7_source_bundle(tmp_path/"bundle")
    _rewrite_w7_manifest(bundle,sources=[{"sha256":digest,"size":6},{"sha256":digest,"size":6}])
    with pytest.raises(ValidationError, match="unique and sorted"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_016_unsorted_source_manifest_entries_rejected(tmp_path: Path) -> None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle"); entries=[]
    for content in (b"a",b"b"):
        digest=sha256_hex(content); (bundle/"sources"/digest).write_bytes(content); entries.append({"sha256":digest,"size":1})
    entries.sort(key=lambda x:x["sha256"],reverse=True); _rewrite_w7_manifest(bundle,sources=entries)
    with pytest.raises(ValidationError, match="unique and sorted"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_017_missing_declared_source_rejected_before_open(tmp_path: Path) -> None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle"); _rewrite_w7_manifest(bundle,sources=[{"sha256":"a"*64,"size":1}])
    with pytest.raises(ValidationError, match="missing"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_018_actual_source_file_over_limit_rejected_by_fstat(tmp_path: Path) -> None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle"); digest="a"*64; p=bundle/"sources"/digest; p.touch()
    with p.open("r+b") as f: f.truncate((64<<20)+1)
    _rewrite_w7_manifest(bundle,sources=[{"sha256":digest,"size":1}])
    with pytest.raises(ValidationError, match="maximum size"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_019_source_declared_size_mismatch_rejected(tmp_path: Path) -> None:
    bundle,digest=_write_w7_source_bundle(tmp_path/"bundle",b"source")
    _rewrite_w7_manifest(bundle,sources=[{"sha256":digest,"size":5}])
    with pytest.raises(ValidationError, match="Divergent"):
        PortabilityMixin._read_bundle(bundle)


def test_w7_hv_020_source_digest_mismatch_rejected(tmp_path: Path) -> None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle"); digest="a"*64
    (bundle/"sources"/digest).write_bytes(b"wrong"); _rewrite_w7_manifest(bundle,sources=[{"sha256":digest,"size":5}])
    with pytest.raises(ValidationError, match="Divergent"):
        PortabilityMixin._read_bundle(bundle)


def _w7_fake_import_class(events:list[Path],*,exit_hook=None,failures:list[bool]|None=None):
    failures=[] if failures is None else failures
    class _Store:
        def __init__(self,root): self.root=Path(root)
        def __enter__(self): return self
        def __exit__(self,exc_type,exc,tb):
            if exit_hook is not None and exc_type is None: exit_hook(self.root)
        def import_bundle(self,bundle):
            if failures and failures.pop(0): raise RuntimeError("injected import failure")
            return {"schema":"LANTERN_IMPORT_RECEIPT_V1","summary":{}}
        def verify_manifest_consistency(self): return None
    class _Fake(PortabilityMixin):
        @classmethod
        def initialize(cls,root,*,manifest,actor_id):
            p=Path(root); events.append(p); p.mkdir(parents=True,exist_ok=True); (p/"owned-marker").write_text("owned"); return _Store(p)
    return _Fake


def _legacy_clean_import_stage(target:Path)->Path:
    return target.with_name(f".{target.name}.lantern-import-{sha256_hex(str(target))[:12]}")


def test_w7_hv_021_clean_import_existing_target_empty_directory_is_conflict(tmp_path:Path)->None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle"); target=tmp_path/"target"; target.mkdir(); inode=target.stat().st_ino
    with pytest.raises(ConflictError): _w7_fake_import_class([]).import_bundle_new(target,bundle)
    assert target.stat().st_ino==inode


def test_w7_hv_022_foreign_legacy_staging_directory_is_never_deleted(tmp_path:Path)->None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle"); target=tmp_path/"target"; foreign=_legacy_clean_import_stage(target); foreign.mkdir(); marker=foreign/"marker"; marker.write_text("keep")
    with pytest.raises(RuntimeError): _w7_fake_import_class([],failures=[True]).import_bundle_new(target,bundle)
    assert marker.read_text()=="keep"


def test_w7_hv_023_clean_import_staging_name_is_unpredictable_per_invocation(tmp_path:Path)->None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle"); target=tmp_path/"target"; events=[]; fake=_w7_fake_import_class(events,failures=[True,True])
    for _ in range(2):
        with pytest.raises(RuntimeError): fake.import_bundle_new(target,bundle)
    assert len(events)==2 and events[0]!=events[1]


def test_w7_hv_024_late_empty_directory_competitor_is_not_overwritten(tmp_path:Path)->None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle"); target=tmp_path/"target"; seen=[]
    def hook(stage): target.mkdir(); seen.append(target.stat().st_ino)
    with pytest.raises(ConflictError): _w7_fake_import_class([],exit_hook=hook).import_bundle_new(target,bundle)
    assert target.stat().st_ino==seen[0]


def test_w7_hv_025_late_nonempty_directory_competitor_is_typed_conflict_and_preserved(tmp_path:Path)->None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle"); target=tmp_path/"target"
    def hook(stage): target.mkdir(); (target/"competitor").write_text("preserve")
    with pytest.raises(ConflictError): _w7_fake_import_class([],exit_hook=hook).import_bundle_new(target,bundle)
    assert (target/"competitor").read_text()=="preserve"


def test_w7_hv_026_replaced_owned_staging_directory_is_not_published(tmp_path:Path)->None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle"); target=tmp_path/"target"
    def hook(stage): shutil.rmtree(stage); stage.mkdir(); (stage/"attacker").write_text("wrong")
    with pytest.raises(ValidationError,match="staging"):
        _w7_fake_import_class([],exit_hook=hook).import_bundle_new(target,bundle)
    assert not target.exists()


def test_w7_hv_027_existing_regular_file_target_is_preserved(tmp_path:Path)->None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle"); target=tmp_path/"target"; target.write_text("keep")
    with pytest.raises(ConflictError): _w7_fake_import_class([]).import_bundle_new(target,bundle)
    assert target.read_text()=="keep"


def test_w7_hv_028_existing_symlink_target_is_preserved(tmp_path:Path)->None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle"); real=tmp_path/"real"; real.mkdir(); target=tmp_path/"target"; target.symlink_to(real,target_is_directory=True)
    with pytest.raises(ConflictError): _w7_fake_import_class([]).import_bundle_new(target,bundle)
    assert target.is_symlink()


def test_w7_hv_029_clean_import_success_publishes_owned_stage_once(tmp_path:Path)->None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle"); target=tmp_path/"target"; events=[]; receipt=_w7_fake_import_class(events).import_bundle_new(target,bundle)
    assert receipt["schema"]=="LANTERN_IMPORT_RECEIPT_V1" and (target/"owned-marker").read_text()=="owned" and len(events)==1


def test_w7_hv_030_clean_import_failure_cleanup_allows_immediate_retry(tmp_path:Path)->None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle"); target=tmp_path/"target"; fake=_w7_fake_import_class([],failures=[True,False])
    with pytest.raises(RuntimeError): fake.import_bundle_new(target,bundle)
    assert not target.exists(); assert fake.import_bundle_new(target,bundle)["schema"]=="LANTERN_IMPORT_RECEIPT_V1"


class _Cursor:
    def __init__(self,rows): self.rows=rows
    def fetchall(self): return list(self.rows)
class _W7FakeConnection:
    def __init__(self,record_rows=None,source_rows=None,hook=None): self.record_rows=record_rows or []; self.source_rows=source_rows or []; self.hook=hook; self.calls=0
    def execute(self,sql):
        self.calls+=1
        if self.hook is not None and self.calls==1: self.hook()
        if "canonical_json from records" in sql:return _Cursor(self.record_rows)
        if "payload_json from records" in sql:return _Cursor(self.source_rows)
        raise AssertionError(sql)
class _W7FakeExportStore:
    def __init__(self,manifest,*,record_rows=None,source_rows=None,blobs=None,hook=None): self._manifest=manifest; self._connection=_W7FakeConnection(record_rows,source_rows,hook); self._blobs=blobs or {}
    def verify_manifest_consistency(self): return None
    def manifest(self): return self._manifest
    def _lookup_source_blob(self,digest): return self._blobs.get(digest)
def _w7_fake_export_store(*,hook=None,source_content:bytes|None=None,missing_source=False):
    manifest=_w7_project_manifest()
    if source_content is None:return _W7FakeExportStore(manifest,hook=hook)
    digest=sha256_hex(source_content); payload={"custody_mode":"CAPTURED","content_sha256":digest}; blobs={} if missing_source else {digest:source_content}
    return _W7FakeExportStore(manifest,source_rows=[{"payload_json":json.dumps(payload)}],blobs=blobs,hook=hook)


def test_w7_hv_031_export_existing_empty_destination_is_conflict(tmp_path:Path)->None:
    target=tmp_path/"export"; target.mkdir(); inode=target.stat().st_ino
    with pytest.raises(ConflictError): PortabilityMixin.export_bundle(_w7_fake_export_store(),target)
    assert target.stat().st_ino==inode


def test_w7_hv_032_export_existing_nonempty_destination_is_preserved(tmp_path:Path)->None:
    target=tmp_path/"export"; target.mkdir(); (target/"marker").write_text("keep")
    with pytest.raises(ConflictError): PortabilityMixin.export_bundle(_w7_fake_export_store(),target)
    assert (target/"marker").read_text()=="keep"


def test_w7_hv_033_export_preflight_missing_source_leaves_destination_absent(tmp_path:Path)->None:
    target=tmp_path/"export"
    with pytest.raises(ValidationError,match="missing"): PortabilityMixin.export_bundle(_w7_fake_export_store(source_content=b"retained",missing_source=True),target)
    assert not os.path.lexists(target)


def _run_export_competitor(tmp_path:Path,kind:str):
    target=tmp_path/"export"
    def hook():
        if os.path.lexists(target):
            if target.is_dir() and not target.is_symlink(): shutil.rmtree(target)
            else: target.unlink()
        if kind=="empty": target.mkdir()
        elif kind=="nonempty": target.mkdir(); (target/"marker").write_text("keep")
        elif kind=="file": target.write_text("keep")
        else:
            outside=tmp_path/"outside"; outside.mkdir(exist_ok=True); target.symlink_to(outside,target_is_directory=True)
    with pytest.raises(ConflictError): PortabilityMixin.export_bundle(_w7_fake_export_store(hook=hook),target)
    return target


def test_w7_hv_034_export_late_empty_directory_competitor_is_not_overwritten(tmp_path:Path)->None: assert _run_export_competitor(tmp_path,"empty").is_dir()
def test_w7_hv_035_export_late_nonempty_competitor_is_preserved(tmp_path:Path)->None: assert (_run_export_competitor(tmp_path,"nonempty")/"marker").read_text()=="keep"
def test_w7_hv_036_export_late_regular_file_competitor_is_preserved(tmp_path:Path)->None: assert _run_export_competitor(tmp_path,"file").read_text()=="keep"
def test_w7_hv_037_export_late_symlink_competitor_is_preserved(tmp_path:Path)->None: assert _run_export_competitor(tmp_path,"symlink").is_symlink()


def test_w7_hv_038_export_existing_symlink_destination_is_never_followed(tmp_path:Path)->None:
    outside=tmp_path/"outside"; outside.mkdir(); target=tmp_path/"export"; target.symlink_to(outside,target_is_directory=True)
    with pytest.raises(ConflictError): PortabilityMixin.export_bundle(_w7_fake_export_store(),target)
    assert list(outside.iterdir())==[]


def test_w7_hv_039_export_success_roundtrips_exact_staged_bundle(tmp_path:Path)->None:
    target=tmp_path/"export"; content=b"retained-source"; receipt=PortabilityMixin.export_bundle(_w7_fake_export_store(source_content=content),target)
    manifest,records,parsed,blobs=PortabilityMixin._read_bundle(target)
    assert receipt["manifest_sha256"]==sha256_hex((target/"manifest.json").read_bytes()) and records==b"" and parsed==[] and list(blobs.values())==[content]


def test_w7_hv_040_export_failure_cleanup_allows_immediate_retry(tmp_path:Path)->None:
    target=tmp_path/"export"
    with pytest.raises(ValidationError): PortabilityMixin.export_bundle(_w7_fake_export_store(source_content=b"retained",missing_source=True),target)
    assert not os.path.lexists(target); assert PortabilityMixin.export_bundle(_w7_fake_export_store(),target)["schema"]=="LANTERN_EXPORT_MANIFEST_V1"


def test_w7_hv_041_export_preflight_failure_allocates_no_staging(tmp_path:Path,monkeypatch)->None:
    import lantern._store_portability as pm
    target=tmp_path/"export"; seen=[]; original=pm._create_owned_stage
    def cap(*a,**k): r=original(*a,**k); seen.append(r[0]); return r
    monkeypatch.setattr(pm,"_create_owned_stage",cap)
    with pytest.raises(ValidationError): PortabilityMixin.export_bundle(_w7_fake_export_store(source_content=b"retained",missing_source=True),target)
    assert seen==[]


def test_w7_hv_042_export_unsupported_platform_fails_closed_without_destination(tmp_path:Path,monkeypatch)->None:
    import lantern._store_portability as pm
    monkeypatch.setattr(pm.sys,"platform","win32"); target=tmp_path/"export"
    with pytest.raises(ValidationError,match="unsupported"): PortabilityMixin.export_bundle(_w7_fake_export_store(),target)
    assert not target.exists()


def test_w7_hv_043_export_never_calls_os_replace(tmp_path:Path,monkeypatch)->None:
    monkeypatch.setattr(os,"replace",lambda *a,**k: (_ for _ in ()).throw(AssertionError("forbidden")))
    assert PortabilityMixin.export_bundle(_w7_fake_export_store(),tmp_path/"export")["schema"]=="LANTERN_EXPORT_MANIFEST_V1"


def test_w7_hv_044_nfs_profile_fails_closed_before_publication(tmp_path:Path,monkeypatch)->None:
    import lantern._store_portability as pm
    monkeypatch.setattr(pm,"_filesystem_type_for_path",lambda p:"nfs")
    with pytest.raises(ValidationError,match="filesystem"): PortabilityMixin.export_bundle(_w7_fake_export_store(),tmp_path/"export")


def test_w7_hv_045_unknown_filesystem_profile_fails_closed(tmp_path:Path,monkeypatch)->None:
    import lantern._store_portability as pm
    monkeypatch.setattr(pm,"_filesystem_type_for_path",lambda p:"mysteryfs")
    with pytest.raises(ValidationError,match="filesystem"): PortabilityMixin.export_bundle(_w7_fake_export_store(),tmp_path/"export")


@pytest.mark.parametrize("code,needle",[(errno.EXDEV,"cross filesystems"),(errno.EINVAL,"unsupported"),(errno.ENOSYS,"unsupported"),(errno.EIO,"ambiguous")])
def test_w7_hv_046_to_049_errno_classes_fail_closed(tmp_path:Path,monkeypatch,code:int,needle:str)->None:
    import lantern._store_portability as pm
    monkeypatch.setattr(pm,"_renameat2_noreplace",lambda *a,**k: (_ for _ in ()).throw(OSError(code,os.strerror(code))))
    with pytest.raises(ValidationError,match=needle): PortabilityMixin.export_bundle(_w7_fake_export_store(),tmp_path/"export")


def test_w7_hv_050_twenty_five_concurrent_publish_races_have_one_winner(tmp_path:Path)->None:
    for i in range(25):
        target=tmp_path/f"race-{i}"; barrier=threading.Barrier(2); results=[]; errors=[]
        def worker():
            store=_w7_fake_export_store()
            old=store._connection.hook
            store._connection.hook=lambda: barrier.wait(timeout=5)
            try: results.append(PortabilityMixin.export_bundle(store,target))
            except Exception as exc: errors.append(exc)
        threads=[threading.Thread(target=worker) for _ in range(2)]
        [t.start() for t in threads]; [t.join() for t in threads]
        assert len(results)==1 and len(errors)==1 and isinstance(errors[0],ConflictError) and target.is_dir()


def test_w7_hv_051_export_success_leaves_no_owned_staging_sibling(tmp_path:Path)->None:
    target=tmp_path/"export"; PortabilityMixin.export_bundle(_w7_fake_export_store(),target)
    assert [p for p in tmp_path.iterdir() if p.name.startswith(".export.lantern-export-")]==[]


def test_w7_hv_052_import_replaced_stage_cleanup_preserves_replacement(tmp_path:Path)->None:
    bundle=_write_w7_empty_bundle(tmp_path/"bundle"); target=tmp_path/"target"; replacement=[]
    def hook(stage): shutil.rmtree(stage); stage.mkdir(); (stage/"attacker").write_text("keep"); replacement.append(stage)
    with pytest.raises(ValidationError): _w7_fake_import_class([],exit_hook=hook).import_bundle_new(target,bundle)
    assert replacement and (replacement[0]/"attacker").read_text()=="keep"


def test_w7_hv_053_export_aggregate_source_bound_fails_before_staging(tmp_path:Path)->None:
    class Big(_W7FakeExportStore):
        def _lookup_source_blob(self,digest): return b"x"*((64<<20)+1)
    d="a"*64; store=Big(_w7_project_manifest(),source_rows=[{"payload_json":json.dumps({"custody_mode":"CAPTURED","content_sha256":d})}])
    with pytest.raises(ValidationError,match="maximum size"): PortabilityMixin.export_bundle(store,tmp_path/"export")


def test_w7_hv_054_export_invalid_source_digest_rejected_before_staging(tmp_path:Path)->None:
    store=_W7FakeExportStore(_w7_project_manifest(),source_rows=[{"payload_json":json.dumps({"custody_mode":"CAPTURED","content_sha256":"A"*64})}])
    with pytest.raises(ValidationError,match="digest"): PortabilityMixin.export_bundle(store,tmp_path/"export")


def test_w7_hv_055_successful_empty_export_is_reimportable(tmp_path:Path)->None:
    target=tmp_path/"export"; PortabilityMixin.export_bundle(_w7_fake_export_store(),target)
    manifest,records,parsed,blobs=PortabilityMixin._read_bundle(target)
    assert manifest["record_count"]==0 and records==b"" and parsed==[] and blobs=={}
