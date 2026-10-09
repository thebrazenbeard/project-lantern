"""Inspect Lantern source status without claiming current provider readback."""
from __future__ import annotations

import json
from pathlib import Path

STATUS = Path(__file__).resolve().parents[1] / "projects" / "lantern" / "CURRENTNESS_STATUS_V3.json"


def summarize_source_status(path: Path = STATUS) -> dict[str, object]:
    source = json.loads(path.read_text(encoding="utf-8"))
    if source.get("schema") != "PROJECT_LANTERN_CURRENTNESS_STATUS_V3":
        raise ValueError("unrecognized Lantern source status schema")
    backend = source.get("active_currentness_backend")
    if backend is not None and not isinstance(backend, str):
        raise ValueError("invalid declared backend")
    return {
        "evidence_class": "SOURCE_ONLY",
        "declared_backend": backend,
        "declared_source_currentness": source.get("lantern_currentness", "UNKNOWN"),
        "live_currentness": "UNKNOWN",
        "live_provider_read": False,
        "source_observed_at": source.get("observed_at"),
    }


if __name__ == "__main__":
    print(json.dumps(summarize_source_status(), sort_keys=True))
