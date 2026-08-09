from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .benchmark import score_benchmark
from .canonical import canonical_json
from .fixture import apply_fixture
from .store import ConflictError, LanternError, LanternStore, ValidationError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lantern")
    parser.add_argument("--project", default=".lantern")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--project-id")
    init.add_argument("--actor-id", default="operator")
    init.add_argument("--name", default="Lantern Project")
    init.add_argument("--seed-fixture")
    source = commands.add_parser("source")
    source_commands = source.add_subparsers(dest="source_command", required=True)
    observe = source_commands.add_parser("observe")
    for name in ("actor-id", "source-key", "locator", "retrieval-route", "media-type", "retention-status", "observed-at"):
        observe.add_argument(f"--{name}", required=True)
    observe.add_argument("--custody-mode", required=True,
                         choices=["REFERENCE_ONLY", "CAPTURED", "EMBEDDED", "REDACTED", "UNAVAILABLE"])
    observe.add_argument("--content-file")
    observe.add_argument("--predecessor-record-id")
    observe.add_argument("--record-id")
    observe.add_argument("--created-at")
    claim = commands.add_parser("claim")
    claim_commands = claim.add_subparsers(dest="claim_command", required=True)
    claim_add = claim_commands.add_parser("add")
    for name in ("actor-id", "claim-key", "text", "epistemic-class", "attributable-to"):
        claim_add.add_argument(f"--{name}", required=True)
    claim_add.add_argument("--predecessor-record-id")
    claim_add.add_argument("--record-id")
    claim_add.add_argument("--created-at")
    assess = commands.add_parser("assess")
    for name in ("actor-id", "claim-id", "assessor-id", "scope-id", "rationale"):
        assess.add_argument(f"--{name}", required=True)
    assess.add_argument("--disposition", required=True, choices=["ACCEPTED", "DISPUTED", "REJECTED", "UNVERIFIED"])
    assess.add_argument("--predecessor-record-id")
    assess.add_argument("--record-id")
    assess.add_argument("--created-at")
    link = commands.add_parser("link")
    link_commands = link.add_subparsers(dest="link_command", required=True)
    link_add = link_commands.add_parser("add")
    link_add.add_argument("--actor-id", required=True)
    link_add.add_argument("--type", dest="link_type", required=True,
                          choices=["SUPPORTS", "OPPOSES", "CONTRADICTS", "DEPENDS_ON"])
    link_add.add_argument("--source", dest="source_record_id", required=True)
    link_add.add_argument("--target", dest="target_record_id", required=True)
    link_add.add_argument("--record-id")
    link_add.add_argument("--created-at")
    decision = commands.add_parser("decision")
    decision_commands = decision.add_subparsers(dest="decision_command", required=True)
    decision_record = decision_commands.add_parser("record")
    for name in ("actor-id", "decision-key", "authority", "conclusion"):
        decision_record.add_argument(f"--{name}", required=True)
    decision_record.add_argument("--evidence", action="append", default=[])
    decision_record.add_argument("--assumption", dest="assumptions", action="append", default=[])
    decision_record.add_argument("--alternative", dest="alternatives", action="append", default=[])
    decision_record.add_argument("--predecessor-record-id")
    decision_record.add_argument("--record-id")
    decision_record.add_argument("--created-at")
    decision_trace = decision_commands.add_parser("trace")
    decision_trace.add_argument("--decision-id", required=True)
    commands.add_parser("status")
    export = commands.add_parser("export")
    export.add_argument("destination")
    imp = commands.add_parser("import")
    imp.add_argument("source")
    imp.add_argument("--create", action="store_true")
    imp.add_argument("--actor-id", default="importer")
    benchmark = commands.add_parser("benchmark")
    benchmark_commands = benchmark.add_subparsers(dest="benchmark_command", required=True)
    score = benchmark_commands.add_parser("score")
    score.add_argument("--contract", required=True)
    score.add_argument("--measurements", required=True)
    score.add_argument("--freeze-receipt", required=True)
    score.add_argument("--output")
    return parser


def _emit(payload: dict[str, Any]) -> None:
    print(canonical_json(payload))


