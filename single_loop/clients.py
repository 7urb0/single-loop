"""OpenAI 兼容客户端（DeepSeek / DashScope / OpenAI）。

openai 是可选依赖：只做离线测试时不需要装。
"""

from __future__ import annotations

import json

from .loop import Model, Reply, ToolCall
from .testing import RealModelBlocked, real_requests_blocked


class OpenAICompatClient(Model):
    """把 OpenAI 兼容协议适配成 Model 接口。

    extra_headers 用于需要额外路由头的网关。例如 opencode-go 要求
    x-opencode-session，缺了会返回 400 而不是路由到模型。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.extra_headers = dict(extra_headers or {})
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from openai import OpenAI  # 延迟导入

            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def chat(self, messages: list[dict], tools: list[dict]) -> Reply:
        if real_requests_blocked():
            raise RealModelBlocked(
                "测试环境禁止真实模型请求：请改用 single_loop.testing 里的脚本模型"
            )
        client = self._ensure_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            tools=tools or None,
            extra_headers=self.extra_headers or None,
        )
        message = response.choices[0].message
        calls: list[ToolCall] = []
        for call in message.tool_calls or []:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {"_raw": call.function.arguments}
            calls.append(
                ToolCall(call_id=call.id, name=call.function.name, arguments=arguments)
            )
        usage = getattr(response, "usage", None)
        tokens = int(getattr(usage, "total_tokens", 0) or 0)
        return Reply(content=message.content, tool_calls=calls, tokens=tokens)
