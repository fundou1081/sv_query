#!/usr/bin/env python3
"""
coverage_gen_demo.py — Phase 1 POC

用 sv_query 现有信息 (risk --json) 自动生成 SystemVerilog covergroup。

输入: RTL 源文件 + 目标信号名
输出: 完整 covergroup (含 sample 条件, bins, cross)

策略:
  - DATA 信号 (width >= 8): 范围分 bin (zero/low/mid/high/max)
  - CONTROL 信号 (width < 8 或名字含 valid/ready/state/...): 离散 bin
  - cross: 主信号 x 相关 control 信号 (mode, valid 等)

用法:
  python tools/coverage_gen_demo.py <file> <signal> [<related_signal> ...]
  例: python tools/coverage_gen_demo.py sim/openTitan_validation.sv state_q mode_i valid_i
"""
import json
import re
import sys
from pathlib import Path


# =============================================================================
# Step 1: 用 sv_query risk --json 拿信号元信息
# =============================================================================
def query_risk_json(file: str) -> dict:
    import subprocess
    out = subprocess.run(
        ["python", "run_cli.py", "risk", "analyze", "-f", file, "--json"],
        capture_output=True, text=True, cwd=Path(__file__).parent.parent,
    )
    start = out.stdout.find("{")
    if start < 0:
        raise RuntimeError(f"risk analyze --json returned no JSON:\n{out.stdout[:500]}")
    return json.loads(out.stdout[start:])["result"]


def find_signal(sig_name: str, data_signals: list) -> dict | None:
    for s in data_signals:
        # sv_query 报 "state_q[2:0]" 这种带 bit-select, normalize 匹配
        bare = re.sub(r"\[.*?\]", "", s["name"])
        if bare == sig_name:
            return s
    return None


# =============================================================================
# Step 2: 从 RTL 拿精确 width (sv_query 简化成 1, 这里补回真实 width)
# =============================================================================
def parse_width_from_rtl(sig_name: str, file: str) -> tuple[int, int, int]:
    """返回 (width, hi, lo)"""
    src = Path(file).read_text()
    # 匹配多种位宽声明: logic [N:M] / reg [N:M] / wire [N:M] / input/output [N:M] / input/output logic [N:M]
    patterns = [
        # 1) [N:M] 在 type 关键字之前 (port 方向)
        rf"(?:input|output|inout)\s+(?:logic\s+)?\[(\d+):(\d+)\]\s+(?:\w+\s+)*{re.escape(sig_name)}\b",
        # 2) [N:M] 在 type 关键字之后
        rf"(?:logic|reg|wire)\s*\[(\d+):(\d+)\]\s+(?:\w+\s+)*{re.escape(sig_name)}\b",
        # 3) 无 [N:M] 1-bit
        rf"(?:logic|reg|wire|input|output)\s+(?:logic\s+)?(?:\w+\s+){0,2}{re.escape(sig_name)}\b",
    ]
    for i, p in enumerate(patterns[:2]):
        m = re.search(p, src)
        if m:
            return int(m.group(1)) - int(m.group(2)) + 1, int(m.group(1)), int(m.group(2))
    if re.search(patterns[2], src):
        return 1, 0, 0
    return 1, 0, 0  # default 1-bit


def parse_is_input_port(sig_name: str, file: str) -> bool:
    """检查信号是否是 module input port"""
    src = Path(file).read_text()
    return bool(re.search(rf"input\s+(?:logic\s+)?(?:\w+\s+)?(?:\w+\s+)?{re.escape(sig_name)}\b", src)) or \
           bool(re.search(rf"input\s+(?:logic\s+)?\[(\d+):(\d+)\]\s+(?:\w+\s+)*{re.escape(sig_name)}\b", src))


def parse_clock_reset(file: str) -> tuple[str | None, str | None]:
    src = Path(file).read_text()
    clk_m = re.search(r"input\s+(?:logic\s+)?(\w+)\s+(\w+_i|_i)\s*[,;]", src)
    # 简化: 找 "clk_i" / "clk" / 第一个 clock-like input
    clk = None
    rst = None
    for pat in [r"input\s+(?:logic\s+)?\w*\s*clk\w*", r"input\s+(?:logic\s+)?\w+\s+clk\w*"]:
        m = re.search(pat, src)
        if m:
            clk = re.search(r"clk\w+", m.group(0)).group(0)
            break
    for pat in [r"input\s+(?:logic\s+)?\w*\s*rst\w*", r"input\s+(?:logic\s+)?\w+\s+rst\w*"]:
        m = re.search(pat, src)
        if m:
            rst = re.search(r"rst\w+", m.group(0)).group(0)
            break
    return clk, rst


