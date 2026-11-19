"""Test sv_query.trace._safe canonical implementations (P0-1)

Verifies:
- safe_str handles None, normal strings, null bytes, control chars
- clean_name produces identifiers suitable for graph/DOT/JSON
- safe_attr returns default on pyslang-like attribute errors
- canonical functions are used by semantic_adapter and base
"""

from sv_query.trace._safe import clean_name, safe_attr, safe_str

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


# ---- safe_attr degraded signal (P184.2) ----

class _RaisesOnAttr:
    def __init__(self, exc):
        self._exc = exc
        self.calls = 0

    @property
    def name(self):
        self.calls += 1
        raise self._exc


def _collector():
    events = []
    return events, events.append


def test_safe_attr_unicode_decode_error_reports_structured_event():
    exc = UnicodeDecodeError('utf-8', b'\xcc', 0, 1, 'invalid continuation byte')
    obj = _RaisesOnAttr(exc)
    events, cb = _collector()

    assert safe_attr(obj, "name", "fallback", on_degraded=cb) == "fallback"

    assert len(events) == 1
    event = events[0]
    assert event.obj is obj
    assert event.name == "name"
    assert event.exception is exc
    assert event.exception_type is UnicodeDecodeError
    assert "invalid continuation byte" in event.message
    assert obj.calls == 1


def test_safe_attr_type_error_reports_event():
    obj = _RaisesOnAttr(TypeError("bad token"))
    events, cb = _collector()

    assert safe_attr(obj, "name", None, on_degraded=cb) is None
    assert [e.exception_type for e in events] == [TypeError]
    assert events[0].message == "bad token"


def test_safe_attr_generic_exception_reports_event():
    obj = _RaisesOnAttr(RuntimeError("pyslang internals"))
    events, cb = _collector()

    assert safe_attr(obj, "name", "d", on_degraded=cb) == "d"
    assert events[0].exception_type is RuntimeError


def test_safe_attr_without_callback_is_unchanged():
    """旧行为: 无回调时仍只返回 default, 不产生观察副作用。"""
    obj = _RaisesOnAttr(UnicodeDecodeError('utf-8', b'\xcc', 0, 1, 'x'))
    assert safe_attr(obj, "name") is None
    assert safe_attr(obj, "name", "d") == "d"


def test_safe_attr_missing_attribute_also_reports_degraded():
    class X:
        name = "ok"

    events, cb = _collector()
    assert safe_attr(X(), "nonexistent", "d", on_degraded=cb) == "d"
    assert len(events) == 1
    assert events[0].exception_type is AttributeError


def test_safe_attr_success_does_not_report():
    class X:
        name = "ok"

    events, cb = _collector()
    assert safe_attr(X(), "name", "d", on_degraded=cb) == "ok"
    assert events == []


def test_safe_attr_none_does_not_report():
    events, cb = _collector()
    assert safe_attr(None, "name", "d", on_degraded=cb) == "d"
    assert events == []


def test_safe_attr_callback_failure_does_not_change_return(caplog):
    """回调是观察者: 它抛异常时返回值仍是 default, 且失败被记录。"""
    obj = _RaisesOnAttr(TypeError("boom"))
    seen = []

    def bad_cb(event):
        seen.append(event)
        raise ValueError("collector down")

    with caplog.at_level("WARNING", logger="sv_query.trace._safe"):
        result = safe_attr(obj, "name", "fallback", on_degraded=bad_cb)

    assert result == "fallback"
    assert len(seen) == 1
    assert any("on_degraded callback failed" in r.message for r in caplog.records)


def test_safe_attr_legacy_shim_has_no_callback():
    from sv_query.trace._safe import _safe_attr
    obj = _RaisesOnAttr(TypeError("boom"))
    assert _safe_attr(obj, "name", "d") == "d"


# ---- integration: SemanticAdapter uses canonical ----

def test_semantic_adapter_clean_name_uses_canonical():
    """[P0-1] SemanticAdapter.clean_name delegates to _safe.clean_name"""
    from sv_query.trace.core.semantic_adapter import SemanticAdapter
    adapter = SemanticAdapter.__new__(SemanticAdapter)  # skip __init__

    # Should behave identically to _safe.clean_name
    assert adapter.clean_name("hello") == "hello"
    assert adapter.clean_name(None) == ""
    assert adapter.clean_name("  hello  ") == "hello"
    assert adapter.clean_name("hello\x00world") == "helloworld"


# [iter_174] test_base_pyslang_adapter_clean_name_uses_canonical 已退役:
# legacy PyslangAdapter (core/base.py) 移出 src/ → docs 记录; canonical clean_name
# 由上方 test_semantic_adapter_clean_name_uses_canonical 覆盖 (同一实现)
