from __future__ import annotations

from datetime import UTC, datetime

from .canonical import sha256_hex
from .contracts import build_record
from .validation import validate_record_semantics
from ._store_files import stage_source_blobs
from ._store_types import ConflictError, OperationResult


class SourceCommandsMixin:
    def _commit_source_blob(self, *, operation_id: str, digest: str, content: bytes) -> None:
        file_op = stage_source_blobs(self.root, operation_id, {digest: content})
        try:
            with self.transaction():
                file_op.promote()
                self._connection.execute(
                    "insert or ignore into file_operations(operation_id,status,committed_at) values (?,?,?)",
                    (operation_id, "COMMITTED", datetime.now(UTC).isoformat().replace("+00:00", "Z")),
                )
        except Exception:
            file_op.rollback_files()
            raise
        file_op.cleanup_after_success()

    def observe_source(self, *, actor_id: str, source_key: str, locator: str,
                       retrieval_route: str, media_type: str, custody_mode: str,
                       retention_status: str, observed_at: str, content: bytes | None = None,
                       predecessor_record_id: str | None = None, record_id: str | None = None,
                       created_at: str | None = None) -> OperationResult:
        content_digest = sha256_hex(content) if content is not None else None
        record = build_record(
            project_id=self.project_id, record_type="SourceSnapshot", actor_id=actor_id,
            record_id=record_id, created_at=created_at, observed_at=observed_at,
            provenance={"source_locator": locator, "retrieval_route": retrieval_route},
            lineage_key=source_key, predecessor_record_id=predecessor_record_id,
            payload={"source_key": source_key, "locator": locator,
                     "retrieval_route": retrieval_route, "media_type": media_type,
                     "custody_mode": custody_mode, "retention_status": retention_status,
                     "content_sha256": content_digest},
        )
        validate_record_semantics(record, self._lookup_record, source_content=content)
        existing = self._existing_outcome(record)
        if existing is not None:
            if existing.outcome != "VERIFIED" or content is None or content_digest is None:
                return existing
            retained = self._lookup_source_blob(content_digest)
            if retained is not None:
                return existing
            self._commit_source_blob(
                operation_id=f"source-restore:{record.record_id}:{content_digest}",
                digest=content_digest,
                content=content,
            )
            return existing
        if content is None:
            return self.insert_record(record)
        operation_id = f"source-observe:{record.record_id}:{content_digest}"
        file_op = stage_source_blobs(self.root, operation_id, {content_digest: content})
        try:
            with self.transaction():
                self._apply_record_in_transaction(record)
                file_op.promote()
                self._connection.execute(
                    "insert or ignore into file_operations(operation_id,status,committed_at) values (?,?,?)",
                    (operation_id, "COMMITTED", datetime.now(UTC).isoformat().replace("+00:00", "Z")),
                )
        except ConflictError as exc:
            file_op.rollback_files()
            return OperationResult("CONFLICT", record.record_id, {"reason": str(exc)})
        except Exception:
            file_op.rollback_files()
            raise
        file_op.cleanup_after_success()
        return OperationResult("CREATED", record.record_id)
