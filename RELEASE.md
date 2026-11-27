# Release checklist — sv_query

> Beta release process. Do not tag/publish until every blocking item is checked.

## 1. Preconditions

- [x] `PLAN.md` current item and release scope agree.
- [x] `CHANGELOG.md` has the release entry.
- [ ] Independent worker review artifact exists for HEAD, with no open P0/P1
  (see [CODE_REVIEW_PROTOCOL](docs/dev/CODE_REVIEW_PROTOCOL.md)).
- [x] Version in `pyproject.toml` is final (`0.3.7` for the current beta).
- [x] `docs/KNOWN_LIMITATIONS.md` is linked from README.
- [x] No `package.json` / `package-lock.json` at the repository root.
- [x] Dependency ranges are compatible ranges, not exact runtime pins.
- [x] CI matrix is green on Ubuntu and macOS for Python 3.11/3.12.

## 2. Local verification

```bash
python3 tools/check_release_version.py --tag vX.Y.Z
python3 -m pytest sim/tests/ -m "not opensource" -q -p no:randomly
bash tools/run_gates.sh
python3 -m build
python3 -m twine check dist/*
```

GitHub release workflow now has a blocking `release-check` job:
- validates pyproject/session/tag versions;
- runs the canonical gates;
- `build` needs `release-check`, and `publish` needs `build`.
A tag cannot publish if the gate or version check fails.

Install the built wheel into a clean venv and smoke it:

```bash
python3 -m venv /tmp/svq-release-venv
/tmp/svq-release-venv/bin/pip install dist/sv_query-*.whl
/tmp/svq-release-venv/bin/sv_query --help
/tmp/svq-release-venv/bin/sv_query capabilities --json >/dev/null
/tmp/svq-release-venv/bin/sv_query stats \
  --filelist sim/tests/fixtures/scheduler_minimal/filelist.f --json
```

## 3. PyPI setup (one-time)

- [x] PyPI project `sv_query` exists and is owned by the maintainer.
- [x] Trusted publisher configured for this GitHub repo and workflow:
  - owner: `fundou1081`
  - repo: `sv_query`
  - workflow: `release.yml`
  - environment: `pypi`
- [ ] No long-lived PyPI token is stored in the repository.
- [x] GitHub environment `pypi` exists.

## 4. Tag and publish

```bash
git checkout main
git pull
git tag -a v0.3.7 -m "sv_query 0.3.7 beta"
git push origin v0.3.7
```

Pushing a `v*` tag triggers `.github/workflows/release.yml`:

1. build sdist + wheel;
2. `twine check`;
3. trusted-publish to PyPI.

After publish:

```bash
pip index versions sv_query
python3 -m venv /tmp/svq-pypi-smoke
/tmp/svq-pypi-smoke/bin/pip install sv_query==0.3.7
/tmp/svq-pypi-smoke/bin/sv_query capabilities --json
```

Tag a GitHub Release with the changelog and KNOWN_LIMITATIONS link.

Published status (2026-11-20):

```text
sv_query 0.3.0  published (PyPI description stale README; superseded)
sv_query 0.3.1  published (corrected PyPI README/install)
sv_query 0.3.2  published (MissingTimeScale diagnostic fix)
sv_query 0.3.3  published (CLI namespace + external trial readiness)
sv_query 0.3.4  published (cache correctness + local graph session)
sv_query 0.3.5  published (P195 cache/session/width/release hardening)
sv_query 0.3.6  published (P196 snapshot/session correctness)
sv_query 0.3.7  pending tag (P194/P197/P198 correctness + docs)
```

## 5. Rollback

- PyPI releases are immutable: publish a patch version, do not overwrite.
- If the artifact is broken, yank the release on PyPI and publish a fixed patch.
- If the tag is wrong but nothing was published, delete the local/remote tag and retag.

## 6. Post-release

- [x] Update `docs/INDEX.md` current baseline if needed.
- [x] Add release link to `README.md` / CHANGELOG.
- [x] Restore the PyPI badge and `pip install sv_query` line in README after publish.
- [ ] Open follow-up issues for known limitations and external validation.
