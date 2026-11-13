import json
from collections.abc import AsyncIterator

import httpx

from rennew.providers.contracts import (
    ChatRequest,
    ProviderCapabilities,
    ProviderMessage,
    StreamDelta,
)
from rennew.providers.sse import iter_sse_lines

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIResponsesProvider:
    """OpenAI Responses API (`/v1/responses`) with SSE streaming.

    Supports text, reasoning summaries, function tools, and token usage.
    """

    def __init__(
        self,
        name: str = "openai",
        base_url: str | None = None,
        api_key: str | None = None,
        *,
        context_window: int | None = None,
    ) -> None:
        self.name = name
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._api_key = api_key
        self._context_window = context_window

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            streaming=True,
            tool_calling=True,
            parallel_tool_calls=True,
            reasoning=True,
            context_window=self._context_window,
            auth_env=["OPENAI_API_KEY"],
        )

    def _input_items(self, messages: list[ProviderMessage]) -> tuple[list[dict[str, object]], str]:
        """Responses API input items. Content must be an array of typed parts —
        the ChatGPT/Codex backend rejects plain-string content."""
        instructions = ""
        items: list[dict[str, object]] = []
        for message in messages:
            if message.role == "system":
                instructions = (
                    f"{instructions}\n{message.content}".strip() if instructions else message.content
                )
                continue
            if message.role == "tool":
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": message.tool_call_id or "",
                        "output": message.content,
                    }
                )
                continue
            if message.role == "assistant" and message.tool_calls:
                if message.content:
                    items.append(
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": message.content}],
                        }
                    )
                for tool_call in message.tool_calls:
                    function = tool_call.get("function") or {}
                    items.append(
                        {
                            "type": "function_call",
                            "call_id": tool_call.get("id", ""),
                            "name": function.get("name", ""),
                            "arguments": function.get("arguments", "{}"),
                        }
                    )
                continue
            part_type = "output_text" if message.role == "assistant" else "input_text"
            items.append(
                {
                    "type": "message",
                    "role": message.role,
                    "content": [{"type": part_type, "text": message.content}],
                }
            )
        return items, instructions

    def _payload(self, request: ChatRequest) -> dict[str, object]:
        items, instructions = self._input_items(request.messages)
        payload: dict[str, object] = {"model": request.model, "input": items, "stream": True}
        if instructions:
            payload["instructions"] = instructions
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters or {"type": "object", "properties": {}},
                }
                for tool in request.tools
            ]
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_output_tokens"] = request.max_tokens
        if request.reasoning_effort:
            payload["reasoning"] = {"effort": request.reasoning_effort}
        payload.update(request.extra)
        return payload

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamDelta]:
        url = f"{self._base_url}/responses"
        call_buffers: dict[str, dict[str, str]] = {}
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
                        for delta in self._parse_event(event, call_buffers):
                            yield delta
            except httpx.HTTPError as error:
                yield StreamDelta(kind="error", error=f"Connection failed: {error}")

    def _parse_event(
        self, event: dict[str, object], call_buffers: dict[str, dict[str, str]]
    ) -> list[StreamDelta]:
        event_type = event.get("type")
        deltas: list[StreamDelta] = []

        if event_type == "response.output_text.delta":
            deltas.append(StreamDelta(kind="text", text=str(event.get("delta") or "")))
        elif event_type == "response.reasoning_summary_text.delta":
            deltas.append(StreamDelta(kind="reasoning", text=str(event.get("delta") or "")))
        elif event_type == "response.output_item.added":
            item = event.get("item") or {}
            if isinstance(item, dict) and item.get("type") == "function_call":
                call_buffers[str(item.get("id") or "")] = {
                    "call_id": str(item.get("call_id") or ""),
                    "name": str(item.get("name") or ""),
                    "arguments": "",
                }
        elif event_type == "response.function_call_arguments.delta":
            buffer = call_buffers.get(str(event.get("item_id") or ""))
            if buffer is not None:
                buffer["arguments"] += str(event.get("delta") or "")
        elif event_type == "response.output_item.done":
            item = event.get("item") or {}
            if isinstance(item, dict) and item.get("type") == "function_call":
                buffer = call_buffers.pop(str(item.get("id") or ""), None)
                deltas.append(
                    StreamDelta(
                        kind="tool_call",
                        tool_call={
                            "id": str(item.get("call_id") or (buffer or {}).get("call_id", "")),
                            "name": str(item.get("name") or ""),
                            "arguments": str(item.get("arguments") or (buffer or {}).get("arguments", "")),
                        },
                    )
                )
        elif event_type == "response.completed":
            response = event.get("response") or {}
            usage = response.get("usage") if isinstance(response, dict) else None
            if isinstance(usage, dict):
                details = usage.get("output_tokens_details")
                reasoning_tokens = (
                    int(details.get("reasoning_tokens") or 0) if isinstance(details, dict) else 0
                )
                deltas.append(
                    StreamDelta(
                        kind="usage",
                        usage={
                            "input": int(usage.get("input_tokens") or 0),
                            "output": int(usage.get("output_tokens") or 0),
                            "reasoning": reasoning_tokens,
                        },
                    )
                )
            status = response.get("status") if isinstance(response, dict) else None
            deltas.append(StreamDelta(kind="finish", finish_reason=str(status or "completed")))
        elif event_type == "response.incomplete":
            response_obj = event.get("response")
            details = response_obj.get("incomplete_details") if isinstance(response_obj, dict) else None
            reason = details.get("reason") if isinstance(details, dict) else None
            deltas.append(StreamDelta(kind="finish", finish_reason=str(reason or "incomplete")))
        elif event_type == "response.failed":
            response_obj = event.get("response")
            error = response_obj.get("error") if isinstance(response_obj, dict) else None
            message = error.get("message") if isinstance(error, dict) else None
            deltas.append(StreamDelta(kind="error", error=str(message or "response failed")))
        return deltas
