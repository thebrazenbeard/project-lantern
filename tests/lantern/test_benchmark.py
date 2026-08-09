from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from lantern.benchmark import score_benchmark
from lantern.canonical import canonical_json_bytes, sha256_hex
from lantern.store import ValidationError

from conftest import ARTIFACT_ROOT


def _measurements() -> dict:
    freeze = json.loads((ARTIFACT_ROOT / "freeze-receipt-v1.json").read_text(encoding="utf-8"))
    return {
        "schema": "LANTERN_BENCHMARK_MEASUREMENTS_V1",
        "fixture_id": freeze["fixture_id"],
        "frozen_artifact_set_sha256": freeze["artifact_set_sha256"],
        "practice_runs": {"lantern": 1, "control": 1},
        "hard_gate_results": {
            "zero_unsupported_answers": True,
            "zero_missed_contradiction": True,
            "zero_missed_direct_review_required": True,
            "exact_export_import_reconstruction": True,
            "no_overwrite_on_conflict": True,
        },
        "lantern": {
            "capture_seconds": 20,
            "measured_runs": [
                {"operator_seconds": 10, "reconstruction_seconds": 5},
                {"operator_seconds": 11, "reconstruction_seconds": 6},
                {"operator_seconds": 9, "reconstruction_seconds": 5},
            ],
        },
        "control": {
            "capture_seconds": 25,
            "measured_runs": [
                {"operator_seconds": 12, "reconstruction_seconds": 10},
                {"operator_seconds": 13, "reconstruction_seconds": 9},
                {"operator_seconds": 11, "reconstruction_seconds": 11},
            ],
        },
    }


def _score(artifact_root: Path, tmp_path: Path, measurements: dict | None = None):
    measurement_path = tmp_path / "measurements.json"
    measurement_path.write_bytes(canonical_json_bytes(measurements or _measurements()) + b"\n")
    return score_benchmark(
        contract_path=artifact_root / "scoring-contract-v1.json",
        measurements_path=measurement_path,
        freeze_receipt_path=artifact_root / "freeze-receipt-v1.json",
    )


def _copied_artifacts(tmp_path: Path) -> Path:
    target = tmp_path / "benchmark"
    shutil.copytree(ARTIFACT_ROOT, target)
    return target


def test_frozen_benchmark_pass_rule_is_executable(tmp_path: Path) -> None:
    receipt = _score(ARTIFACT_ROOT, tmp_path)
    assert receipt["result"] == "PASS"
    assert receipt["frozen_artifact_set_sha256"] == _measurements()["frozen_artifact_set_sha256"]


@pytest.mark.parametrize(
    ("path", "mutator"),
    [
        ("scoring-contract-v1.json", lambda value: value.__setitem__("required_median_reconstruction_reduction_percent", 1)),
        ("scoring-contract-v1.json", lambda value: value["hard_gates"].append("invented_gate")),
        ("fixture-v1.json", lambda value: value.__setitem__("scope_id", "changed")),
        ("expected-answers-v1.json", lambda value: value.__setitem__("scope_id", "changed")),
        ("scoring-receipt-template-v1.json", lambda value: value["required_fields"].append("changed")),
    ],
)
def test_mutated_frozen_json_artifact_fails_closed(
    tmp_path: Path, path: str, mutator
) -> None:
    root = _copied_artifacts(tmp_path)
    artifact = root / path
    value = json.loads(artifact.read_text(encoding="utf-8"))
    mutator(value)
    artifact.write_bytes(canonical_json_bytes(value) + b"\n")
    with pytest.raises(ValidationError, match="Frozen artifact changed|frozen contract|immutable trust anchor"):
        _score(root, tmp_path)


def test_mutated_control_artifact_fails_closed(tmp_path: Path) -> None:
    root = _copied_artifacts(tmp_path)
    control = root / "control" / "git-markdown-control-v1.md"
    control.write_text(control.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="Frozen artifact changed"):
        _score(root, tmp_path)


@pytest.mark.parametrize("field", ["fixture_id", "artifact_set_sha256", "pass_rule_sha256"])
def test_mutated_freeze_binding_fails_closed(tmp_path: Path, field: str) -> None:
    root = _copied_artifacts(tmp_path)
    path = root / "freeze-receipt-v1.json"
    freeze = json.loads(path.read_text(encoding="utf-8"))
    freeze[field] = "0" * 64 if field != "fixture_id" else "OTHER-FIXTURE"
    path.write_bytes(canonical_json_bytes(freeze) + b"\n")
    with pytest.raises(ValidationError):
        _score(root, tmp_path)


def test_measurements_must_bind_exact_frozen_fixture_and_artifact_set(tmp_path: Path) -> None:
    measurements = _measurements()
    measurements["fixture_id"] = "OTHER"
    with pytest.raises(ValidationError, match="fixture_id"):
        _score(ARTIFACT_ROOT, tmp_path, measurements)
    measurements = _measurements()
    measurements["frozen_artifact_set_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="artifact set"):
        _score(ARTIFACT_ROOT, tmp_path, measurements)


def test_self_consistent_refreeze_attack_fails_against_pinned_trust_anchor(tmp_path: Path) -> None:
    root = _copied_artifacts(tmp_path)
    contract_path = root / "scoring-contract-v1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["required_median_reconstruction_reduction_percent"] = 0
    contract_bytes = canonical_json_bytes(contract) + b"\n"
    contract_path.write_bytes(contract_bytes)

    freeze_path = root / "freeze-receipt-v1.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    for entry in freeze["artifacts"]:
        data = (root / entry["path"]).read_bytes()
        entry["sha256"] = sha256_hex(data)
        entry["size"] = len(data)
    freeze["artifact_set_sha256"] = sha256_hex(canonical_json_bytes(freeze["artifacts"]))
    freeze["pass_rule_sha256"] = sha256_hex(canonical_json_bytes(contract))
    freeze_path.write_bytes(canonical_json_bytes(freeze) + b"\n")

    measurements = _measurements()
    measurements["frozen_artifact_set_sha256"] = freeze["artifact_set_sha256"]
    with pytest.raises(ValidationError, match="immutable trust anchor"):
        _score(root, tmp_path, measurements)
