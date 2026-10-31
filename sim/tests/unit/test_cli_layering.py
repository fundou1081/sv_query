"""
test_cli_layering.py — [iter_231 P1] CLI 分层 / 规范入口 / 兼容别名 / 结构化契约

背景 (方豆 2026-09-09): 命令太多且平铺, 决定分层; 语义 core 的规范入口用**顶层关系名**
(drivers/loads), 老名 (trace fanin/trace fanout) 保留为兼容别名;
core 层命令必须有 --json (agent 契约)。

本文件锁定四件事:
  1. 注册表与 CLI 一致 (每个叶子命令要么是规范名, 要么是已声明别名) —— 防"偷偷加命令"
  2. drivers/loads 与 trace fanin/trace fanout **输出完全一致** (同一实现, 非双份)
  3. capabilities 的分层过滤 (默认 core; exp 需 --include-exp; --recommended 是子集)
  4. 本轮补的三条 core 结构化输出: search / snapshot save / snapshot delete
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# [iter_239 1b] 快照默认目录已在缓存目录 → 测试隔离 (否则写用户 home / 受限环境失败)
os.environ.setdefault("SVQ_SNAPSHOT_DIR", tempfile.mkdtemp(prefix="svq_snap_"))
os.environ["SVQ_SNAPSHOT_DIR"] = os.environ["SVQ_SNAPSHOT_DIR"]
RUN_CLI = str(PROJECT_ROOT / "run_cli.py")
SRC = str(PROJECT_ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

FIXTURE = "sim/tests/fixtures/golden_mini/inst_demo.sv"


def _run(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", RUN_CLI, *args], cwd=str(PROJECT_ROOT),
        capture_output=True, text=True, timeout=180,
    )


def _json(*args) -> dict:
    r = _run(*args)
    assert r.returncode == 0, f"rc={r.returncode}\nstdout={r.stdout[:400]}\nstderr={r.stderr[:400]}"
    return json.loads(r.stdout)


# ---------------------------------------------------------------------------
# 1. 注册表 = CLI 真相 (R1 的测试版)
# ---------------------------------------------------------------------------
class TestRegistryMatchesCli:
    def test_every_leaf_is_canonical_or_declared_alias(self):
        """每个 CLI 叶子命令都必须登记 (规范名或已声明别名) —— 防止命令偷偷平铺增加。"""
        import typer
        from cli._registry import ALIASES, COMMANDS
        from cli.main import app

        root = typer.main.get_command(app)
        leaves: list[str] = []

        def _walk(cmd, prefix=""):
            import click
            if isinstance(cmd, click.Group):
                for name, sub in cmd.commands.items():
                    _walk(sub, f"{prefix}{name} ")
            else:
                leaves.append(prefix.strip())

        _walk(root)
        known = {c.key for c in COMMANDS} | set(ALIASES)
        unknown = sorted(set(leaves) - known)
        assert not unknown, f"未分层命令: {unknown}"

    def test_aliases_resolve_to_registered_commands(self):
        """别名必须指向已登记的规范名 (防改名后留下悬空别名)。"""
        from cli._registry import ALIASES, COMMANDS

        keys = {c.key for c in COMMANDS}
        for alias, canon in ALIASES.items():
            assert canon in keys, f"别名 {alias} 指向未登记命令 {canon}"

    def test_drivers_loads_are_top_level(self):
        """规范入口在顶层 (方豆选的方案 a: 关系名而非方向名)。"""
        from cli._registry import canonical

        assert canonical("trace fanin") == "drivers"
        assert canonical("trace fanout") == "loads"
        # 顶层命令存在且可执行
        for cmd in ("drivers", "loads"):
            r = _run(cmd, "--help")
            assert r.returncode == 0, f"{cmd} --help rc={r.returncode}"


# ---------------------------------------------------------------------------
# 2. 别名 = 同一实现 (输出一致)
# ---------------------------------------------------------------------------
class TestAliasEquivalence:
    def test_drivers_equals_trace_fanin(self):
        a = _json("drivers", "inst_demo.a", "-f", FIXTURE, "--json")
        b = _json("trace", "fanin", "inst_demo.a", "-f", FIXTURE, "--json")
        assert a == b, "drivers 与 trace fanin 必须输出一致 (同一实现)"

    def test_loads_equals_trace_fanout(self):
        a = _json("loads", "inst_demo.a", "-f", FIXTURE, "--json")
        b = _json("trace", "fanout", "inst_demo.a", "-f", FIXTURE, "--json")
        assert a == b, "loads 与 trace fanout 必须输出一致 (同一实现)"

    def test_old_names_still_visible_in_help(self):
        """老名保留 (兼容), 不能静默消失。"""
        r = _run("trace", "--help")
        assert r.returncode == 0
        assert "fanin" in r.stdout and "fanout" in r.stdout


# ---------------------------------------------------------------------------
# 3. capabilities 分层过滤
# ---------------------------------------------------------------------------
class TestCapabilities:
    def test_schema_and_layers_present(self):
        d = _json("capabilities", "--json")
        assert d["schema_version"] == "1"
        assert set(d["layers"]) >= {"core", "view", "exp", "dev", "out"}
        assert any(c["name"] == "drivers" and c["layer"] == "core" for c in d["commands"])

    def test_exp_default_hidden(self):
        """[iter_327] 低完成度能力 (audit/diagnose/view) 降级 exp, 默认不提供。"""
        from cli._registry import COMMANDS
        exp_keys = {c.key for c in COMMANDS if c.layer == "exp"}
        assert {"audit", "diagnose", "visualize graph", "trace overview"} <= exp_keys
        default = _json("capabilities", "--json")
        assert not any(c["layer"] == "exp" for c in default["commands"])
        full = _json("capabilities", "--json", "--include-exp")
        assert exp_keys <= {c["name"] for c in full["commands"]}

    def test_view_not_included_by_default(self):
        """[iter_327] view 已并入 exp, 默认 capabilities 不列。"""
        d = _json("capabilities", "--json")
        assert not any(c["layer"] in ("view", "exp") for c in d["commands"])

    def test_experimental_commands_hidden_from_help(self):
        top = _run("--help").stdout
        assert "audit" not in top and "diagnose" not in top
        assert "visualize" not in top and "design" not in top
        trace_help = _run("trace", "--help").stdout
        assert "overview" not in trace_help

    def test_recommended_is_subset(self):
        d = _json("capabilities", "--json", "--recommended")
        all_d = _json("capabilities", "--json")
        rec = {c["name"] for c in d["commands"]}
        full = {c["name"] for c in all_d["commands"]}
        assert rec and rec <= full
        assert all(c["recommended"] for c in d["commands"])

    def test_readonly_and_stability_declared(self):
        d = _json("capabilities", "--json")
        core = d["layers"]["core"]
        assert core["readonly"] is True
        assert core["stability"] == "stable"
        assert core["schema_version"] == "1"


# ---------------------------------------------------------------------------
# 3.5 机械保障: CLI 模块不得遮蔽 builtin (R7 的测试版)
# ---------------------------------------------------------------------------
class TestNoBuiltinShadowing:
    def test_no_cli_module_shadows_builtin(self):
        """模块级 def list/dict/... 会劫持同模块的 builtin 调用 (iter_231 实测事故)。"""
        import ast
        import builtins

        names = set(dir(builtins))
        offenders: list[str] = []
        for path in sorted((PROJECT_ROOT / "src" / "cli").rglob("*.py")):
            if "__pycache__" in str(path):
                continue
            tree = ast.parse(path.read_text())
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                        and node.name in names:
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno} {node.name}")
        assert not offenders, f"遮蔽 builtin 的定义: {offenders}"


# ---------------------------------------------------------------------------
# 4. 本轮补的 core 结构化输出
# ---------------------------------------------------------------------------
class TestNewJsonContracts:
    def test_search_json(self):
        d = _json("search", "module", "-f", FIXTURE, "--json")
        assert d["keyword"] == "module"
        assert d["total_matches"] >= 1
        assert d["files"] and "lines" in d["files"][0]

    def test_search_text_mode_unchanged(self):
        """加 --json 不能改变文本模式 (老用户/老测试依赖它)。"""
        r = _run("search", "module", "-f", FIXTURE)
        assert r.returncode == 0
        assert "Total:" in r.stdout and "match(es)" in r.stdout

    def test_snapshot_save_delete_json(self, tmp_path):
        sv = tmp_path / "s.sv"
        sv.write_text("module s(input clk, output reg q); always_ff @(posedge clk) q <= ~q; endmodule\n")
        d = _json("snapshot", "save", str(sv), "--tag", "probe_iter231", "--json")
        assert d["ok"] is True and d["tag"] == "probe_iter231"
        assert isinstance(d["node_count"], int) and d["node_count"] > 0
        assert d["failed_files"] == []

        d2 = _json("snapshot", "delete", "probe_iter231", "--force", "--json")
        assert d2["deleted"] is True

    def test_snapshot_save_filelist_json(self, tmp_path):
        """[iter_231 regression] snapshot save --filelist 的 files 元数据必须正确。

        历史 bug (pre-existing, 本迭代暴露): `snapshot.py` 里 `def list(...)` 遮蔽 builtin
        `list` → `_get_tracer_from_filelist()` 里的 `list(sources.keys())` 变成"执行 list 命令"
        → 返回 None + 打印数万行快照表 → `files` 元数据一直为空。
        修法: 命令函数改名 list_cmd (显式 command("list"))。
        """
        fl = tmp_path / "p.f"
        fl.write_text(str(PROJECT_ROOT / FIXTURE) + "\n")
        d = _json("snapshot", "save", str(fl), "--filelist", str(fl),
                  "--tag", "probe_fl_iter231", "--json")
        assert d["files"] == 1, f"filelist 模式的 files 元数据应为 1, 实得 {d['files']}"
        assert d["node_count"] > 0
        _run("snapshot", "delete", "probe_fl_iter231", "--force")

    def test_snapshot_delete_missing_tag_json_reports_error(self):
        r = _run("snapshot", "delete", "no_such_tag_iter231", "--force", "--json")
        assert r.returncode != 0
        d = json.loads(r.stdout)
        assert d["ok"] is False and d["deleted"] is False


class TestCheckerSelfTest:
    """检查器自身能检出违规 (否则规则形同虚设)。"""

    @staticmethod
    def _load_checker():
        import importlib.util

        path = PROJECT_ROOT / "tools/check_cli_layers.py"
        spec = importlib.util.spec_from_file_location("_chk_cli_layers", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_r9_flags_local_output_helper(self, tmp_path):
        """R9: 命令模块自己定义 output_json 必须被检出。"""
        bad = tmp_path / "bad_cmd.py"
        bad.write_text("def output_json(data, pretty=False):\n    print(data)\n")
        chk = self._load_checker()
        hits = chk.local_output_helpers(bad)
        assert [n for _l, n in hits] == ["output_json"], hits

    def test_r9_allows_shared_output_module(self, tmp_path):
        """R9: cli/_output.py 里的定义是唯一合法位置。"""
        good = tmp_path / "_output.py"
        good.write_text("def emit_json(data, pretty=False):\n    print(data)\n")
        chk = self._load_checker()
        assert chk.local_output_helpers(good) == []

    def test_r9_passes_on_real_tree(self):
        """R9: 当前 src/cli 树必须零违规。"""
        chk = self._load_checker()
        offenders = []
        for path in chk.iter_cli_py():
            for lineno, name in chk.local_output_helpers(path):
                offenders.append(f"{path.name}:{lineno} {name}")
        assert offenders == [], offenders
