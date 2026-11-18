"""D12 / P183.4 — Session error envelope ownership + single CLI mapping.

锁定五件事（R-D10 N1 / R-D11 N-3）：

1. `sv_query.errors` 是 Session 三个错误码 / `error.type` 的**唯一来源**；
   `cli.errors.ErrorCode` 逐值接纳同一组码（CLI 不再发出词表外 code）。
2. CLI 只有一个 adapter（`cli._session_adapter.fail_from_session`）把
   Session 失败响应映射到既有 `cli._output.fail`：
   - message 取 `error.message`（缺失/非法 → 显式 fallback）；
   - 未知 code → `E_INTERNAL`，原 code 保留在 `session_error_code`。
3. `capabilities` provider 失败**确实经过**该 adapter（rc=1、结构化 fail）。
4. 成功路径不变：6 个 case 与 D12 baseline `3642e64d` 的 stdout/stderr/rc
   逐字节一致。
5. `session.py` 仍不 import CLI/Typer/sys/os/env/`sv_query.trace`；
   `sv_query/errors.py` 零 import（层中立，连 stdlib 都不需要）。
"""
from __future__ import annotations

import ast
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC = PROJECT_ROOT / "src"
SESSION_PY = SRC / "sv_query" / "session.py"
ERRORS_PY = SRC / "sv_query" / "errors.py"
CAPABILITIES_REL = "cli/core/locate/capabilities.py"

#: D12 开工前的最后一个提交（baseline）。成功路径 A/B 的 oracle。
BASELINE_COMMIT = "3642e64d"

sys.path.insert(0, str(SRC))

import sv_query.errors as session_errors  # noqa: E402
from cli import _session_adapter  # noqa: E402
from cli.errors import ErrorCode  # noqa: E402
from sv_query.errors import (  # noqa: E402
    E_HANDLER_FAILED,
    E_INVALID_REQUEST,
    E_UNSUPPORTED_OP,
    SESSION_ERROR_CODES,
)
from sv_query.session import Session  # noqa: E402


# ---------------------------------------------------------------------------
# 1. 词表一致：sv_query.errors ↔ cli.errors.ErrorCode
# ---------------------------------------------------------------------------
def test_session_error_codes_are_exactly_the_three_used_by_session():
    assert SESSION_ERROR_CODES == {
        E_INVALID_REQUEST,
        E_UNSUPPORTED_OP,
        E_HANDLER_FAILED,
    }
    assert session_errors.ERROR_TYPES.keys() == SESSION_ERROR_CODES


@pytest.mark.parametrize(
    "code",
    [E_INVALID_REQUEST, E_UNSUPPORTED_OP, E_HANDLER_FAILED],
    ids=[E_INVALID_REQUEST, E_UNSUPPORTED_OP, E_HANDLER_FAILED],
)
def test_cli_error_code_accepts_every_session_code_with_the_same_value(code):
    assert code in set(ErrorCode)
    assert ErrorCode(code).value == code


def test_session_module_reexports_the_same_code_objects():
    import sv_query.session as session_module

    for name in ("E_INVALID_REQUEST", "E_UNSUPPORTED_OP", "E_HANDLER_FAILED"):
        assert getattr(session_module, name) == getattr(session_errors, name)


@pytest.mark.parametrize(
    "code", [E_INVALID_REQUEST, E_UNSUPPORTED_OP, E_HANDLER_FAILED]
)
def test_session_does_not_redefine_error_code_literals(code):
    """码值只允许在 sv_query/errors.py 写一遍，session.py 只引用名字。"""
    assert f'"{code}"' not in SESSION_PY.read_text(encoding="utf-8")


def test_session_failure_envelope_uses_the_shared_error_types():
    response = Session().execute({"op": "does_not_exist"})

    assert response["ok"] is False
    assert response["error_code"] == E_UNSUPPORTED_OP
    assert response["error"] == {
        "type": session_errors.ERROR_TYPES[E_UNSUPPORTED_OP],
        "message": "unsupported op: does_not_exist",
    }


