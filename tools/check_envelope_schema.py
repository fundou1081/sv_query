#!/usr/bin/env python3
"""[P182.2] Executable top-level envelope schema for core standard success.

Generates a JSON Schema from JSON_CONTRACT["top_level"], then validates the
26-case P182.1c success matrix. This is a gate for the top-level envelope only;
per-command `result` schemas belong to P182.2b.

Usage:
    python3 tools/check_envelope_schema.py --schema-core
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from _bootstrap import ensure_src_first  # noqa: E402

ensure_src_first()

import check_envelope_contract as envelope  # noqa: E402
import jsonschema  # noqa: E402

from cli._registry import JSON_CONTRACT  # noqa: E402


def standard_success_schema() -> dict:
    """Build the executable schema from the same contract as the CLI docs."""
    top = JSON_CONTRACT["top_level"]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "sv_query standard success envelope",
        "type": "object",
        "required": JSON_CONTRACT["envelope_policy"]["standard"].split("/"),
        "properties": {
            "ok": {"const": True},
            "command": {"type": top["command"]["type"]},
            "params": {"type": top["params"]["type"]},
            "result": {"type": top["result"]["type"]},
            "errors": {
                "type": "array",
                "maxItems": 0,
                "items": {"type": ["string", "object"]},
            },
        },
        "additionalProperties": True,
    }


def validate_success_payload(payload: object, validator=None) -> list[str]:
    if not isinstance(payload, dict):
        return [f"root is {type(payload).__name__}, expected object"]
    validator = validator or jsonschema.Draft202012Validator(
        standard_success_schema()
    )
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
    return [f"{e.message} at {list(e.absolute_path)}" for e in errors[:5]]


def run_schema_core(execute=None) -> tuple[list[str], int]:
    problems: list[str] = []
    validator = jsonschema.Draft202012Validator(standard_success_schema())
    execute = execute or envelope.run_cli_case_with_env
    with tempfile.TemporaryDirectory(prefix="svq_p182_2_") as snapshot_dir:
        env = dict(os.environ, SVQ_SNAPSHOT_DIR=snapshot_dir)
        for case in envelope.CORE_SUCCESS_MANIFEST:
            for setup_argv in case.setup:
                setup = execute(setup_argv, env)
                if setup.rc != 0:
                    problems.append(f"{case.command}: setup rc={setup.rc}")
                    break
            else:
                run = execute(case.argv, env)
                if run.rc != 0:
                    problems.append(f"{case.command}: rc={run.rc}, expected 0")
                    continue
                root, parse_problems = envelope._parse_root(run)
                problems.extend(f"{case.command}: {p}" for p in parse_problems)
                if root is not None:
                    problems.extend(
                        f"{case.command}: {p}"
                        for p in validate_success_payload(root, validator)
                    )
    return problems, len(envelope.CORE_SUCCESS_MANIFEST)


def result_key_schema(command: str) -> dict:
    """Per-command result schema: required result_fields, no value types yet."""
    contract = JSON_CONTRACT["commands"][command]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"sv_query {command} result keys",
        "type": "object",
        "required": [
            field for field in contract["result_fields"]
            if field not in contract.get("optional_result_fields", [])
        ],
        "additionalProperties": True,
    }


def validate_result_payload(command: str, payload: object, validator=None) -> list[str]:
    if not isinstance(payload, dict):
        return [f"result is {type(payload).__name__}, expected object"]
    validator = validator or jsonschema.Draft202012Validator(result_key_schema(command))
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
    return [f"{e.message} at {list(e.absolute_path)}" for e in errors[:5]]


def _run_case(case, execute, env) -> tuple[dict | None, list[str]]:
    for setup_argv in case.setup:
        setup = execute(setup_argv, env)
        if setup.rc != 0:
            return None, [f"setup rc={setup.rc}"]
    run = execute(case.argv, env)
    if run.rc != 0:
        return None, [f"rc={run.rc}, expected 0"]
    root, parse_problems = envelope._parse_root(run)
    if root is not None and root.get("ok") is not True:
        parse_problems.append(f"ok={root.get('ok')!r}, expected true")
    return root, parse_problems


def run_schema_results(execute=None) -> tuple[list[str], int]:
    problems: list[str] = []
    execute = execute or envelope.run_cli_case_with_env
    with tempfile.TemporaryDirectory(prefix="svq_p182_2b_") as snapshot_dir:
        env = dict(os.environ, SVQ_SNAPSHOT_DIR=snapshot_dir)
        for case in envelope.CORE_SUCCESS_MANIFEST:
            root, case_problems = _run_case(case, execute, env)
            problems.extend(f"{case.command}: {p}" for p in case_problems)
            if root is None:
                continue
            problems.extend(
                f"{case.command}: {p}" for p in
                validate_result_payload(case.command, root.get("result"))
            )
    return problems, len(envelope.CORE_SUCCESS_MANIFEST)


TYPE_SCHEMAS: dict[str, dict[str, object]] = {
    "stats": {
        "total_nodes": "integer", "total_edges": "integer",
        "nodes": "object", "edges": "object",
        "modules": "array", "elaboration_errors": "array",
    },
    "drivers": {
        "signals": "array", "total_signals": "integer",
        "total_count": "integer", "total_pre_filter": "integer",
        "truncated": "boolean", "failed_signals": "integer",
    },
    "loads": {
        "signals": "array", "total_signals": "integer",
        "total_count": "integer", "total_pre_filter": "integer",
        "truncated": "boolean", "failed_signals": "integer",
    },
    "graph nodes": {"nodes": "array", "total": "integer"},
    "graph edges": {"edges": "array", "total": "integer"},
    "controlflow analyze": {
        "signal": "string", "conditioned_drivers": "array",
        "condition_status": "string", "warnings": "array",
    },
    "dataflow analyze": {
        "from_signal": "string", "to_signal": "string",
        "from_resolved": "string", "to_resolved": "string",
        "bits": "object", "is_reachable": ["boolean", "null"],
        "search_status": "string", "truncated": "boolean",
        "truncation_reason": "string", "expansions": "integer",
        "elapsed_s": "number", "paths_count": "integer",
        "intermediate_signals": "array",
        "primary_latency_cycles": ["integer", "null"],
        "primary_is_async": "boolean", "all_conditions": "array",
        "clock_domain": ["string", "null"], "timing_risk": "string",
        "risk_model": "string", "paths": "array",
    },
    "verify claim": {
        "claim": "object",
        "status": {"type": "string", "enum": ["verified", "contradicted", "unknown"]},
        "reason": "string", "evidence": "array", "counterevidence": "array",
    },
    "trace covergroup": {
        "mode": "string", "covergroup": "object",
        "count": "integer", "complete": "boolean", "reason": "string",
        "links": "array", "samples": "array",
    },
    "trace evidence": {
        "signals": "array", "total_signals": "integer",
        "failed_signals": "integer",
    },
    "trace profile": {
        "signals": "array", "total_signals": "integer",
        "failed_signals": "integer",
    },
    "trace lookup": {
        "paths": "array", "total": "integer",
        "found": "integer", "failed": "integer",
    },
    "trace manifest": {
        "entries": "array", "total": "integer",
        "found": "integer", "failed": "integer",
    },
    "trace constraints": {
        "property": "string", "resolved": "string",
        "count": "integer", "constraints": "array",
    },
    "trace constraint-neighborhood": {
        "root": "string", "nodes": "array", "relations": "array",
        "paths": "object", "summary": "object",
    },
    "trace tb-join": {
        "tb_field": "string", "leaf": "string", "constraints": "array",
        "join_status": "string", "rtl_candidates": "array", "note": "string",
    },
    "trace frontier": {
        "signal": "string", "frontier": "array",
        "summary": "object", "note": "string",
    },
    "trace constraint-chain": {
        "found": "boolean", "source": "string", "target": "string",
        "rand": "object", "hop_count": "integer", "chain": "array",
        "segments": "array", "blocks": "array", "summary": "object",
        "note": "string",
    },
    "trace covergroups": {
        "count": "integer", "covergroups": "array",
        "complete": "boolean", "reason": "string",
    },
    "trace coverpoints": {
        "signal": "string", "count": "integer", "matches": "array",
        "complete": "boolean", "reason": "string",
    },
    "controlflow list-conditioned": {
        "signals": "array", "count": "integer",
    },
    "verify consistency": {
        "verified": "boolean", "coverage_complete": "boolean",
        "partial_checks": "array", "total_violations": "integer",
        "unknown_checks": "array", "checks": "array",
    },
    "verify structural": {
        "verified": "boolean", "coverage_complete": "boolean",
        "partial_checks": "array", "unknown_checks": "array",
        "findings": "array", "total": "integer", "truncated": "boolean",
        "coverage": "object", "checks": "array",
    },
    "scope": {
        "scope": "string", "canonical_id": "string", "kind": "string",
        "module_type": "string", "parent": ["string", "null"],
        "children": "array", "ports": "array", "parameters": "array",
        "signals": "array", "members": "array", "instances": "array",
    },
    "filelist prune": {
        "top": "string", "total_files": "integer", "selected_files": "array",
        "selected_count": "integer", "dropped": "integer", "reason": "string",
        "declarations": "object", "output": "string", "written": "boolean",
        "dry_run": "boolean", "backup": ["string", "null"],
        "requires_apply": "boolean",
    },
    "graph subgraph": {
        "nodes": "array", "edges": "array", "boundary": "array",
        "truncated": "object", "stats": "object",
    },
}
TYPE_SOURCES = {
    "stats": "stats_result",
    "graph nodes": "graph_nodes_result",
    "graph edges": "graph_edges_result",
    "verify claim": "verify_claim_result",
    "dataflow analyze": "dataflow_result",
    "trace evidence": "evidence_result",
    "trace profile": "profile_result",
    "trace lookup": "lookup_result",
    "trace manifest": "manifest_result",
    "graph subgraph": "subgraph_result",
}
TYPE_VARIANTS = (
    ("trace covergroup --rand", "trace covergroup",
     ("trace", "covergroup", "cg_env", "--instance", "top.e",
      "--rand", "-f", envelope.FIX_MIXED, "--json")),
    ("dataflow analyze no-path", "dataflow analyze",
     ("dataflow", "analyze", "sync_fifo.clk", "sync_fifo.data_out",
      "-f", envelope.FIX_SYNC_FIFO, "--json")),
)


def _schema_type(meta: object) -> object:
    """Translate a JSON_CONTRACT field spec into a JSON Schema type."""
    if isinstance(meta, str):
        return "object" if meta == "bit_normalization" else meta
    declared = meta.get("type") if isinstance(meta, dict) else None
    if not isinstance(declared, str):
        return "object"
    if declared.startswith("array"):
        return "array"
    if "|" in declared:
        return declared.split("|")
    enum = meta.get("enum") if isinstance(meta, dict) else None
    if enum:
        return {"type": declared, "enum": list(enum)}
    return declared


def _type_specs(command: str) -> dict[str, object]:
    specs = dict(TYPE_SCHEMAS[command])
    source = TYPE_SOURCES.get(command)
    if source:
        for field, meta in JSON_CONTRACT[source].items():
            if field in specs:
                specs[field] = _schema_type(meta)
    return specs


def value_type_schema(command: str) -> dict:
    base = result_key_schema(command)
    properties = {}
    for field, spec in _type_specs(command).items():
        if isinstance(spec, str):
            properties[field] = {"type": spec}
        elif isinstance(spec, list):
            properties[field] = {"type": spec}
        else:
            properties[field] = dict(spec)
    base["properties"] = properties
    return base


def validate_value_payload(command: str, payload: object, validator=None) -> list[str]:
    if not isinstance(payload, dict):
        return [f"result is {type(payload).__name__}, expected object"]
    validator = validator or jsonschema.Draft202012Validator(value_type_schema(command))
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
    return [f"{e.message} at {list(e.absolute_path)}" for e in errors[:5]]


def run_schema_types(execute=None) -> tuple[list[str], int]:
    problems: list[str] = []
    execute = execute or envelope.run_cli_case_with_env
    covered = 0
    with tempfile.TemporaryDirectory(prefix="svq_p182_2c_") as snapshot_dir:
        env = dict(os.environ, SVQ_SNAPSHOT_DIR=snapshot_dir)
        for case in envelope.CORE_SUCCESS_MANIFEST:
            if case.command not in TYPE_SCHEMAS:
                continue
            covered += 1
            root, case_problems = _run_case(case, execute, env)
            problems.extend(f"{case.command}: {p}" for p in case_problems)
            if root is not None:
                problems.extend(
                    f"{case.command}: {p}" for p in
                    validate_value_payload(case.command, root.get("result"))
                )
        for label, command, argv in TYPE_VARIANTS:
            run = execute(argv, env)
            if run.rc != 0:
                problems.append(f"{label}: rc={run.rc}, expected 0")
                continue
            root, parse_problems = envelope._parse_root(run)
            if root is not None and root.get("ok") is not True:
                parse_problems.append(f"ok={root.get('ok')!r}, expected true")
            problems.extend(f"{label}: {p}" for p in parse_problems)
            if root is not None:
                problems.extend(
                    f"{label}: {p}" for p in
                    validate_value_payload(command, root.get("result"))
                )
            covered += 1
    expected = len(envelope.CORE_SUCCESS_MANIFEST) + len(TYPE_VARIANTS)
    if covered != expected:
        problems.append(f"covered {covered} cases, expected {expected}")
    return problems, covered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema-core", action="store_true",
                        help="validate the 26 core standard success cases")
    parser.add_argument("--schema-results", action="store_true",
                        help="validate per-command result keys for 26 core standard cases")
    parser.add_argument("--schema-types", action="store_true",
                        help="validate high-value result value types")
    args = parser.parse_args(argv)
    if not (args.schema_core or args.schema_results or args.schema_types):
        parser.error("use --schema-core, --schema-results or --schema-types")
    manifest_problems = envelope.matrix_manifest_problems()
    if args.schema_types:
        problems, total = run_schema_types()
        label = "schema-types"
    elif args.schema_results:
        problems, total = run_schema_results()
        label = "schema-results"
    else:
        problems, total = run_schema_core()
        label = "schema-core"
    problems = [f"manifest: {p}" for p in manifest_problems] + problems
    if problems:
        for problem in problems:
            print(f"FAIL\t{problem}")
        print(f"{label}: FAIL ({len(problems)} problems / {total})")
        return 1
    print(f"{label}: PASS ({total}/{total})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
