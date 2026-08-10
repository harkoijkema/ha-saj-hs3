"""Tests for the confirmed Elekeeper Open Platform client."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from aiohttp import ClientConnectionError

from custom_components.saj_hs3.api import (
    SajApiError,
    SajAppDisabledError,
    SajAuthenticationError,
    SajConnectionError,
    SajElekeeperApiClient,
    generate_parameter_signature,
)

APP_ID = "test-app-id"
APP_SECRET = "test-app-secret"
ACCESS_TOKEN = "test-access-token"


class FakeResponse:
    """Small aiohttp response context manager."""

    def __init__(self, payload: Any, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def json(self, *, content_type: None = None) -> Any:
        del content_type
        return self.payload


class FakeSession:
    """Return queued responses without making network requests."""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def _client(
    responses: list[Any],
    *,
    clock: Callable[[], float] = lambda: 1000.0,
) -> tuple[SajElekeeperApiClient, FakeSession]:
    session = FakeSession(responses)
    return (
        SajElekeeperApiClient(  # type: ignore[arg-type]
            session,
            APP_ID,
            APP_SECRET,
            base_url="https://example.invalid",
            monotonic_time=clock,
        ),
        session,
    )


def _token_response(expires: int = 28800) -> FakeResponse:
    return FakeResponse(
        {
            "code": 200,
            "msg": "",
            "data": {"access_token": ACCESS_TOKEN, "expires": expires},
        }
    )


def test_signature_matches_official_examples() -> None:
    assert generate_parameter_signature({"appId": "123456789"}) == (
        "696C9D8C59F2CCB6C5C3C7C76EF5D36A6206C967F751F2FEE8A2359E0065FB7D"
    )
    assert (
        generate_parameter_signature({"deviceSn": "123456789", "appId": "123456789"})
        == "602EDF03828821359B06F75BCE12DD0829038E7FBEFF55AEDB2CDE85F0E23F01"
    )


def test_successful_authentication_and_read_only_plant_count() -> None:
    client, session = _client(
        [_token_response(), FakeResponse({"code": 200, "total": 1})]
    )

    assert asyncio.run(client.async_get_authorized_plant_count()) == 1
    assert client.is_authenticated
    assert client.token_lifetime == 28800
    assert len(session.calls) == 2
    assert session.calls[0]["params"] == {
        "appId": APP_ID,
        "appSecret": APP_SECRET,
    }
    assert "accessToken" not in session.calls[0]["headers"]
    assert session.calls[1]["headers"]["accessToken"] == ACCESS_TOKEN
    assert "clientSign" in session.calls[1]["headers"]


def test_invalid_credentials() -> None:
    client, _ = _client([FakeResponse({"code": 100009, "msg": "rejected"})])

    try:
        asyncio.run(client.async_authenticate())
    except SajAuthenticationError:
        pass
    else:
        raise AssertionError("Authentication unexpectedly succeeded")


def test_disabled_or_not_released_app() -> None:
    client, _ = _client([FakeResponse({"code": 200014, "msg": "not released"})])

    try:
        asyncio.run(client.async_authenticate())
    except SajAppDisabledError:
        pass
    else:
        raise AssertionError("Disabled app unexpectedly authenticated")


def test_timeout_is_safely_classified() -> None:
    client, _ = _client([TimeoutError()])

    try:
        asyncio.run(client.async_authenticate())
    except SajConnectionError as err:
        assert APP_SECRET not in str(err)
    else:
        raise AssertionError("Timeout unexpectedly succeeded")


def test_connection_error_is_safely_classified() -> None:
    client, _ = _client([ClientConnectionError("private transport details")])

    try:
        asyncio.run(client.async_authenticate())
    except SajConnectionError as err:
        assert "private transport details" not in str(err)
    else:
        raise AssertionError("Connection failure unexpectedly succeeded")


def test_token_is_renewed_before_expiry() -> None:
    now = [1000.0]
    client, session = _client(
        [_token_response(600), _token_response(600)],
        clock=lambda: now[0],
    )

    asyncio.run(client.async_authenticate())
    now[0] = 1200.0
    asyncio.run(client.async_authenticate())
    assert len(session.calls) == 1

    now[0] = 1301.0
    asyncio.run(client.async_authenticate())
    assert len(session.calls) == 2


def test_secrets_and_tokens_are_not_exposed_by_exceptions() -> None:
    client, _ = _client([FakeResponse("not a mapping")])

    try:
        asyncio.run(client.async_authenticate())
    except SajApiError as err:
        rendered = f"{err!r} {err}"
        assert APP_SECRET not in rendered
        assert ACCESS_TOKEN not in rendered
        assert APP_ID not in rendered
    else:
        raise AssertionError("Invalid response unexpectedly succeeded")
