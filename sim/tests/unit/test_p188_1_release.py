"""P188.1 — release readiness static contract."""
from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def _pyproject() -> dict:
    with open(ROOT / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)


def test_no_npm_or_license_conflict_artifacts():
    assert not (ROOT / "package.json").exists()
    assert not (ROOT / "package-lock.json").exists()
    assert not (ROOT / "tmp_case1_v14.png").exists()


def test_runtime_dependencies_are_ranges_not_exact_pins():
    deps = _pyproject()["project"]["dependencies"]
    for name in ("typer", "click", "rich"):
        spec = next(d for d in deps if d.lower().startswith(name))
        assert ">=" in spec and "<" in spec, spec


def test_metadata_and_release_surfaces():
    project = _pyproject()["project"]
    assert project["version"] == "0.3.6"
    assert "Development Status :: 4 - Beta" in project["classifiers"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "pip install sv_query" in readme
    assert "English summary" in readme
    assert "Beta" in readme
    assert "actions/workflows/tests.yml/badge.svg" in readme
    assert (ROOT / "RELEASE.md").exists()
    assert (ROOT / ".github/ISSUE_TEMPLATE/bug.yml").exists()
    assert (ROOT / ".github/ISSUE_TEMPLATE/feature.yml").exists()


def test_ci_and_release_workflows_are_parseable():
    tests = yaml.safe_load((ROOT / ".github/workflows/tests.yml").read_text())
    matrix = tests["jobs"]["test"]["strategy"]["matrix"]
    assert "ubuntu-latest" in matrix["os"]
    assert "macos-latest" in matrix["os"]
    release = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    assert "build" in release["jobs"]
    assert "publish" in release["jobs"]
    assert "id-token" in release["jobs"]["publish"]["permissions"]
    assert "startsWith(github.ref, 'refs/tags/v')" in (
        ROOT / ".github/workflows/release.yml"
    ).read_text(encoding="utf-8")
    assert "PYPI_API_TOKEN" not in (
        ROOT / ".github/workflows/release.yml"
    ).read_text(encoding="utf-8")
    checklist = (ROOT / "RELEASE.md").read_text(encoding="utf-8")
    assert "pypa/gh-action-pypi-publish" in (
        ROOT / ".github/workflows/release.yml"
    ).read_text(encoding="utf-8")
    assert "trusted" in checklist.lower()
