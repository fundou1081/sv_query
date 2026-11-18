"""P189.1 — agent 入口文档自洽 gate (check_agent_docs.py) 回归测试。

反事实: 删掉路径校验/命令登记/计数/版本任一分支, 对应注入用例会变红。
"""
from __future__ import annotations

from pathlib import Path

from check_agent_docs import (
    REPO,
    collect_violations,
    find_hardcoded_counts,
    find_missing_paths,
    find_version_mismatches,
    main,
    normalize_command_tokens,
    unknown_commands,
)

FEATURE_SECTION = """
## 功能分层

| 层 | 命令 |
|---|---|
| **Scope** | `scope` / `class` |
| **Trace** | `drivers` / `trace evidence/profile/lookup/manifest` |
| **Class** | `class --relations` |
| **State** | `snapshot save/list/compare/delete` |
| **Locate** | `graph nodes/edges` |
"""

MIN_PYPROJECT = """[project]
requires-python = ">=3.11"
dependencies = ["pyslang>=11.0.0,<12.0.0"]
"""


def _make_repo(root: Path, readme: str) -> Path:
    for rel in ("AGENTS.md", "docs/USER_GUIDE.md"):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# doc\n", encoding="utf-8")
    (root / "README.md").write_text(readme, encoding="utf-8")
    (root / "pyproject.toml").write_text(MIN_PYPROJECT, encoding="utf-8")
    return root


def test_current_tree_passes(capsys):
    assert collect_violations(REPO) == []
    assert main(REPO) == 0
    assert "PASS" in capsys.readouterr().out


def test_grouped_commands_normalize_to_registered_keys():
    assert normalize_command_tokens("`trace evidence/profile/lookup/manifest`") == [
        "trace evidence", "trace profile", "trace lookup", "trace manifest"]
    assert unknown_commands(FEATURE_SECTION) == []


def test_unknown_command_fails(tmp_path, capsys):
    readme = FEATURE_SECTION + "| **Bad** | `not-a-command` / `graph nodes/frobs` |\n"
    root = _make_repo(tmp_path, readme)
    assert unknown_commands(readme) == ["not-a-command", "graph frobs"]
    assert main(root) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out and "not-a-command" in out


def test_missing_relative_path_fails(tmp_path, capsys):
    readme = "# doc\n\n[gone](docs/missing.md) and `tools/nope.py`\n" + FEATURE_SECTION
    root = _make_repo(tmp_path, readme)
    missing = {raw for _doc, raw in find_missing_paths(readme, Path("README.md"), root)}
    assert missing == {"docs/missing.md", "tools/nope.py"}
    assert main(root) == 1
    assert "docs/missing.md" in capsys.readouterr().out


def test_ignored_reference_forms_are_not_checked(tmp_path):
    text = ("[http](https://example.com/x.md) [anchor](#section) "
            "[glob](docs/*.md) `sim/<file>` `src/{a,b}.py`")
    assert find_missing_paths(text, Path("README.md"), tmp_path) == []


def test_hardcoded_count_fails(tmp_path, capsys):
    readme = "# doc\n\n全量 **3019 passed** / 0 failed\n" + FEATURE_SECTION
    root = _make_repo(tmp_path, readme)
    assert find_hardcoded_counts(readme) == ["3019 passed"]
    assert find_hardcoded_counts("T2 48/48, 12 tests deferred") == []
    assert main(root) == 1
    assert "docs/INDEX.md" in capsys.readouterr().out


def test_version_declarations_must_match_pyproject(capsys):
    expected = {"python": (3, 11), "pyslang": (11, 0)}
    assert find_version_mismatches("Python 3.11+ / pyslang v11", expected) == []
    assert find_version_mismatches("Python 3.12+ / pyslang v12", expected) == [
        "Python 3.12", "pyslang v12"]
    assert find_version_mismatches("Python API", expected) == []


def test_declared_version_mismatch_fails(tmp_path, capsys):
    readme = "# doc\n\nPython 3.12+\n" + FEATURE_SECTION
    root = _make_repo(tmp_path, readme)
    assert main(root) == 1
    assert "Python 3.12" in capsys.readouterr().out
