"""GitHub Copilot provider: GitHub device-code sign-in, Copilot token exchange, and an
OpenAI-compatible chat endpoint at api.githubcopilot.com."""

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx

from rennew.providers.contracts import ChatRequest, ProviderCapabilities, StreamDelta
from rennew.providers.openai_responses import OpenAIResponsesProvider

# Public client id used by GitHub Copilot integrations for the device flow.
GITHUB_CLIENT_ID = "Iv1.b507a08c87ecfe98"
DEVICE_CODE_URL = "https://github.com/login/device/code"
ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
COPILOT_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"
COPILOT_BASE_URL = "https://api.githubcopilot.com"

COPILOT_HEADERS = {
    "Editor-Version": "vscode/1.99.0",
    "Editor-Plugin-Version": "copilot-chat/0.26.0",
    "Copilot-Integration-Id": "vscode-chat",
    "User-Agent": "GitHubCopilotChat/0.26.0",
    "Openai-Intent": "conversation-panel",
}


async def start_device_flow() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            DEVICE_CODE_URL,
            headers={"Accept": "application/json"},
            data={"client_id": GITHUB_CLIENT_ID, "scope": "read:user"},
        )
        response.raise_for_status()
        return dict(response.json())


async def poll_device_flow(device_code: str) -> dict[str, Any]:
    """Single poll. Returns {"status": "pending"|"complete"|"error", ...}."""
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            ACCESS_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
        )
        payload = response.json()
    if payload.get("access_token"):
        return {"status": "complete", "access_token": payload["access_token"]}
    error = payload.get("error")
    if error in {"authorization_pending", "slow_down"}:
        return {"status": "pending", "error": error}
    return {"status": "error", "error": error or "unknown"}


async def exchange_copilot_token(github_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            COPILOT_TOKEN_URL,
            headers={
                "Authorization": f"token {github_token}",
                "Accept": "application/json",
                **COPILOT_HEADERS,
            },
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Copilot token exchange failed ({response.status_code}): {response.text[:200]}"
            )
        return dict(response.json())


class CopilotProvider(OpenAIResponsesProvider):
    """GitHub Copilot chat. New Copilot models only accept the Responses API, so this
    adapter speaks /responses with the IDE headers Copilot requires. `secret` holds
    {"github_token": ..., "copilot_token": ..., "expires_at": ...}; tokens refresh
    transparently and persist via `persist`."""

    def __init__(
        self,
        secret: dict[str, Any] | None,
        persist: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__(
            name="copilot",
            base_url=COPILOT_BASE_URL,
            api_key=(secret or {}).get("copilot_token"),
        )
        self._secret: dict[str, Any] = dict(secret or {})
        self._persist = persist
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return bool(self._secret.get("github_token"))

    def capabilities(self) -> ProviderCapabilities:
        caps = super().capabilities()
        caps.auth_env = ["GITHUB_TOKEN"]
        return caps

    async def prepare(self) -> None:
        """Ensure a fresh Copilot token before making requests."""
        async with self._lock:
            github_token = self._secret.get("github_token")
            if not github_token:
                raise RuntimeError("GitHub Copilot is not signed in.")
            expires_at = float(self._secret.get("expires_at") or 0)
            if self._secret.get("copilot_token") and expires_at - 60 > time.time():
                self._api_key = str(self._secret["copilot_token"])
                return
            payload = await exchange_copilot_token(str(github_token))
            self._secret["copilot_token"] = payload.get("token")
            self._secret["expires_at"] = payload.get("expires_at", time.time() + 1500)
            self._api_key = str(self._secret["copilot_token"])
            if self._persist is not None:
                self._persist(self._secret)

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        headers.update(COPILOT_HEADERS)
        return headers

    def _payload(self, request: ChatRequest) -> dict[str, object]:
        payload = super()._payload(request)
        payload["store"] = False
        return payload

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamDelta]:
        try:
            await self.prepare()
        except Exception as error:  # noqa: BLE001
            yield StreamDelta(kind="error", error=str(error))
            return
        async for delta in super().stream(request):
            yield delta
