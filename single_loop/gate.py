"""门控：轮次、预算、重复拒绝止损。

架构图里这一层在主循环外面，任何一轮开始前都要过。
它只回答一个问题：还该不该继续。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum


class StopReason(str, Enum):
    NONE = "none"
    TURNS = "turns"
    BUDGET = "budget"
    REPEAT_DENIAL = "repeat_denial"


@dataclass
class Budget:
    """门控的三个上限。"""

    max_turns: int = 12
    max_tokens: int = 200_000
    max_repeat_denials: int = 3

    def __post_init__(self) -> None:
        if self.max_turns < 1:
            raise ValueError("max_turns 必须 >= 1")
        if self.max_tokens < 1:
            raise ValueError("max_tokens 必须 >= 1")
        if self.max_repeat_denials < 1:
            raise ValueError("max_repeat_denials 必须 >= 1")


class Gate:
    """外层门控。

    重复拒绝止损是为了补一个洞：工具拒绝之后模型很可能换个参数再试，
    来回几次就把轮次耗光。同一个调用签名被拒满次数，直接停。
    """

    def __init__(self, budget: Budget | None = None) -> None:
        self.budget = budget or Budget()
        self.turns = 0
        self.tokens = 0
        self._denials: Counter[str] = Counter()

    def before_turn(self) -> StopReason:
        """返回本轮是否放行。"""
        if self.turns >= self.budget.max_turns:
            return StopReason.TURNS
        if self.tokens >= self.budget.max_tokens:
            return StopReason.BUDGET
        if self._denials and max(self._denials.values()) >= self.budget.max_repeat_denials:
            return StopReason.REPEAT_DENIAL
        return StopReason.NONE

    def enter_turn(self) -> None:
        self.turns += 1

    def charge(self, tokens: int) -> None:
        if tokens > 0:
            self.tokens += tokens

    def note_denial(self, signature: str) -> None:
        """记录一次被拒绝的调用。"""
        self._denials[signature] += 1

    def clear_denial(self, signature: str) -> None:
        """该签名后来成功过一次，说明不是死路，把计数清掉。"""
        self._denials.pop(signature, None)

    @property
    def denial_counts(self) -> dict[str, int]:
        return dict(self._denials)