# ---------------------------------------------------------------------------
# 2. 适配 helper：已知码 / 未知码 / message fallback / 成功响应拒绝
# ---------------------------------------------------------------------------
def _fail_payload(capsys, response, *, context="capabilities 查询失败"):
    import typer

    with pytest.raises(typer.Exit) as excinfo:
        _session_adapter.fail_from_session(
            response,
            json_output=True,
            pretty=False,
            context=context,
        )
    assert excinfo.value.exit_code == 1
    return json.loads(capsys.readouterr().out)


def test_known_session_code_is_passed_through_unchanged(capsys):
    payload = _fail_payload(
        capsys,
        {
            "ok": False,
            "op": "capabilities",
            "error_code": E_HANDLER_FAILED,
            "error": {"type": "HandlerFailed", "message": "provider boom"},
        },
    )

    assert payload == {
        "ok": False,
        "error": "capabilities 查询失败: provider boom",
        "error_code": E_HANDLER_FAILED,
    }


def test_unknown_session_code_becomes_e_internal_and_preserves_original(capsys):
    payload = _fail_payload(
        capsys,
        {
            "ok": False,
            "error_code": "E_FROM_THE_FUTURE",
            "error": {"type": "FutureFailure", "message": "new failure"},
        },
    )

    assert payload["ok"] is False
    assert payload["error_code"] == ErrorCode.E_INTERNAL.value
    assert payload["session_error_code"] == "E_FROM_THE_FUTURE"
    assert payload["error"] == "capabilities 查询失败: new failure"


@pytest.mark.parametrize(
    "error",
    [
        {"type": "InvalidRequest"},
        {"type": "InvalidRequest", "message": ""},
        {"type": "InvalidRequest", "message": 17},
        "not-a-mapping",
        None,
    ],
    ids=["missing", "empty", "non-str", "non-mapping", "none"],
)
def test_missing_or_invalid_message_uses_an_explicit_fallback(capsys, error):
    payload = _fail_payload(
        capsys,
        {"ok": False, "error_code": E_INVALID_REQUEST, "error": error},
    )

    assert payload["error_code"] == E_INVALID_REQUEST
    assert payload["error"] == (
        "capabilities 查询失败: session response has no error message"
    )


def test_missing_error_code_becomes_e_internal_and_records_the_raw_value(capsys):
    payload = _fail_payload(capsys, {"ok": False, "error": {"message": "boom"}})

    assert payload["error_code"] == ErrorCode.E_INTERNAL.value
    assert payload["session_error_code"] == "None"
    assert payload["error"] == "capabilities 查询失败: boom"


def test_success_response_is_rejected_not_silently_mapped_to_failure():
    with pytest.raises(TypeError):
        _session_adapter.fail_from_session(
            {"ok": True, "op": "version", "result": {}},
            json_output=True,
            pretty=False,
        )


def test_non_mapping_response_is_rejected():
    with pytest.raises(TypeError):
        _session_adapter.fail_from_session(
            "not-a-response",
            json_output=True,
            pretty=False,
        )


# ---------------------------------------------------------------------------
# 3. capabilities 失败路径确实经过 adapter
# ---------------------------------------------------------------------------
def test_capabilities_provider_failure_goes_through_the_adapter(monkeypatch):
    import typer

    from cli.core.locate import capabilities as mod

    def boom(**kwargs):
        raise RuntimeError("registry down")

    monkeypatch.setattr(mod, "to_json", boom)

    seen: dict[str, object] = {}

    def recording_fail(msg, json_output, pretty, **extra):
        seen.update(msg=msg, json_output=json_output, pretty=pretty, extra=extra)
        raise typer.Exit(code=1)

    monkeypatch.setattr(_session_adapter, "fail", recording_fail)

    with pytest.raises(typer.Exit) as excinfo:
        mod.capabilities(
            json_output=True, pretty=False, recommended=False, include_exp=False
        )

    assert excinfo.value.exit_code == 1
    assert "capabilities 查询失败: " in seen["msg"]
    assert "registry down" in seen["msg"]
    assert seen["json_output"] is True
    assert seen["pretty"] is False
    assert seen["extra"] == {"error_code": E_HANDLER_FAILED}


