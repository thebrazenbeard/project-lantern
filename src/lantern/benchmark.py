from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

from .canonical import canonical_json_bytes, normalize_relative_posix_path, sha256_hex, strict_json_loads
from ._store_types import ValidationError

_EXPECTED_FREEZE_RECEIPT_SHA256 = "ad3d6df9cb416957e818e5a91a3aac33f622a1d390887cf20a04e5069646112c"
_FREEZE_KEYS = {"artifact_set_sha256", "artifacts", "fixture_id", "limitation", "pass_rule_sha256", "schema", "status"}
_ARTIFACT_KEYS = {"path", "sha256", "size"}


def _load_json_bytes(path: str | Path, label: str) -> tuple[bytes, dict[str, Any]]:
    data = Path(path).read_bytes()
    value = strict_json_loads(data)
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be a JSON object")
    return data, value


def _verify_freeze(contract_bytes: bytes, contract: dict[str, Any], freeze_path: Path,
                   freeze_bytes: bytes, freeze: dict[str, Any]) -> None:
    if set(freeze) != _FREEZE_KEYS or freeze.get("schema") != "LANTERN_BENCHMARK_FREEZE_RECEIPT_V1":
        raise ValidationError("Unsupported or malformed freeze receipt")
    if freeze.get("status") != "FROZEN_BEFORE_IMPLEMENTATION_RESULTS":
        raise ValidationError("Freeze receipt is not in the frozen state")
    artifacts = freeze.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValidationError("Freeze receipt has no artifacts")
    seen_paths: set[str] = set()
    verified_entries: list[dict[str, Any]] = []
    contract_entry: dict[str, Any] | None = None
    for entry in artifacts:
        if not isinstance(entry, dict) or set(entry) != _ARTIFACT_KEYS:
            raise ValidationError("Malformed frozen artifact entry")
        path = normalize_relative_posix_path(entry["path"])
        digest = entry["sha256"]
        size = entry["size"]
        if path in seen_paths:
            raise ValidationError("Frozen artifacts must be unique")
        seen_paths.add(path)
        if not isinstance(digest, str) or len(digest) != 64 or not isinstance(size, int) or size < 0:
            raise ValidationError("Malformed frozen artifact digest or size")
        artifact_path = freeze_path.parent / path
        if not artifact_path.exists():
            raise ValidationError(f"Frozen artifact is missing: {path}")
        data = artifact_path.read_bytes()
        if len(data) != size or sha256_hex(data) != digest:
            raise ValidationError(f"Frozen artifact changed: {path}")
        normalized = {"path": path, "sha256": digest, "size": size}
        verified_entries.append(normalized)
        if path == "scoring-contract-v1.json":
            contract_entry = normalized
            if data != contract_bytes:
                raise ValidationError("Supplied scoring contract does not match frozen contract bytes")
    if contract_entry is None:
        raise ValidationError("Freeze receipt does not bind the scoring contract")
    artifact_set = sha256_hex(canonical_json_bytes(verified_entries))
    if artifact_set != freeze.get("artifact_set_sha256"):
        raise ValidationError("Frozen artifact-set digest mismatch")
    pass_rule = sha256_hex(canonical_json_bytes(contract))
    if pass_rule != freeze.get("pass_rule_sha256"):
        raise ValidationError("Frozen pass-rule digest mismatch")
    if canonical_json_bytes(freeze) + b"\n" != freeze_bytes:
        raise ValidationError("Freeze receipt must use canonical JSON plus one newline")


