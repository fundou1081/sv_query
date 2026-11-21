"""D11 / P183.4 — `capabilities` adapter via `Session` injected handlers.

锁定六件事:

1. `Session(handlers=...)` 把已注入 op 分派给 handler，handler **只调用一次**，
   收到原始 request；
2. 默认 `Session()` / 未注入 op → `E_UNSUPPORTED_OP`（不静默成功）；
3. handler 抛异常或返回非 mapping → 结构化 `E_HANDLER_FAILED`，无裸异常；
4. `version` 是 Session 内置 op，不可被 handler 覆盖（构造时显式报错）；
5. CLI `capabilities` 经 `Session.execute` 走 `sv_query.cli._registry.to_json` 单一数据源，
   失败路径走 `cli._output.fail`；
6. CLI A/B（subprocess，fixture 中 D11 baseline `capabilities.py` vs 当前实现）
   六个 case 的 stdout / stderr / 退出码逐字节一致。
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC = PROJECT_ROOT / "src"
SESSION_PY = SRC / "sv_query" / "session.py"

#: D11 pre-change file, archived as a fixture so clean clones do not need old git history.
BASELINE_COMMIT = "129035bd"
BASELINE_FILE = PROJECT_ROOT / "sim/tests/fixtures/baseline/d11_capabilities.py.txt"
CAPABILITIES_REL = "sv_query/cli/core/locate/capabilities.py"

sys.path.insert(0, str(SRC))

from sv_query.session import (  # noqa: E402
    E_HANDLER_FAILED,
    E_INVALID_REQUEST,
    E_UNSUPPORTED_OP,
    Session,
)


def _session(handlers=None) -> Session:
    return Session() if handlers is None else Session(handlers=handlers)


def _assert_error(response: object, code: str) -> dict:
    assert type(response) is dict
    payload = response
    assert payload["ok"] is False
    assert payload["error_code"] == code
    assert type(payload["error"]) is dict
    assert set(payload["error"]) == {"type", "message"}
    assert isinstance(payload["error"]["type"], str) and payload["error"]["type"]
    assert isinstance(payload["error"]["message"], str) and payload["error"]["message"]
    assert "result" not in payload
    return payload


# ---------------------------------------------------------------------------
# 1. 注入 handler：调用一次、收到原始 request、result 是普通 dict
# ---------------------------------------------------------------------------
def test_injected_handler_is_called_once_with_the_original_request():
    calls: list[object] = []

    def handler(request):
        calls.append(request)
        return {"value": 7}

    request = {"op": "echo", "request_id": "r-1"}
    response = _session({"echo": handler}).execute(request)

    assert len(calls) == 1
    assert calls[0] is request
    assert response == {
        "ok": True,
        "op": "echo",
        "request_id": "r-1",
        "result": {"value": 7},
    }
    assert type(response["result"]) is dict


def test_handler_result_is_a_copy_not_shared_with_the_handler():
    payload = {"value": 1}

    def handler(request):
        return payload

    response = _session({"echo": handler}).execute({"op": "echo"})
    payload["value"] = 2

    assert response["result"] == {"value": 1}


def test_handler_may_return_any_mapping_and_result_is_plain_dict():
    def handler(request):
        return MappingProxyType({"value": 3})

    response = _session({"echo": handler}).execute({"op": "echo"})

    assert type(response["result"]) is dict
    assert response["result"] == {"value": 3}


def test_handler_success_is_json_transportable():
    def handler(request):
        return {"nested": {"a": [1, 2, 3]}, "text": "中文"}

    response = _session({"echo": handler}).execute({"op": "echo"})
    assert json.loads(json.dumps(response)) == response


# ---------------------------------------------------------------------------
# 2. 未注入 / 未知 op
# ---------------------------------------------------------------------------
def test_default_session_supports_only_version():
    assert _session().execute({"op": "version"})["ok"] is True
    _assert_error(_session().execute({"op": "capabilities"}), E_UNSUPPORTED_OP)


def test_unknown_op_with_other_handlers_is_unsupported_and_not_called():
    calls: list[object] = []

    def handler(request):
        calls.append(request)
        return {}

    payload = _assert_error(
        _session({"other": handler}).execute({"op": "capabilities"}),
        E_UNSUPPORTED_OP,
    )
    assert payload["op"] == "capabilities"
    assert calls == []


def test_handler_op_still_validates_request_id():
    def handler(request):
        return {}

    payload = _assert_error(
        _session({"echo": handler}).execute({"op": "echo", "request_id": 7}),
        E_INVALID_REQUEST,
    )
    assert "request_id" not in payload


# ---------------------------------------------------------------------------
# 3. handler 失败 → 结构化 E_HANDLER_FAILED
# ---------------------------------------------------------------------------
def test_handler_exception_becomes_structured_error():
    def handler(request):
        raise RuntimeError("provider boom")

    response = _session({"echo": handler}).execute(
        {"op": "echo", "request_id": "r-2"}
    )

    payload = _assert_error(response, E_HANDLER_FAILED)
    assert payload["op"] == "echo"
    assert payload["request_id"] == "r-2"
    assert "RuntimeError" in payload["error"]["message"]
    assert "provider boom" in payload["error"]["message"]


@pytest.mark.parametrize("bad_result", [None, ["x"], "text", 3, object()])
def test_non_mapping_handler_result_becomes_structured_error(bad_result):
    def handler(request):
        return bad_result

    payload = _assert_error(
        _session({"echo": handler}).execute({"op": "echo"}),
        E_HANDLER_FAILED,
    )
    assert payload["op"] == "echo"


def test_hostile_handler_result_mapping_becomes_structured_error():
    class HostileMapping(Mapping):
        def __init__(self):
            pass

        def __getitem__(self, key):
            raise RuntimeError("hostile items")

        def __iter__(self):
            raise RuntimeError("hostile items")

        def __len__(self):
            return 1

    def handler(request):
        return HostileMapping()

    payload = _assert_error(
        _session({"echo": handler}).execute({"op": "echo"}),
        E_HANDLER_FAILED,
    )
    assert "hostile items" in payload["error"]["message"]


# ---------------------------------------------------------------------------
# 4. 构造期校验：内置 op 不可覆盖、handler 必须可调用、handlers 被复制
# ---------------------------------------------------------------------------
def test_version_handler_cannot_override_builtin_op():
    with pytest.raises(ValueError):
        Session(handlers={"version": lambda request: {}})


@pytest.mark.parametrize("handlers", [{"echo": None}, {"echo": 3}, {"": lambda r: {}}])
def test_invalid_handlers_are_rejected_at_construction(handlers):
    with pytest.raises((TypeError, ValueError)):
        Session(handlers=handlers)


def test_handlers_mapping_is_copied_at_construction():
    handlers = {"echo": lambda request: {"value": 1}}
    session = Session(handlers=handlers)

    handlers["echo"] = lambda request: {"value": 2}

    assert session.execute({"op": "echo"})["result"] == {"value": 1}


# ---------------------------------------------------------------------------
# 5. session.py 不依赖 CLI / process globals
# ---------------------------------------------------------------------------
FORBIDDEN_IMPORT_ROOTS = {"cli", "typer", "click", "argparse", "sys", "os", "importlib", "sv_query"}


def test_session_source_imports_no_cli_or_process_globals():
    tree = ast.parse(SESSION_PY.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])

    assert not (imported & FORBIDDEN_IMPORT_ROOTS), (
        f"session.py 不应 import {sorted(imported & FORBIDDEN_IMPORT_ROOTS)}"
    )


# ---------------------------------------------------------------------------
# 6. CLI 接线（进程内）：Session.execute 是唯一入口，to_json 是唯一数据源
# ---------------------------------------------------------------------------
def test_cli_capabilities_routes_through_session_once(monkeypatch, capsys):
    from sv_query.cli.core.locate import capabilities as mod

    recorded: dict[str, object] = {}

    class RecordingSession:
        def __init__(self, handlers=None):
            recorded["handlers"] = handlers

        def execute(self, request):
            recorded["request"] = dict(request)
            result = mod.to_json(
                include_exp=request["include_exp"],
                recommended_only=request["recommended"],
            )
            return {"ok": True, "op": "capabilities", "result": result}

    monkeypatch.setattr(mod, "Session", RecordingSession)

    mod.capabilities(
        json_output=True, pretty=False, recommended=True, include_exp=True
    )

    assert recorded["request"] == {
        "op": "capabilities",
        "recommended": True,
        "include_exp": True,
    }
    handlers = recorded["handlers"]
    assert isinstance(handlers, dict) and set(handlers) == {"capabilities"}

    expected = mod.to_json(include_exp=True, recommended_only=True)
    assert json.loads(capsys.readouterr().out) == expected


def test_cli_capabilities_provider_failure_is_structured(monkeypatch, capsys):
    import typer

    from sv_query.cli.core.locate import capabilities as mod

    def boom(**kwargs):
        raise RuntimeError("registry down")

    monkeypatch.setattr(mod, "to_json", boom)

    with pytest.raises(typer.Exit) as excinfo:
        mod.capabilities(
            json_output=True, pretty=False, recommended=False, include_exp=False
        )

    assert excinfo.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error_code"] == E_HANDLER_FAILED
    assert "registry down" in payload["error"]


def test_cli_capabilities_provider_rejects_non_bool_options():
    from sv_query.cli.core.locate import capabilities as mod

    assert mod._capabilities_provider({"recommended": True, "include_exp": True})[
        "schema_version"
    ] == "1"

    with pytest.raises(TypeError):
        mod._capabilities_provider({"recommended": "yes"})


# ---------------------------------------------------------------------------
# 7. CLI A/B（subprocess）：baseline 129035bd vs 当前实现
# ---------------------------------------------------------------------------
CASES = [
    ("json", ("capabilities", "--json")),
    ("json_pretty", ("capabilities", "--json", "--pretty")),
    ("json_recommended", ("capabilities", "--json", "--recommended")),
    ("json_include_exp", ("capabilities", "--json", "--include-exp")),
    ("human", ("capabilities",)),
    ("help", ("--help",)),
]

_RUNNER = (
    "import sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "cli_args = sys.argv[2:]\n"
    "from sv_query.cli.main import run\n"
    "sys.argv = ['sv_query', *cli_args]\n"
    "run()\n"
)


@pytest.fixture(scope="module")
def baseline_src(tmp_path_factory) -> Path:
    """把 fixture 中 D11 baseline 的 `capabilities.py` 覆盖到当前 src 副本上。"""
    if not BASELINE_FILE.is_file():
        pytest.fail(f"missing baseline fixture: {BASELINE_FILE}")
    root = tmp_path_factory.mktemp("d11_baseline") / "src"
    shutil.copytree(
        SRC,
        root,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    (root / CAPABILITIES_REL).write_text(
        BASELINE_FILE.read_text(encoding="utf-8"), encoding="utf-8",
    )
    return root


def _run_with_src(src_root: Path, args: tuple[str, ...]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", _RUNNER, str(src_root), *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=180,
        env=dict(os.environ),
    )


def test_baseline_snapshot_really_differs_from_current_implementation(baseline_src):
    baseline_text = (baseline_src / CAPABILITIES_REL).read_text(encoding="utf-8")
    current_text = (SRC / CAPABILITIES_REL).read_text(encoding="utf-8")
    assert baseline_text != current_text, "A/B 的两侧必须是不同实现，否则断言无区分力"


@pytest.mark.parametrize("name,args", CASES, ids=[c[0] for c in CASES])
def test_cli_output_is_byte_identical_to_baseline(baseline_src, name, args):
    before = _run_with_src(baseline_src, args)
    after = _run_with_src(SRC, args)

    assert before.returncode == after.returncode, (
        f"{name}: rc {before.returncode} -> {after.returncode}\n"
        f"stderr(before)={before.stderr[:500]}\nstderr(after)={after.stderr[:500]}"
    )
    assert before.stdout == after.stdout, f"{name}: stdout changed"
    assert before.stderr == after.stderr, f"{name}: stderr changed"
    assert after.stdout, f"{name}: 输出不应为空（A/B 不能是同为空）"


def test_ab_cases_are_not_all_identical(baseline_src):
    """六个 case 不是同一个输出：include-exp / recommended 确实改变 payload。"""
    default = _run_with_src(baseline_src, ("capabilities", "--json"))
    recommended = _run_with_src(baseline_src, ("capabilities", "--json", "--recommended"))
    include_exp = _run_with_src(baseline_src, ("capabilities", "--json", "--include-exp"))

    assert default.stdout != recommended.stdout
    assert default.stdout != include_exp.stdout
    assert len(include_exp.stdout) > len(default.stdout)


def test_error_type_values_are_explicitly_locked():
    """R-D10 N9 / R-D11 N-2: error.type is part of the public envelope."""
    def boom(request):
        raise RuntimeError("boom")

    assert Session().execute({})["error"]["type"] == "InvalidRequest"
    assert Session().execute({"op": "nope"})["error"]["type"] == "UnsupportedOperation"
    assert Session(handlers={"boom": boom}).execute({"op": "boom"})["error"]["type"] == "HandlerFailed"
