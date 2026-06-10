"""
applications.bus.normalize - 信号名标准化

Phase A Session 1: 名字标准化层

设计要点
========

1. **6 步流水线** (顺序不可乱):
   1. take_last_dot     — 取 `.` 后的最后一段 (处理 `u_master.io_aw_valid`)
   2. strip_array_index — 去 `[...]` 数组下标 (处理 `awaddr[31:0]`)
   3. strip_infix       — 去中缀 (`_bits_`, `_chan_`, `_payload_`, `_data_`)
   4. strip_prefix      — 去前缀 (`io_`, `m_`, `s_`, `axi_` 等), 反复 strip 直到稳定
   5. strip_suffix      — 去后缀 (`_o`, `_i`, `_r`, `_next`, `_reg`)
   6. remove_underscore — 去下划线 (统一 Chisel `aw_valid` vs SpinalHDL `awvalid`)

2. **改 YAML 改规则, 不动 Python 代码** — 符合 Phase A 原则 1
3. **NormalizeResult 是 str 子类** — 保留原始名, 同时当字符串用
4. **prefix 按长度降序** — 长 prefix 优先匹配 (`io_s_axi_` 在 `io_` 之前)
5. **prefix 反复 strip** — 支持嵌套 (`io_m_s_axi_aw_valid` → `aw_valid`)

使用
====

    from applications.bus.normalize import SignalNormalizer, NormalizeConfig

    norm = SignalNormalizer(NormalizeConfig.default())
    result = norm.normalize("io_aw_valid")
    assert result == "awvalid"
    assert result.original == "io_aw_valid"

    # 或加载自定义 YAML
    cfg = NormalizeConfig.from_yaml("config/protocols/normalize/default.yaml")
    norm = SignalNormalizer(cfg)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Union


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

@dataclass
class NormalizeConfig:
    """信号名标准化配置.

    所有列表按 "长度降序" 排序后使用 — 避免短 prefix 抢匹配.
    """

    strip_prefix: List[str] = field(default_factory=list)
    strip_suffix: List[str] = field(default_factory=list)
    remove_infix: List[str] = field(default_factory=list)
    remove_underscore: bool = True
    take_last_dot: bool = True
    strip_array_index: bool = True

    # ----- 工厂方法 -----

    @classmethod
    def default(cls) -> "NormalizeConfig":
        """内置默认配置 — 覆盖常见生成代码 / 手写代码命名风格.

        与 config/protocols/normalize/default.yaml 保持同步.
        任何一方修改, 必须同步另一方.
        """
        return cls(
            strip_prefix=[
                # 多层复合 (长 prefix 优先)
                "io_s_axi_", "io_m_axi_",
                "io_s_axil_", "io_m_axil_",
                "io_s_", "io_m_", "io_",
                # verilog-axi dual-port (s_axi_<port>_<channel>_<sig>)
                "s_axi_a_", "s_axi_w_", "s_axi_b_", "s_axi_ar_", "s_axi_r_",
                # verilog-axi / verilog-axis 风格
                "s_axi_", "m_axi_",
                "s_axil_", "m_axil_",
                "s_axis_", "m_axis_",
                "io_axis_", "axis_",
                "s_", "m_",
                # 方向 + 类型
                "slave_", "master_",
                "axi_", "axil_", "axi4_", "axi3_", "axilite_",
                "ahb_", "apb_",
                # 工具生成
                "gen_", "my_",
            ],
            strip_suffix=[
                # 方向后缀
                "_o", "_i", "_io",
                # FIFO 端口
                "_r", "_w",
                # 时序后缀
                "_next", "_reg", "_q",
                # 内部/外部
                "_int", "_ext",
                # 差分
                "_n", "_p",
            ],
            remove_infix=[
                "_bits_", "_chan_", "_payload_", "_data_",
            ],
            remove_underscore=True,
        )

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "NormalizeConfig":
        """从 YAML 加载配置."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"YAML not found: {path}")
        data = _yaml_safe_load(path)
        return cls._from_dict(data)

    @classmethod
    def from_yaml_with_default(
        cls,
        override_path: Union[str, Path],
        base_path: Union[str, Path],
    ) -> "NormalizeConfig":
        """加载 base + override 合并配置.

        YAML 中可用 `extra_strip_prefix` / `extra_strip_suffix` / `extra_remove_infix`
        在 base 基础上追加, 也可直接覆盖 `strip_prefix` / `strip_suffix` 等键.
        空 list 不覆盖 base 的值 (避免误删).
        """
        base = cls.from_yaml(base_path)
        # 重新加载 override 拿原始 dict (避免 _to_dict() 丢失 extra_ 键)
        override_data = _yaml_safe_load(Path(override_path))
        return base._merge_dict(override_data)

    @staticmethod
    def _from_dict(data: dict) -> "NormalizeConfig":
        """从 dict 构造. 缺失键用空值."""
        return NormalizeConfig(
            strip_prefix=list(data.get("strip_prefix", [])),
            strip_suffix=list(data.get("strip_suffix", [])),
            remove_infix=list(data.get("remove_infix", [])),
            remove_underscore=bool(data.get("remove_underscore", True)),
            take_last_dot=bool(data.get("take_last_dot", True)),
            strip_array_index=bool(data.get("strip_array_index", True)),
        )

    def _to_dict(self) -> dict:
        return {
            "strip_prefix": list(self.strip_prefix),
            "strip_suffix": list(self.strip_suffix),
            "remove_infix": list(self.remove_infix),
            "remove_underscore": self.remove_underscore,
            "take_last_dot": self.take_last_dot,
            "strip_array_index": self.strip_array_index,
        }

    def _merge_dict(self, override: dict) -> "NormalizeConfig":
        """merge override 进 self, 处理 extra_* 字段.

        语义:
        - `extra_strip_prefix` 等: 追加到 base 列表
        - `strip_prefix` 等直接覆盖键: 覆盖 base (但空 list 不覆盖)
        """
        result = self._to_dict()

        # 1) 处理 extra_* 字段: 追加
        if "extra_strip_prefix" in override:
            result["strip_prefix"] = list(self.strip_prefix) + list(override["extra_strip_prefix"])
        if "extra_strip_suffix" in override:
            result["strip_suffix"] = list(self.strip_suffix) + list(override["extra_strip_suffix"])
        if "extra_remove_infix" in override:
            result["remove_infix"] = list(self.remove_infix) + list(override["extra_remove_infix"])

        # 2) 其他直接键: 覆盖 (但空 list 跳过, 避免误删)
        for key, val in override.items():
            if key.startswith("extra_"):
                continue
            if isinstance(val, list) and len(val) == 0 and key in result:
                base_val = result[key]
                if isinstance(base_val, list) and len(base_val) > 0:
                    # base 有值, override 是空 list, 跳过
                    continue
            result[key] = val

        return NormalizeConfig._from_dict(result)

    def merge(
        self,
        strip_prefix_extra: Optional[Iterable[str]] = None,
        strip_suffix_extra: Optional[Iterable[str]] = None,
        remove_infix_extra: Optional[Iterable[str]] = None,
        **overrides,
    ) -> "NormalizeConfig":
        """in-memory merge — 返回新 config, 不改 self."""
        new = self._to_dict()
        if strip_prefix_extra:
            new["strip_prefix"] = list(self.strip_prefix) + list(strip_prefix_extra)
        if strip_suffix_extra:
            new["strip_suffix"] = list(self.strip_suffix) + list(strip_suffix_extra)
        if remove_infix_extra:
            new["remove_infix"] = list(self.remove_infix) + list(remove_infix_extra)
        for key, val in overrides.items():
            new[key] = val
        return NormalizeConfig._from_dict(new)

    def with_overrides(self, **kwargs) -> "NormalizeConfig":
        """覆盖字段, 返回新 config."""
        new = self._to_dict()
        for key, val in kwargs.items():
            if key in new:
                new[key] = val
        return NormalizeConfig._from_dict(new)


