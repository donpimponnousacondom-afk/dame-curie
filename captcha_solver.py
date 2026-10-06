"""Discord CAPTCHA solving for the Maxwell self-bot.

Discord challenges certain API actions (most commonly accepting a server
invite, but also login/phone flows) with an hCaptcha or reCAPTCHA
challenge. The library (discord.py-self) surfaces this as
``discord.CaptchaRequired`` on the HTTP layer and, when a
``captcha_handler`` is installed on the client, retries the request with
the solved token in ``X-Captcha-Key`` (plus ``X-Captcha-Rqtoken`` for
enterprise hCaptcha).

This module implements that handler using an external solving service
(CapSolver or 2captcha — the two that reliably support Discord's
enterprise hCaptcha with rqdata). When no solver is configured it falls
back to surfacing the challenge details so the caller (join_server /
leave_server) can report them instead of failing silently.

Env config (see config.py):
    CAPTCHA_SOLVER_SERVICE   "capsolver" | "2captcha" | "" (disabled)
    CAPTCHA_SOLVER_API_KEY   the solver service API key
    CAPTCHA_SOLVER_TIMEOUT   max seconds to wait for a solution (default 180)
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

DISCORD_URL = "https://discord.com"


class CaptchaSolveError(Exception):
    """Raised when the CAPTCHA could not be solved."""


class _BaseSolver:
    service = ""

    def __init__(self, api_key: str, timeout: int = 180) -> None:
        self.api_key = api_key
        self.timeout = timeout

    async def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp,
            ):
                text = await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CaptchaSolveError(f"{self.service}: request failed: {err}") from err
        try:
            data: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError as err:
            raise CaptchaSolveError(
                f"solver returned non-JSON ({resp.status}): {text[:200]}"
            ) from err
        if resp.status != 200 or data.get("errorId") not in (None, 0):
            raise CaptchaSolveError(
                f"{self.service} API error {resp.status}: {json.dumps(data)[:300]}"
            )
        return data

    async def _poll(
        self,
        get_result: Callable[[], Awaitable[dict[str, Any]]],
        timeout: int | None = None,
    ) -> dict[str, Any]:
        deadline = asyncio.get_event_loop().time() + (timeout or self.timeout)
        while True:
            data = await get_result()
            status = data.get("status")
            # CapSolver uses "ready"/"success"; 2captcha JSON uses status=1
            # with the token in "request". Integer 1 never matched the string
            # set, so 2captcha polls timed out even after a valid solve.
            if status in (1, "1", "ready", "success", "completed"):
                return data
            request = str(data.get("request") or "")
            if status in (0, "0") and request == "CAPCHA_NOT_READY":
                pass
            elif status in ("failed", "error") or (
                status in (0, "0") and request and request != "CAPCHA_NOT_READY"
            ):
                raise CaptchaSolveError(f"{self.service}: task failed: {data}")
            if asyncio.get_event_loop().time() > deadline:
                raise CaptchaSolveError(
                    f"{self.service}: timed out after {timeout or self.timeout}s"
                )
            await asyncio.sleep(3)

    async def solve(
        self,
        *,
        service: str,
        sitekey: str,
        rqdata: str | None = None,
        invisible: bool = False,
    ) -> str:
        raise NotImplementedError


class CapSolverSolver(_BaseSolver):
    service = "capsolver"
    _BASE = "https://api.capsolver.com"

    async def solve(
        self,
        *,
        service: str,
        sitekey: str,
        rqdata: str | None = None,
        invisible: bool = False,
    ) -> str:
        task: dict[str, Any] = {
            "type": "HCaptchaTaskProxyLess",
            "websiteURL": DISCORD_URL,
            "websiteKey": sitekey,
            "isInvisible": bool(invisible),
        }
        if rqdata:
            task["enterprisePayload"] = {"rqdata": rqdata}
        create = await self._post_json(
            f"{self._BASE}/createTask", {"clientKey": self.api_key, "task": task}
        )
        task_id = create.get("taskId")
        if not task_id:
            raise CaptchaSolveError(f"capsolver: no taskId in {create}")
        logger.info(
            "capsolver task %s created for sitekey=%s invisible=%s",
            task_id,
            sitekey,
            invisible,
        )

        async def get_result() -> dict[str, Any]:
            return await self._post_json(
                f"{self._BASE}/getTaskResult",
                {"clientKey": self.api_key, "taskId": task_id},
            )

        data = await self._poll(get_result)
        solution = data.get("solution") or {}
        token = (
            solution.get("gRecaptchaResponse")
            or solution.get("token")
            or solution.get("captcha_key")
        )
        if not token:
            raise CaptchaSolveError(f"capsolver: no solution token in {data}")
        logger.info("capsolver task %s solved (%d chars)", task_id, len(token))
        return str(token)


class TwoCaptchaSolver(_BaseSolver):
    service = "2captcha"
    _IN = "https://2captcha.com/in.php"
    _RES = "https://2captcha.com/res.php"

    async def _get(self, url: str, params: dict[str, Any]) -> str:
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp,
            ):
                return await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CaptchaSolveError(f"2captcha: request failed: {err}") from err

    async def solve(
        self,
        *,
        service: str,
        sitekey: str,
        rqdata: str | None = None,
        invisible: bool = False,
    ) -> str:
        params: dict[str, Any] = {
            "key": self.api_key,
            "method": "hcaptcha",
            "sitekey": sitekey,
            "pageurl": DISCORD_URL,
            "json": "1",
            "soft_id": "4001",
        }
        if rqdata:
            params["data"] = rqdata
        if invisible:
            params["is_invisible"] = "1"

        text = await self._get(self._IN, params)
        try:
            data: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError as err:
            raise CaptchaSolveError(f"2captcha in.php non-JSON: {text[:200]}") from err
        if data.get("status") != 1:
            raise CaptchaSolveError(f"2captcha in.php error: {data}")
        captcha_id = data.get("request")
        logger.info(
            "2captcha task %s created for sitekey=%s invisible=%s",
            captcha_id,
            sitekey,
            invisible,
        )

        async def get_result() -> dict[str, Any]:
            res_params = {
                "key": self.api_key,
                "action": "get",
                "id": captcha_id,
                "json": "1",
            }
            txt = await self._get(self._RES, res_params)
            try:
                return json.loads(txt)
            except json.JSONDecodeError as err:
                raise CaptchaSolveError(
                    f"2captcha res.php non-JSON: {txt[:200]}"
                ) from err

        data = await self._poll(get_result)
        token = data.get("request")
        if not token or token == "CAPCHA_NOT_READY":
            raise CaptchaSolveError(f"2captcha: no token: {data}")
        logger.info("2captcha task %s solved (%d chars)", captcha_id, len(token))
        return str(token)


def build_solver(
    service: str | None, api_key: str | None, timeout: int = 180
) -> _BaseSolver | None:
    """Return a solver instance or None when not configured."""
    service = (service or "").strip().lower()
    api_key = (api_key or "").strip()
    if not service or not api_key:
        return None
    if service == "capsolver":
        return CapSolverSolver(api_key, timeout)
    if service == "2captcha":
        return TwoCaptchaSolver(api_key, timeout)
    logger.warning(
        "CAPTCHA_SOLVER_SERVICE=%r not supported (capsolver/2captcha)", service
    )
    return None
