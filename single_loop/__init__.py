"""single_loop —— 单循环 Agent 的最小实现。

对应文章《从多智能体到单循环》里的架构图：一个模型、一个上下文窗口、
四类资产走渐进披露、工具内部自查前置与权限、门控在循环外、验收分两层。
"""

from .disclosure import Disclosure, Hit, tokenize
from .gate import Budget, Gate, StopReason
from .loop import (
    META_DISCOVER,
    META_PLAN,
    LoopResult,
    MainLoop,
    Model,
    Reply,
    ToolCall,
    render_plan_note,
)
from .registry import Registry
from .runtime import Outcome, ToolDef, ToolResult, ToolRuntime
from .spec import AssetKind, AssetSpec, InvariantError, assert_kinds_closed
from .verify import (
    BlocklistVerifier,
    CheckResult,
    DefaultFormalVerifier,
    FormalVerifier,
    SemanticVerifier,
    Verdict,
)

__version__ = "0.1.0"

__all__ = [
    "AssetKind",
    "AssetSpec",
    "BlocklistVerifier",
    "Budget",
    "CheckResult",
    "DefaultFormalVerifier",
    "Disclosure",
    "FormalVerifier",
    "Gate",
    "Hit",
    "InvariantError",
    "LoopResult",
    "META_DISCOVER",
    "META_PLAN",
    "MainLoop",
    "Model",
    "Outcome",
    "Registry",
    "Reply",
    "SemanticVerifier",
    "StopReason",
    "ToolCall",
    "ToolDef",
    "ToolResult",
    "ToolRuntime",
    "Verdict",
    "__version__",
    "assert_kinds_closed",
    "render_plan_note",
    "tokenize",
]
