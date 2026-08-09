from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

from .canonical import canonical_json, sha256_hex
from .contracts import RecordEnvelope
from .ids import require_uuid7, uuid7
from .validation import manifest_bytes, validate_project_manifest, validate_record_semantics
from ._store_files import recover_file_operations
from ._store_helpers import Transaction
from ._store_types import ConflictError, LanternError, OperationResult, ValidationError

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class StoreBase:
    DB_NAME = "lantern.sqlite3"
    MANIFEST_NAME = "project-manifest.json"

    def __init__(self, root: Path, connection: sqlite3.Connection) -> None:
        self.root = root
        self.db_path = root / self.DB_NAME
        self.sources_path = root / "sources"
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA synchronous = FULL")

    @classmethod
    def initialize(
        cls, root: str | Path, *, project_id: str | None = None, actor_id: str = "operator",
        project_name: str = "Lantern Project", manifest: dict[str, Any] | None = None,
    ) -> Self:
        path = Path(root)
        path.mkdir(parents=True, exist_ok=True)
        db_path = path / cls.DB_NAME
        if db_path.exists():
            raise ConflictError(f"Lantern store already exists: {db_path}")
        connection = sqlite3.connect(db_path, isolation_level=None)
        store = cls(path, connection)
        try:
            store._create_schema()
            if manifest is None:
                assigned_project_id = require_uuid7(project_id) if project_id else uuid7()
                created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
                manifest = {
                    "schema": "LANTERN_PROJECT_MANIFEST_V1",
                    "project_id": assigned_project_id,
                    "project_name": project_name,
                    "schema_version": "1.0",
                    "interchange_version": "1.0",
                    "created_at": created_at,
                    "created_by": actor_id,
                    "custody_policy": "LOCAL_FIRST",
                    "export_policy": "EXPLICIT_ONLY",
                    "path_rules": "PROJECT_ROOT_RELATIVE_POSIX",
                }
            else:
                manifest = validate_project_manifest(manifest)
                if project_id is not None and require_uuid7(project_id) != manifest["project_id"]:
                    raise ValidationError("Explicit project_id conflicts with imported ProjectManifest")
            with store.transaction():
                for key, value in manifest.items():
                    store._connection.execute(
                        "insert into project_manifest(key, value_json) values (?, ?)",
                        (key, canonical_json(value)),
                    )
            store.sources_path.mkdir(exist_ok=True)
            (path / cls.MANIFEST_NAME).write_bytes(manifest_bytes(manifest))
            return store
        except Exception:
            connection.close()
            raise

    @classmethod
    def open(cls, root: str | Path) -> Self:
        path = Path(root)
        db_path = path / cls.DB_NAME
        if not db_path.exists():
            raise LanternError(f"No Lantern store exists at {db_path}")
        connection = sqlite3.connect(db_path, isolation_level=None)
        store = cls(path, connection)
        try:
            recover_file_operations(path, connection)
            store.verify_manifest_consistency()
            return store
        except Exception:
            connection.close()
            raise

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def transaction(self):
        return Transaction(self._connection)

    @property
    def project_id(self) -> str:
        row = self._connection.execute("select value_json from project_manifest where key='project_id'").fetchone()
        if row is None:
            raise LanternError("Project manifest is missing project_id")
        return require_uuid7(json.loads(row["value_json"]))

    def manifest(self) -> dict[str, Any]:
        rows = self._connection.execute("select key, value_json from project_manifest order by key").fetchall()
        return validate_project_manifest({row["key"]: json.loads(row["value_json"]) for row in rows})

    def verify_manifest_consistency(self) -> None:
        expected = manifest_bytes(self.manifest())
        path = self.root / self.MANIFEST_NAME
        if not path.exists() or path.read_bytes() != expected:
            raise ValidationError("SQLite ProjectManifest and project-manifest.json are not byte-equivalent")

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            begin immediate;
            create table project_manifest (key text primary key, value_json text not null);
            create table records (
                record_id text primary key, project_id text not null, record_type text not null,
                schema_version text not null, actor_id text not null, created_at text not null,
                observed_at text, provenance_json text not null, lineage_key text,
                predecessor_record_id text references records(record_id) deferrable initially deferred,
                payload_json text not null, record_sha256 text not null, canonical_json text not null,
                inserted_at text not null
            );
            create unique index records_hash_idx on records(record_sha256);
            create index records_type_idx on records(record_type, created_at, record_id);
            create index records_lineage_idx on records(project_id, record_type, lineage_key);
            create table lineage_heads (
                project_id text not null, record_type text not null, lineage_key text not null,
                record_id text not null references records(record_id),
                primary key(project_id, record_type, lineage_key)
            );
            create table links (
                record_id text primary key references records(record_id), link_type text not null,
                source_record_id text not null references records(record_id),
                target_record_id text not null references records(record_id),
                unique(link_type, source_record_id, target_record_id)
            );
            create index links_target_idx on links(link_type, target_record_id);
            create table state_events (
                record_id text primary key references records(record_id),
                subject_record_id text not null references records(record_id), event_type text not null,
                predecessor_event_id text references state_events(record_id), event_key text not null unique,
                details_json text not null
            );
            create table state_heads (
                subject_record_id text primary key references records(record_id),
                event_record_id text not null references state_events(record_id)
            );
            create table file_operations (
                operation_id text primary key, status text not null check(status='COMMITTED'),
                committed_at text not null
            );
            create view derived_supersedes as
            select record_id as successor_record_id, predecessor_record_id from records
            where predecessor_record_id is not null and record_type <> 'StateEvent';
            commit;
            """
        )

    def _row_to_record(self, row: sqlite3.Row) -> RecordEnvelope:
        return RecordEnvelope(
            project_id=row["project_id"], record_id=row["record_id"], record_type=row["record_type"],
            schema_version=row["schema_version"], actor_id=row["actor_id"], created_at=row["created_at"],
            observed_at=row["observed_at"], provenance_json=row["provenance_json"],
            lineage_key=row["lineage_key"], predecessor_record_id=row["predecessor_record_id"],
            payload_json=row["payload_json"], record_sha256=row["record_sha256"],
            canonical_json=row["canonical_json"],
        )

    def _lookup_record(self, record_id: str) -> RecordEnvelope | None:
        row = self._connection.execute("select * from records where record_id=?", (record_id,)).fetchone()
        return self._row_to_record(row) if row is not None else None

    def _lookup_source_blob(self, digest: str) -> bytes | None:
        if not isinstance(digest, str) or not _HEX64.fullmatch(digest):
            raise ValidationError("Source blob lookup requires a lowercase SHA-256 digest")
        if self.sources_path.is_symlink():
            raise ValidationError("Lantern sources directory cannot be a symlink")
        source_root = self.sources_path.resolve(strict=True)
        target = self.sources_path / digest
        if target.is_symlink():
            raise ValidationError(f"Retained source blob cannot be a symlink: {digest}")
        if not target.exists():
            return None
        if not target.is_file() or target.resolve(strict=True).parent != source_root:
            raise ValidationError(f"Retained source blob escapes sources directory: {digest}")
        content = target.read_bytes()
        if sha256_hex(content) != digest:
            raise ValidationError(f"Retained source blob digest mismatch: {digest}")
        return content

    def get_record(self, record_id: str) -> RecordEnvelope:
        record = self._lookup_record(record_id)
        if record is None:
            raise LanternError(f"Unknown record: {record_id}")
        return record

    def _existing_outcome(self, record: RecordEnvelope) -> OperationResult | None:
        row = self._connection.execute("select canonical_json from records where record_id=?", (record.record_id,)).fetchone()
        if row is None:
            return None
        if row["canonical_json"] == record.canonical_json:
            return OperationResult("VERIFIED", record.record_id)
        return OperationResult("CONFLICT", record.record_id, {"reason": "same record_id has divergent canonical bytes"})

    def _insert_record_row(self, record: RecordEnvelope) -> None:
        if record.project_id != self.project_id:
            raise ValidationError("Record project_id does not match target store")
        self._connection.execute(
            """insert into records(record_id,project_id,record_type,schema_version,actor_id,created_at,
            observed_at,provenance_json,lineage_key,predecessor_record_id,payload_json,record_sha256,
            canonical_json,inserted_at) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (record.record_id, record.project_id, record.record_type, record.schema_version, record.actor_id,
             record.created_at, record.observed_at, record.provenance_json, record.lineage_key,
             record.predecessor_record_id, record.payload_json, record.record_sha256, record.canonical_json,
             datetime.now(UTC).isoformat().replace("+00:00", "Z")),
        )

    def _validate_successor(self, record: RecordEnvelope) -> None:
        if record.record_type == "StateEvent":
            return
        if record.lineage_key is None:
            if record.predecessor_record_id is not None:
                raise ValidationError("A successor record must have a lineage_key")
            return
        current = self._connection.execute(
            "select record_id from lineage_heads where project_id=? and record_type=? and lineage_key=?",
            (record.project_id, record.record_type, record.lineage_key),
        ).fetchone()
        if record.predecessor_record_id is None:
            if current is not None:
                raise ConflictError("A current lineage head already exists")
            return
        predecessor = self._connection.execute(
            "select record_type,lineage_key from records where record_id=?", (record.predecessor_record_id,)
        ).fetchone()
        if predecessor is None:
            raise ConflictError("Named predecessor does not exist")
        if predecessor["record_type"] != record.record_type or predecessor["lineage_key"] != record.lineage_key:
            raise ConflictError("Predecessor record type or lineage key does not match")
        if current is None or current["record_id"] != record.predecessor_record_id:
            raise ConflictError("Stale predecessor or competing successor")

    def _advance_lineage(self, record: RecordEnvelope) -> None:
        if record.record_type == "StateEvent" or record.lineage_key is None:
            return
        self._connection.execute(
            """insert into lineage_heads(project_id,record_type,lineage_key,record_id) values (?,?,?,?)
            on conflict(project_id,record_type,lineage_key) do update set record_id=excluded.record_id""",
            (record.project_id, record.record_type, record.lineage_key, record.record_id),
        )

    def _apply_record_in_transaction(self, record: RecordEnvelope) -> None:
        self._validate_successor(record)
        self._insert_record_row(record)
        if record.record_type == "Link":
            self._project_link(record)
        elif record.record_type == "StateEvent":
            self._project_state_event(record)
        self._advance_lineage(record)
        if record.predecessor_record_id and record.record_type != "StateEvent":
            self._emit_supersession_effects(record)

    def insert_record(self, record: RecordEnvelope) -> OperationResult:
        validate_record_semantics(record, self._lookup_record, source_blob_lookup=self._lookup_source_blob)
        existing = self._existing_outcome(record)
        if existing is not None:
            return existing
        try:
            with self.transaction():
                self._apply_record_in_transaction(record)
        except ConflictError as exc:
            return OperationResult("CONFLICT", record.record_id, {"reason": str(exc)})
        return OperationResult("CREATED", record.record_id)
