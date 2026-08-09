from __future__ import annotations

import ctypes
import errno
import json
import os
import re
import secrets
import shutil
import stat
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .canonical import canonical_json_bytes, normalize_relative_posix_path, sha256_hex, strict_json_loads
from .contracts import RecordEnvelope, parse_record
from .validation import manifest_bytes, validate_project_manifest, validate_record_semantics
from ._store_files import stage_source_blobs
from ._store_helpers import _counts, _dependency_closure, _topological_records
from ._store_types import ConflictError, ValidationError

_EXPORT_KEYS = {"schema", "project_manifest", "record_count", "records_path", "records_sha256", "sources"}
_SOURCE_ENTRY_KEYS = {"sha256", "size"}


_MANIFEST_MAX_BYTES = 1 << 20
_RECORDS_MAX_BYTES = 64 << 20
_SOURCE_MAX_BYTES = 64 << 20
_SOURCES_AGGREGATE_MAX_BYTES = 512 << 20
_READ_CHUNK_BYTES = 1 << 20
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_QUALIFIED_LOCAL_FILESYSTEMS = {"ext4"}


def _safe_open_flags(*, directory: bool = False) -> int:
    if not hasattr(os, "O_NOFOLLOW"):
        raise ValidationError("Safe no-follow file access is unsupported on this platform")
    flags = os.O_RDONLY | os.O_NOFOLLOW
    if directory:
        if not hasattr(os, "O_DIRECTORY"):
            raise ValidationError("Safe directory access is unsupported on this platform")
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    return flags


def _open_directory_fd(path: str | Path, *, label: str, dir_fd: int | None = None) -> int:
    try:
        fd = os.open(path, _safe_open_flags(directory=True), dir_fd=dir_fd)
    except OSError as exc:
        raise ValidationError(f"Unsafe or unavailable {label}") from exc
    info = os.fstat(fd)
    if not stat.S_ISDIR(info.st_mode):
        os.close(fd)
        raise ValidationError(f"{label} must be a directory")
    return fd


def _open_regular_fd(parent_fd: int, name: str, *, label: str) -> int:
    try:
        fd = os.open(name, _safe_open_flags(), dir_fd=parent_fd)
    except OSError as exc:
        raise ValidationError(f"Unsafe or unavailable {label}") from exc
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):
        os.close(fd)
        raise ValidationError(f"{label} must be a regular file")
    return fd


