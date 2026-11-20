"""真实模型演示：验证三件事。

1. 模型会不会主动检索（不检索就没有工具可用）
2. 模型会不会用 update_plan 维护计划
3. 被工具拒绝之后，是改路还是原样重试

跑法：
    python examples/live_demo.py
需要项目根目录或 D:\\agent\\intent-anchor\\.env 里配好 key。
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from single_loop import Budget, MainLoop, Registry, ToolDef  # noqa: E402
from single_loop.clients import OpenAICompatClient  # noqa: E402


def load_env(*candidates: str) -> None:
    for candidate in candidates:
        path = Path(candidate)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
        return


def schema(name: str, desc: str, props: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


def build_tools() -> dict[str, ToolDef]:
    # 置 LIVE_INJECT_FAILURE=1 时，承运商接口第一次调用超时，第二次成功。
    # 用来观察：被拒之后模型是重试、改路，还是直接放弃。
    inject_failure = os.environ.get("LIVE_INJECT_FAILURE") == "1"
    attempts = {"n": 0}

    def get_order(order_id: str) -> dict:
        return {"order_id": order_id, "status": "shipped", "carrier": "中通"}

    def update_address(order_id: str, address: str) -> dict:
        return {"order_id": order_id, "address": address, "ok": True}

    def create_carrier_change(order_id: str, carrier: str) -> dict:
        attempts["n"] += 1
        if inject_failure and attempts["n"] == 1:
            raise TimeoutError("承运商改派接口超时 30s，可稍后重试")
        return {"order_id": order_id, "carrier": carrier, "ticket": "CC-88231-01"}

    return {
        "get_order": ToolDef(
            name="get_order",
            fn=get_order,
            schema=schema(
                "get_order", "查订单", {"order_id": {"type": "string"}}, ["order_id"]
            ),
            description="按订单号查询订单状态",
        ),
        "update_address": ToolDef(
            name="update_address",
            fn=update_address,
            schema=schema(
                "update_address",
                "改地址",
                {"order_id": {"type": "string"}, "address": {"type": "string"}},
                ["order_id", "address"],
            ),
            description="修改收货地址",
            requires=("get_order",),
        ),
        "create_carrier_change": ToolDef(
            name="create_carrier_change",
            fn=create_carrier_change,
            schema=schema(
                "create_carrier_change",
                "提改派单",
                {"order_id": {"type": "string"}, "carrier": {"type": "string"}},
                ["order_id", "carrier"],
            ),
            description="向承运商提交改派单",
            requires=("update_address",),
        ),
    }


def main() -> int:
    load_env(
        str(Path(__file__).resolve().parents[1] / ".env"),
        r"D:\agent\intent-anchor\.env",
    )
    if not os.environ.get("OPENAI_API_KEY"):
        print("缺少 OPENAI_API_KEY")
        return 1

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")
    extra_headers: dict[str, str] = {}
    if "opencode" in base_url:
        extra_headers["x-opencode-session"] = os.environ.get(
            "OPENCODE_SESSION", uuid.uuid4().hex
        )

    model = OpenAICompatClient(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=base_url,
        model=os.environ.get("OPENAI_MODEL", "deepseek-v4.1-flash"),
        extra_headers=extra_headers,
    )
    loop = MainLoop(
        model,
        Registry(),
        budget=Budget(max_turns=10, max_repeat_denials=2),
    )
    for tool in build_tools().values():
        loop.register_tool(tool)

    task = os.environ.get(
        "LIVE_TASK",
        "订单 SO-88231 的收货地址要改到杭州西湖区，客户催得急，帮我看下能不能改。",
    )
    print("=" * 70)
    print(f"任务：{task}")
    print("=" * 70)

    result = loop.run(task)

    print("\n工具调用轨迹：")
    for message in result.messages:
        if message["role"] == "tool":
            payload = json.loads(message["content"])
            print(
                f"  {message['tool_call_id']:<14} "
                f"{payload.get('outcome', '?'):<22} "
                f"{payload.get('detail') or payload.get('note') or ''}"
            )

    print("\n" + "-" * 70)
    print(f"轮次：{result.turns}   停止：{result.stopped.value}")
    print(f"计划：{result.plan or '（模型没有写计划）'}")
    print(f"被拒：{result.denied}")
    print(f"形式验收：{result.verification.detail if result.verification else '无'}"
          f"（{result.verification.verdict.value if result.verification else ''}）")
    print(f"答案：{result.answer}")

    # 障碍包括：工具报错、前置条件不满足、权限拒绝、没检索就调用。
    # 只看 denied 会漏掉工具自己抛错的情况。
    obstacles: list[str] = []
    for message in result.messages:
        if message["role"] != "tool":
            continue
        outcome = json.loads(message["content"]).get("outcome")
        if outcome in ("error", "precondition_failed", "permission_denied", "not_loaded"):
            obstacles.append(outcome)

    used_discover = "discover" in result.calls
    used_plan = bool(result.plan)
    recovered = bool(obstacles) and bool(result.answer) and result.stopped.value == "none"
    print("\n三项观察：")
    print(f"  主动检索：{'是' if used_discover else '否'}")
    print(f"  维护计划：{'是' if used_plan else '否'}")
    print(f"  遇到障碍：{obstacles or '无'}")
    print(f"  障碍后恢复：{'是' if recovered else '否'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
