"""
test_compiler_source_manager_lifetime.py — [iter_186] SourceManager 生命周期回归锁

背景 (iter_185): `SVCompiler._do_compile()` 曾把 `pyslang.SourceManager` 存成
**局部变量**, parse 循环结束后被 GC → 它持有的源文件 buffer 被释放 → 所有符号名
/ token 文本 (指向 buffer 的 `string_view`) 变成释放内存的垃圾字节。症状是随机
的: 乱码 instance 名 / `name` getter 抛 `UnicodeDecodeError` / elaboration 部分
失败 / 节点数跨次漂移 (真因复盘见
`docs/task_tree/iterations/iter_185_slang_sourcemanager_lifetime.md`)。

本测试锁住**不变量**: 只要 compiler 对象还活着, 编译出的符号名就必须可读 —
即使中间发生了 GC + 大量内存分配 (复用被释放的内存, 这正是原 bug 的触发条件)。

注意: 触发原 bug 的前提是 `include_dirs` 非空 (只有那条分支会创建私有
SourceManager), 所以本测试必须传 include_dirs。
"""
import gc

from trace.core.compiler import SVCompiler

TOP_SV = """
module sm_top;
  logic [3:0] counter;
  sm_sub u_sub (.din(counter));
endmodule
"""

SUB_SV = """
module sm_sub (input logic [3:0] din);
  logic [3:0] shadow;
  always_comb shadow = din;
endmodule
"""


def _churn_memory() -> None:
    """分配再释放大量对象 — 复用被释放内存, 放大悬垂 string_view 的可见性。"""
    junk = [bytearray(256) for _ in range(200_000)]
    junk2 = [str(i) for i in range(200_000)]
    del junk, junk2
    gc.collect()


def _collect_names(node, out, depth=0):
    """递归收集子树里所有可读的符号名 (读不到就记 None)。"""
    if node is None or depth > 8:
        return out
    try:
        name = node.name
    except (UnicodeDecodeError, AttributeError):
        out.append(None)
    else:
        out.append(str(name))
    # 只下钻实例体 (够覆盖 top → sub 链)
    body = getattr(node, "body", None)
    if body is not None:
        try:
            children = list(body)
        except TypeError:
            return out
        for child in children:
            _collect_names(child, out, depth + 1)
    return out


def _compile(tmp_path) -> tuple[SVCompiler, object]:
    """编译 top + sub, 带 include_dirs (触发私有 SourceManager 分支)。"""
    incdir = tmp_path / "inc"
    incdir.mkdir()
    (incdir / "defs.svh").write_text("`define SM_WIDTH 4\n", encoding="utf-8")
    comp = SVCompiler(
        {"sm_top.sv": TOP_SV, "sm_sub.sv": SUB_SV},
        log_level="ERROR",
        strict=True,
        top_modules=["sm_top"],
    )
    comp.add_include_dir(str(incdir))
    return comp, comp.get_root()


def test_source_manager_outlives_compilation(tmp_path):
    """compiler 必须持有 SourceManager (否则 buffer 随 GC 消失)。"""
    comp, _root = _compile(tmp_path)
    assert comp._source_manager is not None, (
        "SVCompiler 未持有 SourceManager — 源文件 buffer 会在 parse 循环结束后"
        "被释放, 符号名变垃圾 (iter_185)"
    )


def test_symbol_names_readable_after_gc_churn(tmp_path):
    """核心不变量: GC + 内存churn 之后, 符号名仍必须可读。

    修复前 (局部变量版) 此断言必失败: 名字变成释放内存里的字节 /
    UnicodeDecodeError (iter_185 最小复现 4/4)。
    """
    comp, root = _compile(tmp_path)
    tops = list(root.topInstances)
    assert len(tops) == 1, f"应只有 1 个 top, got {len(tops)}"

    assert str(tops[0].name) == "sm_top", f"编译期就该可读, got {tops[0].name!r}"

    # 关键: 制造 GC + 内存复用, 再读 (buffer 若已释放 → 这里必炸/乱码)
    _churn_memory()

    names = _collect_names(tops[0], [])
    assert None not in names, f"存在读不出名字的符号 (悬垂 string_view): {names}"
    assert all(n == "" or (n.isprintable() and n.isascii()) for n in names), (
        f"符号名含乱码字节 (悬垂 string_view): {names}"
    )
    # top 名 + 子实例名 + 子实例的**定义名** (定义名也指向源 buffer)
    assert "sm_top" in names and "u_sub" in names, f"实例链名字缺失: {names}"
    sub_inst = next(
        (c for c in list(tops[0].body) if getattr(c, "name", None) == "u_sub"), None
    )
    assert sub_inst is not None, f"未找到子实例 u_sub: {names}"
    assert sub_inst.definition.name == "sm_sub", (
        f"子实例定义名不可读/错误: {sub_inst.definition.name!r}"
    )
