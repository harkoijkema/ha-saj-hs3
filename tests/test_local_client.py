"""Offline transport tests using a simulated eManager GATT service."""

from __future__ import annotations

import asyncio
import json

import pytest

from custom_components.saj_hs3.const import (
    ENERGY_EMS_DATA_IDS,
    GATT_WRITE_LIMIT,
    NOTIFY_UUID,
    REALTIME_EMS_DATA_IDS,
    SERVICE_UUID,
    TRANSMODBUS_READ_BLOCKS,
    WRITE_UUID,
)
from custom_components.saj_hs3.local_client import (
    SajLocalClient,
    SajLocalConnectionError,
)
from custom_components.saj_hs3.local_protocol import (
    FrameAssembler,
    decrypt_payload,
    derive_session_key,
    encode_frames,
    encrypt_payload,
)


class FakeCharacteristic:
    """Minimal characteristic metadata."""

    def __init__(self, properties: list[str]) -> None:
        self.properties = properties


class FakeServices:
    """Minimal confirmed GATT layout."""

    def get_service(self, uuid: str) -> object | None:
        return object() if uuid == SERVICE_UUID else None

    def get_characteristic(self, uuid: str) -> FakeCharacteristic | None:
        if uuid == WRITE_UUID:
            return FakeCharacteristic(["write"])
        if uuid == NOTIFY_UUID:
            return FakeCharacteristic(["notify", "read"])
        return None


