import json
from collections.abc import AsyncIterator

import httpx

from rennew.providers.contracts import (
    ChatRequest,
    ProviderCapabilities,
    ProviderMessage,
    StreamDelta,
    ToolSchema,
)
from rennew.providers.sse import iter_sse_lines


class OpenAICompatibleProvider:
    """Any endpoint speaking OpenAI `chat/completions` with SSE streaming.

    Covers OpenAI, Ollama, vLLM, LM Studio, OpenRouter, Groq, LiteLLM,
    and custom/self-hosted gateways. Configured by base_url + api_key.
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str | None,
        *,
        default_headers: dict[str, str] | None = None,
        supports_reasoning: bool = False,
        context_window: int | None = None,
    ) -> None:
        self.name = name
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._headers = dict(default_headers or {})
        self._supports_reasoning = supports_reasoning
        self._context_window = context_window

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            streaming=True,
            tool_calling=True,
            parallel_tool_calls=True,
            reasoning=self._supports_reasoning,
            context_window=self._context_window,
            auth_env=["OPENAI_API_KEY"],
        )

    def _payload(self, request: ChatRequest) -> dict[str, object]:
        tools = [self._tool_schema(t) for t in request.tools]
        payload: dict[str, object] = {
            "model": request.model,
            "messages": [self._message(m) for m in request.messages],
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            payload["tools"] = tools
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        payload.update(request.extra)
        return payload

    @staticmethod
    def _message(message: ProviderMessage) -> dict[str, object]:
        msg = message.model_dump(exclude_none=True)
        role = msg.get("role")
        if role == "tool":
            return {
                "role": "tool",
                "tool_call_id": msg.get("tool_call_id", ""),
                "content": msg.get("content", ""),
            }
        if role == "assistant" and msg.get("tool_calls"):
            return {
                "role": "assistant",
                "content": msg.get("content", "") or None,
                "tool_calls": msg["tool_calls"],
            }
        return {"role": role, "content": msg.get("content", "")}

    @staticmethod
    def _tool_schema(tool: ToolSchema) -> dict[str, object]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters or {"type": "object", "properties": {}},
            },
        }

    def _request_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self._headers}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamDelta]:
        url = f"{self._base_url}/chat/completions"
        tool_buffers: dict[int, dict[str, str]] = {}
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream(
                    "POST", url, json=self._payload(request), headers=self._request_headers()
                ) as response:
                    if response.status_code != 200:
                        body = (await response.aread()).decode("utf-8", errors="replace")
                        yield StreamDelta(kind="error", error=f"HTTP {response.status_code}: {body}")
                        return
                    async for data in iter_sse_lines(response.aiter_lines()):
                        if data.strip() == "[DONE]":
                            break
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        for delta in self._parse_event(event, tool_buffers):
                            yield delta
            except httpx.HTTPError as error:
                yield StreamDelta(kind="error", error=f"Connection failed: {error}")

    def _parse_event(
        self, event: dict[str, object], tool_buffers: dict[int, dict[str, str]]
    ) -> list[StreamDelta]:
        deltas: list[StreamDelta] = []
        usage = event.get("usage")
        if isinstance(usage, dict):
            deltas.append(
                StreamDelta(
                    kind="usage",
                    usage={
                        "input": int(usage.get("prompt_tokens") or 0),
                        "output": int(usage.get("completion_tokens") or 0),
                        "reasoning": int(
                            (usage.get("completion_tokens_details") or {}).get(
                                "reasoning_tokens", 0
                            )
                            if isinstance(usage.get("completion_tokens_details"), dict)
                            else 0
                        ),
                    },
                )
            )

        choices = event.get("choices")
        if not isinstance(choices, list):
            return deltas

        for choice in choices:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta") or {}
            text = delta.get("content")
            if isinstance(text, str) and text:
                deltas.append(StreamDelta(kind="text", text=text))
            reasoning = delta.get("reasoning_content") or delta.get("reasoning")
            if isinstance(reasoning, str) and reasoning:
                deltas.append(StreamDelta(kind="reasoning", text=reasoning))

            tool_calls = delta.get("tool_calls")
            if isinstance(tool_calls, list):
                for tool_call in tool_calls:
                    if not isinstance(tool_call, dict):
                        continue
                    index = int(tool_call.get("index") or 0)
                    buffer = tool_buffers.setdefault(
                        index, {"id": "", "name": "", "arguments": ""}
                    )
                    if tool_call.get("id"):
                        buffer["id"] = str(tool_call["id"])
                    function = tool_call.get("function") or {}
                    if isinstance(function, dict):
                        if function.get("name"):
                            buffer["name"] = str(function["name"])
                        if function.get("arguments"):
                            buffer["arguments"] += str(function["arguments"])

            finish_reason = choice.get("finish_reason")
            if finish_reason:
                for index in sorted(tool_buffers):
                    buffer = tool_buffers[index]
                    if buffer["name"]:
                        deltas.append(
                            StreamDelta(
                                kind="tool_call",
                                tool_call={
                                    "id": buffer["id"],
                                    "name": buffer["name"],
                                    "arguments": buffer["arguments"],
                                },
                            )
                        )
                tool_buffers.clear()
                deltas.append(StreamDelta(kind="finish", finish_reason=str(finish_reason)))
        return deltas
