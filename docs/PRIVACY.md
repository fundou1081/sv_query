# Privacy and local-only operation — P193.8

> **Status**: current product contract, 2026-11-21.
> **Scope**: installed `sv_query` runtime (`src/`), not development scripts.

## 1. No telemetry, no RTL upload

`sv_query` does not include telemetry, analytics, crash-reporting, or a network
client in the installed runtime. Queries, RTL, filelists, snapshots and JSON
results stay on the local machine.

There is no opt-in telemetry endpoint. If telemetry is ever proposed, it must be
opt-in, documented in a release note, and must not upload RTL/query content.

## 2. Local cache / snapshots

Only local files are written:

```text
$SVQ_CACHE_DIR (or $XDG_CACHE_HOME/svq or ~/.svq/cache)
$SVQ_SNAPSHOT_DIR (or <cache_dir>/snapshots)
```

These contain derived graph/snapshot data, not source uploads. They can be
deleted by the user; see `sv_query snapshot --help`.

## 3. Output and logs

Normal output goes to stdout/stderr. Python logging is configured by the caller
and is not sent anywhere by sv_query.

## 4. Issue reports

Do not paste proprietary RTL into GitHub issues. Use the
[miss-report guide](MISS_REPORT_GUIDE.md) and a desensitized fixture or a
structural-only report.

## 5. Verification

```bash
python3 tools/check_no_telemetry.py
# no-telemetry: PASS (no network/telemetry imports in src/)
```

The gate covers `src/` imports and obvious telemetry markers. It is a static
guard, not a network sandbox.
