#==============================================================================
# class_hierarchy.py - Class extends 继承链管理
#==============================================================================
# [铁律13] 金标准测试: 每个方法独立测试
# [铁律15] Visitor 模式不适用: ClassHierarchy 是纯数据层，不走 AST 遍历
#
# 设计原则:
# - ClassHierarchy 独立实现，不进 SignalGraph
# - 只维护 extends 关系映射，给下游提供查询 API
# - 不涉及任何 AST 解析，纯数据结构

from typing import Dict, List, Optional


class ClassHierarchy:
    """Class extends 继承链管理

    铁律16: 独立实现，extends 链查询不进图

    不进 SignalGraph，纯数据层。下游任务自己判断是否需要向上追约束。

    使用示例:
        hierarchy = ClassHierarchy()
        hierarchy.add_class("child", extends="parent")
        hierarchy.add_class("parent", extends=None)

        # 查询
        hierarchy.get_parent("child")          # "parent"
        hierarchy.get_ancestors("child")       # ["parent"]
        hierarchy.get_subclasses("parent")     # ["child"]
        hierarchy.is_ancestor_of("parent", "child")  # True
    """

    def __init__(self):
        # class_name → parent_class_name
        self._parent_map: Dict[str, Optional[str]] = {}
        # class_name → [direct_subclass_names]
        self._subclass_map: Dict[str, List[str]] = {}

    def add_class(self, name: str, extends: Optional[str] = None) -> None:
        """注册一个 class 及其父类

        Args:
            name: class 名称
            extends: 父类名称，None 表示无父类（根类）
        """
        if name not in self._parent_map:
            self._parent_map[name] = extends
        if extends is not None:
            if extends not in self._subclass_map:
                self._subclass_map[extends] = []
            if name not in self._subclass_map[extends]:
                self._subclass_map[extends].append(name)

    def get_parent(self, class_name: str) -> Optional[str]:
        """获取直接父类

        Args:
            class_name: class 名称

        Returns:
            父类名称，无父类返回 None
        """
        return self._parent_map.get(class_name)

    def get_ancestors(self, class_name: str) -> List[str]:
        """递归获取所有祖先类（向上追溯）

        Args:
            class_name: class 名称

        Returns:
            祖先类列表，按从直接父类到根类的顺序
            例如: ["parent", "grandparent"]
        """
        ancestors = []
        current = self._parent_map.get(class_name)
        while current is not None:
            ancestors.append(current)
            current = self._parent_map.get(current)
        return ancestors

    def get_subclasses(self, class_name: str) -> List[str]:
        """获取所有子类（向下追溯，直接子类）

        Args:
            class_name: class 名称

        Returns:
            直接子类名称列表
        """
        return list(self._subclass_map.get(class_name, []))

    def get_all_descendants(self, class_name: str) -> List[str]:
        """递归获取所有后代类（向下追溯）

        Args:
            class_name: class 名称

        Returns:
            所有后代类列表
        """
        descendants = []
        stack = list(self._subclass_map.get(class_name, []))
        while stack:
            subclass = stack.pop()
            descendants.append(subclass)
            stack.extend(self._subclass_map.get(subclass, []))
        return descendants

    def is_ancestor_of(self, ancestor: str, descendant: str) -> bool:
        """判断 ancestor 是否是 descendant 的祖先类

        Args:
            ancestor: 可能的祖先类
            descendant: 可能的后代类

        Returns:
            True 如果 ancestor 是 descendant 的祖先
        """
        return ancestor in self.get_ancestors(descendant)

    def is_descendant_of(self, descendant: str, ancestor: str) -> bool:
        """判断 descendant 是否是 ancestor 的后代类

        Args:
            descendant: 可能的后代类
            ancestor: 可能的祖先类

        Returns:
            True 如果 descendant 是 ancestor 的后代
        """
        return ancestor in self.get_ancestors(descendant)

    def get_depth(self, class_name: str) -> int:
        """获取类的继承深度（根类深度为 0）

        Args:
            class_name: class 名称

        Returns:
            继承深度
        """
        depth = 0
        current = self._parent_map.get(class_name)
        while current is not None:
            depth += 1
            current = self._parent_map.get(current)
        return depth

    def get_root(self, class_name: str) -> Optional[str]:
        """获取类的根类（无父类的祖先）

        Args:
            class_name: class 名称

        Returns:
            根类名称，无父类返回自身
        """
        ancestors = self.get_ancestors(class_name)
        if not ancestors:
            return class_name
        return ancestors[-1]

    def __repr__(self) -> str:
        lines = []
        for name, parent in sorted(self._parent_map.items()):
            if parent:
                lines.append(f"  {name} extends {parent}")
            else:
                lines.append(f"  {name} (root)")
        return "\n".join(lines)


# [铁律11] Agent 调用示例
if __name__ == "__main__":
    # === 示例 ===
    hierarchy = ClassHierarchy()
    hierarchy.add_class("base_item")
    hierarchy.add_class("packet", extends="base_item")
    hierarchy.add_class("req", extends="packet")
    hierarchy.add_class("resp", extends="packet")

    print("=== ClassHierarchy 示例 ===")
    print(f"packet 父类: {hierarchy.get_parent('packet')}")
    print(f"req 祖先类: {hierarchy.get_ancestors('req')}")
    print(f"packet 子类: {hierarchy.get_subclasses('packet')}")
    print(f"base_item 所有后代: {hierarchy.get_all_descendants('base_item')}")
    print(f"base_item 是 req 的祖先: {hierarchy.is_ancestor_of('base_item', 'req')}")
    print(f"packet 继承深度: {hierarchy.get_depth('req')}")
    print(f"req 根类: {hierarchy.get_root('req')}")
    print()
    print(hierarchy)
