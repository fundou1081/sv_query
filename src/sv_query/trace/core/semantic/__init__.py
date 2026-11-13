# semantic/ — SemanticAdapter 分域 mixin 包 (iter_174~176)
#
# 背景: semantic_adapter.py 曾 3,049 行单类;按方案
# (docs/architecture/semantic_adapter_split_plan.md) 分域搬迁 — 方法名/签名
# 全部不变 (API 面冻结测试锁定), 调用方零改动。
#
# 域划分:
#   source_core  — 源位置/文本/子节点/名字清洗
#   modules      — module/instance/generate/primitive 导航
#   ports_ifaces — 端口/接口/modport
#   connections  — 实例连接/表达式→信号名/索引求值
#   exprs_drivers— 赋值/数据声明/驱动/任务函数参数 (含表达式信号抽取分派器)
#   classes      — class/约束/参数化特化
from .source_core import SourceCoreMixin
from .modules import ModulesMixin
from .ports_ifaces import PortsIfacesMixin
from .connections import ConnectionsMixin
from .exprs_drivers import ExprsDriversMixin
from .classes import ClassesMixin

__all__ = ["SourceCoreMixin", "ModulesMixin", "PortsIfacesMixin",
           "ConnectionsMixin", "ExprsDriversMixin", "ClassesMixin"]
