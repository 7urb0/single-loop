"""工具运行时：前置条件、权限、机械部分。

这三件事都放在工具内部，不放在协调者里。
好处是同一个循环可以服务不同权限的用户，不必为每级权限配一个代理。
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Outcome(str, Enum):
    OK = "ok"
    PRECONDITION = "precondition_failed"
    PERMISSION = "permission_denied"
    UNKNOWN = "unknown_tool"
    ERROR = "error"


@dataclass
class ToolResult:
    outcome: Outcome
    data: Any = None
    detail: str = ""

    def to_payload(self) -> dict:
        if self.outcome is Outcome.OK:
            return {"outcome": self.outcome.value, "data": self.data}
        return {"outcome": self.outcome.value, "detail": self.detail}

    @property
    def denied(self) -> bool:
        return self.outcome in (Outcome.PRECONDITION, Outcome.PERMISSION)


@dataclass
class ToolDef:
    """一个可执行工具。

    requires 是硬前置条件：列出的工具必须先成功跑过一次。
    permission 接收本次参数，返回是否放行。两者都可以不填。
    """

    name: str
    fn: Callable[..., Any]
    schema: dict
    description: str = ""
    requires: tuple[str, ...] = ()
    permission: Callable[[dict], bool] | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)


class ToolRuntime:
    """工具执行器。拒绝也返回结构化结果，模型读得懂就能自己改路。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}
        self._succeeded: set[str] = set()
        self._lock = threading.Lock()

    def register(self, tool: ToolDef) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def schemas(self, names: list[str]) -> list[dict]:
        out: list[dict] = []
        for name in names:
            tool = self._tools.get(name)
            if tool is not None:
                out.append(tool.schema)
        return out

    def call(self, name: str, args: dict) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(Outcome.UNKNOWN, detail=f"未知工具 {name}")

        if tool.permission is not None and not tool.permission(args):
            return ToolResult(
                Outcome.PERMISSION,
                detail=f"{name}：当前调用者无权执行该操作",
            )

        with self._lock:
            done = set(self._succeeded)
        missing = [r for r in tool.requires if r not in done]
        if missing:
            return ToolResult(
                Outcome.PRECONDITION,
                detail=f"{name} 需要先成功调用 {missing}，再接收它的输出",
            )

        try:
            data = tool.fn(**args)
        except Exception as exc:  # 工具内部异常不当崩溃处理，回填给模型
            return ToolResult(Outcome.ERROR, detail=f"{type(exc).__name__}: {exc}")

        with self._lock:
            self._succeeded.add(name)
        return ToolResult(Outcome.OK, data=data)

    @property
    def succeeded(self) -> set[str]:
        with self._lock:
            return set(self._succeeded)
