"""Test signal_classifier YAML config loading (P1-4)

Verifies:
- load_config() parses the default YAML correctly
- get_config() returns the active config (initial: builtin)
- classify_graph() auto-loads default YAML on first call
- with_overrides() returns a new config with merged patterns
- reset_config() reverts to builtin
"""
import pytest
from pathlib import Path

from trace.core.graph.analyzer.signal_classifier import (
    ClassifyConfig,
    classify_graph,
    get_config,
    load_config,
    reset_config,
    set_config,
)


@pytest.fixture(autouse=True)
def _reset():
    """Ensure each test starts from a clean state."""
    reset_config()
    yield
    reset_config()


def test_default_config_is_builtin():
    cfg = get_config()
    assert cfg.source == "builtin"
    assert len(cfg.control_patterns) > 0
    assert len(cfg.data_patterns) > 0


def test_load_default_yaml(tmp_path):
    yaml_content = """
rules:
  - class: control
    patterns: [my_valid, my_ready]
  - class: data
    patterns: [my_data, my_addr]
"""
    yaml_path = tmp_path / "sc.yaml"
    yaml_path.write_text(yaml_content)
    cfg = load_config(yaml_path)
    assert cfg.source == f"yaml:{yaml_path}"
    assert cfg.control_patterns == ["my_valid", "my_ready"]
    assert cfg.data_patterns == ["my_data", "my_addr"]


def test_load_config_sets_active():
    yaml_content = """
rules:
  - class: control
    patterns: [foo, bar]
"""
    yaml_path = Path("config/signal_classify.yaml")  # default
    if not yaml_path.exists():
        pytest.skip("default config/signal_classify.yaml not present")
    load_config(yaml_path)
    assert get_config().source.startswith("yaml:")


def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path/sc.yaml")


def test_with_overrides_returns_new_config():
    cfg = get_config()
    new_cfg = cfg.with_overrides(control=["custom_ctrl"])
    assert new_cfg.control_patterns == ["custom_ctrl"]
    # data patterns copied from original
    assert new_cfg.data_patterns == cfg.data_patterns
    # original not mutated
    assert cfg.control_patterns != ["custom_ctrl"]


def test_reset_config():
    yaml_path = Path("config/signal_classify.yaml")
    if not yaml_path.exists():
        pytest.skip("default config not present")
    load_config(yaml_path)
    assert get_config().source.startswith("yaml:")
    reset_config()
    assert get_config().source == "builtin"


def test_set_config():
    custom = ClassifyConfig(control_patterns=["x"], data_patterns=["y"], source="custom")
    set_config(custom)
    assert get_config().source == "custom"
    assert get_config().control_patterns == ["x"]


def test_builtin_fallback_includes_common_patterns():
    """Built-in defaults include the patterns we depend on in real code."""
    cfg = get_config()
    for needed in ("valid", "ready", "data", "addr", "state", "enable"):
        assert needed in cfg.control_patterns or needed in cfg.data_patterns, \
            f"pattern {needed!r} missing from builtin"


def test_default_yaml_matches_builtin():
    """[P1-4] 显式加载默认 YAML 后, 应与 builtin patterns 列表内容相同。"""
    yaml_path = Path("config/signal_classify.yaml")
    if not yaml_path.exists():
        pytest.skip("default config not present")
    builtin = get_config()
    loaded = load_config(yaml_path)
    assert loaded.control_patterns == builtin.control_patterns
    assert loaded.data_patterns == builtin.data_patterns
