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

## Verified probes

- source profile: reading repo `README.md` → `Operation not permitted`;
- source profile: executing `sv_query` → denied;
- source/T2 DeepSeek on AXI fanin task → correct canonical IDs.

MiniMax quota recovered; a single-task source/T2 retry passed. The full
two-model 12x3 hard-isolated matrix is still **not** run.
