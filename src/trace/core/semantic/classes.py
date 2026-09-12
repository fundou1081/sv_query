# classes.py — SemanticAdapter 的 classes 域 mixin (iter_176 分域搬迁)
#
# 方法名/签名与原 SemanticAdapter 完全一致 (API 面冻结测试锁定);
# `self` 即 SemanticAdapter 实例 (状态: _root/_compiler/_target_module/
# _fixed_names/_genvar_context/_spec_members 等), 无独立状态。
"""classes 域: class/约束/参数化特化"""
import logging
from typing import Callable, Iterator

import pyslang

from ..._safe import _safe_attr, _safe_str, clean_name, safe_attr, safe_str
from ..ast_utils import is_syntax_list, iter_syntax_list

logger = logging.getLogger(__name__)


class ClassesMixin:
    """classes 域方法集 (mixin — 由 SemanticAdapter 组合)"""

    def get_classes(self) -> list:
        """获取所有类定义（包括 package 内的 class）"""
        classes = []

        # 遍历所有 CompilationUnit [铁律1]
        for comp_unit in self._root:
            kind = str(getattr(comp_unit, "kind", ""))
            # Instance 需要用 body 遍历
            if "Instance" in kind:
                if hasattr(comp_unit, "body"):
                    for item in comp_unit.body:
                        kind_str = str(getattr(item, "kind", ""))
                        if "Class" in kind_str:
                            classes.append(item)
                continue
            if "CompilationUnit" not in kind:
                continue
            try:
                for item in comp_unit:
                    try:
                        kind_str = str(getattr(item, "kind", ""))
                    except UnicodeDecodeError:
                        continue
                    if "Class" in kind_str:
                        classes.append(item)
                    # 进入 Package 查找 class
                    elif "Package" in kind_str:
                        try:
                            for child in item:
                                try:
                                    ck = str(getattr(child, "kind", ""))
                                except UnicodeDecodeError:
                                    continue
                                if "Class" in ck:
                                    classes.append(child)
                        except (TypeError, UnicodeDecodeError) as _e:
                            logger.debug("提取失败 ((TypeError, UnicodeDecodeError)): %s", _e)
            except (TypeError, UnicodeDecodeError) as _e:
                logger.debug("提取失败 ((TypeError, UnicodeDecodeError)): %s", _e)

        # 去重（Semantic AST 和 SyntaxTree 可能都找到**同一个** class 对象）
        # [iter_154 C4-C / D5] 按**对象身份**去重 (id) — 同名不同定义是合法
        # SV (跨文件/scope), 必须保留给 class_graph_builder 冲突检测;
        # 旧按 name 去重会静默杀掉第二个定义 (C4 实证: 冲突检测形同虚设)。
        seen = set()
        unique_classes = []
        for c in classes:
            if id(c) not in seen:
                seen.add(id(c))
                unique_classes.append(c)
        classes = unique_classes

        # pyslang Unicode bug 兜底：用 sourceRange 从源码提取类名
        self._fix_unicode_class_names(classes)

        # 去重
        seen = set()
        unique_classes = []
        for c in classes:
            # [iter_154 C4-C] 按对象身份去重 (同名不同定义保留给冲突检测)
            if id(c) not in seen:
                seen.add(id(c))
                unique_classes.append(c)

        return unique_classes

    # ------------------------------------------------------------------
    # [iter_170 参数化 class] 统一成员访问面
    # ------------------------------------------------------------------


    def get_class_members(self, cls) -> list:
        """class 成员符号列表 (语义面, iter_170 参数化支持).

        - ClassType (普通 class): 迭代 def 符号本身 (原行为)。
        - GenericClassDef (参数化 class 定义): 定义符号**无成员面**
          (不可迭代/无 body — iter_169 实证) → 用**特化符号**成员
          (实例变量/成员属性的特化 ClassType — 有完整语义成员:
          Parameter/ClassProperty/CovergroupType/Subroutine)。未实例化
          的参数化 class 无特化 → [] (显式, 无静默假成员)。
        调用方: class_graph_builder (_iter_class_properties/_iter_constraints/
        _build_method_assignments) / function_extractor._find_class_method /
        covergroup_extractor (提取走特化成员)。
        """
        try:
            kind = str(getattr(cls, "kind", ""))
        except (UnicodeDecodeError, TypeError):
            return []
        if "GenericClassDef" in kind:
            try:
                name = str(getattr(cls, "name", "")).strip()
            except (UnicodeDecodeError, TypeError):
                return []
            if not name:
                return []
            if self._spec_members is None:
                self._spec_members = self._scan_class_specializations()
            return list(self._spec_members.get(name, []))
        try:
            return list(cls)
        except TypeError:
            return []
        except Exception as e:
            logger.warning("class 成员迭代失败: %s", e)
            return []



    def _scan_class_specializations(self) -> dict[str, list]:
        """扫全树 class 类型变量/成员属性 → {特化类名: [成员符号]} (首见保).

        特化 ClassType (packet#(16) 实例化后) 挂在变量/属性的 .type 上 —
        定义 (GenericClassDef) 无成员面, 实例化符号才有。
        """
        out: dict[str, list] = {}

        def record_spec(t):
            """记录特化成员 + 沿 baseClass 链收录父类特化
            (参数化父类只被继承无实例变量 → 实例符号的 baseClass 才有成员)."""
            try:
                tname = str(getattr(t, "name", "")).strip()
                tkind = str(getattr(t, "kind", ""))
            except Exception:
                return
            if "ClassType" not in tkind:
                return
            try:
                kids = list(t)
            except (TypeError, UnicodeDecodeError):
                kids = []
            if tname and kids and tname not in out:
                out[tname] = kids
            try:
                bc = getattr(t, "baseClass", None)
            except Exception:
                bc = None
            if bc is not None:
                record_spec(bc)
            # [iter_178] 下钻特化成员里的嵌套 class 成员 (参数化 class 内嵌另一个
            # 参数化 class: packet#(W) 的成员 i 类型 inner#(W)) — 否则内层特化
            # 不进入映射 → 内层成员节点/方法链缺失
            for mem in kids:
                try:
                    mk = str(getattr(mem, "kind", ""))
                except Exception:
                    continue
                if "Variable" not in mk and "ClassProperty" not in mk:
                    continue
                mt = getattr(mem, "type", None)
                if mt is None:
                    continue
                try:
                    if "ClassType" in str(getattr(mt, "kind", "")):
                        record_spec(mt)
                except Exception:
                    continue

        def walk(node):
            if node is None:
                return
            try:
                kind = str(getattr(node, "kind", ""))
            except Exception:
                return
            if "Variable" in kind or "ClassProperty" in kind:
                t = getattr(node, "type", None)
                if t is not None:
                    try:
                        tk = str(getattr(t, "kind", ""))
                    except Exception:
                        tk = ""
                    if "ClassType" in tk:
                        record_spec(t)
            body = getattr(node, "body", None)
            if body is not None:
                try:
                    for c in body:
                        walk(c)
                except TypeError as e:
                    logger.debug("%s: 忽略 TypeError: %s", __name__, e)
            try:
                for c in node:
                    walk(c)
            except TypeError as e:
                logger.debug("%s: 忽略 TypeError: %s", __name__, e)

        for top in self._root:
            walk(top)
        return out



    def _fix_unicode_class_names(self, classes: list):
        """修复 pyslang Unicode bug 导致的类名损坏

        通过 syntax.sourceRange.offset 从 compiler._sources 提取类名。
        存储到 self._fixed_names 字典（pyslang 对象不允许设置属性）。
        """
        if not self._compiler:
            return

        sources = getattr(self._compiler, "_sources", {})
        if not sources:
            return

        import re

        for cls in classes:
            try:
                str(_safe_attr(cls, "name", ""))
                continue
            except UnicodeDecodeError as _e:
                logger.debug("提取失败 (UnicodeDecodeError): %s", _e)

            syntax = getattr(cls, "syntax", None)
            if not syntax:
                continue
            sr = getattr(syntax, "sourceRange", None)
            if not sr:
                continue
            start = getattr(sr, "start", None)
            if not start:
                continue
            offset = getattr(start, "offset", 0)

            for _fname, src in sources.items():
                if offset < len(src):
                    snippet = src[offset : offset + 100]
                    match = re.match(r"class\s+(\w+)", snippet)
                    if match:
                        self._fixed_names[id(cls)] = match.group(1)
                        break