def _operation_response(command: str, result: Any) -> dict[str, Any]:
    body = result.to_dict() if hasattr(result, "to_dict") else result if isinstance(result, dict) else {"result": result}
    return {"schema": "LANTERN_CLI_RESPONSE_V1", "command": command, "status": "OK", "result": body}


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.project)
    try:
        if args.command == "init":
            fixture_project_id = None
            if args.seed_fixture:
                fixture_project_id = json.loads(Path(args.seed_fixture).read_text(encoding="utf-8")).get("project_id")
            with LanternStore.initialize(root, project_id=args.project_id or fixture_project_id,
                                         actor_id=args.actor_id, project_name=args.name) as store:
                receipt: dict[str, Any] = {"schema": "LANTERN_INIT_RECEIPT_V1", "project_manifest": store.manifest()}
                if args.seed_fixture:
                    receipt["fixture"] = apply_fixture(store, args.seed_fixture)
                _emit(_operation_response("init", receipt))
            return 0
        if args.command == "benchmark":
            result = score_benchmark(contract_path=args.contract, measurements_path=args.measurements,
                                     freeze_receipt_path=args.freeze_receipt, output_path=args.output)
            _emit(_operation_response("benchmark score", result))
            return 0 if result["result"] == "PASS" else 2
        if args.command == "import" and args.create:
            result = LanternStore.import_bundle_new(root, args.source, actor_id=args.actor_id)
            _emit(_operation_response("import", result))
            return 0
        with LanternStore.open(root) as store:
            if args.command == "source":
                content = Path(args.content_file).read_bytes() if args.content_file else None
                result = store.observe_source(actor_id=args.actor_id, source_key=args.source_key,
                    locator=args.locator, retrieval_route=args.retrieval_route, media_type=args.media_type,
                    custody_mode=args.custody_mode, retention_status=args.retention_status,
                    observed_at=args.observed_at, content=content,
                    predecessor_record_id=args.predecessor_record_id, record_id=args.record_id,
                    created_at=args.created_at)
                command = "source observe"
            elif args.command == "claim":
                result = store.add_claim(actor_id=args.actor_id, claim_key=args.claim_key, text=args.text,
                    epistemic_class=args.epistemic_class, attributable_to=args.attributable_to,
                    predecessor_record_id=args.predecessor_record_id, record_id=args.record_id,
                    created_at=args.created_at)
                command = "claim add"
            elif args.command == "assess":
                result = store.add_assessment(actor_id=args.actor_id, claim_id=args.claim_id,
                    assessor_id=args.assessor_id, scope_id=args.scope_id, disposition=args.disposition,
                    rationale=args.rationale, predecessor_record_id=args.predecessor_record_id,
                    record_id=args.record_id, created_at=args.created_at)
                command = "assess"
            elif args.command == "link":
                result = store.add_link(actor_id=args.actor_id, link_type=args.link_type,
                    source_record_id=args.source_record_id, target_record_id=args.target_record_id,
                    record_id=args.record_id, created_at=args.created_at)
                command = "link add"
            elif args.command == "decision" and args.decision_command == "record":
                result = store.add_decision(actor_id=args.actor_id, decision_key=args.decision_key,
                    authority=args.authority, conclusion=args.conclusion, evidence=args.evidence,
                    assumptions=args.assumptions, alternatives=args.alternatives,
                    predecessor_record_id=args.predecessor_record_id, record_id=args.record_id,
                    created_at=args.created_at)
                command = "decision record"
            elif args.command == "decision":
                result = store.decision_trace(args.decision_id)
                command = "decision trace"
            elif args.command == "status":
                result = store.status(); command = "status"
            elif args.command == "export":
                result = store.export_bundle(args.destination); command = "export"
            elif args.command == "import":
                result = store.import_bundle(args.source); command = "import"
            else:
                raise ValidationError("Unsupported command")
            _emit(_operation_response(command, result))
            return 2 if hasattr(result, "outcome") and result.outcome == "CONFLICT" else 0
    except (LanternError, ValueError, OSError, json.JSONDecodeError) as exc:
        _emit({"schema": "LANTERN_CLI_RESPONSE_V1", "command": getattr(args, "command", "unknown"),
               "status": "ERROR", "error": {"class": type(exc).__name__, "message": str(exc)}})
        return 2 if isinstance(exc, (ConflictError, ValidationError)) else 1


def main() -> int:
    return run(sys.argv[1:])
