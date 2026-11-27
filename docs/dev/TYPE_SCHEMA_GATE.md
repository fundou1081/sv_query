# Static type + generated result-schema gate (P194.6)

## Scoped mypy

`pyproject.toml [tool.mypy]` checks a deliberately small, stable seam:

```text
src/sv_query/errors.py
src/sv_query/session.py
src/sv_query/trace/core/query/verification.py
```

`follow_imports = "skip"` and `ignore_missing_imports` keep the gate focused on
these typed boundaries; `check_untyped_defs` still checks bodies. The gate is
`python3 -m mypy` and is part of `tools/run_gates.sh`.

## Generated result schema

`tools/generated_result_schema.json` is generated from
`sv_query.cli._registry.JSON_CONTRACT` (result fields, optional fields, paths
mode variants) by:

```bash
python3 tools/gen_result_schema.py          # write
python3 tools/gen_result_schema.py --check  # drift gate
```

Do not edit the generated file. The registry remains the source of truth; the
schema is a machine-readable projection of required/optional result keys.
Type detail (`string`/`integer`/`null`) is not duplicated here; the generated
artifact deliberately carries keys only.
