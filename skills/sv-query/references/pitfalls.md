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
   to declaration. Snapshot evidence is keyed but its `source_location` may be null. Never dump `enclosing_chain`
   wholesale; extract `source_location`/`source_text`.

8. **Evidence trust is limited**  
   `credibility_score` is one of `{0.0,0.2,0.4,0.6,1.0}`; `is_verified` is a
   snippet+expr/name check. Neither is a proof. A 0.4/0.6 result needs human review.

9. **Semantic commands are source-only**  
   `class`, `trace constraints`, `trace covergroups`, `controlflow analyze` do not
   accept `--from-snapshot` (see [snapshot.md](snapshot.md)). `class --member`
   takes a member name (`addr`); `trace constraints`/coverpoint queries use the
   instance-qualified id (`top.e.p.addr`).

10. **Coverpoint reverse lookup can fail**  
    `trace coverpoints <instance member>` may return `count=0` with
    `reason=relative_class_property`. Build the mapping forward from
    `trace covergroups` / `trace covergroup --instance --rand`; do not claim no
    coverage from a reverse lookup alone.

11. **`audit` is exp/heuristic**  
    `audit --checks cdc,risk` is hidden, unstable, and not a fact. It does not
    return evidence; do not present its CDC/risk findings as verified.

12. **`driver_count` is not `len(drivers)`**  
    It counts distinct DRIVER-edge sources (PORT_IN/CONST can count); it excludes
    CLOCK/RESET/CONNECTION/BRANCH and self. Use `count`/`drivers[].id` for the
    full direct-neighbor list.

13. **Driver claim orientation**  
    `{"type":"driver","signal":TARGET,"driver":SOURCE}`: `signal` is the target,
    `driver` is the source. Reversing them flips verified/contradicted.

14. **Control/mux edges need `branch`**  
    `graph subgraph --edge-kinds driver,connection` omits OP_TERNARY/branch edges.
    Use `--edge-kinds branch` and `graph nodes --kind OP_TERNARY`.

15. **`-q` is not a guarantee**  
    Some lower-level warnings can still reach stderr. Always parse stdout separately.
