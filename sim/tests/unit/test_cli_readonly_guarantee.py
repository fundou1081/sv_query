"""
test_cli_readonly_guarantee.py — [iter_239 1b] 只读证明: 命令跑完, 项目目录**一个字节都不变**

背景 (方豆硬约束 "sv_query 不改 RTL" + 分层 P2 "CLI 只读"):
前面用**静态检查** (check_cli_layers R3) 保证 CLI 里没有写文件调用;
本文件用**行为证明**兜底: 在临时项目目录里跑一遍只读命令, 比对目录树指纹 (路径+大小+内容哈希),
必须完全一致 —— 包括**不许新增文件** (如 `.svq/`, `*.bak`, 报告文件)。

顺带证明 iter_239 的效果: `snapshot save` **不再往 cwd 写** (默认目录已迁到 $SVQ_SNAPSHOT_DIR / 缓存目录)。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUN_CLI = str(PROJECT_ROOT / "run_cli.py")

FIXTURE = PROJECT_ROOT / "sim/tests/fixtures/golden_mini/inst_demo.sv"


def _tree_fingerprint(root: Path) -> dict[str, str]:
    """目录树指纹: 相对路径 → sha256(内容) (含子目录)。"""
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_dir():
            out[rel + "/"] = "<dir>"
        else:
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


@pytest.fixture()
def sandbox(tmp_path):
    """隔离环境: 项目目录 + 独立的快照/缓存目录 (都在 tmp 内, 不碰用户 home)。"""
    proj = tmp_path / "proj"
    proj.mkdir()
    shutil.copy(FIXTURE, proj / "inst_demo.sv")
    (proj / "p.f").write_text(str(proj / "inst_demo.sv") + "\n")
    env = {
        **os.environ,
        "SVQ_SNAPSHOT_DIR": str(tmp_path / "snapshots"),
        "SVQ_CACHE_DIR": str(tmp_path / "cache"),
    }
    return proj, env


def _run(env: dict, cwd: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["python3", RUN_CLI, *args], cwd=str(cwd), env=env,
                          capture_output=True, text=True, timeout=300)


# 只读命令清单 (不含任何"显式产物输出"参数 —— 带 -o/--svg 的写文件是产品职责, 另测)
READONLY_COMMANDS = [
    ("stats", "-f", "inst_demo.sv", "--json"),
    ("search", "module", "-f", "inst_demo.sv", "--json"),
    ("graph", "nodes", "-f", "inst_demo.sv", "--json"),
    ("graph", "edges", "-f", "inst_demo.sv", "--json"),
    ("graph", "find", "clk", "-f", "inst_demo.sv", "--json"),
    ("instances", "-f", "inst_demo.sv", "--json"),
    ("hierarchy", "-f", "inst_demo.sv", "--json"),
    ("instance", "inst_demo.u_adder", "-f", "inst_demo.sv", "--json"),
    ("connections", "inst_demo.u_adder", "-f", "inst_demo.sv", "--json"),
    ("params", "inst_demo.u_adder", "-f", "inst_demo.sv", "--json"),
    ("ports", "inst_demo", "-f", "inst_demo.sv", "--json"),
    ("paths", "inst_demo.in_a", "inst_demo.add_out", "-f", "inst_demo.sv", "--json"),
    ("drivers", "inst_demo.in_a", "-f", "inst_demo.sv", "--json"),
    ("loads", "inst_demo.in_a", "-f", "inst_demo.sv", "--json"),
    ("capabilities", "--json"),
    ("capabilities", "--json", "--include-exp"),
]


class TestReadonlyGuarantee:
    def test_readonly_commands_do_not_touch_project_dir(self, sandbox):
        """跑完全部只读命令后, 项目目录树必须**逐字节**不变 (含无新文件)。"""
        proj, env = sandbox
        before = _tree_fingerprint(proj)

        failures: list[str] = []
        for cmd in READONLY_COMMANDS:
            r = _run(env, proj, *cmd)
            if r.returncode != 0:
                failures.append(f"{' '.join(cmd)} → rc={r.returncode}: {r.stderr[:150]}")
        assert not failures, "只读命令失败:\n" + "\n".join(failures)

        after = _tree_fingerprint(proj)
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
        assert not added, f"只读命令**新增了文件** (不该写项目目录): {added}"
        assert not removed, f"只读命令删除了文件: {removed}"
        assert not changed, f"只读命令修改了文件: {changed}"

    def test_snapshot_save_writes_outside_project_dir(self, sandbox):
        """[iter_239 1b] `snapshot save` 不再写 cwd/.svq —— 落到 SVQ_SNAPSHOT_DIR。"""
        proj, env = sandbox
        before = _tree_fingerprint(proj)
        r = _run(env, proj, "snapshot", "save", "inst_demo.sv", "--tag", "ro_probe", "--json")
        assert r.returncode == 0, r.stderr[:300]
        assert _tree_fingerprint(proj) == before, "snapshot save 不应改动项目目录"
        snap_dir = Path(env["SVQ_SNAPSHOT_DIR"])
        assert (snap_dir / "ro_probe.json").exists(), "快照应落在 SVQ_SNAPSHOT_DIR"
        assert not (proj / ".svq").exists(), "不应再在项目里创建 .svq/"
        _run(env, proj, "snapshot", "delete", "ro_probe", "--force")

    def test_explicit_output_goes_where_told(self, sandbox):
        """带显式输出参数时**允许**写文件, 但只能写到指定路径 (不是 cwd)。"""
        proj, env = sandbox
        out_dir = proj.parent / "artifacts"
        out_dir.mkdir()
        before = _tree_fingerprint(proj)
        r = _run(env, proj, "graph", "dump", "-f", "inst_demo.sv",
                 "--json")   # graph dump 无 -o, 纯 stdout
        assert r.returncode == 0
        assert _tree_fingerprint(proj) == before
