"""Offline regression tests for the read-only local protocol."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from custom_components.saj_hs3.const import (
    ENERGY_EMS_DATA_IDS,
    GATT_WRITE_LIMIT,
    REALTIME_EMS_DATA_IDS,
)
from custom_components.saj_hs3.local_protocol import (
    FrameAssembler,
    SajLocalProtocolError,
    SajLocalSafetyError,
    build_reading_device_request,
    build_transmodbus_read_request,
    decrypt_payload,
    derive_session_key,
    encode_frames,
    encrypt_payload,
    normalize_transmodbus_fields,
    parse_device_discovery_response,
    parse_reading_device_response,
    parse_sinfo_response,
    parse_transmodbus_response,
)


def test_crypto_framing_round_trip() -> None:
    key = derive_session_key(b"123456789")
    plaintext = b"read-only regression payload" * 20
    encrypted = encrypt_payload(plaintext, key)
    frames = encode_frames(encrypted, sequence=7, packet_limit=GATT_WRITE_LIMIT)
    assert all(len(frame) <= GATT_WRITE_LIMIT for frame in frames)
    assembler = FrameAssembler()
    assembled = None
    for frame in frames:
        assembled = assembler.add(frame)
    assert assembled == encrypted
    assert decrypt_payload(assembled, key) == plaintext


@pytest.mark.parametrize("batch", [REALTIME_EMS_DATA_IDS, ENERGY_EMS_DATA_IDS])
def test_only_confirmed_batches_are_built(batch: tuple[str, ...]) -> None:
    command = build_reading_device_request(
        session_uuid="123",
        emanager_serial="TEST-SERIAL",
        data_ids=batch,
        timestamp=datetime(2026, 8, 18, tzinfo=UTC),
    )
    assert command.startswith(b"0AT+SETTINGDEVICE=")
    assert b'"function":"readingDevice"' in command


def test_modified_batch_is_rejected() -> None:
    with pytest.raises(SajLocalSafetyError):
        build_reading_device_request(
            session_uuid="123",
            emanager_serial="TEST-SERIAL",
            data_ids=("39",),
            timestamp=datetime(2026, 8, 18, tzinfo=UTC),
        )


def test_sinfo_parser_accepts_only_emanager_identity() -> None:
    payload = (
        b'0JSON={"module information":{"model":"eManager",'
        b'"sn":"TEST-SERIAL"},"ble":{"pswSwitch":"0"}}\r\n'
    )
    assert parse_sinfo_response(payload) == "TEST-SERIAL"
    with pytest.raises(SajLocalProtocolError):
        parse_sinfo_response(
            b'0JSON={"module information":{"model":"other","sn":"x"}}\r\n'
        )


def test_response_parser_preserves_values_and_makes_magnitudes() -> None:
    message = {
        "function": "readingDevice_rsp",
        "context": {
            "UUID": "123",
            "readingDevice": [
                {
                    "SN": "TEST-SERIAL",
                    "dataId": ["39", "40", "41", "44", "45"],
                    "dataValue": ["166.000", "-286.000", "81.300", "-9.000", "461.000"],
                    "errCode": ["0", "0", "0", "0", "0"],
                }
            ],
        },
    }
    payload = f"0+SETTINGDEVICE={json.dumps(message)}\r\n".encode()
    assert parse_reading_device_response(payload, "123") == {
        "39": 166.0,
        "40": 286.0,
        "41": 81.3,
        "44": 9.0,
        "45": 461.0,
    }


def test_checksum_and_uuid_errors_are_rejected() -> None:
    frame = bytearray(encode_frames(b"payload", 0, GATT_WRITE_LIMIT)[0])
    frame[-1] ^= 1
    with pytest.raises(SajLocalProtocolError):
        FrameAssembler().add(bytes(frame))
    payload = (
        b'0+SETTINGDEVICE={"function":"readingDevice_rsp","context":'
        b'{"UUID":"wrong","readingDevice":[]}}\r\n'
    )
    with pytest.raises(SajLocalProtocolError):
        parse_reading_device_response(payload, "expected")


def test_no_raw_or_state_changing_command_surface() -> None:
    import inspect

    from custom_components.saj_hs3 import local_client, local_protocol

    source = inspect.getsource(local_client) + inspect.getsource(local_protocol)
    forbidden = (
        "writeTransModbus",
        "send_raw_command",
        "custom_request",
        "send_modbus",
    )
    assert not any(term in source for term in forbidden)


def test_device_discovery_selects_only_online_hs3() -> None:
    payload = (
        b'0JSON={"devices":[{"state":"1","devicetype":"meter",'
        b'"sn":"METER"},{"state":"1","devicetype":"pcs",'
        b'"ddf":"1610_v1.0.240816.csv","sn":"HS3"}]}\r\n'
    )
    assert parse_device_discovery_response(payload) == "HS3"


def test_transmodbus_allowlist_and_normalization() -> None:
    command = build_transmodbus_read_request(
        session_uuid="123",
        device_serial="HS3",
        function_code="35",
        address="0x6506",
        count=4,
        timestamp=datetime(2026, 8, 19, tzinfo=UTC),
    )
    assert b'"function":"transModbus"' in command
    with pytest.raises(SajLocalSafetyError):
        build_transmodbus_read_request(
            session_uuid="123",
            device_serial="HS3",
            function_code="06",
            address="0x6506",
            count=1,
            timestamp=datetime(2026, 8, 19, tzinfo=UTC),
        )
    assert normalize_transmodbus_fields(("35", "0x6506", 4), [0, 2500, 56, 4454]) == {
        "tm_battery_current": 5.6,
        "tm_battery_voltage": 445.4,
    }


def test_confirmed_hs3_pv_and_backup_block_normalization() -> None:
    words = [0] * 76
    words[0:3] = [2300, 100, 5000]
    words[4] = 1000
    words[6:8] = [2301, 0xFF9C]
    words[10] = 900
    words[12:14] = [2302, 50]
    words[16] = 800
    words[28:34] = [4000, 123, 500, 3990, 120, 480]
    assert normalize_transmodbus_fields(("03", "0x4055", 76), words) == {
        "tm_backup_voltage_l1": 230.0,
        "tm_backup_current_l1": 1.0,
        "tm_backup_frequency": 50.0,
        "tm_backup_power_l1": 1000,
        "tm_backup_voltage_l2": 230.1,
        "tm_backup_current_l2": -1.0,
        "tm_backup_power_l2": 900,
        "tm_backup_voltage_l3": 230.2,
        "tm_backup_current_l3": 0.5,
        "tm_backup_power_l3": 800,
        "tm_pv1_voltage": 400.0,
        "tm_pv1_current": 1.23,
        "tm_pv1_power": 500,
        "tm_pv2_voltage": 399.0,
        "tm_pv2_current": 1.2,
        "tm_pv2_power": 480,
    }


def test_transmodbus_response_requires_exact_contract() -> None:
    message = {
        "function": "transModbus_rsp",
        "context": {
            "UUID": "123",
            "transModbus": [
                {
                    "SN": "HS3",
                    "funcCode": "33",
                    "regAddr": ["0x0400"],
                    "regNum": ["2"],
                    "regValue": ["00002710"],
                    "errCode": ["0"],
                }
            ],
        },
    }
    payload = f"0+SETTINGDEVICE={json.dumps(message)}\r\n".encode()
    words = parse_transmodbus_response(payload, "123", ("33", "0x0400", 2))
    assert words == [0, 10000]