# ---------------------------------------------------------------------------
# 结果 (str 子类)
# ---------------------------------------------------------------------------

class NormalizeResult(str):
    """str 子类, 保留原始信号名, 同时可当字符串用.

    例:
        r = NormalizeResult("io_aw_valid", "awvalid")
        r == "awvalid"            # ✅ str 比较
        r.startswith("aw")        # ✅ str 方法
        r.original == "io_aw_valid"  # ✅ 原始名
        str(r) == "awvalid"       # ✅ 转字符串
    """

    __slots__ = ("_original",)

    def __new__(cls, original: str, normalized: str) -> "NormalizeResult":
        instance = super().__new__(cls, normalized)
        instance._original = original
        return instance

    @property
    def original(self) -> str:
        """标准化前的原始信号名."""
        return self._original

    @property
    def normalized(self) -> str:
        """标准化后的信号名 (与 str(self) 相同)."""
        return str(self)

    def __repr__(self) -> str:
        return f"NormalizeResult({self._original!r} -> {str(self)!r})"


# ---------------------------------------------------------------------------
# 主类
# ---------------------------------------------------------------------------

class SignalNormalizer:
    """信号名标准化器.

    实例化后可多次调用 `.normalize(name)`, 每次都走 6 步流水线.
    """

    # 数组下标正则: `[anything]` (非贪婪)
    _ARRAY_RE = re.compile(r"\[[^\]]*\]")

    def __init__(self, config: Optional[NormalizeConfig] = None):
        self.config = config or NormalizeConfig.default()
        # 排序: 长 prefix 优先
        self._prefixes = sorted(
            self.config.strip_prefix, key=len, reverse=True,
        )
        self._suffixes = sorted(
            self.config.strip_suffix, key=len, reverse=True,
        )
        self._infixes = sorted(
            self.config.remove_infix, key=len, reverse=True,
        )

    def normalize(self, name: str) -> NormalizeResult:
        """6 步流水线, 返回 NormalizeResult."""
        original = name
        if self.config.take_last_dot:
            name = self._take_last_dot(name)
        if self.config.strip_array_index:
            name = self._strip_array_index(name)
        name = self._strip_infix(name)
        name = self._strip_prefix(name)
        name = self._strip_suffix(name)
        if self.config.remove_underscore:
            name = self._remove_underscore(name)
        return NormalizeResult(original, name)

    # ----- 6 步 -----

    def _take_last_dot(self, name: str) -> str:
        """步骤 1: 取 `.` 后的最后一段."""
        if "." in name:
            return name.rsplit(".", 1)[-1]
        return name

    def _strip_array_index(self, name: str) -> str:
        """步骤 2: 去 `[...]` 数组下标."""
        return self._ARRAY_RE.sub("", name)

    def _strip_infix(self, name: str) -> str:
        """步骤 3: 去中缀. 中缀带前后下划线 (`_bits_`), 替换为单下划线 (`_`).

        例:
          - `aw_bits_data` → `aw_data` (`_bits_` 替为 `_`)
          - `r_data_payload` → `r_payload`
        """
        for infix in self._infixes:
            # 中缀是 `_<word>_` 形式, 替换为 `_` 以保持单词边界
            if infix in name:
                name = name.replace(infix, "_")
        return name

    def _strip_prefix(self, name: str) -> str:
        """步骤 4: 去前缀 (反复 strip 直到稳定).

        例: `io_m_s_axi_aw_valid`
          → io_m_ (iter 1) → s_axi_aw_valid
          → s_axi_ (iter 2) → aw_valid
        """
        if not self._prefixes:
            return name
        max_iters = 32  # 安全网, 防止无限循环
        for _ in range(max_iters):
            stripped = name
            for prefix in self._prefixes:
                if name.startswith(prefix) and len(name) > len(prefix):
                    name = name[len(prefix):]
                    break
            if name == stripped:
                break
        return name

    def _strip_suffix(self, name: str) -> str:
        """步骤 5: 去后缀 (只去一次, 取最长的匹配)."""
        for suffix in self._suffixes:
            if name.endswith(suffix) and len(name) > len(suffix):
                return name[: -len(suffix)]
        return name

    def _remove_underscore(self, name: str) -> str:
        """步骤 6: 去所有下划线 (受 `config.remove_underscore` 控制)."""
        if not self.config.remove_underscore:
            return name
        return name.replace("_", "")


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def _yaml_safe_load(path: Path) -> dict:
    """轻量 YAML 加载 — 不强制依赖 PyYAML.

    如果有 PyYAML, 用它; 否则用极简 parser (仅支持 list[str] / bool 配置).
    """
    text = path.read_text()
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ValueError(f"YAML root must be dict, got {type(data).__name__}")
        return data
    except ImportError:
        return _mini_yaml_load(text)


def _mini_yaml_load(text: str) -> dict:
    """极简 YAML parser — 满足 default.yaml 格式 (无嵌套 list/dict).

    格式:
        strip_prefix:
          - "io_"
          - "m_"
        remove_underscore: false
    """
    result: dict = {}
    current_key: Optional[str] = None
    current_list: Optional[list] = None
    pending_string: Optional[str] = None  # 等待 `:` 或行尾

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # 列表项:  `- "..."` 或 `  - item`
        if stripped.startswith("- "):
            if current_list is not None:
                item = stripped[2:].strip().strip('"').strip("'")
                current_list.append(item)
            continue
        # key: value 或 key:
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            if val == "":
                # 多行 list 开始
                current_key = key
                current_list = []
                result[key] = current_list
            else:
                # 单行 kv
                if val.lower() in ("true", "false"):
                    parsed: object = (val.lower() == "true")
                else:
                    parsed = val.strip('"').strip("'")
                result[key] = parsed
                current_key = None
                current_list = None
    return result
