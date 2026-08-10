"""Async client for the official SAJ Elekeeper Open Platform."""

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

_REQUEST_TIMEOUT = ClientTimeout(total=15)
_SUCCESS_CODE = 200
_INVALID_CREDENTIAL_CODES = {
    401,
    100009,
    200002,
    200008,
    200009,
    200010,
    200012,
    200015,
}
_APP_NOT_RELEASED_CODE = 200014


class SajApiError(Exception):
    """Base exception for a safe, redacted SAJ API failure."""


class SajAuthenticationError(SajApiError):
    """The Open Platform rejected the credentials or authentication material."""


class SajAppDisabledError(SajAuthenticationError):
    """The developer app is not released."""


class SajConnectionError(SajApiError):
    """The Open Platform could not be reached."""


class SajRateLimitError(SajApiError):
    """The Open Platform HTTP rate limit was reached."""


@dataclass(frozen=True, slots=True)
class SajTokenMetadata:
    """Non-secret metadata about the in-memory access token."""

    expires_in: int
    expires_at_monotonic: float


def generate_parameter_signature(parameters: Mapping[str, object]) -> str:
    """Generate the official comma-separated ASCII-sorted SHA-256 signature."""
    canonical = ",".join(
        f"{key}={parameters[key]}" for key in sorted(parameters, key=str)
    )
    return sha256(canonical.encode()).hexdigest().upper()


class SajElekeeperApiClient:
    """Minimal read-only client for confirmed official endpoints."""

    def __init__(
        self,
        session: ClientSession,
        app_id: str,
        app_secret: str,
        *,
        base_url: str = OPEN_PLATFORM_BASE_URL,
        monotonic_time: Callable[[], float] = monotonic,
    ) -> None:
        """Initialize the client without making a request."""
        self._session = session
        self._app_id = app_id
        self._app_secret = app_secret
        self._base_url = base_url.rstrip("/")
        self._monotonic_time = monotonic_time
        self._access_token: str | None = None
        self._token_metadata: SajTokenMetadata | None = None
        self._auth_lock = asyncio.Lock()

    @property
    def is_authenticated(self) -> bool:
        """Return whether a reusable in-memory token is present."""
        return self._token_is_reusable()

    @property
    def token_expires_in(self) -> int | None:
        """Return remaining token lifetime without exposing the token."""
        if self._token_metadata is None:
            return None
        return max(
            0,
            int(self._token_metadata.expires_at_monotonic - self._monotonic_time()),
        )

    @property
    def token_lifetime(self) -> int | None:
        """Return the server-provided token lifetime."""
        if self._token_metadata is None:
            return None
        return self._token_metadata.expires_in

    async def async_authenticate(self, *, force: bool = False) -> SajTokenMetadata:
        """Obtain or reuse an official access token."""
        if not force and self._token_is_reusable():
            assert self._token_metadata is not None
            return self._token_metadata

        async with self._auth_lock:
            if not force and self._token_is_reusable():
                assert self._token_metadata is not None
                return self._token_metadata

            payload = await self._async_get_json(
                OPEN_PLATFORM_TOKEN_ENDPOINT,
                params={"appId": self._app_id, "appSecret": self._app_secret},
                authenticated=False,
            )
            data = payload.get("data")
            if not isinstance(data, dict):
                raise SajApiError("SAJ returned an invalid token response")

            access_token = data.get("access_token")
            expires = data.get("expires")
            if (
                not isinstance(access_token, str)
                or not access_token
                or not isinstance(expires, int)
                or isinstance(expires, bool)
                or expires <= 0
            ):
                raise SajApiError("SAJ returned invalid token metadata")

            expires_at = self._monotonic_time() + expires
            self._access_token = access_token
            self._token_metadata = SajTokenMetadata(expires, expires_at)
            return self._token_metadata

    async def async_get_authorized_plant_count(self) -> int:
        """Return only the count from the confirmed read-only plant-list endpoint."""
        await self.async_authenticate()
        parameters: dict[str, str | int] = {
            "appId": self._app_id,
            "pageNum": 1,
            "pageSize": 100,
        }
        payload = await self._async_get_json(
            OPEN_PLATFORM_PLANTS_ENDPOINT,
            params=parameters,
            authenticated=True,
        )
        total = payload.get("total")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise SajApiError("SAJ returned an invalid authorized-plant count")
        return total

    def invalidate_token(self) -> None:
        """Forget the runtime token without exposing or persisting it."""
        self._access_token = None
        self._token_metadata = None

    def _token_is_reusable(self) -> bool:
        if self._access_token is None or self._token_metadata is None:
            return False
        return (
            self._token_metadata.expires_at_monotonic - self._monotonic_time()
            > TOKEN_REFRESH_MARGIN_SECONDS
        )

    async def _async_get_json(
        self,
        endpoint: str,
        *,
        params: Mapping[str, str | int],
        authenticated: bool,
    ) -> dict[str, Any]:
        headers = {"content-language": "en_US"}
        if authenticated:
            if self._access_token is None:
                raise SajAuthenticationError("No SAJ access token is available")
            headers["accessToken"] = self._access_token
            headers["clientSign"] = generate_parameter_signature(params)

        try:
            async with self._session.get(
                f"{self._base_url}{endpoint}",
                params=params,
                headers=headers,
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                payload = await self._async_decode_response(response)
        except TimeoutError as err:
            raise SajConnectionError("SAJ request timed out") from err
        except ClientError as err:
            raise SajConnectionError("SAJ connection failed") from err

        return self._validate_response(payload)

    async def _async_decode_response(self, response: ClientResponse) -> Any:
        if response.status == 429:
            raise SajRateLimitError("SAJ rate limit reached")
        if response.status in {401, 403}:
            raise SajAuthenticationError("SAJ authentication failed")
        if response.status >= 400:
            raise SajApiError("SAJ returned an HTTP error")
        try:
            return await response.json(content_type=None)
        except (ValueError, TypeError) as err:
            raise SajApiError("SAJ returned a non-JSON response") from err

    def _validate_response(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SajApiError("SAJ returned an invalid response")

        code = payload.get("code")
        if code == _SUCCESS_CODE:
            return payload
        if code == _APP_NOT_RELEASED_CODE:
            self.invalidate_token()
            raise SajAppDisabledError("The SAJ developer app is not released")
        if code in _INVALID_CREDENTIAL_CODES:
            self.invalidate_token()
            raise SajAuthenticationError("SAJ authentication failed")
        raise SajApiError("SAJ returned an API error")
