# Hard isolation probes (macOS sandbox-exec)

Purpose: run a **headless** DSH agent with OS-level filesystem/process denial,
not just a prompt that says "don't use sv_query".

## Profiles

- `source.sb`: allow default, deny read of the sv_query repo and the old
  `/tmp/lr_pilot` workspace, deny exec of the `sv_query` binary.
- `t2.sb`: allow default, deny read of `/tmp/lr_pilot`; treatment agents may
  use the repo (editable install needs `src/cli`) and `sv_query`.

## Run

```bash
export DEEPSEEK_API_KEY="$(...)"   # from DSH credentials; do not commit
export DSH_PERMISSION_MODE=danger-full-access

cd /tmp/lr_hard_ws
sandbox-exec \
  -D REPO=/Users/fundou/my_dv_proj/sv_query \
  -D PILOT=/tmp/lr_pilot \
  -D SVQ=/Users/fundou/miniconda3/bin/sv_query \
  -f tools/benchmark/hard_isolated/source.sb \
  dsh --profile headless "source-only task..."
```

`DSH_PERMISSION_MODE=danger-full-access` is required because the DSH-internal
bash sandbox backend is not available on this host; the **external**
`sandbox-exec` profile is the actual isolation boundary.

## Canonical-path audit

`/tmp` is a symlink to `/private/tmp`. Denying only `/tmp/lr_pilot` does not
deny `/private/tmp/lr_pilot` in `sandbox-exec`. Profiles deny both paths.

## Verified probes

- source profile: reading repo `README.md` → `Operation not permitted`;
- source profile: executing `sv_query` → denied;
- source/T2 DeepSeek on AXI fanin task → correct canonical IDs.

MiniMax quota recovered; after fixing canonical-path denial, both models'
source/T2 single-task probes passed. The full two-model 12x3 hard-isolated
matrix is still **not** run.

## Long-range runner (P81)

`tools/benchmark/run_long_range.py` stages only RTL + local filelists and uses:

- `source.sb` for source arm;
- `t2_long.sb` for T2, additionally denying repo benchmark/task JSON and docs.

```bash
python3 tools/benchmark/run_long_range.py \
  --tasks axi_araddr_neighbors --models DeepSeek-Flash --seed 1
```