def parse_enums(file: str) -> dict[str, list[tuple[str, int]]]:
    """粗略提取 typedef enum 里的 enum 名 + 值 (用于 FSM state bin 命名)"""
    src = Path(file).read_text()
    result = {}
    for m in re.finditer(r"typedef\s+enum[^{]*\{([^}]+)\}\s*(\w+)\s*;", src):
        body = m.group(1)
        ty_name = m.group(2)
        items = []
        next_val = 0
        for line in body.split("\n"):
            line = line.strip().rstrip(",").rstrip(";").strip()
            if not line or line.startswith("//"):
                continue
            # 名字 (可选 = 值)
            mm = re.match(r"(\w+)(?:\s*=\s*(\d+)'?d?(\d+)|\s*=\s*(\d+))?", line)
            if not mm:
                continue
            n = mm.group(1)
            # 拿 value
            if mm.group(4):
                v = int(mm.group(4))
            elif mm.group(2) and mm.group(3):
                v = int(mm.group(3))  # 忽略 bit-width
            else:
                v = next_val
            items.append((n, v))
            next_val = v + 1
        if items:
            result[ty_name] = items
    return result


# =============================================================================
# Step 3: 信号分类 (data vs control)
# =============================================================================
_CONTROL_PATTERNS = [
    "valid", "ready", "stall", "ack", "req", "grant", "enable", "en_", "_en",
    "sel", "select", "we", "re", "cs", "ce", "we_i",
    "state", "next_state", "nxt_state", "state_q", "state_d",
    "mode", "op_mode",
    "done", "busy", "idle", "error", "fault", "alert", "trigger",
    "start", "stop", "flush", "flag", "status",
]


def classify(name: str, width: int) -> str:
    nl = name.lower()
    for p in _CONTROL_PATTERNS:
        if p in nl:
            return "CONTROL"
    if width >= 8:
        return "DATA"
    return "CONTROL"  # 1-bit default to control


# =============================================================================
# Step 4: bin 生成 (data vs control 策略不同)
# =============================================================================
def gen_bins_data(name: str, width: int) -> str:
    """DATA 信号: 范围分 bin (按 2^N 边界)"""
    if width == 32:
        return f"""    // DATA bins: 32-bit range partition
    bins zero  = {{32'h0}};
    bins byte  = {{[32'h1:32'hFF]}};          // 1-byte values
    bins word  = {{[32'h100:32'hFFFF]}};       // 2-byte values
    bins dword = {{[32'h10000:32'hFFFFFF]}};   // 3-byte values
    bins max   = {{32'hFFFF_FFFF}};"""
    if width == 16:
        return f"""    // DATA bins: 16-bit range partition
    bins zero = {{16'h0}};
    bins low  = {{[16'h1:16'hFF]}};
    bins mid  = {{[16'h100:16'h7FFF]}};
    bins high = {{[16'h8000:16'hFFFF]}};"""
    if width == 8:
        return f"""    // DATA bins: 8-bit range partition
    bins zero = {{8'h0}};
    bins low  = {{[8'h1:8'h7F]}};
    bins high = {{[8'h80:8'hFE]}};
    bins max  = {{8'hFF}};"""
    # generic
    return f"    bins auto = {{[0:{(1 << width) - 1}]}};  // width={width}"


def gen_bins_control(name: str, width: int, enums: dict, signal_enum: str | None) -> str:
    """CONTROL 信号: 离散 bin (用 enum 名字, 找不到就 generic)"""
    if signal_enum and signal_enum in enums:
        # 解析 enum names + 实际值 (从 typedef enum 里拿 N 或 N'hNN, 不再用 list index)
        # 返回 (name, value) list
        items = enums[signal_enum]  # list[tuple[name, value]] (重写 parse_enums)
        lines = [f"    // CONTROL bins (from enum {signal_enum}):"]
        used_vals = set()
        for n, v in items:
            lines.append(f"    bins {n.lower()} = {{{v}}};")
            used_vals.add(v)
        # 兜底: 未使用值
        max_v = (1 << width) - 1
        unused = sorted(set(range(max_v + 1)) - used_vals)
        if unused:
            lo, hi = min(unused), max(unused)
            lines.append(f"    bins reserved = {{[{lo}:{hi}]}};")
        return "\n".join(lines)
    if width == 1:
        return "    // CONTROL bins: 1-bit\n    bins low  = {1'b0};\n    bins high = {1'b1};"
    if width <= 4:
        max_v = (1 << width) - 1
        return f"""    // CONTROL bins: width={width} (1-of-N)
    bins zero  = {{0}};
    bins one   = {{1}};
    bins two   = {{2}};
    bins three = {{3}};
    bins other = {{[4:{max_v}]}};"""
    if width <= 7:
        max_v = (1 << width) - 1
        return f"""    // CONTROL bins: width={width} (1-of-N)
    bins zero  = {{0}};
    bins low   = {{[1:{max_v // 2}]}};
    bins high  = {{[{max_v // 2 + 1}:{max_v - 1}]}};
    bins max   = {{{max_v}}};"""
    # width 8+: 用 data bins
    return gen_bins_data(name, width)


