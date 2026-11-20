"""工具运行时：前置条件、权限、机械部分。"""

from __future__ import annotations

import pytest

from single_loop import Outcome, ToolDef, ToolRuntime


def make_runtime() -> ToolRuntime:
    rt = ToolRuntime()

    rt.register(
        ToolDef(
            name="fetch",
            fn=lambda q: {"data": q},
            schema={"type": "function", "function": {"name": "fetch", "parameters": {}}},
            description="取数",
        )
    )
    rt.register(
        ToolDef(
            name="transform",
            fn=lambda q: {"out": q},
            schema={"type": "function", "function": {"name": "transform", "parameters": {}}},
            description="加工",
            requires=("fetch",),
        )
    )
    rt.register(
        ToolDef(
            name="delete_account",
            fn=lambda uid: {"deleted": uid},
            schema={"type": "function", "function": {"name": "delete_account", "parameters": {}}},
            description="删号",
            permission=lambda args: args.get("uid") == "self",
        )
    )
    return rt


def test_ok_call() -> None:
    result = make_runtime().call("fetch", {"q": "A"})
    assert result.outcome is Outcome.OK
    assert result.data == {"data": "A"}


def test_precondition_blocks_until_dependency_succeeds() -> None:
    rt = make_runtime()
    denied = rt.call("transform", {"q": "A"})
    assert denied.outcome is Outcome.PRECONDITION
    assert "fetch" in denied.detail

    rt.call("fetch", {"q": "A"})
    assert rt.call("transform", {"q": "A"}).outcome is Outcome.OK


def test_permission_denied() -> None:
    rt = make_runtime()
    denied = rt.call("delete_account", {"uid": "someone_else"})
    assert denied.outcome is Outcome.PERMISSION
    assert rt.call("delete_account", {"uid": "self"}).outcome is Outcome.OK


def test_unknown_tool() -> None:
    assert make_runtime().call("nope", {}).outcome is Outcome.UNKNOWN


def test_exception_becomes_error_result() -> None:
    rt = ToolRuntime()
    rt.register(
        ToolDef(
            name="boom",
            fn=lambda: (_ for _ in ()).throw(TimeoutError("超时 30s")),
            schema={"type": "function", "function": {"name": "boom", "parameters": {}}},
        )
    )
    result = rt.call("boom", {})
    assert result.outcome is Outcome.ERROR
    assert "TimeoutError" in result.detail


def test_payload_shape() -> None:
    rt = make_runtime()
    ok = rt.call("fetch", {"q": "A"}).to_payload()
    assert ok["outcome"] == "ok" and "data" in ok

    fresh = make_runtime()
    denied = fresh.call("transform", {"q": "A"}).to_payload()
    assert denied["outcome"] == "precondition_failed" and "detail" in denied


def test_schemas_only_returns_known() -> None:
    rt = make_runtime()
    names = [s["function"]["name"] for s in rt.schemas(["fetch", "nope"])]
    assert names == ["fetch"]
