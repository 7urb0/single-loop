"""测试与演示用的模型：脚本回放、按消息决策、真实请求熔断。"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from .loop import Model, Reply, ToolCall

__all__ = [
    "RealModelBlocked",
    "ScriptedModel",
    "block_real_requests",
    "text",
    "tool_call",
]


class RealModelBlocked(RuntimeError):
    """测试环境误发真实模型请求。"""


_BLOCKED = False


def set_real_requests_blocked(blocked: bool) -> None:
    global _BLOCKED
    _BLOCKED = blocked


def real_requests_blocked() -> bool:
    return _BLOCKED


@contextmanager
def block_real_requests() -> Iterator[None]:
    set_real_requests_blocked(True)
    try:
        yield
    finally:
        set_real_requests_blocked(False)


def text(content: str) -> Reply:
    return Reply(content=content)


def tool_call(name: str, arguments: dict, call_id: str | None = None) -> Reply:
    return Reply(
        content=None,
        tool_calls=[ToolCall(call_id or f"call_{name}", name, arguments)],
    )


class ScriptedModel(Model):
    """按脚本顺序回放。脚本耗尽时可选抛错或返回空回复。"""

    def __init__(self, script: list[Reply], on_exhausted: str = "raise") -> None:
        self._script = list(script)
        self._on_exhausted = on_exhausted
        self.calls: list[list[dict]] = []
        self.tools_seen: list[list[str]] = []

    def chat(self, messages: list[dict], tools: list[dict]) -> Reply:
        self.calls.append([dict(m) for m in messages])
        self.tools_seen.append(
            [t["function"]["name"] for t in tools if "function" in t]
        )
        if not self._script:
            if self._on_exhausted == "raise":
                raise AssertionError("脚本耗尽：模型被调用次数超出预期")
            return Reply(content="（脚本已耗尽）")
        return self._script.pop(0)

    @property
    def remaining(self) -> int:
        return len(self._script)


class FunctionModel(Model):
    """按当前消息动态决定回复。"""

    def __init__(self, fn: Callable[[list[dict]], Reply]) -> None:
        self._fn = fn
        self.calls: list[list[dict]] = []
        self.tools_seen: list[list[str]] = []

    def chat(self, messages: list[dict], tools: list[dict]) -> Reply:
        self.calls.append([dict(m) for m in messages])
        self.tools_seen.append(
            [t["function"]["name"] for t in tools if "function" in t]
        )
        return self._fn(messages)
