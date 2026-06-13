"""Test trace._safe canonical implementations (P0-1)

Verifies:
- safe_str handles None, normal strings, null bytes, control chars
- clean_name produces identifiers suitable for graph/DOT/JSON
- safe_attr returns default on pyslang-like attribute errors
- canonical functions are used by semantic_adapter and base
"""
import pytest
from trace._safe import safe_str, clean_name, safe_attr


# ---- safe_str ----

def test_safe_str_none():
    assert safe_str(None) == ""


def test_safe_str_normal():
    assert safe_str("hello") == "hello"
    assert safe_str("data_o") == "data_o"
    assert safe_str("a.b.c") == "a.b.c"


def test_safe_str_filters_null_bytes():
    assert safe_str("hello\x00\x00world") == "helloworld"


def test_safe_str_filters_control_chars():
    assert safe_str("hello\x01\x02world") == "helloworld"


def test_safe_str_preserves_printable():
    assert safe_str("hello world") == "hello world"
    assert safe_str("a + b") == "a + b"
    assert safe_str("data[7:0]") == "data[7:0]"


def test_safe_str_all_null_returns_placeholder():
    result = safe_str("\x00\x00\x00")
    assert result == "<id:binary>", f"got {result!r}"


def test_safe_str_unicode_decode_error():
    """When str() raises, returns <id:0x...> or <id:non-utf8>"""
    class ThrowsOnStr:
        def __str__(self):
            raise UnicodeDecodeError('utf-8', b'\xcc', 0, 1, 'invalid continuation byte')
        @property
        def rawText(self):
            return b'\xcc\xcc\xcc\xcc'
    
    result = safe_str(ThrowsOnStr())
    assert result.startswith("<id:0x") or result == "<id:non-utf8>", f"got {result!r}"


# ---- clean_name ----

def test_clean_name_none_and_empty():
    assert clean_name(None) == ""
    assert clean_name("") == ""


def test_clean_name_normal():
    assert clean_name("clk") == "clk"
    assert clean_name("data_o") == "data_o"


def test_clean_name_strips_whitespace():
    assert clean_name("  hello  ") == "hello"
    assert clean_name("hello\nworld") == "hello world"
    assert clean_name("\thello\tworld") == "hello world"


def test_clean_name_filters_null_bytes():
    assert clean_name("hello\x00world") == "helloworld"


def test_clean_name_filters_control_chars():
    assert clean_name("hello\x01\x02") == "hello"


def test_clean_name_empty_after_filter():
    """When nothing printable remains, returns empty (not placeholder)"""
    assert clean_name("\x00\x00\x00") == ""
    assert clean_name("\x01\x02\x03") == ""


# ---- safe_attr ----

def test_safe_attr_normal():
    class X:
        name = "ok"
    assert safe_attr(X(), "name") == "ok"


def test_safe_attr_missing():
    class X:
        name = "ok"
    assert safe_attr(X(), "nonexistent") is None
    assert safe_attr(X(), "nonexistent", "default") == "default"


def test_safe_attr_none():
    assert safe_attr(None, "name") is None
    assert safe_attr(None, "name", "default") == "default"


# ---- integration: SemanticAdapter uses canonical ----

def test_semantic_adapter_clean_name_uses_canonical():
    """[P0-1] SemanticAdapter.clean_name delegates to _safe.clean_name"""
    from trace.core.semantic_adapter import SemanticAdapter
    adapter = SemanticAdapter.__new__(SemanticAdapter)  # skip __init__
    
    # Should behave identically to _safe.clean_name
    assert adapter.clean_name("hello") == "hello"
    assert adapter.clean_name(None) == ""
    assert adapter.clean_name("  hello  ") == "hello"
    assert adapter.clean_name("hello\x00world") == "helloworld"


def test_base_pyslang_adapter_clean_name_uses_canonical():
    """[P0-1] PyslangAdapter.clean_name delegates to _safe.clean_name"""
    from trace.core.base import PyslangAdapter
    # Try to instantiate without going through full init
    try:
        adapter = PyslangAdapter.__new__(PyslangAdapter)
    except Exception:
        pytest.skip("PyslangAdapter cannot be instantiated without compiler")
    
    assert adapter.clean_name("hello") == "hello"
    assert adapter.clean_name(None) == ""
