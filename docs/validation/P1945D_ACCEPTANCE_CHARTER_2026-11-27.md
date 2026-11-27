# P194.5d acceptance charter — defensible external benchmark

> **Status**: charter only. P194.5d remains `<阻塞>` until every acceptance
> gate below is satisfied; no benchmark claim is made by this document.

## 1. Question

Does `sv_query`, compared with source-only and grep/ctags baselines, reduce the
**total token cost and wall-clock time** for correct cross-module RTL queries on
**external** projects, without reducing correctness?

## 2. Dataset

- At least **3 heterogeneous external projects** (different vendors/authors;
  not canonical `sim/tests/fixtures`, not projects used to design P194.5).
- Pin project commit, filelist, include dirs, defines, and top module in a
  machine-readable manifest.
- At least one large project where a single source read does not fit the
  baseline context budget.
- Record license and a desensitized fixture story; no proprietary RTL.

## 3. Tasks and ground truth

- At least **10 tasks per project**, **30 tasks total**, covering:
  drivers, loads, paths, bit-select, cross-module, evidence, and a negative
  control (no path / unknown endpoint).
- Each task has an independent oracle: simulation/Verilator, a manually
  reviewed golden answer, or a reproducible structural script. The oracle
  author must not be the query author.
- Blind adjudication: the grader sees answers without knowing which arm
  produced them.
- Correctness is exact for canonical ids and required fields; partial/coarse
  answers are counted as failures unless the charter requires an explicit
  `unknown` and the arm returns it.

## 4. Arms and controls

- `source-only`: agent may read files but not run sv_query.
- `grep/ctags`: agent may use text search/navigation only.
- `sv_query`: agent may use sv_query CLI/session.
- Same model, provider, version, temperature, system prompt, task budget, and
  retry policy for every arm. At least **3 independent runs** per task/arm.
- Arms run on the same machine/container image; tool versions pinned.

## 5. Token accounting

- Use the provider's **actual tokenizer/usage** (input + output + cache
  creation/read as reported), not bytes/4.
- Include system prompt, user task, tool definitions, tool calls and results,
  and final answer. Report per phase and total.
- Report cost in USD if pricing is available; otherwise state unavailable.
- Capability-discovery overhead (`capabilities`) is charged to the sv_query
  arm, not hidden.

## 6. Metrics and acceptance

Primary:

- task correctness rate (oracle-pass fraction);
- total provider tokens per correct task;
- wall-clock time per correct task.

Secondary: number of tool calls, bytes read, cache hit rate, failures/retries.

Acceptance requires **all**:

1. sv_query correctness is not worse than source-only by more than 2 percentage
   points (and ≥ source-only on the cross-module subset).
2. Median total tokens per correct task is lower than source-only with a
   bootstrap 95% CI excluding zero.
3. Median wall-clock per correct task is lower than source-only with a
   bootstrap 95% CI excluding zero.
4. Results are reported per project and in aggregate; no aggregate-only claim.

If any gate fails, P194.5d reports the negative result and remains unverified.

## 7. Artifacts and reproducibility

Commit or archive: dataset manifest, task prompts, oracle answers, raw provider
usage logs (desensitized), runner scripts, and an analysis notebook/script.
A clean-room rerun from the manifest must reproduce the aggregate table.

## 8. Dependencies and exit

P194.5d can start only after P194.5f–P194.5h are complete and the green gate at
`3380 passed / 0 failed` (or a documented successor) exists. It exits complete
only when §6 passes and the artifacts in §7 are present; otherwise it stays
blocked with the measured negative result.
