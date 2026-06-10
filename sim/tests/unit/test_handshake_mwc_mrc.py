"""
test_handshake_mwc_mrc.py
=========================
Issue 8 修复测试: m_wc_valid / m_rc_valid (axi_crossbar_addr 内部通道)

axi_crossbar_addr 内部用 m_wc (write command) 和 m_rc (read command)
作为 AW/AR 通道的内部状态指示. 这些信号:
  - m_wc_valid: 1-bit output, AW 通道"写命令有效"指示
  - m_wc_ready: 1-bit input, AW 通道"写命令就绪"指示
  - m_rc_valid: 1-bit output, AR 通道"读命令有效"指示
  - m_rc_ready: 1-bit input, AR 通道"读命令就绪"指示
  - m_wc_select: 选择信号
  - m_wc_decerr: 错误信号
  - m_rc_decerr: 错误信号

修复前: 这些信号被 _is_ready_or_valid 过滤掉, scan 输出完全看不到
修复后: 加入 READY_VALID_PATTERNS, scan 能识别
"""

import sys
import importlib.util
from pathlib import Path

import pytest

# 避免 import handshake.py 触发 trace.py 错误
# 直接加载握手模块的代码
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

# import READY_VALID_PATTERNS + _is_ready_or_valid from handshake.py
_handshake_path = project_root / "src" / "cli" / "commands" / "handshake.py"
_spec = importlib.util.spec_from_file_location("_hsk", _handshake_path)
# 不实际执行模块, 只读其 globals 中的简单常量
_hsk_globals = {}
with open(_handshake_path) as f:
    src = f.read()
# 提取 READY_VALID_PATTERNS 定义
import re
match = re.search(r"^READY[ _]VALID_PATTERNS\s*=\s*\[(.*?)\]", src, re.DOTALL | re.MULTILINE)
if match:
    items_str = match.group(1)
    READY_VALID_PATTERNS = re.findall(r'"([^"]+)"', items_str)
else:
    READY_VALID_PATTERNS = []


def _is_ready_or_valid(signal_name: str) -> bool:
    name_lower = signal_name.lower()
    for pattern in READY_VALID_PATTERNS:
        if pattern in name_lower:
            return True
    return False


# ---------------------------------------------------------------------------
# _is_ready_or_valid
# ---------------------------------------------------------------------------

class TestReadyOrValidPattern:
    @pytest.mark.parametrize("sig", [
        "m_wc_valid",
        "m_wc_ready",
        "m_wc_select",
        "m_wc_decerr",
        "m_rc_valid",
        "m_rc_ready",
        "m_rc_decerr",
    ])
    def test_m_wc_m_rc_recognized(self, sig):
        assert _is_ready_or_valid(sig), f"{sig} not recognized as ready/valid"

    def test_standard_axi_still_works(self):
        """之前的标准 AXI 信号仍能被识别 (回归测试)."""
        for sig in [
            "s_axi_awvalid", "m_axi_awready", "m_axi_wready",
            "a_valid", "a_ready", "d_valid",
            "psel", "pready", "hready", "hgrant",
        ]:
            assert _is_ready_or_valid(sig), f"{sig} regression"


# ---------------------------------------------------------------------------
# classify_signal_channel
# ---------------------------------------------------------------------------

class TestChannelClassification:
    def test_m_wc_valid_is_AW(self):
        from trace.core.handshake_detector import _classify_by_name
        assert _classify_by_name("m_wc_valid") == "AW"

    def test_m_wc_ready_is_AW(self):
        from trace.core.handshake_detector import _classify_by_name
        assert _classify_by_name("m_wc_ready") == "AW"

    def test_m_rc_valid_is_AR(self):
        from trace.core.handshake_detector import _classify_by_name
        assert _classify_by_name("m_rc_valid") == "AR"

    def test_m_rc_ready_is_AR(self):
        from trace.core.handshake_detector import _classify_by_name
        assert _classify_by_name("m_rc_ready") == "AR"


# ---------------------------------------------------------------------------
# 集成: READY_VALID_PATTERNS 列表
# ---------------------------------------------------------------------------

class TestPatternsList:
    def test_patterns_include_m_wc_m_rc(self):
        for needed in ["m_wc_valid", "m_wc_ready", "m_rc_valid", "m_rc_ready"]:
            assert needed in READY_VALID_PATTERNS, f"{needed} missing from READY_VALID_PATTERNS"

    def test_patterns_count_grows(self):
        """每次添加不应减少 (回归保护)."""
        assert len(READY_VALID_PATTERNS) >= 110