class FakeClient:
    """Reassemble requests and emit matching read-only fixture responses."""

    services = FakeServices()

    def __init__(self) -> None:
        self.seed = b"123456789"
        self.key = derive_session_key(self.seed)
        self.callback = None
        self.assembler = FrameAssembler()
        self.request_count = 0
        self.disconnected = False
        self.stop_notify_called = False

    async def start_notify(self, uuid: str, callback: object) -> None:
        assert uuid == NOTIFY_UUID
        self.callback = callback

    async def stop_notify(self, uuid: str) -> None:
        assert uuid == NOTIFY_UUID
        self.stop_notify_called = True

    async def read_gatt_char(self, uuid: str) -> bytes:
        assert uuid == NOTIFY_UUID
        return self.seed

    async def write_gatt_char(self, uuid: str, frame: bytes, *, response: bool) -> None:
        assert uuid == WRITE_UUID
        assert response is True
        encrypted = self.assembler.add(frame)
        if encrypted is None:
            return
        plaintext = decrypt_payload(encrypted, self.key).decode()
        if plaintext == "0AT+SINFO?\r\n":
            payload = (
                b'0JSON={"module information":{"model":"eManager",'
                b'"sn":"TEST-SERIAL"},"ble":{"pswSwitch":"0"}}\r\n'
            )
            self.assembler = FrameAssembler()
            self.request_count += 1
            assert self.callback is not None
            for response_frame in encode_frames(
                encrypt_payload(payload, self.key),
                self.request_count,
                GATT_WRITE_LIMIT,
            ):
                self.callback(None, bytearray(response_frame))
            return
        if plaintext == "0AT+EMSDEVICECONFIG?\r\n":
            payload = (
                b'0JSON={"devices":[{"state":"1","devicetype":"pcs",'
                b'"ddf":"1610_v1.0.240816.csv","sn":"TEST-HS3"}]}\r\n'
            )
            self.assembler = FrameAssembler()
            self.request_count += 1
            assert self.callback is not None
            for response_frame in encode_frames(
                encrypt_payload(payload, self.key),
                self.request_count,
                GATT_WRITE_LIMIT,
            ):
                self.callback(None, bytearray(response_frame))
            return
        message = json.loads(plaintext[plaintext.find("{") : plaintext.rfind("}") + 1])
        if message["function"] == "transModbus":
            request = message["context"]["transModbus"][0]
            block = (
                request["funcCode"],
                request["regAddr"][0],
                int(request["regNum"][0]),
            )
            assert block in TRANSMODBUS_READ_BLOCKS
            count = block[2]
            words = ["0000"] * count
            if block == ("03", "0x8F00", 13):
                words[:3] = ["1610", "2710", "03E8"]
            elif block == ("03", "0x4031", 19):
                values = {
                    0: "0906",
                    1: "007B",
                    2: "1389",
                    4: "0320",
                    7: "0901",
                    8: "FF9C",
                    9: "1388",
                    11: "FF38",
                    14: "08FB",
                    15: "0032",
                    16: "1387",
                    18: "0190",
                }
                for index, value in values.items():
                    words[index] = value
            elif block == ("03", "0x4055", 76):
                values = {
                    0: "08FC",
                    1: "0064",
                    2: "1388",
                    4: "03E8",
                    6: "08FD",
                    7: "FF9C",
                    10: "0384",
                    12: "08FE",
                    13: "0032",
                    16: "0320",
                    24: "FF38",
                    28: "0FA0",
                    29: "007B",
                    30: "01F4",
                    31: "0F96",
                    32: "0078",
                    33: "01E0",
                }
                for index, value in values.items():
                    words[index] = value
            elif block == ("33", "0x0400", 2):
                words = ["0000", "2710"]
            elif block == ("35", "0x6506", 4):
                words = ["0000", "09D0", "0038", "1166"]
            response_message = {
                "function": "transModbus_rsp",
                "context": {
                    "UUID": message["context"]["UUID"],
                    "transModbus": [
                        {
                            **request,
                            "regValue": ["".join(words)],
                            "errCode": ["0"],
                        }
                    ],
                },
            }
            payload = f"0+SETTINGDEVICE={json.dumps(response_message)}\r\n".encode()
            self.assembler = FrameAssembler()
            self.request_count += 1
            assert self.callback is not None
            for response_frame in encode_frames(
                encrypt_payload(payload, self.key),
                self.request_count,
                GATT_WRITE_LIMIT,
            ):
                self.callback(None, bytearray(response_frame))
            return
        request = message["context"]["readingDevice"][0]
        ids = request["dataId"]
        assert tuple(ids) in (REALTIME_EMS_DATA_IDS, ENERGY_EMS_DATA_IDS)
        values = [
            json.dumps({"energyManager": {"currentMode": "modeUserAI"}})
            if data_id == "102"
            else str(index + 1)
            for index, data_id in enumerate(ids)
        ]
        response_message = {
            "function": "readingDevice_rsp",
            "context": {
                "UUID": message["context"]["UUID"],
                "readingDevice": [
                    {
                        "SN": "TEST-SERIAL",
                        "dataId": ids,
                        "dataValue": values,
                        "errCode": ["0"] * len(ids),
                    }
                ],
            },
        }
        payload = f"0+SETTINGDEVICE={json.dumps(response_message)}\r\n".encode()
        self.assembler = FrameAssembler()
        self.request_count += 1
        assert self.callback is not None
        for response_frame in encode_frames(
            encrypt_payload(payload, self.key), self.request_count, GATT_WRITE_LIMIT
        ):
            self.callback(None, bytearray(response_frame))

    async def disconnect(self) -> None:
        self.disconnected = True


class NoResponseClient(FakeClient):
    """Accept the identity request without returning a notification."""

    async def write_gatt_char(self, uuid: str, frame: bytes, *, response: bool) -> None:
        assert uuid == WRITE_UUID
        assert response is True


