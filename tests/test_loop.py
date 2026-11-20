"""主循环：单上下文、渐进披露、计划自管、门控。"""

from __future__ import annotations

from single_loop import Budget, MainLoop, Registry, Reply, StopReason
from single_loop.testing import ScriptedModel, text, tool_call


def build(registry: Registry, order_tools, script, **kwargs) -> tuple[MainLoop, ScriptedModel]:
    model = ScriptedModel(script)
    loop = MainLoop(model, registry, **kwargs)
    for tool in order_tools.values():
        loop.register_tool(tool)
    return loop, model


def test_end_to_end(registry: Registry, order_tools) -> None:
    loop, model = build(
        registry,
        order_tools,
        [
            tool_call("discover", {"query": "订单"}),
            tool_call("get_order", {"order_id": "SO-1"}),
            tool_call("discover", {"query": "地址"}),
            tool_call("update_address", {"order_id": "SO-1", "address": "杭州西湖区"}),
            tool_call("discover", {"query": "改派"}),
            tool_call("create_carrier_change", {"order_id": "SO-1", "carrier": "中通"}),
            text("地址已改，改派单 CC-001 已提交。"),
        ],
    )
    result = loop.run("把 SO-1 的地址改到杭州西湖区")

    assert result.answer == "地址已改，改派单 CC-001 已提交。"
    assert result.stopped is StopReason.NONE
    assert result.calls == [
        "discover",
        "get_order",
        "discover",
        "update_address",
        "discover",
        "create_carrier_change",
    ]
    assert result.denied == []
    assert result.verification is not None and result.verification.passed


def test_tools_are_hidden_until_loaded(registry: Registry, order_tools) -> None:
    loop, model = build(registry, order_tools, [text("好")])
    loop.run("随便")
    first = model.tools_seen[0]
    assert first == ["discover", "update_plan"]


def test_loaded_tool_becomes_visible(registry: Registry, order_tools) -> None:
    loop, model = build(
        registry,
        order_tools,
        [tool_call("discover", {"query": "订单"}), text("好")],
    )
    loop.run("查订单")
    assert "get_order" in model.tools_seen[1]
    assert "update_address" not in model.tools_seen[1]


def test_unloaded_tool_call_is_rejected(registry: Registry, order_tools) -> None:
    loop, model = build(
        registry,
        order_tools,
        [tool_call("get_order", {"order_id": "SO-1"}), text("好")],
    )
    result = loop.run("查订单")
    tool_payload = [m for m in result.messages if m["role"] == "tool"][0]["content"]
    assert "not_loaded" in tool_payload


def test_precondition_denial_is_reported(registry: Registry, order_tools) -> None:
    loop, model = build(
        registry,
        order_tools,
        [
            tool_call("discover", {"query": "地址"}),
            tool_call("update_address", {"order_id": "SO-1", "address": "杭州"}),
            text("先查订单"),
        ],
    )
    result = loop.run("改地址")
    assert result.denied == ["update_address"]
    payload = [m for m in result.messages if m["role"] == "tool"][-1]["content"]
    assert "precondition_failed" in payload


def test_plan_note_is_injected_after_update(registry: Registry, order_tools) -> None:
    loop, model = build(
        registry,
        order_tools,
        [
            tool_call("update_plan", {"steps": ["查订单", "改地址", "提改派"]}),
            text("好"),
        ],
    )
    result = loop.run("改地址")
    assert result.plan == ["查订单", "改地址", "提改派"]
    system_notes = [
        m["content"] for m in result.messages if m["role"] == "system"
    ]
    assert any("当前计划" in note for note in system_notes)


def test_turn_limit_stops_loop(registry: Registry, order_tools) -> None:
    loop, _ = build(
        registry,
        order_tools,
        [tool_call("discover", {"query": "订单"}) for _ in range(10)],
        budget=Budget(max_turns=2),
    )
    result = loop.run("查订单")
    assert result.stopped is StopReason.TURNS
    assert result.answer is None


def test_repeat_denial_stops_loop(registry: Registry, order_tools) -> None:
    loop, _ = build(
        registry,
        order_tools,
        [
            tool_call("discover", {"query": "地址"}),
            tool_call("update_address", {"order_id": "SO-1", "address": "杭州"}),
            tool_call("update_address", {"order_id": "SO-1", "address": "杭州"}),
            text("好"),
        ],
        budget=Budget(max_turns=50, max_repeat_denials=2),
    )
    result = loop.run("改地址")
    assert result.stopped is StopReason.REPEAT_DENIAL


def test_discover_no_hit(registry: Registry, order_tools) -> None:
    loop, _ = build(
        registry, order_tools, [tool_call("discover", {"query": "量子计算"}), text("好")]
    )
    result = loop.run("问点别的")
    payload = [m for m in result.messages if m["role"] == "tool"][0]["content"]
    assert "no_hit" in payload


def test_discover_returns_skill_body(registry: Registry, order_tools) -> None:
    from single_loop import AssetKind, AssetSpec

    registry.add(
        AssetSpec(
            id="refund-sop",
            kind=AssetKind.SKILL,
            index="退款审批流程与判断标准",
            body="超过 3000 元需要财务审批",
        )
    )
    loop, _ = build(
        registry, order_tools, [tool_call("discover", {"query": "退款审批"}), text("好")]
    )
    result = loop.run("退款")
    payload = [m for m in result.messages if m["role"] == "tool"][0]["content"]
    assert "超过 3000 元" in payload


def test_batch_calls_run_in_parallel_path(registry: Registry, order_tools) -> None:
    """同一轮发出多个调用时走并行分支，结果仍按顺序回填。"""

    batch = Reply(
        content=None,
        tool_calls=[
            tool_call("discover", {"query": "订单"}, "c1").tool_calls[0],
            tool_call("discover", {"query": "地址"}, "c2").tool_calls[0],
        ],
    )
    loop, _ = build(registry, order_tools, [batch, text("好")])
    result = loop.run("并行检索")
    tool_msgs = [m for m in result.messages if m["role"] == "tool"]
    assert len(tool_msgs) == 2
    assert tool_msgs[0]["tool_call_id"] == "c1"
    assert tool_msgs[1]["tool_call_id"] == "c2"
