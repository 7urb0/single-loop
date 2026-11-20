"""主循环：一个模型、一个上下文窗口、计划自管。

这里只有一份 messages。所有决策、所有工具结果、所有计划修改都落在同一份
上下文里，不经过任何摘要或转述。
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from .disclosure import Disclosure
from .gate import Budget, Gate, StopReason
from .registry import Registry
from .runtime import Outcome, ToolDef, ToolRuntime
from .spec import AssetKind, AssetSpec
from .verify import (
    CheckResult,
    DefaultFormalVerifier,
    FormalVerifier,
    SemanticVerifier,
    Verdict,
)


# ----------------------------------------------------------------------
# 模型接口
# ----------------------------------------------------------------------


@dataclass
class ToolCall:
    call_id: str
    name: str
    arguments: dict


@dataclass
class Reply:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens: int = 0


class Model:
    """模型客户端协议。"""

    def chat(self, messages: list[dict], tools: list[dict]) -> Reply:
        raise NotImplementedError


# ----------------------------------------------------------------------
# 结果
# ----------------------------------------------------------------------


@dataclass
class LoopResult:
    answer: str | None
    turns: int
    stopped: StopReason
    calls: list[str]
    denied: list[str]
    plan: list[str]
    verification: CheckResult | None
    semantic: CheckResult | None
    messages: list[dict]


# ----------------------------------------------------------------------
# 元工具
# ----------------------------------------------------------------------

META_DISCOVER = "discover"
META_PLAN = "update_plan"

_META_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": META_DISCOVER,
            "description": (
                "检索资产。工具会在这里被加载并立即可调用；"
                "技能和知识会直接返回正文。不先检索的东西不会进入上下文。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "你想要什么"},
                    "kind": {
                        "type": "string",
                        "enum": ["skill", "tool", "knowledge", "code"],
                        "description": "限定类型，不填则全类型检索",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": META_PLAN,
            "description": "写下或修改当前计划。后续每一轮都能看到它。",
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "按顺序的计划步骤",
                    }
                },
                "required": ["steps"],
            },
        },
    },
]

_SYSTEM_TEMPLATE = """你是一个单循环 Agent。只有一个上下文窗口，所有工作都在这里完成。

{index}

