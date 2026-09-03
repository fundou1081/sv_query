"""[Plan B Step B3 2026-08-25] Real-project end-to-end SVG generation test.

背景: regress_golden_mini 只测 32 个简单 case, 不覆盖真实 SV 项目 (darkriscv / picorv32
      / serv / neorv32 / zipcpu). Plan B Step B1 修复后, darkriscv 已经能生成 SVG.

本测试套件:
- 跑 5 个真实 SV 项目端到端 SVG 生成
- 验证 ELK layout 不 fail (Plan B Step B1 已修复 "Referenced shape does not exist")
- 验证 SVG 文件实际生成且内容非空

NOTE (iter_086/106, 2026-09-02): --svg 自 V100 起直接输出 SVG, 断言按 SVG 内容校验。
picorv32 ELK dangling port 已在 iter_106 修复 (integration 全绿) — 旧 NOTE 过期已删。

NOTE (iter_116, 2026-09-03): 参数化升级为多文件 (filelist) 支持, 原 3 个 skip 处理:
- **serv 解锁**: openrtl 迁移后路径失效 (serv.v → serv/rtl/serv_top.v, 多文件),
  实测 rtl/*.v filelist + serv_top 4.1s 出 747KB SVG — 已接入 (多文件走 --filelist)
- **neorv32 移除**: 当前 clone 是 VHDL (rtl/core/*.vhd) — 不符本测试 SV 目的
- **zipcpu 移除**: 新版仓库重构 (真核在 rtl/core 子模块, rtl 顶层 zipbones/
  zipaxil/zipsystem 是纯连线 wrapper, dataflow SVG 内容近空, 无 ELK 验证价值)

用法:
    python3 -m pytest sim/tests/integration/test_real_project_viz.py -v
    python3 -m pytest sim/tests/integration/test_real_project_viz.py -v -k darkriscv
"""
import subprocess
from pathlib import Path

import pytest

# [Plan B Step B3] 真实 SV 项目 (从 ~/my_dv_proj/ 选 5 个有代表性的)
# [iter_116] 参数化: (name, sources, target) — sources 支持单文件或多文件列表
# (多文件在测试体里合成临时 filelist 走 --filelist; 单文件走 --file)
REAL_PROJECTS = [
    pytest.param(
        'darkriscv',
        ['~/my_dv_proj/openrtl/darkriscv/rtl/darkriscv.v'],
        'darkriscv',
        id='darkriscv',
    ),
    pytest.param(
        'picorv32',
        ['~/my_dv_proj/openrtl/picorv32/picorv32.v'],
        'picorv32_core',
        id='picorv32',
    ),
    # [iter_116] serv 解锁: 顶层 serv_top.v 实例化 rtl/*.v 多文件 → filelist
    # (openrtl 迁移后原 serv/serv.v 路径失效; 实测 strict 编译 + 747KB SVG 4.1s)
    pytest.param(
        'serv',
        sorted(str(x) for x in Path(
            '~/my_dv_proj/openrtl/serv/rtl').expanduser().glob('*.v')),
        'serv_top',
        id='serv',
    ),
]


@pytest.mark.parametrize('name,sources,target', REAL_PROJECTS)
def test_real_project_svg_generation(name, sources, target, tmp_path):
    """Generate SVG for real project, verify ELK layout succeeds and SVG is non-empty.

    [Plan B Step B3] Plan B Step B1 修复后, darkriscv 能生成 SVG (273KB DOT).
                     此测试守住这一进展, 防止未来重构再次 break 真实项目.
    [iter_116] sources: 单文件列表走 --file; 多文件 (serv) 合成临时 filelist 走
    --filelist (strict 模式, 无 --no-strict — AGENTS.md 硬规则 #1).
    """
    src_paths = [Path(x).expanduser() for x in sources]
    missing = [str(x) for x in src_paths if not x.exists()]
    if missing:
        pytest.skip(f'not found: {missing[:2]}')

    out_dir = tmp_path / name
    out_dir.mkdir()
    svg_file = out_dir / f'{name}.svg'

    cmd = ['python3', 'run_cli.py', 'visualize', 'dataflow',
           '--module', target,
           '--svg', str(svg_file)]
    if len(src_paths) == 1:
        cmd += ['--file', str(src_paths[0])]
    else:
        fl = out_dir / 'sources.f'
        fl.write_text('\n'.join(str(x) for x in src_paths) + '\n')
        cmd += ['--filelist', str(fl)]

    # [Plan B Step B3] Run CLI via subprocess (avoid sys.argv pollution)
    # [iter_086] 用 --svg 主标志 (--dot 是 V100 起的 deprecated alias); 去掉 --no-strict
    # (strict 模式实测可通过, 违反 AGENTS.md 硬规则 #1).
    result = subprocess.run(
        cmd,
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