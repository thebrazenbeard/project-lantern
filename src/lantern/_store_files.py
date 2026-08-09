from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import canonical_json_bytes, sha256_hex, strict_json_loads
from ._store_types import ConflictError, ValidationError

_JOURNAL_SCHEMA = "LANTERN_FILE_OPERATION_V1"
_JOURNAL_KEYS = {"schema", "operation_id", "stage_dir", "new_targets"}
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _operation_token(operation_id: str) -> str:
    if not isinstance(operation_id, str) or not operation_id:
        raise ValidationError("File operation_id must be a non-empty string")
    return sha256_hex(operation_id)[:32]


def _contained(root: Path, path: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
    except (ValueError, FileNotFoundError):
        return False
    return True


def _safe_directory(root: Path, relative: str, *, create: bool = False) -> Path:
    path = root / relative
    if path.is_symlink():
        raise ValidationError(f"Lantern internal directory cannot be a symlink: {relative}")
    if path.exists() and not path.is_dir():
        raise ValidationError(f"Lantern internal path must be a directory: {relative}")
    if not _contained(root, path):
        raise ValidationError(f"Lantern internal directory escapes project root: {relative}")
    if create:
        path.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise ValidationError(f"Unable to create safe Lantern directory: {relative}")
    return path


def _validate_digest(digest: str) -> str:
    if not isinstance(digest, str) or not _HEX64.fullmatch(digest):
        raise ValidationError(f"Source digest must be lowercase SHA-256: {digest!r}")
    return digest


def _source_target(root: Path, digest: str) -> Path:
    digest = _validate_digest(digest)
    sources = _safe_directory(root, "sources", create=True)
    target = sources / digest
    if target.is_symlink():
        raise ValidationError(f"Source target cannot be a symlink: {digest}")
    if not _contained(root, target) or target.resolve(strict=False).parent != sources.resolve(strict=True):
        raise ValidationError(f"Source target escapes sources directory: {digest}")
    if target.exists() and not target.is_file():
        raise ValidationError(f"Source target must be a regular file: {digest}")
    return target


def _validate_tree_for_cleanup(root: Path, directory: Path) -> None:
    if directory.is_symlink():
        raise ValidationError(f"Cleanup directory cannot be a symlink: {directory}")
    if not directory.exists():
        return
    if not directory.is_dir() or not _contained(root, directory):
        raise ValidationError(f"Unsafe cleanup directory: {directory}")
    for path in directory.rglob("*"):
        if path.is_symlink() or not _contained(root, path):
            raise ValidationError(f"Unsafe symlink or escaped path in staging directory: {path}")


def _remove_stage_dir(root: Path, stage_dir: Path) -> None:
    if not stage_dir.exists() and not stage_dir.is_symlink():
        return
    _validate_tree_for_cleanup(root, stage_dir)
    shutil.rmtree(stage_dir)


def _unlink_journal(root: Path, journal_path: Path) -> None:
    if not journal_path.exists() and not journal_path.is_symlink():
        return
    if journal_path.is_symlink() or not journal_path.is_file() or not _contained(root, journal_path):
        raise ValidationError(f"Unsafe file-operation journal: {journal_path}")
    journal_path.unlink()


def _remove_source_target(root: Path, target: Path) -> None:
    if not target.exists() and not target.is_symlink():
        return
    if target.is_symlink() or not target.is_file() or not _contained(root, target):
        raise ValidationError(f"Unsafe source target during recovery: {target}")
    digest = target.name
    _validate_digest(digest)
    if sha256_hex(target.read_bytes()) != digest:
        raise ValidationError(f"Recovery refuses to delete divergent source bytes: {digest}")
    target.unlink()


@dataclass(slots=True)
class StagedFileOperation:
    root: Path
    operation_id: str
    stage_dir: Path
    journal_path: Path
    staged: dict[str, Path]
    new_targets: list[Path]

    def promote(self) -> None:
        self.new_targets = []
        for digest, staged_path in sorted(self.staged.items()):
            target = _source_target(self.root, digest)
            if staged_path.is_symlink() or not staged_path.is_file() or not _contained(self.root, staged_path):
                raise ValidationError(f"Unsafe staged source blob: {digest}")
            if sha256_hex(staged_path.read_bytes()) != digest:
                raise ValidationError(f"Staged source blob digest mismatch: {digest}")
            if target.exists():
                if sha256_hex(target.read_bytes()) != digest:
                    raise ConflictError(f"Divergent source bytes for digest {digest}")
                staged_path.unlink()
                continue
            self.new_targets.append(target)
        self._write_journal()
        for target in self.new_targets:
            staged_path = self.staged[target.name]
            created = False
            try:
                os.link(staged_path, target)
                created = True
            except FileExistsError:
                if target.is_symlink() or not target.is_file() or sha256_hex(target.read_bytes()) != target.name:
                    raise ConflictError(f"Divergent source bytes for digest {target.name}")
            if not created:
                staged_path.unlink(missing_ok=True)

    def _write_journal(self) -> None:
        payload = {
            "schema": _JOURNAL_SCHEMA,
            "operation_id": self.operation_id,
            "stage_dir": str(self.stage_dir.relative_to(self.root).as_posix()),
            "new_targets": [str(path.relative_to(self.root).as_posix()) for path in self.new_targets],
        }
        journal_dir = _safe_directory(self.root, ".lantern-operations", create=True)
        expected = journal_dir / f"{_operation_token(self.operation_id)}.json"
        if expected != self.journal_path:
            raise ValidationError("File-operation journal path does not match operation_id")
        if self.journal_path.is_symlink():
            raise ValidationError("File-operation journal cannot be a symlink")
        self.journal_path.write_bytes(canonical_json_bytes(payload) + b"\n")

    def cleanup_after_success(self) -> None:
        _remove_stage_dir(self.root, self.stage_dir)
        _unlink_journal(self.root, self.journal_path)

    def rollback_files(self) -> None:
        for target in self.new_targets:
            staged_path = self.staged.get(target.name)
            if (staged_path is not None and staged_path.exists() and not staged_path.is_symlink()
                    and target.exists() and not target.is_symlink() and os.path.samefile(staged_path, target)):
                _remove_source_target(self.root, target)
        _remove_stage_dir(self.root, self.stage_dir)
        _unlink_journal(self.root, self.journal_path)


def stage_source_blobs(root: Path, operation_id: str, blobs: dict[str, bytes]) -> StagedFileOperation:
    root = root.resolve(strict=True)
    safe = _operation_token(operation_id)
    stage_parent = _safe_directory(root, ".lantern-staging", create=True)
    journal_parent = _safe_directory(root, ".lantern-operations", create=True)
    stage_dir = stage_parent / safe
    journal_path = journal_parent / f"{safe}.json"
    if journal_path.exists() or journal_path.is_symlink():
        raise ConflictError(f"Unresolved file-operation journal already exists: {journal_path.name}")
    if stage_dir.exists() or stage_dir.is_symlink():
        _remove_stage_dir(root, stage_dir)
    stage_dir.mkdir()
    staged: dict[str, Path] = {}
    for digest, content in sorted(blobs.items()):
        digest = _validate_digest(digest)
        if sha256_hex(content) != digest:
            raise ValidationError(f"Source blob digest mismatch: {digest}")
        path = stage_dir / digest
        if path.is_symlink() or path.exists():
            raise ValidationError(f"Unsafe duplicate staging path: {digest}")
        path.write_bytes(content)
        staged[digest] = path
    return StagedFileOperation(root, operation_id, stage_dir, journal_path, staged, [])


def _parse_journal(root: Path, journal_path: Path) -> dict[str, Any]:
    if journal_path.is_symlink() or not journal_path.is_file() or not _contained(root, journal_path):
        raise ValidationError(f"Unsafe file-operation journal: {journal_path}")
    raw = journal_path.read_bytes()
    try:
        payload = strict_json_loads(raw)
    except Exception as exc:
        raise ValidationError(f"Unreadable file-operation journal: {journal_path.name}") from exc
    if not isinstance(payload, dict) or set(payload) != _JOURNAL_KEYS:
        raise ValidationError(f"Malformed file-operation journal: {journal_path.name}")
    if canonical_json_bytes(payload) + b"\n" != raw:
        raise ValidationError(f"File-operation journal is not canonical: {journal_path.name}")
    if payload.get("schema") != _JOURNAL_SCHEMA:
        raise ValidationError(f"Unsupported file-operation journal schema: {journal_path.name}")
    operation_id = payload.get("operation_id")
    safe = _operation_token(operation_id)
    if journal_path.name != f"{safe}.json":
        raise ValidationError("File-operation journal filename does not match operation_id")
    expected_stage = f".lantern-staging/{safe}"
    if payload.get("stage_dir") != expected_stage:
        raise ValidationError("File-operation stage_dir does not match operation_id")
    new_targets = payload.get("new_targets")
    if not isinstance(new_targets, list) or any(not isinstance(item, str) for item in new_targets):
        raise ValidationError("File-operation new_targets must be a list of strings")
    if new_targets != sorted(set(new_targets)):
        raise ValidationError("File-operation new_targets must be unique and sorted")
    targets: list[Path] = []
    for relative in new_targets:
        match = re.fullmatch(r"sources/([0-9a-f]{64})", relative)
        if match is None:
            raise ValidationError(f"Unsafe file-operation target: {relative}")
        targets.append(_source_target(root, match.group(1)))
    stage_dir = root / expected_stage
    if stage_dir.is_symlink():
        raise ValidationError("File-operation stage directory cannot be a symlink")
    if stage_dir.exists():
        _validate_tree_for_cleanup(root, stage_dir)
    return {"operation_id": operation_id, "stage_dir": stage_dir, "targets": targets, "journal_path": journal_path}


def recover_file_operations(root: Path, connection) -> None:
    root = root.resolve(strict=True)
    journal_dir = _safe_directory(root, ".lantern-operations", create=False)
    if not journal_dir.exists():
        return
    plans: list[dict[str, Any]] = []
    for journal_path in sorted(journal_dir.glob("*.json")):
        plan = _parse_journal(root, journal_path)
        row = connection.execute(
            "select status from file_operations where operation_id=?", (plan["operation_id"],)
        ).fetchone()
        if row is not None and row["status"] != "COMMITTED":
            raise ValidationError("File-operation database state is unresolved")
        plan["committed"] = row is not None
        for target in plan["targets"]:
            if target.is_symlink():
                raise ValidationError("Recovery target cannot be a symlink")
            if plan["committed"]:
                if not target.exists() or not target.is_file() or sha256_hex(target.read_bytes()) != target.name:
                    raise ValidationError("Committed file operation is missing verified target bytes")
            elif target.exists():
                if not target.is_file() or sha256_hex(target.read_bytes()) != target.name:
                    raise ValidationError("Uncommitted file operation has divergent target bytes")
                staged_path = plan["stage_dir"] / target.name
                if not staged_path.exists() or staged_path.is_symlink() or not staged_path.is_file():
                    raise ValidationError("Uncommitted file operation cannot prove target ownership")
                if not os.path.samefile(staged_path, target):
                    raise ValidationError("Uncommitted file operation target was not created by its staging file")
        plans.append(plan)

    for plan in plans:
        if not plan["committed"]:
            for target in plan["targets"]:
                if target.exists():
                    _remove_source_target(root, target)
        _remove_stage_dir(root, plan["stage_dir"])
        _unlink_journal(root, plan["journal_path"])
