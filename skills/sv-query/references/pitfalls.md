# Verified pitfalls (short + long task corpora)

Each item was observed in the local task corpora or reproduced in 2026-11-15 review.

1. **Missing `--depth 1`**  
   `drivers X` without depth recurses to terminals and mixes sources. For direct
   neighbor questions always pass `--depth 1`. Check `distance==1`.

2. **`paths` is undirected by default**  
   `paths A B` may return a structural path in either direction. Use `--directed`
   for dataflow. Pico example: undirected bvalid→mem_valid looked 2 hops; directed
   reality is 12 hops.

3. **Ternary/mux is not a data path**  
   `paths` traverses DRIVER/CONNECTION; `OP_TERNARY`/`BRANCH_*` are control edges.
   Frozen task ground truths that expect `.ternary_*` in a path are stale
   (P158.1 change); report current canonical path and note the semantic change.

4. **`drivers --depth 1` can include CLOCK/RESET/constant sources**  
   This is the current behavior even without `--include-clock/reset`. Inspect node
   `kind` and `trace profile`; filter sensitivity/constant nodes if the question
   asks data drivers. `loads` excludes CLOCK/RESET by default; add
   `--include-clock --include-reset` to see clock loads.

5. **Bare names resolve `relative`**  
   `clk` can resolve to 0 results; use `top.clk` / canonical id. Use `instances`
   and `drivers` ids, not filename-local names.

6. **`count` is post-cap**  
   With `--max-results`, `count` is capped and `pre_filter_count` is the true count;
   `truncated=true`. Do not report “no more neighbors” without checking.

7. **Evidence ≠ declaration**  
   `trace evidence` points to assignment/always line; `trace profile.source` points
   to declaration. Snapshot evidence may be null. Never dump `enclosing_chain`
   wholesale; extract `source_location`/`source_text`.

8. **Evidence trust is limited**  
   `credibility_score` is one of `{0.0,0.2,0.4,0.6,0.8,1.0}`; `is_verified` is a
   snippet+expr/name check. Neither is a proof. A 0.4/0.6 result needs human review.

9. **Semantic commands are source-only**  
   `class`, `trace constraints`, `trace covergroups`, `controlflow analyze` do not
   accept `--from-snapshot` (see [snapshot.md](snapshot.md)). Class members need
   instance-qualified ids (`top.e.p.addr`, not `p.addr`).

10. **Coverpoint reverse lookup can fail**  
    `trace coverpoints <instance member>` may return `count=0` with
    `reason=relative_class_property`. Build the mapping forward from
    `trace covergroups` / `trace covergroup --instance --rand`; do not claim no
    coverage from a reverse lookup alone.

11. **`audit` is exp/heuristic**  
    `audit --checks cdc,risk` is hidden, unstable, and not a fact. It does not
    return evidence; do not present its CDC/risk findings as verified.

12. **`-q` is not a guarantee**  
    Some lower-level warnings can still reach stderr. Always parse stdout separately.
