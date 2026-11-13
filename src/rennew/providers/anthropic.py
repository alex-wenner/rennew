import json
from collections.abc import AsyncIterator

import httpx

from rennew.providers.contracts import (
    ChatRequest,
    ProviderCapabilities,
    StreamDelta,
)
from rennew.providers.sse import iter_sse_lines

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_BASE_URL = "https://api.anthropic.com"


class AnthropicProvider:
    """Anthropic Messages API with SSE streaming and native tool use."""

    def __init__(self, name: str = "anthropic", base_url: str | None = None, api_key: str | None = None) -> None:
        self.name = name
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._api_key = api_key

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            streaming=True,
            tool_calling=True,
            parallel_tool_calls=True,
            reasoning=True,
            auth_env=["ANTHROPIC_API_KEY"],
        )

    def _payload(self, request: ChatRequest) -> dict[str, object]:
        system_parts: list[str] = []
        messages: list[dict[str, object]] = []
        for message in request.messages:
            data = message.model_dump(exclude_none=True)
            role = data.get("role")
            if role == "system":
                system_parts.append(str(data.get("content", "")))
                continue
            if role == "tool":
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": data.get("tool_call_id", ""),
                                "content": data.get("content", ""),
                            }
                        ],
                    }
                )
                continue
            content: list[dict[str, object]] = []
            if data.get("content"):
                content.append({"type": "text", "text": data["content"]})
            if role == "assistant" and data.get("tool_calls"):
                for tool_call in data["tool_calls"]:
                    function = tool_call.get("function") or {}
                    arguments = function.get("arguments") or "{}"
                    try:
                        parsed = json.loads(arguments)
                    except json.JSONDecodeError:
                        parsed = {}
                    content.append(
                        {
                            "type": "tool_use",
                            "id": tool_call.get("id", ""),
                            "name": function.get("name", ""),
                            "input": parsed,
                        }
                    )
            messages.append({"role": role, "content": content or data.get("content", "")})

        payload: dict[str, object] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or 8192,
            "stream": True,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        if request.tools:
            payload["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters or {"type": "object", "properties": {}},
                }
                for tool in request.tools
            ]
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        payload.update(request.extra)
        return payload

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": ANTHROPIC_VERSION,
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamDelta]:
        url = f"{self._base_url}/v1/messages"
        buffers: dict[int, dict[str, str]] = {}
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream(
                    "POST", url, json=self._payload(request), headers=self._headers()
                ) as response:
                    if response.status_code != 200:
                        body = (await response.aread()).decode("utf-8", errors="replace")
                        yield StreamDelta(kind="error", error=f"HTTP {response.status_code}: {body}")
                        return
                    async for data in iter_sse_lines(response.aiter_lines()):
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        for delta in self._parse_event(event, buffers):
                            yield delta
            except httpx.HTTPError as error:
                yield StreamDelta(kind="error", error=f"Connection failed: {error}")

    def _parse_event(
        self, event: dict[str, object], buffers: dict[int, dict[str, str]]
    ) -> list[StreamDelta]:
        event_type = event.get("type")
        deltas: list[StreamDelta] = []
        block = event.get("content_block") if isinstance(event.get("content_block"), dict) else {}
        delta = event.get("delta") if isinstance(event.get("delta"), dict) else {}
        usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
        message = event.get("message") if isinstance(event.get("message"), dict) else {}
        index = int(str(event.get("index", 0)))

        if event_type == "content_block_start" and isinstance(block, dict) and block.get("type") == "tool_use":
            buffers[index] = {
                "id": str(block.get("id", "")),
                "name": str(block.get("name", "")),
                "arguments": "",
            }
        elif event_type == "content_block_delta" and isinstance(delta, dict):
            if delta.get("type") == "text_delta":
                deltas.append(StreamDelta(kind="text", text=str(delta.get("text", ""))))
            elif delta.get("type") == "thinking_delta":
                deltas.append(StreamDelta(kind="reasoning", text=str(delta.get("thinking", ""))))
            elif delta.get("type") == "input_json_delta":
                if index in buffers:
                    buffers[index]["arguments"] += str(delta.get("partial_json", ""))
        elif event_type == "content_block_stop":
            tool = buffers.pop(index, None)
            if tool is not None:
                deltas.append(StreamDelta(kind="tool_call", tool_call=dict(tool)))
        elif event_type == "message_delta":
            if isinstance(usage, dict) and usage:
                deltas.append(
                    StreamDelta(
                        kind="usage",
                        usage={"input": 0, "output": int(usage.get("output_tokens") or 0), "reasoning": 0},
                    )
                )
            stop_reason = delta.get("stop_reason") if isinstance(delta, dict) else None
            if stop_reason:
                deltas.append(StreamDelta(kind="finish", finish_reason=str(stop_reason)))
        elif event_type == "message_start" and isinstance(message, dict):
            start_usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
            if isinstance(start_usage, dict) and start_usage:
                deltas.append(
                    StreamDelta(
                        kind="usage",
                        usage={"input": int(start_usage.get("input_tokens") or 0), "output": 0, "reasoning": 0},
                    )
                )
        elif event_type == "message_stop":
            deltas.append(StreamDelta(kind="finish", finish_reason="stop"))
        elif event_type == "error":
            deltas.append(StreamDelta(kind="error", error=str(event.get("error") or "stream error")))
        return deltas
