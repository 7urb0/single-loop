"""验收：形式检查在循环内，语义验证外置。

这两层的分工是这套架构里最容易被混掉的一处。
形式检查看的是「答案里有没有不该有的东西」，它在一个上下文里做没问题，
因为它比的是事实，不是理解。
语义验证看的是「答案对不对」，它必须由另一个执行体做，
否则就是让回答者给自己打分。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class Verdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"


@dataclass
class CheckResult:
    verdict: Verdict
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.verdict is Verdict.PASS


class FormalVerifier(Protocol):
    """形式检查。在同一个循环里跑，只比对可核对的事实。"""

    def check(self, answer: str, context: dict) -> CheckResult: ...


class SemanticVerifier(Protocol):
    """语义验证。

    必须在独立执行体里跑：不同的模型调用、不同的上下文。
    如果实现里复用了主循环的 messages，这个接口就失去意义了。
    """

    def verify(self, answer: str, task: str) -> CheckResult: ...


class DefaultFormalVerifier:
    """默认的形式检查：空答案、超长答案、未闭合的代码块。"""

    def __init__(self, max_chars: int = 20_000) -> None:
        self.max_chars = max_chars

    def check(self, answer: str, context: dict) -> CheckResult:
        if not answer or not answer.strip():
            return CheckResult(Verdict.FAIL, "输出为空")
        if len(answer) > self.max_chars:
            return CheckResult(
                Verdict.FAIL, f"输出 {len(answer)} 字符，超过上限 {self.max_chars}"
            )
        if answer.count("```") % 2 != 0:
            return CheckResult(Verdict.FAIL, "代码块未闭合")
        return CheckResult(Verdict.PASS)


class BlocklistVerifier:
    """形式检查的另一种用法：禁止某些字面量出现在最终答案里。

    对应文章里「未批准来源的数值不得进入交付物」那类要求。
    """

    def __init__(self, forbidden: list[str]) -> None:
        self.forbidden = [f for f in forbidden if f]

    def check(self, answer: str, context: dict) -> CheckResult:
        hits = [f for f in self.forbidden if f in answer]
        if hits:
            return CheckResult(Verdict.FAIL, f"输出包含禁用内容：{hits}")
        return CheckResult(Verdict.PASS)