规则：
1. 需要工具或参考资料时，先调用 discover 检索。检索之前，那些东西不在你的上下文里。
2. 任务有多步时，用 update_plan 写下计划；看到结果后可以随时改它。
3. 工具返回的结果是原始数据，不会被压缩，直接读。
4. 工具可能拒绝你，拒绝会说明原因。读原因改做法，不要重复同一个调用。
5. 做完之后直接给答案，不要复述计划。"""


class MainLoop:
    """单循环执行器。"""

    def __init__(
        self,
        model: Model,
        registry: Registry,
        *,
        budget: Budget | None = None,
        max_workers: int = 4,
        formal_verifier: FormalVerifier | None = None,
        semantic_verifier: SemanticVerifier | None = None,
        system_note: str = "",
    ) -> None:
        self.model = model
        self.registry = registry
        self.disclosure = Disclosure(registry)
        self.gate = Gate(budget)
        self.runtime = ToolRuntime()
        self.formal: FormalVerifier = formal_verifier or DefaultFormalVerifier()
        self.semantic = semantic_verifier
        self.max_workers = max(1, max_workers)
        self.system_note = system_note

        self._loaded_tools: set[str] = set()
        self._plan: list[str] = []
        self._calls: list[str] = []
        self._denied: list[str] = []
        self._pending_note: str = ""

    # ---- 注册 ----

    def register_tool(self, tool: ToolDef) -> None:
        """注册一个业务工具。它不会立刻出现在模型可见的工具列表里。"""
        self.runtime.register(tool)
        if self.registry.get(tool.name) is None:
            self.registry.add(
                AssetSpec(
                    id=tool.name,
                    kind=AssetKind.TOOL,
                    index=(tool.description or tool.name)[:120],
                    body=json.dumps(tool.schema, ensure_ascii=False),
                    tags=tool.tags,
                )
            )

    # ---- 对外 ----

    def run(self, task: str) -> LoopResult:
        messages: list[dict] = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": task},
        ]
        answer: str | None = None
        stopped = StopReason.NONE

        while True:
            stopped = self.gate.before_turn()
            if stopped is not StopReason.NONE:
                break
            self.gate.enter_turn()

            reply = self.model.chat(messages, self._visible_schemas())
            self.gate.charge(reply.tokens)

            if not reply.tool_calls:
                answer = reply.content
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": reply.content or "",
                    "tool_calls": [
                        {
                            "id": call.call_id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments, ensure_ascii=False),
                            },
                        }
                        for call in reply.tool_calls
                    ],
                }
            )

            payloads = self._execute_batch(reply.tool_calls)
            for call, payload in zip(reply.tool_calls, payloads, strict=True):
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.call_id,
                        "content": json.dumps(payload, ensure_ascii=False),
                    }
                )
            if self._pending_note:
                messages.append({"role": "system", "content": self._pending_note})
                self._pending_note = ""

        formal = self.formal.check(answer or "", {"turns": self.gate.turns})
        semantic = None
        if self.semantic is not None and formal.verdict is Verdict.PASS:
            semantic = self.semantic.verify(answer or "", task)

        return LoopResult(
            answer=answer,
            turns=self.gate.turns,
            stopped=stopped,
            calls=list(self._calls),
            denied=list(self._denied),
            plan=list(self._plan),
            verification=formal,
            semantic=semantic,
            messages=messages,
        )

    # ---- 内部 ----

    def _system_prompt(self) -> str:
        text = _SYSTEM_TEMPLATE.format(index=self.disclosure.index_text())
        if self.system_note:
            text = f"{text}\n\n{self.system_note}"
        return text

    def _visible_schemas(self) -> list[dict]:
        """元工具常驻，业务工具要加载过才可见。"""
        return [*_META_SCHEMAS, *self.runtime.schemas(sorted(self._loaded_tools))]

    def _execute_batch(self, calls: list[ToolCall]) -> list[dict]:
        if len(calls) <= 1:
            return [self._invoke(call) for call in calls]
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(calls))) as pool:
            futures = [pool.submit(self._invoke, call) for call in calls]
            return [future.result() for future in futures]

    def _invoke(self, call: ToolCall) -> dict:
        self._calls.append(call.name)
        if call.name == META_DISCOVER:
            return self._handle_discover(call.arguments)
        if call.name == META_PLAN:
            return self._handle_plan(call.arguments)
        if call.name not in self._loaded_tools:
            return {
                "outcome": "not_loaded",
                "detail": f"{call.name} 还没有被检索加载，先调用 discover",
            }
        result = self.runtime.call(call.name, call.arguments)
        signature = (
            f"{call.name}:"
            f"{json.dumps(call.arguments, sort_keys=True, ensure_ascii=False)}"
        )
        if result.denied:
            self.gate.note_denial(signature)
            self._denied.append(call.name)
        elif result.outcome is Outcome.OK:
            self.gate.clear_denial(signature)
        return result.to_payload()

    def _handle_discover(self, args: dict) -> dict:
        query = str(args.get("query", ""))
        raw_kind = args.get("kind")
        try:
            kind = AssetKind(raw_kind) if raw_kind else None
        except ValueError:
            return {"outcome": "bad_kind", "detail": f"未知类型 {raw_kind!r}"}

        hits = self.disclosure.search(query, kind)
        if not hits:
            return {"outcome": "no_hit", "detail": f"没有匹配「{query}」的资产"}

        loaded_tools: list[str] = []
        bodies: list[dict] = []
        for hit in hits:
            spec = self.disclosure.load(hit.spec.id)
            if spec.kind is AssetKind.TOOL:
                if self.runtime.get(spec.id) is not None:
                    self._loaded_tools.add(spec.id)
                    loaded_tools.append(spec.id)
            else:
                bodies.append(
                    {"id": spec.id, "kind": spec.kind.value, "body": spec.body}
                )

        payload: dict[str, Any] = {
            "outcome": "ok",
            "matched": [hit.spec.id for hit in hits],
        }
        if loaded_tools:
            payload["loaded_tools"] = loaded_tools
            payload["note"] = "这些工具现在可以调用了"
        if bodies:
            payload["assets"] = bodies
        return payload

    def _handle_plan(self, args: dict) -> dict:
        steps = [str(s) for s in args.get("steps", []) if str(s).strip()]
        self._plan = steps
        self._pending_note = render_plan_note(steps)
        return {"outcome": "ok", "plan": steps, "note": "计划已更新，后续每轮可见"}

    # ---- 供外部查询 ----

    @property
    def plan(self) -> list[str]:
        return list(self._plan)

    @property
    def loaded_tools(self) -> set[str]:
        return set(self._loaded_tools)


def render_plan_note(plan: list[str]) -> str:
    """把计划渲染成一条可插入上下文的 system 消息。"""
    if not plan:
        return ""
    body = "\n".join(f"{i}. {step}" for i, step in enumerate(plan, 1))
    return f"当前计划：\n{body}"
