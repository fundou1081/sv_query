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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema-core", action="store_true",
                        help="validate the 26 core standard success cases")
    parser.add_argument("--schema-results", action="store_true",
                        help="validate per-command result keys for 26 core standard cases")
    args = parser.parse_args(argv)
    if not (args.schema_core or args.schema_results):
        parser.error("use --schema-core or --schema-results")
    manifest_problems = envelope.matrix_manifest_problems()
    if args.schema_results:
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