# =============================================================================
# Step 5: 推断 sample 条件 (信号什么时候 stable)
# =============================================================================
# 启发式:
#   1. 名字含 vld/valid/req/ack/ready/grant/done → 需要 enable 配对
#   2. _q 后缀 (FF output) + width>=8 (data) → 找驱动它的 valid
#   3. _q 后缀 + width<8 (control/FSM) → sample 总是 1 (FSM state 本身总是 valid)
#   4. FSM state (enum 名字) → 1
#   5. 找不到 → None (sample 条件留空, 让用户填)

_VLD_SUFFIXES = ("valid", "vld", "req", "ack", "ready", "grant", "done")


def is_vld_signal(name: str) -> bool:
    """判定是否为 VLD 风格信号 (valid/req/ack/ready/grant/done)."""
    nl = name.lower()
    for suf in _VLD_SUFFIXES:
        # 名字: valid_o / valid_i / valid / din_valid / req_valid
        if nl == suf or nl.startswith(suf + "_") or nl.endswith("_" + suf):
            return True
    return False


_FF_SUFFIX = re.compile(r"_q$|_d$")


def infer_sample_condition(
    target: str,
    width: int,
    sig_class: str,
    related_signals: list[str],
    is_input_port: bool = False,
) -> tuple[str, str]:
    """
    返回 (sample_event, sample_caveat) 元组:
      - sample_event: 完整 sample 事件字符串 (含 @posedge clk 和可选 iff)
      - sample_caveat: 解释为什么这个 sample 条件是对的 (注释)

    策略 (保守):
      - 能确认 stable 条件 → 写 iff <cond>
      - 不能确认 → 只写 @posedge clk (不加 iff), 让用户填
    """
    clk = "clk_i"
    rst = "rst_ni"
    base = f"@(posedge {clk}"

    # 启发 1: VLD 信号 — 需要 enable/valid 配对
    if is_vld_signal(target):
        for r in related_signals:
            bare = re.sub(r"\[.*?\]", "", r)
            if bare in ("enable_i", "valid_i", "valid_o"):
                return f"{base} iff {bare} && !{rst})", f"VLD-style signal — stable when {bare}=1"
        return f"{base} iff !{rst})", "VLD-style signal — no enable pair found; sample every cycle (may be too eager)"

    # 启发 2: Input port — 总是 stable (testbench 给, 每个 cycle 都有效)
    if is_input_port:
        if sig_class == "DATA":
            return f"{base})", "Input port — stable every cycle (testbench-driven)"
        return f"{base} iff !{rst})", "Input port control — always stable when not in reset"

    # 启发 3: Data reg (_q/_d) — 找 valid
    if _FF_SUFFIX.search(target) and sig_class == "DATA":
        for r in related_signals:
            bare = re.sub(r"\[.*?\]", "", r)
            if "valid" in bare.lower() or "enable" in bare.lower():
                return f"{base} iff {bare} && !{rst})", f"Data reg — stable after upstream {bare}"
        return f"{base} iff !{rst})", "Data reg — no valid/enable gating found; sample every cycle (may be too eager)"

    # 启发 4: Control signal (FSM/enum) — 总是 sample
    if sig_class == "CONTROL":
        return f"{base} iff !{rst})", "Control signal (FSM/enum/flag) — always stable when not in reset"

    # 启发 5: default — 无法确认, 只写基础 clk
    return f"{base})", "Unknown — sample condition NOT inferred; please review and add 'iff ...' manually"


# =============================================================================
# Step 6: 找 cross 候选 (主信号的 fan-in 里的 control 信号)
# =============================================================================
_CONTROL_FOR_CROSS = {"mode_i", "valid_i", "valid_o", "enable_i", "trigger_i", "ready_i", "ready_o"}


def pick_cross_relations(main_sig: str, related: list[str], all_data_sigs: list[dict]) -> list[str]:
    """从 related 参数里挑出真正 control 的信号"""
    picked = []
    for r in related:
        bare = re.sub(r"\[.*?\]", "", r)
        if bare in _CONTROL_FOR_CROSS:
            picked.append(bare)
        else:
            # 用 classify 判断
            width, _, _ = parse_width_from_rtl(bare, _file_global)
            if classify(bare, width) == "CONTROL":
                picked.append(bare)
    return picked