def test_client_reads_only_fixed_allowlisted_sources(
    monkeypatch: object,
) -> None:
    import custom_components.saj_hs3.local_client as module

    fake = FakeClient()

    async def connect(*args: object, **kwargs: object) -> FakeClient:
        return fake

    monkeypatch.setattr(module, "establish_connection", connect)  # type: ignore[attr-defined]
    client = SajLocalClient(lambda: object(), "test-address", "eManager:TEST")
    fields = asyncio.run(client.async_read_confirmed_fields())

    assert fake.request_count == 9
    assert fake.disconnected is False
    assert fake.stop_notify_called is False
    assert set(REALTIME_EMS_DATA_IDS + ENERGY_EMS_DATA_IDS).issubset(fields)
    assert fields["40"] == 3.0
    assert fields["44"] == 7.0
    assert fields["tm_battery_capacity"] == 10.0
    assert fields["tm_battery_current"] == 5.6
    assert fields["tm_battery_voltage"] == 445.4
    assert fields["tm_inverter_type"] == "0x1610"
    assert fields["tm_backup_voltage_l1"] == 230.0
    assert fields["tm_backup_current_l2"] == -1.0
    assert fields["tm_backup_frequency"] == 50.0
    assert fields["tm_battery_power_signed"] == -200
    assert fields["tm_grid_voltage_l1"] == 231.0
    assert fields["tm_grid_current_l2"] == -1.0
    assert fields["tm_grid_power_l2"] == -200
    assert fields["tm_grid_frequency"] == 50.01
    assert fields["tm_pv1_voltage"] == 400.0
    assert fields["tm_pv2_power"] == 480
    assert client.cycle_diagnostics["result"] == "success"
    assert client.cycle_diagnostics["stage"] == "complete"
    assert client.cycle_diagnostics["request_count"] == 9
    assert client.cycle_diagnostics["consecutive_failures"] == 0
    assert client.cycle_diagnostics["active_session"] is True
    assert (
        client.cycle_diagnostics["direction_observations"]["battery"]["5"]["samples"]
        == 1
    )


def test_client_reuses_one_gatt_session_across_polls(monkeypatch: object) -> None:
    """Recurring polls must not reconnect or re-enable FF02 notifications."""
    import custom_components.saj_hs3.local_client as module

    fake = FakeClient()
    connects = 0

    async def connect(*args: object, **kwargs: object) -> FakeClient:
        nonlocal connects
        connects += 1
        return fake

    async def scenario() -> None:
        client = SajLocalClient(lambda: object(), "test-address", "eManager:TEST")
        await client.async_read_confirmed_fields()
        await client.async_read_confirmed_fields()
        assert fake.request_count == 16
        assert client.cycle_diagnostics["request_count"] == 7
        assert connects == 1
        assert fake.disconnected is False
        await client.async_close()
        assert fake.disconnected is True

    monkeypatch.setattr(module, "establish_connection", connect)  # type: ignore[attr-defined]
    asyncio.run(scenario())


def test_connection_uses_ha_device_refresh_for_proxy_failover(
    monkeypatch: object,
) -> None:
    """The retry connector can switch from a host path to a remote proxy path."""
    import custom_components.saj_hs3.local_client as module

    fake = FakeClient()
    host_device = object()
    proxy_device = object()
    devices = iter((host_device, proxy_device, proxy_device))
    sources = iter(("host-scanner", "proxy-scanner", "proxy-scanner"))
    captured: dict[str, object] = {}

    async def connect(*args: object, **kwargs: object) -> FakeClient:
        captured["initial_device"] = args[1]
        captured["refreshed_device"] = kwargs["ble_device_callback"]()
        captured["use_services_cache"] = kwargs["use_services_cache"]
        return fake

    monkeypatch.setattr(module, "establish_connection", connect)  # type: ignore[attr-defined]
    client = SajLocalClient(
        lambda: next(devices),
        "test-address",
        "eManager:TEST",
        lambda: next(sources),
    )

    asyncio.run(client.async_read_confirmed_fields())

    assert captured == {
        "initial_device": host_device,
        "refreshed_device": proxy_device,
        "use_services_cache": True,
    }
    assert client.last_connection_source == "proxy-scanner"