def _read_bounded_fd(fd: int, limit: int, *, label: str) -> bytes:
    if os.fstat(fd).st_size > limit:
        raise ValidationError(f"{label} exceeds maximum size of {limit} bytes")
    chunks: list[bytes] = []
    total = 0
    while True:
        remaining = limit + 1 - total
        if remaining <= 0:
            raise ValidationError(f"{label} exceeds maximum size of {limit} bytes")
        chunk = os.read(fd, min(_READ_CHUNK_BYTES, remaining))
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise ValidationError(f"{label} exceeds maximum size of {limit} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _read_child(parent_fd: int, name: str, limit: int, *, label: str) -> bytes:
    fd = _open_regular_fd(parent_fd, name, label=label)
    try:
        return _read_bounded_fd(fd, limit, label=label)
    finally:
        os.close(fd)


def _identity_from_stat(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def _verify_owned_stage(path: Path, stage_fd: int, expected: tuple[int, int]) -> None:
    held = os.fstat(stage_fd)
    if not stat.S_ISDIR(held.st_mode) or _identity_from_stat(held) != expected:
        raise ValidationError("Held staging directory identity changed")
    try:
        current = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise ValidationError("Owned staging directory is missing") from exc
    if path.is_symlink() or not stat.S_ISDIR(current.st_mode) or _identity_from_stat(current) != expected:
        raise ValidationError("Owned staging directory identity changed")


def _create_owned_stage(target: Path, *, purpose: str) -> tuple[Path, int, tuple[int, int]]:
    parent = target.parent
    parent_fd = _open_directory_fd(parent, label="publication parent directory")
    try:
        for _ in range(32):
            name = f".{target.name}.lantern-{purpose}-{secrets.token_hex(16)}"
            try:
                os.mkdir(name, mode=0o700, dir_fd=parent_fd)
            except FileExistsError:
                continue
            stage_fd = _open_directory_fd(name, label="owned staging directory", dir_fd=parent_fd)
            return parent / name, stage_fd, _identity_from_stat(os.fstat(stage_fd))
    finally:
        os.close(parent_fd)
    raise ValidationError("Unable to allocate exclusive owned staging directory")


def _cleanup_owned_stage(stage: Path, stage_fd: int, expected: tuple[int, int]) -> None:
    if not os.path.lexists(stage):
        return
    _verify_owned_stage(stage, stage_fd, expected)
    shutil.rmtree(stage)


def _filesystem_type_for_path(path: Path) -> str:
    info = path.stat()
    device = f"{os.major(info.st_dev)}:{os.minor(info.st_dev)}"
    resolved = str(path.resolve())
    best: tuple[int, str] | None = None
    try:
        lines = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValidationError("Unable to qualify publication filesystem") from exc
    for line in lines:
        parts = line.split()
        if len(parts) < 10 or parts[2] != device or "-" not in parts:
            continue
        sep = parts.index("-")
        mount_point = parts[4].replace("\\040", " ")
        if resolved == mount_point or resolved.startswith(mount_point.rstrip("/") + "/") or mount_point == "/":
            candidate = (len(mount_point), parts[sep + 1])
            if best is None or candidate[0] > best[0]:
                best = candidate
    if best is None:
        raise ValidationError("Publication filesystem profile is unknown")
    return best[1]


def _renameat2_noreplace(parent_fd: int, source_name: str, target_name: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise OSError(errno.ENOSYS, os.strerror(errno.ENOSYS))
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(parent_fd, os.fsencode(source_name), parent_fd, os.fsencode(target_name), 1) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))


def _publish_directory_noreplace(stage: Path, target: Path, stage_fd: int, expected: tuple[int, int]) -> None:
    if sys.platform != "linux":
        raise ValidationError("Atomic no-replace directory publication is unsupported on this platform")
    if stage.parent != target.parent:
        raise ValidationError("Staging and destination must share one parent directory")
    filesystem = _filesystem_type_for_path(stage.parent)
    if filesystem not in _QUALIFIED_LOCAL_FILESYSTEMS:
        raise ValidationError(f"Publication filesystem profile is unsupported: {filesystem}")
    _verify_owned_stage(stage, stage_fd, expected)
    parent_fd = _open_directory_fd(target.parent, label="publication parent directory")
    try:
        try:
            _renameat2_noreplace(parent_fd, stage.name, target.name)
        except OSError as exc:
            if exc.errno in {errno.EEXIST, errno.ENOTEMPTY}:
                raise ConflictError("Publication destination exists") from exc
            if exc.errno == errno.EXDEV:
                raise ValidationError("Atomic no-replace directory publication cannot cross filesystems") from exc
            if exc.errno in {errno.EINVAL, errno.ENOSYS, getattr(errno, "EOPNOTSUPP", 95)}:
                raise ValidationError("Atomic no-replace directory publication primitive is unsupported") from exc
            raise ValidationError(f"Atomic no-replace directory publication ambiguous failure errno {exc.errno}") from exc
        held = os.fstat(stage_fd)
        target_info = os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
        if (not stat.S_ISDIR(target_info.st_mode)
                or _identity_from_stat(held) != expected
                or _identity_from_stat(target_info) != expected):
            raise ValidationError("Published destination identity does not match verified staging")
    finally:
        os.close(parent_fd)


def _write_child_exclusive(parent_fd: int, name: str, content: bytes, *, label: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(name, flags, 0o600, dir_fd=parent_fd)
    except OSError as exc:
        raise ValidationError(f"Unable to create exclusive staged {label}") from exc
    try:
        view = memoryview(content)
        offset = 0
        while offset < len(view):
            count = os.write(fd, view[offset:])
            if count <= 0:
                raise ValidationError(f"Short write for staged {label}")
            offset += count
        os.fsync(fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size != len(content):
            raise ValidationError(f"Staged {label} identity or size mismatch")
    finally:
        os.close(fd)


def _verify_staged_export(stage_fd: int, manifest_payload: bytes, records_bytes: bytes,
                          source_blobs: dict[str, bytes]) -> None:
    if _read_child(stage_fd, "manifest.json", _MANIFEST_MAX_BYTES, label="staged manifest.json") != manifest_payload:
        raise ValidationError("Staged manifest.json bytes changed before publication")
    if _read_child(stage_fd, "records.ndjson", _RECORDS_MAX_BYTES, label="staged records.ndjson") != records_bytes:
        raise ValidationError("Staged records.ndjson bytes changed before publication")
    sources_fd = _open_directory_fd("sources", label="staged sources directory", dir_fd=stage_fd)
    try:
        if sorted(os.listdir(sources_fd)) != sorted(source_blobs):
            raise ValidationError("Staged source entry set changed before publication")
        for digest, expected in sorted(source_blobs.items()):
            actual = _read_child(sources_fd, digest, _SOURCE_MAX_BYTES, label=f"staged source blob {digest}")
            if actual != expected or sha256_hex(actual) != digest:
                raise ValidationError(f"Staged source blob changed before publication: {digest}")
    finally:
        os.close(sources_fd)


class PortabilityMixin:
    def export_bundle(self, destination: str | Path) -> dict[str, Any]:
        self.verify_manifest_consistency()
        target = Path(destination)
        if os.path.lexists(target):
            raise ConflictError("Export destination must be absent")
        rows = self._connection.execute("select canonical_json from records order by record_id").fetchall()
        records_bytes = b"".join(row["canonical_json"].encode("utf-8") + b"\n" for row in rows)
        if len(records_bytes) > _RECORDS_MAX_BYTES:
            raise ValidationError("Export records.ndjson exceeds maximum size")

        referenced: set[str] = set()
        source_rows = self._connection.execute(
            "select payload_json from records where record_type='SourceSnapshot' order by record_id"
        ).fetchall()
        for row in source_rows:
            payload = json.loads(row["payload_json"])
            if payload.get("custody_mode") in {"CAPTURED", "EMBEDDED"}:
                digest = payload.get("content_sha256")
                if not isinstance(digest, str) or _HEX64.fullmatch(digest) is None:
                    raise ValidationError("Referenced source digest must be lowercase SHA-256")
                referenced.add(digest)
        source_blobs: dict[str, bytes] = {}
        exported_sources: list[dict[str, Any]] = []
        aggregate = 0
        for digest in sorted(referenced):
            content = self._lookup_source_blob(digest)
            if content is None:
                raise ValidationError(f"Referenced source blob is missing: {digest}")
            if not isinstance(content, bytes):
                raise ValidationError(f"Referenced source blob must be bytes: {digest}")
            if len(content) > _SOURCE_MAX_BYTES:
                raise ValidationError(f"Referenced source blob exceeds maximum size: {digest}")
            if sha256_hex(content) != digest:
                raise ValidationError(f"Referenced source blob digest mismatch: {digest}")
            aggregate += len(content)
            if aggregate > _SOURCES_AGGREGATE_MAX_BYTES:
                raise ValidationError("Aggregate retained source bytes exceed maximum size")
            source_blobs[digest] = content
            exported_sources.append({"sha256": digest, "size": len(content)})
        manifest = {
            "schema": "LANTERN_EXPORT_MANIFEST_V1",
            "project_manifest": self.manifest(),
            "record_count": len(rows),
            "records_path": normalize_relative_posix_path("records.ndjson"),
            "records_sha256": sha256_hex(records_bytes),
            "sources": exported_sources,
        }
        manifest_payload = canonical_json_bytes(manifest) + b"\n"
        if len(manifest_payload) > _MANIFEST_MAX_BYTES:
            raise ValidationError("Export manifest exceeds maximum size")

        stage, stage_fd, stage_identity = _create_owned_stage(target, purpose="export")
        try:
            try:
                _write_child_exclusive(stage_fd, "records.ndjson", records_bytes, label="records.ndjson")
                os.mkdir("sources", mode=0o700, dir_fd=stage_fd)
                sources_fd = _open_directory_fd("sources", label="staged sources directory", dir_fd=stage_fd)
                try:
                    for digest, content in sorted(source_blobs.items()):
                        _write_child_exclusive(sources_fd, digest, content, label=f"source blob {digest}")
                finally:
                    os.close(sources_fd)
                _write_child_exclusive(stage_fd, "manifest.json", manifest_payload, label="manifest.json")
                _verify_owned_stage(stage, stage_fd, stage_identity)
                _verify_staged_export(stage_fd, manifest_payload, records_bytes, source_blobs)
                _publish_directory_noreplace(stage, target, stage_fd, stage_identity)
                return {**manifest, "manifest_sha256": sha256_hex(manifest_payload)}
            except Exception as exc:
                try:
                    _cleanup_owned_stage(stage, stage_fd, stage_identity)
                except ValidationError as cleanup_exc:
                    raise cleanup_exc from exc
                raise
        finally:
            os.close(stage_fd)

    @staticmethod
    def _read_bundle(bundle: Path) -> tuple[dict[str, Any], bytes, list[RecordEnvelope], dict[str, bytes]]:
        bundle_fd = _open_directory_fd(bundle, label="import bundle root")
        try:
            raw_manifest = _read_child(bundle_fd, "manifest.json", _MANIFEST_MAX_BYTES, label="manifest.json")
            try:
                manifest = strict_json_loads(raw_manifest)
            except Exception as exc:
                raise ValidationError("Invalid manifest.json") from exc
            if not isinstance(manifest, dict):
                raise ValidationError("Export manifest must be an object")
            if canonical_json_bytes(manifest) + b"\n" != raw_manifest:
                raise ValidationError("Export manifest must use exact canonical JSON plus one newline")
            if set(manifest) != _EXPORT_KEYS:
                raise ValidationError("Export manifest keys are incomplete or unknown")
            if manifest.get("schema") != "LANTERN_EXPORT_MANIFEST_V1":
                raise ValidationError("Unsupported export manifest")
            validate_project_manifest(manifest.get("project_manifest"))
            if manifest.get("records_path") != "records.ndjson":
                raise ValidationError("Unsupported records_path")
            records_bytes = _read_child(bundle_fd, "records.ndjson", _RECORDS_MAX_BYTES, label="records.ndjson")
            if sha256_hex(records_bytes) != manifest.get("records_sha256"):
                raise ValidationError("records.ndjson digest mismatch")
            parsed = [parse_record(line) for line in records_bytes.decode("utf-8").splitlines() if line]
            if manifest.get("record_count") != len(parsed):
                raise ValidationError("Export manifest record_count mismatch")
            duplicate_ids = [rid for rid, count in _counts(r.record_id for r in parsed).items() if count > 1]
            if duplicate_ids:
                raise ValidationError(f"Duplicate record IDs in import bundle: {duplicate_ids}")

            sources_value = manifest.get("sources")
            if not isinstance(sources_value, list):
                raise ValidationError("Export manifest sources must be a list")
            declared: list[tuple[str, int]] = []
            previous_digest = ""
            aggregate = 0
            for item in sources_value:
                if not isinstance(item, dict) or set(item) != _SOURCE_ENTRY_KEYS:
                    raise ValidationError("Invalid source manifest entry")
                digest = item.get("sha256"); size = item.get("size")
                if (not isinstance(digest, str) or _HEX64.fullmatch(digest) is None
                        or not isinstance(size, int) or isinstance(size, bool) or size < 0):
                    raise ValidationError("Invalid source manifest digest or size")
                if digest <= previous_digest:
                    raise ValidationError("Source manifest entries must be unique and sorted")
                previous_digest = digest
                if size > _SOURCE_MAX_BYTES:
                    raise ValidationError(f"Source blob exceeds maximum size: {digest}")
                aggregate += size
                if aggregate > _SOURCES_AGGREGATE_MAX_BYTES:
                    raise ValidationError("Aggregate retained source bytes exceed maximum size")
                declared.append((digest, size))

            sources_fd = _open_directory_fd("sources", label="sources directory", dir_fd=bundle_fd)
            try:
                physical = sorted(os.listdir(sources_fd))
                names = [digest for digest, _ in declared]
                if physical != names:
                    missing = sorted(set(names) - set(physical)); undeclared = sorted(set(physical) - set(names))
                    raise ValidationError(f"Physical source entries do not match manifest; missing={missing}, undeclared={undeclared}")
                source_blobs: dict[str, bytes] = {}
                actual_aggregate = 0
                for digest, size in declared:
                    content = _read_child(sources_fd, digest, _SOURCE_MAX_BYTES, label=f"source blob {digest}")
                    actual_aggregate += len(content)
                    if actual_aggregate > _SOURCES_AGGREGATE_MAX_BYTES:
                        raise ValidationError("Aggregate retained source bytes exceed maximum size")
                    if len(content) != size or sha256_hex(content) != digest:
                        raise ValidationError(f"Divergent source blob: {digest}")
                    source_blobs[digest] = content
            finally:
                os.close(sources_fd)
            return manifest, records_bytes, parsed, source_blobs
        finally:
            os.close(bundle_fd)

    def _preflight_import(self, source: str | Path) -> dict[str, Any]:
        bundle = Path(source)
        manifest, records_bytes, parsed, source_blobs = self._read_bundle(bundle)
        project_manifest = manifest["project_manifest"]
        if project_manifest != self.manifest():
            raise ConflictError("Bundle ProjectManifest is incompatible with target store")
        if any(record.project_id != self.project_id for record in parsed):
            raise ValidationError("Import project_id does not match target store")

        by_id = {record.record_id: record for record in parsed}
        existing_cache: dict[str, RecordEnvelope | None] = {}

        def lookup(record_id: str) -> RecordEnvelope | None:
            if record_id in by_id:
                return by_id[record_id]
            if record_id not in existing_cache:
                existing_cache[record_id] = self._lookup_record(record_id)
            return existing_cache[record_id]

        for record in _topological_records(parsed):
            content = None
            if record.record_type == "SourceSnapshot":
                digest = record.payload.get("content_sha256")
                if isinstance(digest, str):
                    content = source_blobs.get(digest)
            validate_record_semantics(record, lookup, source_content=content)

        referenced = {
            record.payload["content_sha256"]
            for record in parsed
            if record.record_type == "SourceSnapshot"
            and record.payload.get("custody_mode") in {"CAPTURED", "EMBEDDED"}
        }
        if referenced != set(source_blobs):
            missing = sorted(referenced - set(source_blobs))
            undeclared = sorted(set(source_blobs) - referenced)
            raise ValidationError(f"Source manifest/reference mismatch; missing={missing}, undeclared={undeclared}")

        outcomes: dict[str, str] = {}
        conflicts: set[str] = set()
        for record in parsed:
            existing = self._connection.execute(
                "select canonical_json from records where record_id=?", (record.record_id,)
            ).fetchone()
            if existing is None:
                continue
            if existing["canonical_json"] == record.canonical_json:
                outcomes[record.record_id] = "VERIFIED"
            else:
                outcomes[record.record_id] = "CONFLICT"
                conflicts.add(record.record_id)
        skipped = _dependency_closure(by_id, conflicts)
        for record_id in skipped:
            outcomes.setdefault(record_id, "SKIPPED")
        to_create = [record for record in _topological_records(parsed) if record.record_id not in outcomes]

        heads = {
            (row["project_id"], row["record_type"], row["lineage_key"]): row["record_id"]
            for row in self._connection.execute("select * from lineage_heads").fetchall()
        }
        for record in to_create:
            if record.record_type == "StateEvent" or record.lineage_key is None:
                continue
            key = (record.project_id, record.record_type, record.lineage_key)
            current = heads.get(key)
            if record.predecessor_record_id is None:
                if current is not None:
                    raise ConflictError("A current lineage head already exists")
            elif current != record.predecessor_record_id:
                raise ConflictError("Stale predecessor or competing successor")
            heads[key] = record.record_id

        effective_ids = {record_id for record_id, outcome in outcomes.items() if outcome == "VERIFIED"}
        effective_ids.update(record.record_id for record in to_create)
        effective_digests = {
            record.payload["content_sha256"]
            for record in parsed
            if record.record_id in effective_ids
            and record.record_type == "SourceSnapshot"
            and record.payload.get("custody_mode") in {"CAPTURED", "EMBEDDED"}
        }
        effective_source_blobs = {digest: source_blobs[digest] for digest in sorted(effective_digests)}

        return {
            "bundle": bundle,
            "manifest": manifest,
            "records_bytes": records_bytes,
            "parsed": parsed,
            "source_blobs": source_blobs,
            "effective_source_blobs": effective_source_blobs,
            "outcomes": outcomes,
            "to_create": to_create,
            "operation_id": f"import:{sha256_hex(canonical_json_bytes(manifest))}:{manifest['records_sha256']}",
        }

    def import_bundle(self, source: str | Path) -> dict[str, Any]:
        plan = self._preflight_import(source)
        file_op = stage_source_blobs(self.root, plan["operation_id"], plan["effective_source_blobs"])
        outcomes: dict[str, str] = dict(plan["outcomes"])
        try:
            with self.transaction():
                for record in plan["to_create"]:
                    self._insert_record_row(record)
                    outcomes[record.record_id] = "CREATED"
                file_op.promote()
                self._rebuild_projections()
                hook = getattr(self, "_import_failure_hook", None)
                if hook is not None:
                    hook()
                self._connection.execute(
                    "insert or ignore into file_operations(operation_id,status,committed_at) values (?,?,?)",
                    (plan["operation_id"], "COMMITTED", datetime.now(UTC).isoformat().replace("+00:00", "Z")),
                )
        except Exception:
            file_op.rollback_files()
            raise
        file_op.cleanup_after_success()
        ordered_results = [{"record_id": record.record_id, "outcome": outcomes[record.record_id]}
                           for record in plan["parsed"]]
        summary: dict[str, int] = defaultdict(int)
        for result in ordered_results:
            summary[result["outcome"]] += 1
        return {"schema": "LANTERN_IMPORT_RECEIPT_V1", "project_id": self.project_id,
                "project_manifest_sha256": sha256_hex(manifest_bytes(self.manifest())),
                "results": ordered_results, "summary": dict(sorted(summary.items()))}

    @classmethod
    def import_bundle_new(cls, target_root: str | Path, source: str | Path, *, actor_id: str = "importer") -> dict[str, Any]:
        target = Path(target_root)
        if os.path.lexists(target):
            raise ConflictError("Clean import target must not already exist")
        bundle = Path(source)
        manifest, _, _, _ = cls._read_bundle(bundle)
        project_manifest = manifest["project_manifest"]
        stage, stage_fd, stage_identity = _create_owned_stage(target, purpose="import")
        try:
            try:
                with cls.initialize(stage, manifest=project_manifest, actor_id=actor_id) as store:
                    receipt = store.import_bundle(bundle)
                    store.verify_manifest_consistency()
                _verify_owned_stage(stage, stage_fd, stage_identity)
                _publish_directory_noreplace(stage, target, stage_fd, stage_identity)
                return receipt
            except Exception as exc:
                try:
                    _cleanup_owned_stage(stage, stage_fd, stage_identity)
                except ValidationError as cleanup_exc:
                    raise cleanup_exc from exc
                raise
        finally:
            os.close(stage_fd)

    def _rebuild_projections(self) -> None:
        rows = self._connection.execute("select * from records order by created_at,record_id").fetchall()
        records = [self._row_to_record(row) for row in rows]
        by_id = {record.record_id: record for record in records}
        lookup = by_id.get
        for record in _topological_records(records):
            validate_record_semantics(record, lookup, source_blob_lookup=self._lookup_source_blob)

        self._connection.execute("delete from lineage_heads")
        self._connection.execute("delete from links")
        self._connection.execute("delete from state_heads")
        self._connection.execute("delete from state_events")
        lineage_groups: dict[tuple[str, str, str], list[RecordEnvelope]] = defaultdict(list)
        for record in records:
            if record.record_type != "StateEvent" and record.lineage_key is not None:
                lineage_groups[(record.project_id, record.record_type, record.lineage_key)].append(record)
        for key, group in lineage_groups.items():
            roots = [record for record in group if record.predecessor_record_id is None]
            if len(roots) != 1:
                raise ValidationError(f"Lineage {key} must have exactly one root")
            children: dict[str, list[RecordEnvelope]] = defaultdict(list)
            for record in group:
                if record.predecessor_record_id is not None:
                    children[record.predecessor_record_id].append(record)
            if any(len(values) > 1 for values in children.values()):
                raise ValidationError(f"Competing successors in lineage {key}")
            current = roots[0]
            visited = {current.record_id}
            while children.get(current.record_id):
                current = children[current.record_id][0]
                if current.record_id in visited:
                    raise ValidationError(f"Cycle in lineage {key}")
                visited.add(current.record_id)
            if len(visited) != len(group):
                raise ValidationError(f"Disconnected lineage {key}")
            self._connection.execute(
                "insert into lineage_heads(project_id,record_type,lineage_key,record_id) values (?,?,?,?)",
                (*key, current.record_id),
            )
        for record in records:
            if record.record_type == "Link":
                self._project_link(record)
        state_records = [record for record in records if record.record_type == "StateEvent"]
        pending = {record.record_id: record for record in state_records}
        while pending:
            progressed = False
            for record_id, record in list(pending.items()):
                if record.predecessor_record_id is None or record.predecessor_record_id not in pending:
                    self._project_state_event(record)
                    del pending[record_id]
                    progressed = True
            if not progressed:
                raise ValidationError("StateEvent stream contains a cycle or missing predecessor")