def score_benchmark(*, contract_path: str | Path, measurements_path: str | Path,
                    freeze_receipt_path: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    freeze_bytes = Path(freeze_receipt_path).read_bytes()
    if sha256_hex(freeze_bytes) != _EXPECTED_FREEZE_RECEIPT_SHA256:
        raise ValidationError("Freeze receipt does not match the immutable trust anchor")
    freeze_value = strict_json_loads(freeze_bytes)
    if not isinstance(freeze_value, dict):
        raise ValidationError("Freeze receipt must be a JSON object")
    freeze = freeze_value
    contract_bytes, contract = _load_json_bytes(contract_path, "Scoring contract")
    measurements_bytes, measurements = _load_json_bytes(measurements_path, "Measurements")
    if contract.get("schema") != "LANTERN_BENCHMARK_SCORING_CONTRACT_V1":
        raise ValidationError("Unsupported benchmark scoring contract")
    if measurements.get("schema") != "LANTERN_BENCHMARK_MEASUREMENTS_V1":
        raise ValidationError("Unsupported benchmark measurements")
    _verify_freeze(contract_bytes, contract, Path(freeze_receipt_path), freeze_bytes, freeze)
    fixture_id = freeze.get("fixture_id")
    if contract.get("fixture_id") != fixture_id or measurements.get("fixture_id") != fixture_id:
        raise ValidationError("Benchmark fixture_id does not match the frozen fixture")
    if measurements.get("frozen_artifact_set_sha256") != freeze.get("artifact_set_sha256"):
        raise ValidationError("Measurements are not bound to the frozen artifact set")
    if measurements.get("practice_runs") != contract.get("practice_runs") or measurements.get("practice_runs") != {"lantern": 1, "control": 1}:
        raise ValidationError("Exactly one untimed practice run per workflow is required")
    lantern = _workflow_metrics(measurements, "lantern", int(contract.get("measured_runs_per_workflow", 0)))
    control = _workflow_metrics(measurements, "control", int(contract.get("measured_runs_per_workflow", 0)))
    hard_gate_names = contract.get("hard_gates")
    hard_gate_results = measurements.get("hard_gate_results")
    if not isinstance(hard_gate_names, list) or any(not isinstance(name, str) for name in hard_gate_names):
        raise ValidationError("Contract hard_gates must be a list of strings")
    if not isinstance(hard_gate_results, dict) or set(hard_gate_results) != set(hard_gate_names):
        raise ValidationError("Measurements must report exactly the frozen hard gates")
    if any(not isinstance(value, bool) for value in hard_gate_results.values()):
        raise ValidationError("Hard gate results must be boolean")
    hard_gates_pass = all(hard_gate_results[name] for name in hard_gate_names)
    total_time_pass = lantern["total_operator_seconds"] <= control["total_operator_seconds"]
    required_reduction = contract.get("required_median_reconstruction_reduction_percent")
    if not isinstance(required_reduction, int) or not 0 <= required_reduction <= 100:
        raise ValidationError("Invalid reconstruction reduction threshold")
    threshold_numerator = control["median_reconstruction_seconds"] * (100 - required_reduction)
    reconstruction_pass = lantern["median_reconstruction_seconds"] * 100 <= threshold_numerator
    passed = hard_gates_pass and total_time_pass and reconstruction_pass
    receipt = {
        "schema": "LANTERN_BENCHMARK_SCORING_RECEIPT_V1",
        "fixture_id": fixture_id,
        "frozen_artifact_set_sha256": freeze["artifact_set_sha256"],
        "contract_sha256": sha256_hex(contract_bytes),
        "measurements_sha256": sha256_hex(measurements_bytes),
        "freeze_receipt_sha256": sha256_hex(freeze_bytes),
        "hard_gate_results": {name: hard_gate_results[name] for name in hard_gate_names},
        "lantern": lantern,
        "control": control,
        "required_median_reconstruction_reduction_percent": required_reduction,
        "maximum_lantern_median_reconstruction_seconds_ratio": {
            "numerator": threshold_numerator,
            "denominator": 100,
        },
        "gates": {
            "hard_gates_pass": hard_gates_pass,
            "total_operator_time_no_greater_than_control": total_time_pass,
            "median_reconstruction_reduction_met": reconstruction_pass,
        },
        "result": "PASS" if passed else "FAIL",
    }
    if output_path is not None:
        Path(output_path).write_bytes(canonical_json_bytes(receipt) + b"\n")
    return receipt


def _workflow_metrics(measurements: dict[str, Any], name: str, measured_runs: int) -> dict[str, Any]:
    workflow = measurements.get(name)
    if not isinstance(workflow, dict):
        raise ValidationError(f"Missing workflow measurements: {name}")
    capture = workflow.get("capture_seconds")
    runs = workflow.get("measured_runs")
    if not isinstance(capture, int) or capture < 0:
        raise ValidationError(f"{name}.capture_seconds must be a non-negative integer")
    if not isinstance(runs, list) or len(runs) != measured_runs or measured_runs <= 0:
        raise ValidationError(f"{name} requires exactly {measured_runs} measured runs")
    reconstruction: list[int] = []
    run_total = 0
    for run in runs:
        if not isinstance(run, dict) or set(run) != {"operator_seconds", "reconstruction_seconds"}:
            raise ValidationError(f"{name} run must contain exact timing fields")
        operator = run["operator_seconds"]
        reconstruct = run["reconstruction_seconds"]
        if not isinstance(operator, int) or operator < 0:
            raise ValidationError(f"{name} operator_seconds must be a non-negative integer")
        if not isinstance(reconstruct, int) or reconstruct < 0:
            raise ValidationError(f"{name} reconstruction_seconds must be a non-negative integer")
        run_total += operator
        reconstruction.append(reconstruct)
    return {
        "capture_seconds": capture,
        "measured_operator_seconds": run_total,
        "total_operator_seconds": capture + run_total,
        "reconstruction_seconds": reconstruction,
        "median_reconstruction_seconds": statistics.median(reconstruction),
    }