def test_capabilities_provider_failure_is_structured(monkeypatch, capsys):
    import typer

    from cli.core.locate import capabilities as mod

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
    assert payload["error"] == (
        "capabilities 查询失败: handler for op 'capabilities' raised "
        "RuntimeError: registry down"
    )
    assert "session_error_code" not in payload


def test_capabilities_provider_failure_human_path(monkeypatch, capsys):
    import typer

    from cli.core.locate import capabilities as mod

    def boom(**kwargs):
        raise RuntimeError("registry down")

    monkeypatch.setattr(mod, "to_json", boom)

    with pytest.raises(typer.Exit) as excinfo:
        mod.capabilities(
            json_output=False, pretty=False, recommended=False, include_exp=False
        )

    assert excinfo.value.exit_code == 1
    out = capsys.readouterr().out
    assert out.startswith("❌ capabilities 查询失败: ")
    assert "registry down" in out


# ---------------------------------------------------------------------------
# 4. 成功路径 A/B：baseline 3642e64d vs 当前实现
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
    "from cli.main import run\n"
    "sys.argv = ['sv_query', *cli_args]\n"
    "run()\n"
)


@pytest.fixture(scope="module")
def baseline_src(tmp_path_factory) -> Path:
    """用 `git archive` 导出 D12 baseline 的 `src/`（不碰工作区）。"""
    try:
        proc = subprocess.run(
            ["git", "archive", "--format=tar", BASELINE_COMMIT, "src"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            timeout=120,
        )
    except FileNotFoundError:
        pytest.skip("git 不可用，无法读取 baseline 快照")
    if proc.returncode != 0:
        pytest.skip(
            f"baseline 快照不可用: {proc.stderr.decode('utf-8', 'replace').strip()[:200]}"
        )

    root = tmp_path_factory.mktemp("d12_baseline")
    with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as archive:
        archive.extractall(root)
    src_root = root / "src"
    assert (src_root / CAPABILITIES_REL).is_file()
    return src_root


def _run_with_src(src_root: Path, args: tuple[str, ...]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", _RUNNER, str(src_root), *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_baseline_snapshot_really_differs_from_current_implementation(baseline_src):
    before = (baseline_src / CAPABILITIES_REL).read_text(encoding="utf-8")
    after = (SRC / CAPABILITIES_REL).read_text(encoding="utf-8")
    assert before != after, "A/B 的两侧必须是不同实现，否则断言无区分力"
    assert not (baseline_src / "cli" / "_session_adapter.py").exists()


def _normalise_intentional_paths_metadata(stdout: str) -> dict:
    """P182.1c deliberately reclassifies paths as direct; compare the rest."""
    data = json.loads(stdout)
    for command in data["commands"]:
        if command["name"] == "paths":
            command["envelope"] = "<P182.1c: direct>"
    policy = data.get("json_contract", {}).get("envelope_policy", {})
    exceptions = policy.get("exceptions")
    if isinstance(exceptions, list) and "paths" in exceptions:
        policy["exceptions"] = [x for x in exceptions if x != "paths"]
    commands = data.get("json_contract", {}).get("commands", {})
    for key in ("drivers", "loads", "trace fanin", "trace fanout",
                "trace covergroup", "filelist prune"):
        commands.pop(key, None)
    data.get("json_contract", {}).pop("dataflow_result", None)
    data.get("json_contract", {}).pop("stats_result", None)
    return data


@pytest.mark.parametrize("name,args", CASES, ids=[c[0] for c in CASES])
def test_capabilities_success_output_matches_baseline_except_paths_metadata(
    baseline_src, name, args
):
    before = _run_with_src(baseline_src, args)
    after = _run_with_src(SRC, args)

    assert before.returncode == after.returncode, (
        f"{name}: rc {before.returncode} -> {after.returncode}\n"
        f"stderr(before)={before.stderr[:500]}\nstderr(after)={after.stderr[:500]}"
    )
    if name.startswith("json"):
        current = json.loads(after.stdout)
        paths = next(c for c in current["commands"] if c["name"] == "paths")
        assert paths["envelope"] == "direct"
        assert "paths" in current["json_contract"]["envelope_policy"]["exceptions"]
        commands = current["json_contract"]["commands"]
        assert commands["drivers"]["result_fields"][:2] == ["signals", "total_signals"]
        assert commands["trace covergroup"]["optional_result_fields"] == [
            "links", "samples"]
        assert "output" in commands["filelist prune"]["optional_result_fields"]
        assert current["json_contract"]["dataflow_result"][
            "primary_latency_cycles"]["type"] == "integer|null"
        assert current["json_contract"]["stats_result"][
            "elaboration_errors"]["type"] == "array<object>"
        assert _normalise_intentional_paths_metadata(before.stdout) == \
            _normalise_intentional_paths_metadata(after.stdout)
    else:
        assert before.stdout == after.stdout, f"{name}: stdout changed"
    assert before.stderr == after.stderr, f"{name}: stderr changed"
    assert after.stdout, f"{name}: 输出不应为空（A/B 不能是同为空）"


def test_ab_cases_are_not_all_identical(baseline_src):
    default = _run_with_src(baseline_src, ("capabilities", "--json"))
    recommended = _run_with_src(baseline_src, ("capabilities", "--json", "--recommended"))
    include_exp = _run_with_src(baseline_src, ("capabilities", "--json", "--include-exp"))

    assert default.stdout != recommended.stdout
    assert default.stdout != include_exp.stdout
    assert len(include_exp.stdout) > len(default.stdout)


# ---------------------------------------------------------------------------
# 5. 层中立：session.py 仍无 CLI/全局态依赖；errors.py 零 import
# ---------------------------------------------------------------------------
FORBIDDEN_IMPORT_ROOTS = {
    "cli",
    "typer",
    "click",
    "argparse",
    "sys",
    "os",
    "importlib",
    "sv_query",
    "trace",  # relative `.trace...` == sv_query.trace
}


def _import_roots(path: Path) -> set[str]:
    """Absolute roots plus relative submodule roots (so `.trace` is caught)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_session_source_imports_no_cli_or_process_globals():
    roots = _import_roots(SESSION_PY)
    assert not (roots & FORBIDDEN_IMPORT_ROOTS), (
        f"session.py 不应 import {sorted(roots & FORBIDDEN_IMPORT_ROOTS)}"
    )


def test_errors_module_is_import_free():
    tree = ast.parse(ERRORS_PY.read_text(encoding="utf-8"))
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert imports == [], "sv_query/errors.py 必须零 import（层中立词表）"


def test_importing_errors_does_not_pull_cli_typer_or_engine():
    script = (
        "import sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import sv_query.errors\n"
        "loaded = [m for m in ('cli', 'typer', 'sv_query.trace') if m in sys.modules]\n"
        "print(','.join(loaded))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script, str(SRC)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "", f"import 副作用加载了: {proc.stdout.strip()}"


def test_cli_error_code_references_session_names_not_literal_only():
    """N-3: CLI must reference sv_query.errors names, not duplicate literals."""
    cli_errors = (SRC / "cli" / "errors.py").read_text(encoding="utf-8")
    for name in ("E_INVALID_REQUEST", "E_UNSUPPORTED_OP", "E_HANDLER_FAILED"):
        assert f'"{name}"' not in cli_errors
    assert ErrorCode.E_HANDLER_FAILED.value == session_errors.E_HANDLER_FAILED
