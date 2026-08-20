"""Async client for the confirmed SAJ Elekeeper Open Platform endpoints."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

from .const import (
    OPEN_PLATFORM_BASE_URL,
    OPEN_PLATFORM_PLANTS_ENDPOINT,
    OPEN_PLATFORM_TOKEN_ENDPOINT,
    TOKEN_REFRESH_MARGIN_SECONDS,
)

_TIMEOUT = ClientTimeout(total=15)
_INVALID_AUTH = {401, 100009, 200002, 200008, 200009, 200010, 200012, 200015}


class SajApiError(Exception):
    """Safe base API exception."""


class SajAuthenticationError(SajApiError):
    """Authentication failed."""


class SajAppDisabledError(SajAuthenticationError):
    """Developer app is not released."""


class SajConnectionError(SajApiError):
    """Connection failed."""


class SajRateLimitError(SajApiError):
    """Rate limit reached."""


@dataclass(frozen=True, slots=True)
class SajTokenMetadata:
    """Non-secret token metadata."""

    expires_in: int
    expires_at_monotonic: float


def generate_parameter_signature(parameters: Mapping[str, object]) -> str:
    """Generate the live-confirmed Open Platform parameter signature."""
    canonical = ",".join(f"{key}={parameters[key]}" for key in sorted(parameters))
    return sha256(canonical.encode()).hexdigest().upper()


class SajElekeeperApiClient:
    """Minimal read-only client for confirmed Open Platform calls."""

    def __init__(
        self,
        session: ClientSession,
        app_id: str,
        app_secret: str,
        *,
        base_url: str = OPEN_PLATFORM_BASE_URL,
        monotonic_time: Callable[[], float] = monotonic,
    ) -> None:
        self._session = session
        self._app_id = app_id
        self._app_secret = app_secret
        self._base_url = base_url.rstrip("/")
        self._monotonic = monotonic_time
        self._access_token: str | None = None
        self._token: SajTokenMetadata | None = None
        self._lock = asyncio.Lock()

    @property
    def is_authenticated(self) -> bool:
        return self._token_reusable()

    @property
    def token_expires_in(self) -> int | None:
        if self._token is None:
            return None
        return max(0, int(self._token.expires_at_monotonic - self._monotonic()))

    async def async_authenticate(self, *, force: bool = False) -> SajTokenMetadata:
        if not force and self._token_reusable():
            assert self._token is not None
            return self._token
        async with self._lock:
            if not force and self._token_reusable():
                assert self._token is not None
                return self._token
            payload = await self._get_json(
                OPEN_PLATFORM_TOKEN_ENDPOINT,
                {"appId": self._app_id, "appSecret": self._app_secret},
                authenticated=False,
            )
            data = payload.get("data")
            if not isinstance(data, dict):
                raise SajApiError("Invalid SAJ token response")
            token, expires = data.get("access_token"), data.get("expires")
            if (
                not isinstance(token, str)
                or not token
                or not isinstance(expires, int)
                or expires <= 0
            ):
                raise SajApiError("Invalid SAJ token metadata")
            self._access_token = token
            self._token = SajTokenMetadata(expires, self._monotonic() + expires)
            return self._token

    async def async_get_authorized_plant_count(self) -> int:
        await self.async_authenticate()
        params: dict[str, str | int] = {
            "appId": self._app_id,
            "pageNum": 1,
            "pageSize": 100,
        }
        payload = await self._get_json(
            OPEN_PLATFORM_PLANTS_ENDPOINT, params, authenticated=True
        )
        total = payload.get("total")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise SajApiError("Invalid authorized plant count")
        return total

    def _token_reusable(self) -> bool:
        return (
            self._access_token is not None
            and self._token is not None
            and (
                self._token.expires_at_monotonic - self._monotonic()
                > TOKEN_REFRESH_MARGIN_SECONDS
            )
        )

    def _forget_token(self) -> None:
        self._access_token = None
        self._token = None

    async def _get_json(
        self, endpoint: str, params: Mapping[str, str | int], *, authenticated: bool
    ) -> dict[str, Any]:
        headers = {"content-language": "en_US"}
        if authenticated:
            if self._access_token is None:
                raise SajAuthenticationError("No access token")
            headers.update(
                {
                    "accessToken": self._access_token,
                    "clientSign": generate_parameter_signature(params),
                }
            )
        try:
            async with self._session.get(
                f"{self._base_url}{endpoint}",
                params=params,
                headers=headers,
                timeout=_TIMEOUT,
            ) as response:
                payload = await self._decode(response)
        except TimeoutError as err:
            raise SajConnectionError("SAJ request timed out") from err
        except ClientError as err:
            raise SajConnectionError("SAJ connection failed") from err
        if not isinstance(payload, dict):
            raise SajApiError("Invalid SAJ response")
        code = payload.get("code")
        if code == 200:
            return payload
        if code == 200014:
            self._forget_token()
            raise SajAppDisabledError("Developer app is not released")
        if code in _INVALID_AUTH:
            self._forget_token()
            raise SajAuthenticationError("SAJ authentication failed")
        raise SajApiError("SAJ API error")

    async def _decode(self, response: ClientResponse) -> Any:
        if response.status == 429:
            raise SajRateLimitError("SAJ rate limit reached")
        if response.status in {401, 403}:
            raise SajAuthenticationError("SAJ authentication failed")
        if response.status >= 400:
            raise SajApiError("SAJ HTTP error")
        try:
            return await response.json(content_type=None)
        except (TypeError, ValueError) as err:
            raise SajApiError("SAJ returned non-JSON data") from err
