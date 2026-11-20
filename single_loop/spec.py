"""资产规格：四类资产的分类与不变式。

这套架构把所有可挂载的东西收敛成四类，各自走一条披露通道。
分类不是为了整齐，是为了让「什么时候该加载什么」变成可判断的问题。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AssetKind(str, Enum):
    """四类资产。

    - SKILL：流程。团队的工作方式，步骤、规则、判断标准。
    - TOOL：动作。执行操作、读取实时数据、返回固定格式结果。
    - KNOWLEDGE：事实。偶尔查阅的参考资料，政策、指标定义、产品规格。
    - CODE：预处理。成本低且几乎总是相关的内容，实体解析之类。
    """

    SKILL = "skill"
    TOOL = "tool"
    KNOWLEDGE = "knowledge"
    CODE = "code"


class InvariantError(RuntimeError):
    """违反架构不变式。"""


@dataclass(frozen=True)
class AssetSpec:
    """一份资产的元数据与正文。

    index 常驻上下文，body 只在被检索命中后进入上下文。
    """

    id: str
    kind: AssetKind
    index: str
    body: str = ""
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise InvariantError("资产必须有 id")
        if not self.index.strip():
            raise InvariantError(f"资产 {self.id} 必须有常驻索引，否则无法被检索")
        if len(self.index) > 120:
            raise InvariantError(
                f"资产 {self.id} 的索引有 {len(self.index)} 字符；"
                "索引常驻，超过 120 字符就会自己挤占窗口"
            )
        if self.kind is AssetKind.CODE and not self.body:
            raise InvariantError(f"代码资产 {self.id} 必须有正文，否则加载不到东西")


def assert_kinds_closed(specs: list[AssetSpec]) -> None:
    """分类闭合：不允许出现四类之外的东西。"""
    for spec in specs:
        if not isinstance(spec.kind, AssetKind):
            raise InvariantError(f"资产 {spec.id} 的类型不在四类之内：{spec.kind!r}")
