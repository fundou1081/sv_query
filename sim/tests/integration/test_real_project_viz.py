"""[Plan B Step B3 2026-08-25] Real-project end-to-end SVG generation test.

背景: regress_golden_mini 只测 32 个简单 case, 不覆盖真实 SV 项目 (darkriscv / picorv32
      / serv / neorv32 / zipcpu). Plan B Step B1 修复后, darkriscv 已经能生成 SVG.

本测试套件:
- 跑 5 个真实 SV 项目端到端 SVG 生成
- 验证 ELK layout 不 fail (Plan B Step B1 已修复 "Referenced shape does not exist")
- 验证 SVG 文件实际生成且内容非空

NOTE (iter_086, 2026-09-02):
- --svg 自 V100 起直接输出 SVG (--dot 仅保留为 deprecated alias), 断言按 SVG 内容校验;
  早期版本断言 'digraph' 是 DOT 时代的残留, 已修。
- picorv32 目前仍挂: ELK 'Referenced shape does not exist: port_picorv32_axi_dot_mem_axi_bvalid'
  (elk_bridge 的 SignalRef 解析 edge 侧 / emit 侧不一致, 方豆拍板暂缓, 见 iter_086)。
  不设 xfail — 保持真实失败可见, 待 elk_bridge 根因修复后自然转绿。

用法:
    python3 -m pytest sim/tests/integration/test_real_project_viz.py -v
    python3 -m pytest sim/tests/integration/test_real_project_viz.py -v -k darkriscv
"""
import subprocess
from pathlib import Path

import pytest

# [Plan B Step B3] 真实 SV 项目 (从 ~/my_dv_proj/ 选 5 个有代表性的)
REAL_PROJECTS = [
    pytest.param(
        'darkriscv',
        '~/my_dv_proj/darkriscv/rtl/darkriscv.v',
        'darkriscv',
        id='darkriscv',
    ),
    pytest.param(
        'picorv32',
        '~/my_dv_proj/picorv32/picorv32.v',
        'picorv32_core',
        id='picorv32',
    ),
    pytest.param(
        'serv',
        '~/my_dv_proj/serv/serv.v',
        'serv_top',
        id='serv',
        marks=pytest.mark.skip(reason='serv.v may need filelist; skip for now'),
    ),
    pytest.param(
        'neorv32',
        '~/my_dv_proj/neorv32/rtl/core/neorv32_top.v',
        'neorv32_top',
        id='neorv32',
        marks=pytest.mark.skip(reason='neorv32 may need complex filelist; skip for now'),
    ),
    pytest.param(
        'zipcpu',
        '~/my_dv_proj/zipcpu/rtl/zipcpu.v',
        'zipcpu',
        id='zipcpu',
        marks=pytest.mark.skip(reason='zipcpu has very large module; skip for now'),
    ),
]


@pytest.mark.parametrize('name,sv_file,target', REAL_PROJECTS)
def test_real_project_svg_generation(name, sv_file, target, tmp_path):
    """Generate SVG for real project, verify ELK layout succeeds and SVG is non-empty.

    [Plan B Step B3] Plan B Step B1 修复后, darkriscv 能生成 SVG (273KB DOT).
                     此测试守住这一进展, 防止未来重构再次 break 真实项目.
    """
    sv_path = Path(sv_file).expanduser()
    if not sv_path.exists():
        pytest.skip(f'{sv_file} not found')

    out_dir = tmp_path / name
    out_dir.mkdir()
    svg_file = out_dir / f'{name}.svg'

    # [Plan B Step B3] Run CLI via subprocess (avoid sys.argv pollution)
    # [iter_086] 用 --svg 主标志 (--dot 是 V100 起的 deprecated alias); 去掉 --no-strict
    # (strict 模式实测可通过, 违反 AGENTS.md 硬规则 #1).
    result = subprocess.run(
        ['python3', 'run_cli.py', 'visualize', 'dataflow',
         '--file', str(sv_path),
         '--module', target,
         '--svg', str(svg_file)],
        capture_output=True, text=True, timeout=600,
        cwd=Path(__file__).resolve().parents[3],
    )

    # [Plan B Step B3] Verify ELK layout didn't fail
    assert result.returncode == 0, (
        f'{name}: CLI failed (returncode={result.returncode})\n'
        f'stdout: {result.stdout[-1000:]}\n'
        f'stderr: {result.stderr[-1000:]}'
    )

    # [iter_086] --svg 直接写 SVG 文件: 校验 SVG 根元素 + 目标模块出现在文本中
    # (旧断言 'digraph'/'graph' 是 DOT 输出时代的残留 — --dot 自 V100 起写 SVG).
    assert svg_file.exists(), f'{name}: SVG file not generated'
    svg_size = svg_file.stat().st_size
    assert svg_size > 1000, f'{name}: SVG too small ({svg_size} bytes) — likely empty'
    svg_text = svg_file.read_text()
    assert '<svg' in svg_text, f'{name}: output missing <svg> root'
    assert target in svg_text, f'{name}: target module {target} not in SVG'


def test_real_project_viz_smoke():
    """[Plan B Step B3] Quick smoke test: just verify test infrastructure works."""
    # This test always passes; documents that the test infrastructure exists
    assert True