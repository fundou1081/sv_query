"""D3 regression — ClassHierarchy traversals must be cycle-safe (P183.1)."""
from __future__ import annotations

import pytest

from sv_query.trace.core.class_hierarchy import ClassHierarchy


def test_acyclic_ancestors_depth_root_and_descendants():
    h = ClassHierarchy()
    h.add_class("base")
    h.add_class("left", extends="base")
    h.add_class("right", extends="base")
    h.add_class("leaf", extends="left")
    h.add_class("leaf2", extends="right")

    assert h.get_ancestors("leaf") == ["left", "base"]
    assert h.get_depth("leaf") == 2
    assert h.get_root("leaf") == "base"
    assert h.get_ancestors("base") == []
    assert h.get_depth("base") == 0
    assert h.get_root("base") == "base"

    descendants = h.get_all_descendants("base")
    assert set(descendants) == {"left", "right", "leaf", "leaf2"}
    assert len(descendants) == len(set(descendants))


def test_diamond_is_not_a_cycle():
    # Multiple inheritance is represented by repeated add calls on a child.
    h = ClassHierarchy()
    h.add_class("root")
    h.add_class("left", extends="root")
    h.add_class("right", extends="root")
    h.add_class("leaf", extends="left")
    h.add_class("leaf", extends="right")

    assert h.get_ancestors("leaf") == ["left", "root"]
    assert h.get_depth("leaf") == 2
    descendants = h.get_all_descendants("root")
    assert set(descendants) == {"left", "right", "leaf"}
    # Preserve pre-D3 traversal semantics (duplicates from multiple paths allowed);
    # only cycles are new failures.
    assert len(descendants) == 4


def test_self_parent_cycle_ancestors_raises():
    h = ClassHierarchy()
    h.add_class("a", extends="a")
    with pytest.raises(ValueError, match="class hierarchy cycle"):
        h.get_ancestors("a")
    with pytest.raises(ValueError, match="class hierarchy cycle"):
        h.get_depth("a")


def test_two_node_cycle_ancestors_raises():
    h = ClassHierarchy()
    h.add_class("a", extends="b")
    h.add_class("b", extends="a")
    with pytest.raises(ValueError, match="class hierarchy cycle"):
        h.get_ancestors("a")
    with pytest.raises(ValueError, match="class hierarchy cycle"):
        h.get_root("a")


def test_descendant_cycle_raises():
    h = ClassHierarchy()
    h.add_class("a", extends="b")
    h.add_class("b", extends="a")
    with pytest.raises(ValueError, match="class hierarchy cycle"):
        h.get_all_descendants("a")


def test_unknown_class_semantics_unchanged():
    h = ClassHierarchy()
    assert h.get_ancestors("missing") == []
    assert h.get_depth("missing") == 0
    assert h.get_root("missing") == "missing"
    assert h.get_all_descendants("missing") == []
