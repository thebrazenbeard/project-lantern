from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from .store import LanternStore, OperationResult, ValidationError


def apply_fixture(store: LanternStore, fixture_path: str | Path) -> dict[str, Any]:
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    if fixture.get("schema") != "LANTERN_SEEDED_FIXTURE_V1":
        raise ValidationError("Unsupported fixture schema")
    if fixture.get("project_id") != store.project_id:
        raise ValidationError("Fixture project_id does not match initialized store")
    results: list[dict[str, Any]] = []
    for operation in fixture.get("operations", []):
        if not isinstance(operation, dict):
            raise ValidationError("Fixture operations must be objects")
        kind = operation.get("operation")
        args = dict(operation.get("args", {}))
        if kind == "source.observe":
            encoded = args.pop("content_base64", None)
            content = base64.b64decode(encoded) if isinstance(encoded, str) else None
            result = store.observe_source(content=content, **args)
        elif kind == "claim.add":
            result = store.add_claim(**args)
        elif kind == "assess":
            result = store.add_assessment(**args)
        elif kind == "decision.record":
            result = store.add_decision(**args)
        elif kind == "link.add":
            result = store.add_link(**args)
        else:
            raise ValidationError(f"Unsupported fixture operation: {kind}")
        results.append({"operation": kind, **_result_dict(result)})
        if result.outcome not in {"CREATED", "VERIFIED"}:
            raise ValidationError(f"Fixture operation failed: {kind}: {result.to_dict()}")
    return {
        "schema": "LANTERN_FIXTURE_APPLY_RECEIPT_V1",
        "fixture_id": fixture.get("fixture_id"),
        "project_id": store.project_id,
        "results": results,
    }


def _result_dict(result: OperationResult) -> dict[str, Any]:
    return {"outcome": result.outcome, "record_id": result.record_id, "details": result.details}