# Globals for cross picker (since we need file path)
_file_global: str = ""


# =============================================================================
# Step 7: 主生成函数
# =============================================================================
def generate_covergroup(
    file: str,
    target_signal: str,
    related_signals: list[str] = None,
) -> str:
    related_signals = related_signals or []
    global _file_global
    _file_global = file

    risk = query_risk_json(file)
    sig_info = find_signal(target_signal, risk["data_signals"])
    width, hi, lo = parse_width_from_rtl(target_signal, file)
    clk, rst = parse_clock_reset(file)
    enums = parse_enums(file)
    sig_class = classify(target_signal, width)

    # 找 enum 名 (用于 CONTROL bin 命名)
    signal_enum = None
    for ty_name, names in enums.items():
        if target_signal.replace("_q", "").replace("_d", "") in ty_name.replace("_e", ""):
            signal_enum = ty_name
            break
        # 启发: 名字相似
        if ty_name.replace("_e", "") in target_signal:
            signal_enum = ty_name
            break

    # 找 cross 候选
    cross_sigs = pick_cross_relations(target_signal, related_signals, risk["data_signals"])

    # ---- 拼 covergroup ----
    sample_clk = clk or "clk"
    sample_rst = rst or "rst_n"
    # 判定是 input port 还是 internal
    is_input_port = parse_is_input_port(target_signal, file)
    # ★ Sample 条件推断 (保守策略: 能确认才写 iff, 不能确认留空)
    sample_evt, sample_caveat = infer_sample_condition(
        target_signal, width, sig_class, related_signals, is_input_port
    )

    risk_score = sig_info["func_score"] if sig_info else 0
    risk_level = sig_info.get("func_level", "MEDIUM") if sig_info else "MEDIUM"

    lines = []
    lines.append(f"// ======================================================================")
    lines.append(f"// Auto-generated covergroup for: {target_signal}")
    lines.append(f"//   class:     {sig_class}")
    lines.append(f"//   width:     {width} bits  (RTL: [{hi}:{lo}])")
    lines.append(f"//   risk:      {risk_score:.1f} ({risk_level})  fan_in={sig_info['fan_in'] if sig_info else '?'} fan_out={sig_info['fan_out'] if sig_info else '?'}")
    lines.append(f"//   generator: tools/coverage_gen_demo.py (Phase 1 POC)")
    lines.append(f"// ======================================================================")
    lines.append(f"covergroup cg_{target_signal} {sample_evt};")
    lines.append(f"  option.per_instance = 1;")
    lines.append(f"  option.comment = \"{target_signal} ({sig_class}, {width}-bit, risk={risk_score:.1f})\";")
    lines.append(f"")
    lines.append(f"  // ---- Primary coverpoint ----")
    lines.append(f"  cp_{target_signal}: coverpoint {target_signal} {{")

    if sig_class == "DATA":
        lines.append(gen_bins_data(target_signal, width))
    else:
        lines.append(gen_bins_control(target_signal, width, enums, signal_enum))
    lines.append(f"  }}")
    lines.append(f"")

    # ---- Cross coverpoints ----
    if cross_sigs:
        lines.append(f"  // ---- Cross coverpoints (related control signals) ----")
        for i, cs in enumerate(cross_sigs):
            cs_width, cs_hi, cs_lo = parse_width_from_rtl(cs, file)
            cs_class = classify(cs, cs_width)
            lines.append(f"  cp_{cs}_for_{target_signal}: coverpoint {cs} {{")
            if cs_class == "CONTROL":
                lines.append(gen_bins_control(cs, cs_width, enums, None))
            else:
                lines.append(gen_bins_data(cs, cs_width))
            lines.append(f"  }}")
        lines.append(f"")
        lines.append(f"  // ---- Cross combinations ----")
        for cs in cross_sigs:
            lines.append(f"  cx_{target_signal}_x_{cs}: cross cp_{target_signal}, cp_{cs}_for_{target_signal};")
        lines.append(f"")

    # ---- Sample 条件注解 ----
    lines.append(f"  // ---- Sample event: {sample_evt} ----")
    lines.append(f"  //   {sample_caveat}")

    lines.append(f"endgroup: cg_{target_signal}")

    return "\n".join(lines)


# =============================================================================
# Main
# =============================================================================
def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    file = sys.argv[1]
    target = sys.argv[2]
    related = sys.argv[3:]
    cg = generate_covergroup(file, target, related)
    print(cg)


if __name__ == "__main__":
    main()
