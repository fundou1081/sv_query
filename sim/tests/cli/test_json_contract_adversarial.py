"""
test_json_contract_adversarial.py — [iter_201] JSON 契约对抗矩阵回归测试

来源: iter_200 对抗性测试发现的 4 个问题, iter_201 修复后固化为回归锁。

F1 --json 的错误路径必须给出**结构化错误信封** (过去 stdout 为空)
F2 --json + --svg 必须**显式告警** (过去静默丢弃产物)
F3 --json + --timing 必须**显式告警** (过去静默忽略语义)
F4 --max-paths 负值必须**报错** (过去静默当 0)
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
CORDIC = REPO / "sim" / "tests" / "fixtures" / "golden_mini" / "golden_dataflow_39_cordic_pipeline.v"
BINARY = REPO / "sim" / "tests" / "fixtures" / "hostile_input" / "binary.sv"
MISSING = REPO / "sim" / "tests" / "fixtures" / "hostile_input" / "fl_missing_entry.f"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO / "run_cli.py"), *args],
        capture_output=True, text=True, timeout=300, cwd=REPO,
    )


def _json_or_none(out: str):
    try:
        return json.loads(out)
    except Exception:
        return None


# ── F1: 错误路径的结构化信封 ────────────────────────────────────────────────
@pytest.mark.parametrize("name,args", [
    ("二进制文件", ["visualize", "pipeline", "-f", str(BINARY), "--json"]),
    ("文件不存在", ["timing", "analyze", "-f", str(REPO / "no_such.sv"), "--json"]),
    ("filelist 缺条目", ["visualize", "pipeline", "--filelist", str(MISSING), "--json"]),
])
def test_f1_error_path_emits_json_envelope(name, args):
    """F1: 请求了 --json 时, 错误也必须打结构化信封到 stdout。"""
    r = _run(args)
    assert r.returncode != 0, f"{name}: 应失败, rc={r.returncode}"
    payload = _json_or_none(r.stdout)
    assert payload is not None, f"{name}: stdout 不是 JSON (F1 回归): {r.stdout[:200]!r}"
    assert payload.get("ok") is False, payload
    assert "command" in payload and "error" in payload, payload
    assert payload["error"].get("type") and payload["error"].get("message"), payload


def test_f1_success_envelope_unchanged():
    """F1 反向: 成功路径信封不受影响 (ok=True + result)。"""
    r = _run(["visualize", "pipeline", "-f", str(CORDIC), "--json"])
    assert r.returncode == 0, r.stderr[-300:]
    payload = _json_or_none(r.stdout)
    assert payload and payload["ok"] is True and "result" in payload


# ── F2/F3: 被 --json 忽略的 flag 必须显式告警 ───────────────────────────────
@pytest.mark.parametrize("flag", ["--svg", "--timing"])
def test_f2_f3_ignored_flag_warns(flag, tmp_path):
    """F2/F3: --json 与输出/模式 flag 组合时必须告警 (不静默丢弃)。"""
    args = ["visualize", "pipeline", "-f", str(CORDIC), "--json"]
    if flag == "--svg":
        args += [flag, str(tmp_path / "out.svg")]
    else:
        args += [flag]
    r = _run(args)
    assert r.returncode == 0, r.stderr[-300:]
    assert "被忽略" in r.stderr, f"{flag}: 应显式告警, stderr={r.stderr[-300:]!r}"
    assert flag in r.stderr, r.stderr[-300:]
    if flag == "--svg":
        assert not (tmp_path / "out.svg").exists(), "被忽略时不应产出文件"


# ── F4: 参数校验 ────────────────────────────────────────────────────────────
def test_f4_negative_max_paths_rejected():
    """F4: --max-paths 负值必须报错 (过去静默当 0)。"""
    r = _run(["timing", "analyze", "-f", str(CORDIC), "--json", "--max-paths", "-1"])
    assert r.returncode != 0, f"负值应报错: {r.stdout[:200]}"
    assert "不能为负" in (r.stderr + r.stdout), (r.stderr[-300:], r.stdout[:200])


def test_f4_zero_max_paths_is_valid():
    """F4 反向: 0 是合法值 (不输出路径), 不能误报。"""
    r = _run(["timing", "analyze", "-f", str(CORDIC), "--json", "--max-paths", "0"])
    assert r.returncode == 0, r.stderr[-300:]
    payload = _json_or_none(r.stdout)
    assert payload and payload["result"]["critical_paths"] == []


# ── F5 (iter_202): --quiet 契约必须真的安静 ─────────────────────────────────
def test_f5_quiet_suppresses_all_stderr():
    """F5: `--quiet` 的契约是抑制所有 stderr (给 LLM 消费方)。

    iter_202 对抗测试发现: 实测仍泄漏 6 行 (Phase 3/4 进度 + pipeline 摘要)。
    """
    r = _run(["visualize", "pipeline", "-f", str(CORDIC), "--quiet"])
    assert r.returncode == 0, r.stderr[-300:]
    assert r.stderr.strip() == "", f"--quiet 下 stderr 必须为空, 实际: {r.stderr[:300]!r}"


def test_f5_quiet_keeps_errors_visible():
    """F5 反向: --quiet 不能把**错误**也吞掉 (失败仍要可见)。"""
    r = _run(["visualize", "pipeline", "-f", str(BINARY), "--quiet"])
    assert r.returncode != 0
    assert r.stderr.strip(), "错误信息不应被 --quiet 吞掉"


def test_f5_quiet_with_json_keeps_stdout_pure():
    """F5: --quiet + -j → stderr 全空, stdout 仍是纯 JSON。"""
    r = _run(["visualize", "pipeline", "-f", str(CORDIC), "--quiet", "-j"])
    assert r.returncode == 0, r.stderr[-300:]
    assert r.stderr.strip() == "", r.stderr[:300]
    payload = _json_or_none(r.stdout)
    assert payload is not None and payload["ok"] is True, r.stdout[:200]


# ── F6 (iter_203): `--format json` 必须给结构化 JSON ───────────────────────
ADV = REPO / "sim" / "tests" / "fixtures" / "hostile_input" / "macro_inst.sv"


@pytest.mark.parametrize("mode", ["fanin", "fanout"])
def test_f6_format_json_is_structured(mode):
    """F6: `--format json` 过去落到 text 分支 → stdout 是被 JSON 转义的**字符串**。

    实测 (修复前): `"Fanin of 'macro_top.a_q_q':\\n  (no drivers)\\n"`
    (一个 JSON 字符串, 不是对象) → 消费者无法取字段。
    """
    if not ADV.exists():
        pytest.skip(f"fixture 缺失: {ADV}")
    r = _run(["trace", mode, "macro_top.a_q_q", "-f", str(ADV), "--format", "json"])
    assert r.returncode == 0, r.stderr[-300:]
    payload = _json_or_none(r.stdout)
    assert payload is not None, f"--format json 必须是 JSON: {r.stdout[:200]!r}"
    assert isinstance(payload, dict), f"必须是 JSON 对象, 不是字符串: {type(payload).__name__}"
    assert payload.get("ok") is True and "command" in payload, payload


def test_f6_format_json_matches_json_flag():
    """F6: `--format json` 与 `--json` 必须给出同一结构 (单一实现)。"""
    if not ADV.exists():
        pytest.skip(f"fixture 缺失: {ADV}")
    a = _run(["trace", "fanin", "macro_top.a_q_q", "-f", str(ADV), "--format", "json"])
    b = _run(["trace", "fanin", "macro_top.a_q_q", "-f", str(ADV), "--json"])
    pa, pb = _json_or_none(a.stdout), _json_or_none(b.stdout)
    assert pa and pb
    assert set(pa.keys()) == set(pb.keys()), (sorted(pa), sorted(pb))


# ── R4-3 (iter_207): filelist 的 +incdir+ 必须传给编译器 ────────────────────
INCDIR_CASE = REPO / "sim" / "tests" / "fixtures" / "hostile_input" / "incdir_case"


@pytest.mark.parametrize("cmd", [["stats"], ["visualize", "graph"]])
def test_r4_3_filelist_incdir_applied(cmd):
    """R4-3: `--filelist` 的 `+incdir+` 过去被丢弃 → `include 失败 → 宏不展开。

    症状伪装成"宏 token paste 不生效"; 真因是 include 目录没传进编译器
    (iter_205 调查链证明); trace 路径 (走 SVCompiler.add_filelist) 一直正常。
    """
    fl = INCDIR_CASE / "fl_incdir.f"
    if not fl.exists():
        pytest.skip(f"fixture 缺失: {fl}")
    r = _run([*cmd, "--filelist", str(fl)])
    assert "Undeclared" not in r.stderr, f"{cmd}: +incdir+ 未生效\n{r.stderr[-400:]}"
    assert r.returncode == 0, f"{cmd}: rc={r.returncode}\n{r.stderr[-400:]}"


def test_r4_3_trace_path_unaffected():
    """R4-3 回归: trace 路径 (走 add_filelist) 不因本次改动而坏。"""
    fl = INCDIR_CASE / "fl_incdir.f"
    if not fl.exists():
        pytest.skip(f"fixture 缺失: {fl}")
    r = _run(["trace", "fanin", "top_inc.data_q", "--filelist", str(fl), "--json"])
    assert r.returncode == 0, r.stderr[-400:]
    payload = _json_or_none(r.stdout)
    assert payload and payload.get("ok") is True, r.stdout[:200]


# ── R4-1 (iter_209): filelist 内容经 `-f` 传入必须给明确提示 ───────────────
def test_r4_1_filelist_content_via_file_flag_warns():
    """R4-1: 非 .f 扩展名的 filelist 用 `-f` 传入 → 必须明确说"这是 filelist"。

    过去只给下游 elaboration 错误 + 已禁用的降级提示。
    两条经验教训 (iter_208 踩到, 已在实现里体现):
      ① 判据不能只看首行 (预处理器注入 `` `timescale `` 把 +incdir+ 挤到第 2 行);
      ② 裸路径判据要收紧 (endswith('.v') 会误判 `endmodule // x.v`)。
    """
    fl = INCDIR_CASE / "list_noext.txt"
    if not fl.exists():
        pytest.skip(f"fixture 缺失: {fl}")
    r = _run(["stats", "-f", str(fl)])
    assert r.returncode != 0, "filelist 当源码传应失败"
    assert "内容看起来是 filelist" in r.stderr, f"应明确提示是 filelist:\n{r.stderr[-300:]}"
    assert "请用 --filelist" in r.stderr, r.stderr[-300:]


@pytest.mark.parametrize("name", ["inst_demo.sv", "golden_dataflow_39_cordic_pipeline.v"])
def test_r4_1_legit_sources_not_misjudged(name):
    """R4-1 反向: 合法源码 (含 .v 语料与行尾注释) 不得被误判成 filelist。"""
    sv = REPO / "sim" / "tests" / "fixtures" / "golden_mini" / name
    if not sv.exists():
        pytest.skip(f"fixture 缺失: {sv}")
    r = _run(["stats", "-f", str(sv)])
    assert "内容看起来是" not in r.stderr, f"{name} 被误判:\n{r.stderr[-200:]}"
    assert r.returncode == 0, f"{name}: rc={r.returncode}\n{r.stderr[-300:]}"
