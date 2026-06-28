#!/usr/bin/env python3
"""[Phase 2 B1 2026-06-28] Validate sv_query JSON output against llm_schema.json.

Usage:
    python tools/llm_schema_validate.py
    # validates all commands with sample inputs

Or programmatically:
    from tools.llm_schema_validate import validate_command
    validate_command("stats", {"file": "/tmp/tiny.sv"})

This script:
1. Loads tools/llm_schema.json
2. Runs each command with sample args + --json
3. Validates output against the command's result_schema
4. Reports pass/fail
"""
import json
import subprocess
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("jsonschema required: pip install jsonschema")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = ROOT / "tools" / "llm_schema.json"


def load_schema():
    with open(SCHEMA_FILE) as f:
        return json.load(f)


def run_command(args: list[str]) -> dict:
    """Run sv_query command and parse JSON output."""
    cmd = ["python3", "run_cli.py"] + args + ["--json", "-q"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=60)
    out = r.stdout.strip()
    if not out.startswith("{"):
        return {"_error": f"Non-JSON output: {out[:200]}", "_stderr": r.stderr[:200]}
    return json.loads(out)


def validate_command(name: str, schema: dict, args: list[str]) -> bool:
    """Run command, validate output. Return True if valid."""
    output = run_command(args)
    if "_error" in output:
        print(f"  ❌ {name}: {output['_error']}")
        return False

    cmd_name = output.get("command", "")
    if cmd_name != name:
        print(f"  ❌ {name}: command mismatch (got {cmd_name})")
        return False

    # Validate result_schema
    if "result" not in output:
        print(f"  ❌ {name}: missing 'result' field")
        return False

    # Schema for this specific command variant
    cmd_schema_key = name
    cmd_schema = schema["commands"].get(cmd_schema_key, {})
    if not cmd_schema:
        print(f"  ⚠️ {name}: no schema definition (skipping)")
        return True

    # Build per-command schema
    full_schema = {
        "$ref": f"#/commands/{cmd_schema_key}/result_schema"
    }

    # Validate with the loaded schema
    validator = jsonschema.Draft202012Validator(schema)
    try:
        validator.validate(output["result"], full_schema)
        print(f"  ✅ {name}: valid")
        return True
    except jsonschema.ValidationError as e:
        print(f"  ❌ {name}: {e.message}")
        return False


def main():
    schema = load_schema()
    print(f"Loaded schema v{schema['version']}")
    print()

    # Sample inputs for each command
    samples = [
        ("stats", ["stats", "-f", "/tmp/tiny.sv", "--no-strict"]),
        ("trace_fanin", ["trace", "fanin", "clk", "-f", "/tmp/tiny.sv", "--no-strict"]),
        ("trace_fanout", ["trace", "fanout", "clk", "-f", "/tmp/tiny.sv", "--no-strict"]),
    ]

    # Ensure test file exists
    Path("/tmp/tiny.sv").write_text("""
module top(input clk, input [7:0] data, output reg [7:0] q);
  always_ff @(posedge clk) q <= data;
endmodule
""")

    print("=== Validating commands ===")
    results = []
    for name, args in samples:
        results.append(validate_command(name, schema, args))

    print()
    if all(results):
        print(f"✅ All {len(results)} commands validated")
        return 0
    else:
        print(f"❌ {sum(1 for r in results if not r)}/{len(results)} commands failed validation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
