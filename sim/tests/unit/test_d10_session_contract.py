"""D10 / P183.4 — `Session.execute` request/response contract.

锁定四件事:

1. `version` 是唯一支持的只读 op，返回普通 dict + 结构化 result；
2. 所有非法输入（非 mapping、缺/坏 `op`、坏 `request_id`、未知 op）
   都返回结构化错误，不抛裸异常；
3. `request_id` 是可选字符串，合法时原样回显（成功和失败都回显）；
4. `sv_query.session` 不依赖 CLI / Typer / `sys.argv` / 环境变量 / 全局态，
   且 package version 常量与 `pyproject.toml` 不漂移。
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC = PROJECT_ROOT / "src"
SESSION_PY = SRC / "sv_query" / "session.py"

from sv_query import Session  # noqa: E402
from sv_query.session import (  # noqa: E402
    E_INVALID_REQUEST,
    E_UNSUPPORTED_OP,
    PACKAGE_VERSION,
    SESSION_CONTRACT_VERSION,
)
from sv_query.session import Session as ModuleSession  # noqa: E402


def _execute(request: object) -> dict:
    """测试统一入口：始终调用公开的 `Session.execute`。"""
    return Session().execute(request)  # type: ignore[arg-type]


def _assert_structured_error(response: object, code: str) -> dict:
    assert type(response) is dict, f"失败响应必须是普通 dict，实际 {type(response)!r}"
    payload = response
    assert payload["ok"] is False
    assert payload["error_code"] == code
    assert type(payload["error"]) is dict
    assert set(payload["error"]) == {"type", "message"}
    assert isinstance(payload["error"]["type"], str) and payload["error"]["type"]
    assert isinstance(payload["error"]["message"], str) and payload["error"]["message"]
    return payload


# ---------------------------------------------------------------------------
# 1. 合法 version
# ---------------------------------------------------------------------------
def test_version_returns_structured_success():
    response = _execute({"op": "version"})

    assert type(response) is dict
    assert response == {
        "ok": True,
        "op": "version",
        "result": {
            "schema_version": SESSION_CONTRACT_VERSION,
            "package_version": PACKAGE_VERSION,
        },
    }
    assert type(response["result"]) is dict
    # 输出必须可直接作为 JSON 传输
    assert json.loads(json.dumps(response)) == response


def test_version_constants_are_explicit_strings():
    assert isinstance(SESSION_CONTRACT_VERSION, str) and SESSION_CONTRACT_VERSION
    assert isinstance(PACKAGE_VERSION, str) and PACKAGE_VERSION


def test_package_version_does_not_drift_from_pyproject():
    """运行时显式常量与构建元数据是同一版本（独立 oracle）。"""
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert PACKAGE_VERSION == pyproject["project"]["version"]


def test_session_is_exported_from_package_namespace():
    assert Session is ModuleSession


# ---------------------------------------------------------------------------
# 2. request 结构错误
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("request_obj", [None, [], (), "version", 42, object()])
def test_non_mapping_request_returns_structured_error(request_obj):
    payload = _assert_structured_error(_execute(request_obj), E_INVALID_REQUEST)
    assert "op" not in payload
    assert "result" not in payload


def test_missing_op_returns_structured_error():
    payload = _assert_structured_error(_execute({}), E_INVALID_REQUEST)
    assert "op" not in payload


@pytest.mark.parametrize("bad_op", [None, 7, 3.14, True, ["version"], {"op": "version"}])
def test_non_string_op_returns_structured_error(bad_op):
    payload = _assert_structured_error(_execute({"op": bad_op}), E_INVALID_REQUEST)
    assert "op" not in payload
    assert "result" not in payload


def test_empty_string_op_returns_structured_error():
    payload = _assert_structured_error(_execute({"op": ""}), E_INVALID_REQUEST)
    assert payload["op"] == ""


# ---------------------------------------------------------------------------
# 3. 未知 op
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("unknown_op", ["does_not_exist", "stats", "Version"])
def test_unknown_op_returns_unsupported_error(unknown_op):
    payload = _assert_structured_error(_execute({"op": unknown_op}), E_UNSUPPORTED_OP)
    assert payload["op"] == unknown_op
    assert "result" not in payload


# ---------------------------------------------------------------------------
# 4. request_id 回显
# ---------------------------------------------------------------------------
def test_request_id_echoed_on_success():
    response = _execute({"op": "version", "request_id": "req-42"})
    assert response["ok"] is True
    assert response["request_id"] == "req-42"


def test_request_id_echoed_on_failure():
    response = _execute({"op": "does_not_exist", "request_id": "req-43"})
    payload = _assert_structured_error(response, E_UNSUPPORTED_OP)
    assert payload["request_id"] == "req-43"
    assert payload["op"] == "does_not_exist"


def test_empty_string_request_id_is_a_valid_string_and_echoed():
    response = _execute({"op": "version", "request_id": ""})
    assert response["ok"] is True
    assert response["request_id"] == ""


@pytest.mark.parametrize("bad_request_id", [None, 7, 3.14, True, ["req"], {"id": 1}])
def test_non_string_request_id_returns_structured_error(bad_request_id):
    payload = _assert_structured_error(
        _execute({"op": "version", "request_id": bad_request_id}),
        E_INVALID_REQUEST,
    )
    assert "request_id" not in payload
    assert "result" not in payload


# ---------------------------------------------------------------------------
# 5. 确定性与纯函数
# ---------------------------------------------------------------------------
def test_version_output_is_deterministic():
    first = _execute({"op": "version"})
    second = _execute({"op": "version"})
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_version_output_is_independent_of_environment(monkeypatch):
    baseline = _execute({"op": "version"})

    monkeypatch.setenv("SVQ_QUIET", "1")
    monkeypatch.setenv("SVQ_DEBUG", "1")
    monkeypatch.setenv("SVQ_CONFIG", "/definitely/not/a/config")
    monkeypatch.setenv("SVQ_SNAPSHOT_DIR", "/definitely/not/a/snapshot/dir")

    assert _execute({"op": "version"}) == baseline


def test_version_output_is_independent_of_sys_argv(monkeypatch):
    baseline = _execute({"op": "version"})

    monkeypatch.setattr(sys, "argv", ["sv_query", "not-a-command", "--json"])

    assert _execute({"op": "version"}) == baseline


def test_returned_result_is_not_shared_between_calls():
    first = _execute({"op": "version"})
    first["result"]["schema_version"] = "tampered"

    second = _execute({"op": "version"})
    assert second["result"]["schema_version"] == SESSION_CONTRACT_VERSION


# ---------------------------------------------------------------------------
# 6. 无 CLI / sys.argv 依赖（结构 + 子进程）
# ---------------------------------------------------------------------------
FORBIDDEN_IMPORT_ROOTS = {
    "cli",
    "typer",
    "click",
    "argparse",
    "sv_query",
    "sys",
    "os",
    "importlib",
}
FORBIDDEN_NAMES = {"_QUIET", "_ACTIVE_CONFIG"}
FORBIDDEN_ATTRIBUTES = {"sys.argv", "os.environ", "os.getenv"}


def _dotted_name(node: ast.AST) -> str | None:
    """展开 `a.b.c` 形式的属性链；不是纯名字链时返回 None。"""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def test_session_source_imports_no_cli_or_process_globals():
    tree = ast.parse(SESSION_PY.read_text(encoding="utf-8"))
    imported: set[str] = set()
    used_names: set[str] = set()
    used_attributes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            dotted = _dotted_name(node)
            if dotted:
                used_attributes.add(dotted)

    assert not (imported & FORBIDDEN_IMPORT_ROOTS), (
        f"session.py 不应 import {sorted(imported & FORBIDDEN_IMPORT_ROOTS)}"
    )
    assert not (used_names & FORBIDDEN_NAMES), (
        f"session.py 不应引用全局态 {sorted(used_names & FORBIDDEN_NAMES)}"
    )
    assert not (used_attributes & FORBIDDEN_ATTRIBUTES), (
        f"session.py 不应引用进程全局 {sorted(used_attributes & FORBIDDEN_ATTRIBUTES)}"
    )


def _run_py(code: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    prior = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + prior if prior else "")
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )


def test_importing_session_does_not_load_cli_or_typer():
    code = (
        "import json, sys\n"
        "sys.argv = ['sv_query', 'not-a-command', '--json']\n"
        "from sv_query import Session\n"
        "response = Session().execute({'op': 'version'})\n"
        "print(json.dumps({\n"
        "    'ok': response['ok'],\n"
        "    'cli_loaded': 'cli' in sys.modules,\n"
        "    'typer_loaded': 'typer' in sys.modules,\n"
        "}))\n"
    )
    result = _run_py(code)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {"ok": True, "cli_loaded": False, "typer_loaded": False}


def test_hostile_mapping_returns_structured_error_not_bare_exception():
    class HostileMapping(dict):
        def get(self, *args, **kwargs):
            raise RuntimeError("boom from mapping")

    response = _execute(HostileMapping())
    payload = _assert_structured_error(response, E_INVALID_REQUEST)
    assert "result" not in payload
    assert "boom from mapping" in payload["error"]["message"]
