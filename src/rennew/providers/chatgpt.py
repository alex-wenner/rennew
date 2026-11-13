"""OpenAI via a ChatGPT subscription. Uses the same OAuth/PKCE flow as the Codex CLI and
talks to the Codex Responses backend with the resulting access token."""

import asyncio
import base64
import hashlib
import json
import secrets
import time
import urllib.parse
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx

from rennew.providers.contracts import ChatRequest, ProviderCapabilities, StreamDelta
from rennew.providers.openai_responses import OpenAIResponsesProvider

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
REDIRECT_PORT = 1455
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/auth/callback"
CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
SCOPE = "openid profile email offline_access"


def _pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _jwt_claims(token: str) -> dict[str, Any]:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return dict(json.loads(base64.urlsafe_b64decode(payload)))
    except Exception:  # noqa: BLE001
        return {}


def account_id_from_token(access_token: str) -> str | None:
    claims = _jwt_claims(access_token)
    auth = claims.get("https://api.openai.com/auth")
    if isinstance(auth, dict) and auth.get("chatgpt_account_id"):
        return str(auth["chatgpt_account_id"])
    return None


class ChatGPTLogin:
    """Runs the browser OAuth flow: builds the URL, hosts the loopback callback,
    exchanges the code for tokens."""

    def __init__(self) -> None:
        self.verifier, self.challenge = _pkce()
        self.state = secrets.token_urlsafe(24)
        self.result: dict[str, Any] | None = None
        self.error: str | None = None
        self._server: asyncio.AbstractServer | None = None

    def authorize_url(self) -> str:
        params = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
            "code_challenge": self.challenge,
            "code_challenge_method": "S256",
            "state": self.state,
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
        }
        return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    async def start_callback_server(self) -> None:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", REDIRECT_PORT)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await reader.readline()
            while (await reader.readline()).strip():
                pass
            target = request_line.decode(errors="replace").split(" ")[1] if request_line else "/"
            query = urllib.parse.parse_qs(urllib.parse.urlparse(target).query)
            code = (query.get("code") or [""])[0]
            state = (query.get("state") or [""])[0]
            body = "Signed in. You can return to Rennew."
            if not code or state != self.state:
                self.error = "Invalid callback (missing code or state mismatch)."
                body = self.error
            else:
                try:
                    self.result = await self.exchange(code)
                except Exception as error:  # noqa: BLE001
                    self.error = str(error)
                    body = self.error
            payload = body.encode()
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: "
                + str(len(payload)).encode()
                + b"\r\nConnection: close\r\n\r\n"
                + payload
            )
            await writer.drain()
        finally:
            writer.close()

    async def exchange(self, code: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "authorization_code",
                    "client_id": CLIENT_ID,
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                    "code_verifier": self.verifier,
                },
            )
            if response.status_code != 200:
                raise RuntimeError(f"Token exchange failed: {response.text[:200]}")
            payload = response.json()
        return _normalize_tokens(payload)

    async def wait(self, timeout: float = 300) -> dict[str, Any]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.result is not None:
                return self.result
            if self.error:
                raise RuntimeError(self.error)
            await asyncio.sleep(0.25)
        raise TimeoutError("Sign-in timed out.")

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()


def _normalize_tokens(payload: dict[str, Any]) -> dict[str, Any]:
    access = str(payload.get("access_token") or "")
    return {
        "access_token": access,
        "refresh_token": payload.get("refresh_token"),
        "id_token": payload.get("id_token"),
        "expires_at": time.time() + float(payload.get("expires_in") or 3600),
        "account_id": account_id_from_token(access),
    }


async def refresh_tokens(refresh_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "refresh_token": refresh_token,
            },
        )
        if response.status_code != 200:
            raise RuntimeError(f"Token refresh failed: {response.text[:200]}")
        return _normalize_tokens(response.json())


class ChatGPTProvider(OpenAIResponsesProvider):
    """Responses API against the Codex backend using ChatGPT subscription tokens."""

    def __init__(
        self,
        secret: dict[str, Any] | None,
        persist: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__(
            name="openai",
            base_url=CODEX_BASE_URL,
            api_key=(secret or {}).get("access_token"),
        )
        self._secret: dict[str, Any] = dict(secret or {})
        self._persist = persist
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return bool(self._secret.get("access_token"))

    def capabilities(self) -> ProviderCapabilities:
        caps = super().capabilities()
        caps.auth_env = []
        return caps

    async def prepare(self) -> None:
        async with self._lock:
            if not self._secret.get("access_token"):
                raise RuntimeError("ChatGPT is not signed in.")
            expires_at = float(self._secret.get("expires_at") or 0)
            if expires_at - 120 < time.time() and self._secret.get("refresh_token"):
                self._secret.update(await refresh_tokens(str(self._secret["refresh_token"])))
                if self._persist is not None:
                    self._persist(self._secret)
            self._api_key = str(self._secret["access_token"])

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        headers["OpenAI-Beta"] = "responses=experimental"
        headers["originator"] = "codex_cli_rs"
        account_id = self._secret.get("account_id") or account_id_from_token(self._api_key or "")
        if account_id:
            headers["chatgpt-account-id"] = str(account_id)
        return headers

    def _payload(self, request: ChatRequest) -> dict[str, object]:
        payload = super()._payload(request)
        payload["store"] = False
        payload.setdefault("instructions", "You are a coding agent.")
        payload.pop("max_output_tokens", None)
        return payload

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamDelta]:
        try:
            await self.prepare()
        except Exception as error:  # noqa: BLE001
            yield StreamDelta(kind="error", error=str(error))
            return
        async for delta in super().stream(request):
            yield delta
