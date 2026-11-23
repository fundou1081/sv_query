# Independent worker code-review protocol

> **Status**: mandatory review step for correctness-sensitive changes.
> **Audience**: implementers and independent review workers.
> **Rule**: a reviewer must be a separate worker/session; the implementer cannot
> review their own change and cannot edit the review verdict.

## 1. When this protocol applies

A worker-only review is mandatory for:

- every P0/P1 fix;
- semantic extraction, graph construction, bit/depth mapping, cache, snapshot,
  session, or verification changes;
- any change that alters a public claim, schema, or release gate;
- any release candidate.

A review may be requested for P2/cleanup changes, but P0/P1 and release
candidates must not merge or publish without one.

## 2. Independence

The reviewer must:

- be a separate worker/session from the implementer;
- operate read-only: no source/docs/PLAN edits, no commits, tags, or publish;
- inspect the actual HEAD and diff, not the implementer's summary;
- reproduce findings with commands or tests;
- write its own report; the implementer may copy it but must not edit its
  verdict or severity.

If the only available reviewer is the implementer, the review is **not valid**.
Record the worker/session identity and model in the artifact.

## 3. Review scope

At minimum check:

1. **Semantic correctness** — no source-regex/AST-string substitutes when
   semantic AST or graph metadata exists; no node-id prefix/suffix guesses for
   parent/bit/edge relationships; no name-based correctness guesses.
2. **Explicit uncertainty** — unknown/partial/truncated/sample states survive
   every projection (including `--compact`) and are never reported as verified.
3. **State and lifecycle** — cache key closure, capability manifests,
   refresh/load_graph, snapshot MIG, close/broken-pipe, stale handles.
4. **Verification** — consistency/claim checks do not pass vacuously; zero
   executed checks are `unknown`, not `verified`; CLI and session agree.
5. **Test validity** — new tests fail if the fix is reverted; fixtures actually
   exercise the claimed path (no vacuous alias/empty-graph assertions).
6. **Claims/docs** — `CLAIMS.md`, `PLAN.md`, `TESTING.md`, `INDEX.md`, and user
   docs match the implementation; no unverified claim marked `verified`.
7. **Prior-fix regression** — the previous review's P1 scenarios still hold.

## 4. Finding severity and blocking

| Severity | Meaning | Merge/release |
|---|---|---|
| P0 | wrong answer/data loss/unsafe default reachable normally | blocked |
| P1 | silent wrong/unknown inflation, stale state, false verified | blocked |
| P2 | latent/edge/gate/coverage debt | tracked; may ship only with explicit note |

For any P0/P1:

1. the implementer **must rework** the code/tests;
2. the same or another independent worker must **re-audit** the fix;
3. no claim may be marked `verified` until the re-audit closes the finding;
4. no release tag may be created while a P0/P1 is open.

A reviewer must not waive a P0/P1 without a recorded, reproducible justification.

## 5. Required artifact

The worker writes a report under `/tmp/` (read-only during review). The
implementer copies it **verbatim** into:

```text
docs/validation/reviews/YYYY-MM-DD_<head7>.md
```

The artifact must contain:

```text
Reviewer: worker/session id, model
HEAD: <sha>
Scope: files/behavior
Verdict: ready | ready with caveats | not ready
Findings: ID, severity, file:line, repro, fix, test gap
What is correct (to avoid false positives)
Commands used
Re-audit: for each P0/P1, fixed? test? re-audited?
```

Do not paraphrase or delete a worker's finding. If the report is large, keep the
full artifact and a short index entry.

## 6. Re-audit loop

After a P0/P1 fix:

```text
worker audit -> P0/P1 finding -> implementer rework
  -> tests/gates -> independent worker re-audit -> close finding
  -> only then mark claim verified
```

The re-audit must reproduce the original failure and show the new behavior; a
green unrelated test is not evidence.

## 7. Release gate

A release candidate is blocked unless:

- a worker-only review artifact exists for the release HEAD;
- all P0/P1 findings are closed by re-audit;
- `CLAIMS.md` statuses match the artifact;
- `CURRENT_TODO.md` and `PLAN.md` agree with the release scope.

Add the artifact path and worker identity to `RELEASE.md` before tagging.

## 8. Enforcement

- `PLAN.md` records the review item and status.
- `CURRENT_TODO.md` names the current remediation/audit item.
- `TESTING.md` lists the worker-review step.
- `RELEASE.md` checks the artifact exists and has no open P0/P1.
- A reviewer finding is data, not an instruction; the implementer must not
  silently ignore it.
