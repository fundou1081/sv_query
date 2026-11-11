"""fix_openrtl_imports.py — [P158.12.2] 补 OPENRTL_ROOT 定义/导入/skip 守卫

批量路径替换之后的三件收尾:
  1. 缺 `import os` / `from pathlib import Path` 的文件补导入;
  2. 使用 OPENRTL_ROOT 但没有定义的文件插入定义 (poc/generate 自带, 跳过);
  3. 外部 corpus 依赖文件加显式 skipif (缺失 → skip 不假失败)。
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(".").resolve()

OPENRTL_DEF = (
    "# [P158.12] 外部 corpus 根: 环境变量可覆盖, 缺失时显式 skip (不假失败)\n"
    'OPENRTL_ROOT = Path(os.environ.get("SVQ_OPENRTL_ROOT",\n'
    '                                str(Path.home() / "my_dv_proj" / "openrtl")))'
)

SKIP_REASON = '"external openrtl corpus missing; set SVQ_OPENRTL_ROOT"'

# (file, need_os, need_path, need_def, skip_style)
# skip_style: None=不加; "opensource"=在 pytestmark.opensource 上加 skipif;
#             "module"=新增模块级 pytestmark skipif
FILES = [
    ("sim/tests/unit/conftest.py",            True,  False, True,  None),
    ("sim/tests/unit/test_trace_include_flags.py", True, False, True, "opensource"),
    ("sim/tests/unit/test_controlflow_mutex.py",   True, False, True, "opensource"),
    ("sim/tests/unit/test_p3_bugs.py",        False, True,  True,  "opensource"),
    ("sim/tests/integration/test_benchmark_picorv32.py", True, False, True, "opensource"),
    ("sim/tests/usage/test_dataflow_latency_open_source.py", True, False, True, "opensource"),
    ("sim/tests/usage/test_dataflow_controlflow_open_source.py", True, False, True, "opensource"),
    ("sim/tests/cli/test_ventus_viz_validation.py", True, False, True, "opensource"),
    ("sim/tests/cli/test_cli_f_flag_filelist_routing.py", True, True, True, "opensource"),
    ("sim/tests/regression/test_generate_real_world.py", False, False, False, "module"),
    ("sim/tests/poc/test_portconn_native_poc.py", False, True, False, "module"),
    # 仅补 Path 导入的仓库内路径文件
    ("sim/tests/integration/test_dataflow_golden.py", False, True, False, None),
    ("sim/tests/integration/test_dataflow_else_if_comprehensive.py", False, True, False, None),
    ("sim/tests/cli/test_no_swap_reclaim.py", False, True, False, None),
]


def ensure_imports(t: str, need_os: bool, need_path: bool) -> str:
    lines = t.split("\n")
    has_os = any(l.startswith("import os") for l in lines)
    has_path = any(l.startswith("from pathlib import") for l in lines)
    ins_at = None
    for i, l in enumerate(lines):
        if l.startswith("import sys"):
            ins_at = i
            break
    if ins_at is None:
        for i, l in enumerate(lines):
            if l.startswith("import pytest"):
                ins_at = i
                break
    add = []
    if need_os and not has_os:
        add.append("import os")
    if need_path and not has_path:
        add.append("from pathlib import Path")
    if add:
        lines[ins_at:ins_at] = add
    return "\n".join(lines)


def insert_def(t: str) -> str:
    if "OPENRTL_ROOT = " in t:
        return t
    lines = t.split("\n")
    # 插在第一个引用 OPENRTL_ROOT 的行之前
    for i, l in enumerate(lines):
        if "OPENRTL_ROOT" in l:
            lines[i:i] = [OPENRTL_DEF, ""]
            break
    return "\n".join(lines)


def add_skip(t: str, style: str) -> str:
    if "SVQ_OPENRTL_ROOT" in t and "skipif" in t:
        return t
    if style == "opensource":
        old = "pytestmark = pytest.mark.opensource"
        new = ("pytestmark = [pytest.mark.opensource,\n"
               f"            pytest.mark.skipif(not OPENRTL_ROOT.exists(), reason={SKIP_REASON})]")
        if old in t:
            return t.replace(old, new)
        return t
    if style == "module":
        # generate_real_world: guard 变量名不同
        if "test_generate_real_world" in t or "ZIPCPU_RTL" in t:
            old = "ZIPCPU_RTL = Path(os.environ.get("
            guard = ("\n\npytestmark = pytest.mark.skipif(\n"
                     '    not ZIPCPU_RTL.exists(),\n'
                     '    reason="external zipcpu corpus missing; set SVQ_OPENRTL_ROOT")')
            anchor = t.split("zipcpu/rtl\")")[0] + 'zipcpu/rtl")'
            end = t.find('zipcpu/rtl")') + len('zipcpu/rtl")')
            # 找到该赋值行的行尾
            eol = t.find("\n", end)
            return t[:eol] + guard + t[eol:]
        # poc
        guard = ("\n\npytestmark = pytest.mark.skipif(\n"
                 f"    not OPENRTL_ROOT.exists(), reason={SKIP_REASON})")
        anchor_end = t.find("\n", t.find("my_dv_proj\", / \"openrtl\"))"))
        anchor_end = t.find("\n", t.find('"openrtl"))')) if anchor_end == -1 else anchor_end
        return t[:anchor_end] + guard + t[anchor_end:]
    return t


changed, failed = [], []
for rel, need_os, need_path, need_def, skip_style in FILES:
    p = ROOT / rel
    t = p.read_text(encoding="utf-8")
    orig = t
    t = ensure_imports(t, need_os, need_path)
    if need_def:
        t = insert_def(t)
    if skip_style:
        t = add_skip(t, skip_style)
    if t != orig:
        p.write_text(t, encoding="utf-8")
        changed.append(rel)

print(f"changed: {len(changed)}")
for rel in changed:
    print("  +", rel)

# 语法 + 引用完整性校验
errs = []
for rel, *_ in FILES:
    try:
        ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    except SyntaxError as e:
        errs.append((rel, str(e)[:90]))
print("syntax:", errs or "OK")

# 每个 OPENRTL_ROOT 引用文件必须有定义
r = subprocess.run(["grep", "-rln", "OPENRTL_ROOT", "sim/tests/", "--include=*.py"],
                   capture_output=True, text=True)
missing_def = [f for f in r.stdout.split() if "openrtl\"))" not in (ROOT / f).read_text(encoding="utf-8") and "OPENRTL_ROOT = " not in (ROOT / f).read_text(encoding="utf-8")]
print("missing OPENRTL_ROOT def:", missing_def or "无")
