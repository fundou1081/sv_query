# Semantic domain: class / constraint / covergroup

These commands are **query** over semantic AST facts. They are not a solver and do
not prove coverage closure.

## Class / members

```bash
sv_query class <Class> --relations --filelist rtl.f --json -q
sv_query class <Class> --member <member> --filelist rtl.f --json -q
sv_query class <Class> --member <member> --filelist rtl.f --json -q
```

`class --member` takes a **member name** (`addr`), not an instance-qualified id.
It returns `candidates[]` (e.g. `top.e.p.addr`); `count=0` can mean “no graph
instance”, so report candidates. `class` has no `--instance` option;
`--instance` belongs to `trace covergroup`. For `trace constraints`, use the
instance-qualified id (`top.e.p.addr`).

## Constraints

```bash
sv_query trace constraints top.e.p.len --filelist rtl.f --json -q
sv_query trace constraint-neighborhood top.e.p.len --max-depth 6 --max-nodes 200 \
  --filelist rtl.f --json -q
sv_query trace constraint-chain top.e.p.addr top.e.p.len --filelist rtl.f --json -q
```

Fields to report: block id, `defined_in`, `inherited`, `vars`, `conditions`,
`expr_count`, `rand_vars`, `solve_before`, `dist`.

`class` member facts include `rand_mode` and declared `type`; use those for
rand/randc questions. `--instance` is **not** a `class` option.

This is **co-membership / declared constraints**, not SAT/UNSAT or an implication
proof.

## Covergroups

```bash
sv_query trace covergroups --filelist rtl.f --json -q
sv_query trace covergroup <cg> --instance <inst> --rand --filelist rtl.f --json -q
sv_query trace coverpoints <signal> --filelist rtl.f --json -q
```

`trace covergroup --rand` links coverpoints to declared constraints; `bins` are
definition facts, not simulation hits. Reverse `coverpoints` may be unresolved for
relative class members; build forward and state the limitation.

## Do not claim

- coverage generation (separate project);
- coverage closure / hit results (needs simulation);
- constraint UNSAT/UNIQUE proof (separate constraint solver project);
- typo candidates (separate rtl_typo_checker project).