def test_busy_emanager_uses_one_bounded_pre_request_retry(
    monkeypatch: object,
) -> None:
    """A failure before any BSaj request gets one delayed clean reconnect."""
    import custom_components.saj_hs3.local_client as module

    fake = FakeClient()
    calls = 0
    attempt_limits: list[int] = []

    async def connect(*args: object, **kwargs: object) -> FakeClient:
        nonlocal calls
        calls += 1
        attempt_limit = kwargs["max_attempts"]
        assert isinstance(attempt_limit, int)
        attempt_limits.append(attempt_limit)
        if calls == 1:
            raise RuntimeError("simulated exclusive BLE client")
        return fake

    monkeypatch.setattr(module, "establish_connection", connect)  # type: ignore[attr-defined]
    client = SajLocalClient(lambda: object(), "test-address", "eManager:TEST")

    monkeypatch.setattr(module, "_PRE_REQUEST_RETRY_DELAY", 0)
    fields = asyncio.run(client.async_read_confirmed_fields())

    assert fields
    assert calls == 2
    assert attempt_limits == [1, 1]
    assert client.cycle_diagnostics["connection_attempts"] == 2
    assert client.cycle_diagnostics["result"] == "success"
    assert client.cycle_diagnostics["consecutive_failures"] == 0


def test_busy_emanager_stops_after_bounded_retry(monkeypatch: object) -> None:
    """Persistent contention cannot create an unbounded reconnect storm."""
    import custom_components.saj_hs3.local_client as module

    calls = 0

    async def connect(*args: object, **kwargs: object) -> FakeClient:
        nonlocal calls
        calls += 1
        raise RuntimeError("simulated exclusive BLE client")

    monkeypatch.setattr(module, "establish_connection", connect)  # type: ignore[attr-defined]
    monkeypatch.setattr(module, "_PRE_REQUEST_RETRY_DELAY", 0)
    client = SajLocalClient(lambda: object(), "test-address", "eManager:TEST")

    with pytest.raises(SajLocalConnectionError) as caught:
        asyncio.run(client.async_read_confirmed_fields())

    assert caught.value.stage == "connect"
    assert calls == 2
    assert client.cycle_diagnostics["connection_attempts"] == 2
    assert client.cycle_diagnostics["request_count"] == 0
    assert client.cycle_diagnostics["result"] == "temporarily_unavailable"


def test_disconnect_cleanup_error_does_not_discard_valid_data(
    monkeypatch: object,
) -> None:
    """A proxy close acknowledgement cannot invalidate completed reads."""
    import custom_components.saj_hs3.local_client as module

    class DisconnectReportingClient(FakeClient):
        async def disconnect(self) -> None:
            self.disconnected = True
            raise RuntimeError("remote link already closed")

    fake = DisconnectReportingClient()

    async def connect(*args: object, **kwargs: object) -> FakeClient:
        return fake

    monkeypatch.setattr(module, "establish_connection", connect)  # type: ignore[attr-defined]
    client = SajLocalClient(lambda: object(), "test-address", "eManager:TEST")

    fields = asyncio.run(client.async_read_confirmed_fields())

    assert fields
    assert fake.disconnected is False
    asyncio.run(client.async_close())
    assert fake.disconnected
    assert client.cycle_diagnostics["result"] == "success"
    assert client.cycle_diagnostics["cleanup_warning"] is True


def test_read_error_stage_survives_cleanup(monkeypatch: object) -> None:
    """Notify/disconnect cleanup must not hide the timed-out request stage."""
    import custom_components.saj_hs3.local_client as module

    fake = NoResponseClient()

    async def connect(*args: object, **kwargs: object) -> FakeClient:
        return fake

    async def immediate_timeout(future: object, **kwargs: float) -> object:
        del future, kwargs
        raise TimeoutError

    monkeypatch.setattr(module, "establish_connection", connect)  # type: ignore[attr-defined]
    monkeypatch.setattr(module.asyncio, "wait_for", immediate_timeout)
    client = SajLocalClient(lambda: object(), "test-address", "eManager:TEST")

    with pytest.raises(SajLocalConnectionError) as caught:
        asyncio.run(client.async_read_confirmed_fields())

    assert caught.value.stage == "sinfo"
    assert fake.disconnected
    assert client.cycle_diagnostics["stage"] == "sinfo"
