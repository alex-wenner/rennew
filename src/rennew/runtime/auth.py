"""Server-side sign-in flows. The browser only starts a flow and polls status; all
GitHub/OpenAI traffic happens here so browser timers and popup blockers can't
break the handshake."""

import asyncio
import logging
import time
from typing import Any

from rennew.providers import chatgpt, copilot
from rennew.security.credentials import CredentialStore

log = logging.getLogger("rennew.auth")


class AuthFlows:
    def __init__(self, credentials: CredentialStore, on_change: Any) -> None:
        self._credentials = credentials
        self._on_change = on_change
        self._github: dict[str, Any] = {"status": "idle"}
        self._github_task: asyncio.Task[None] | None = None
        self._openai: dict[str, Any] = {"status": "idle"}
        self._openai_login: chatgpt.ChatGPTLogin | None = None
        self._openai_task: asyncio.Task[None] | None = None

    # --- GitHub Copilot -----------------------------------------------------------

    async def github_start(self) -> dict[str, Any]:
        if self._github_task and not self._github_task.done():
            self._github_task.cancel()
        start = await copilot.start_device_flow()
        self._github = {
            "status": "pending",
            "user_code": start["user_code"],
            "verification_uri": start.get("verification_uri", "https://github.com/login/device"),
            "expires_at": time.time() + int(start.get("expires_in", 900)),
        }
        self._github_task = asyncio.create_task(
            self._github_poll_loop(str(start["device_code"]), int(start.get("interval", 5)))
        )
        return self.github_status()

    async def _github_poll_loop(self, device_code: str, interval: int) -> None:
        wait = interval + 1
        while time.time() < float(self._github.get("expires_at", 0)):
            await asyncio.sleep(wait)
            try:
                result = await copilot.poll_device_flow(device_code)
            except Exception as error:  # noqa: BLE001
                log.exception("github poll failed")
                self._github = {"status": "error", "error": str(error)}
                return
            if result["status"] == "pending":
                if result.get("error") == "slow_down":
                    wait += 5
                continue
            if result["status"] == "error":
                self._github = {"status": "error", "error": str(result.get("error"))}
                return
            github_token = str(result["access_token"])
            try:
                token = await copilot.exchange_copilot_token(github_token)
            except Exception as error:  # noqa: BLE001
                log.exception("copilot token exchange failed")
                self._github = {"status": "error", "error": str(error)}
                return
            self._credentials.set_secret(
                "copilot",
                {
                    "github_token": github_token,
                    "copilot_token": token.get("token"),
                    "expires_at": token.get("expires_at"),
                },
            )
            self._on_change()
            self._github = {"status": "complete"}
            log.info("copilot connected")
            return
        self._github = {"status": "error", "error": "Device code expired."}

    def github_status(self) -> dict[str, Any]:
        return dict(self._github)

    # --- OpenAI via ChatGPT ---------------------------------------------------------

    async def openai_start(self) -> dict[str, Any]:
        await self._openai_cleanup()
        login = chatgpt.ChatGPTLogin()
        await login.start_callback_server()
        self._openai_login = login
        self._openai = {"status": "pending", "url": login.authorize_url()}
        self._openai_task = asyncio.create_task(self._openai_wait(login))
        return self.openai_status()

    async def _openai_wait(self, login: chatgpt.ChatGPTLogin) -> None:
        try:
            result = await login.wait(timeout=600)
        except Exception as error:  # noqa: BLE001
            log.exception("chatgpt sign-in failed")
            self._openai = {"status": "error", "error": str(error)}
            await login.close()
            return
        self._credentials.set_secret("openai", {"mode": "chatgpt", **result})
        self._on_change()
        self._openai = {"status": "complete"}
        log.info("openai (chatgpt) connected")
        await login.close()

    async def _openai_cleanup(self) -> None:
        if self._openai_task and not self._openai_task.done():
            self._openai_task.cancel()
        if self._openai_login is not None:
            await self._openai_login.close()
            self._openai_login = None

    def openai_status(self) -> dict[str, Any]:
        return dict(self._openai)

    async def close(self) -> None:
        tasks = [task for task in (self._github_task, self._openai_task) if task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self._openai_cleanup()
