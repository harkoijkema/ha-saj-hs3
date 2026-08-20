"""Evidence-bounded, read-only BSaj protocol primitives."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import md5
from typing import Any

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .const import (
    ALLOWED_EMS_DATA_IDS,
    ENERGY_EMS_DATA_IDS,
    REALTIME_EMS_DATA_IDS,
    TRANSMODBUS_READ_BLOCKS,
)

_MAGIC = b"\xff\xaa"
_KEY_TAIL = b"kaSajC0#@23%0612"
SINFO_READ_REQUEST = b"0AT+SINFO?\r\n"
DEVICE_DISCOVERY_READ_REQUEST = b"0AT+EMSDEVICECONFIG?\r\n"


class SajLocalProtocolError(Exception):
    """A redacted local protocol error."""


class SajLocalSafetyError(SajLocalProtocolError):
    """A command fell outside the hard-coded read-only allowlist."""


def derive_session_key(seed: bytes) -> bytes:
    """Derive the live-validated AES-128 session key."""
    return md5(seed + _KEY_TAIL, usedforsecurity=False).digest()


def encrypt_payload(payload: bytes, key: bytes) -> bytes:
    """Encrypt a BSaj payload using AES-128 ECB with PKCS#7."""
    padder = padding.PKCS7(128).padder()
    padded = padder.update(payload) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return encryptor.update(padded) + encryptor.finalize()


def decrypt_payload(payload: bytes, key: bytes) -> bytes:
    """Decrypt a BSaj payload using the live-validated scheme."""
    decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    padded = decryptor.update(payload) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def _checksum(payload: bytes) -> int:
    value = (len(payload) >> 8) ^ (len(payload) & 0xFF)
    for byte in payload:
        value ^= byte
    return value


def encode_frames(payload: bytes, sequence: int, packet_limit: int) -> list[bytes]:
    """Encode encrypted data into validated BSaj frames."""
    if packet_limit < 20:
        raise ValueError("packet limit is too small")
    if len(payload) <= packet_limit - 7:
        chunks = [(1, sequence, payload)]
    else:
        size = packet_limit - 13
        chunks = [
            (
                2,
                (sequence + index) & 0xFF,
                len(payload).to_bytes(4, "big")
                + index.to_bytes(2, "big")
                + payload[offset : offset + size],
            )
            for index, offset in enumerate(range(0, len(payload), size))
        ]
    return [
        _MAGIC
        + bytes((kind, seq))
        + len(chunk).to_bytes(2, "big")
        + chunk
        + bytes((_checksum(chunk),))
        for kind, seq, chunk in chunks
    ]


@dataclass
class FrameAssembler:
    """Validate and assemble one incoming encrypted message."""

    total_length: int | None = None
    data: bytearray = field(default_factory=bytearray)
    next_index: int = 0

    def add(self, frame: bytes) -> bytes | None:
        if len(frame) < 7 or frame[:2] != _MAGIC:
            raise SajLocalProtocolError("Invalid BSaj frame")
        length = int.from_bytes(frame[4:6], "big")
        if len(frame) != length + 7:
            raise SajLocalProtocolError("Invalid BSaj frame length")
        payload = frame[6:-1]
        if frame[-1] != _checksum(payload):
            raise SajLocalProtocolError("Invalid BSaj checksum")
        if frame[2] == 1:
            return payload
        if frame[2] != 2 or len(payload) < 6:
            raise SajLocalProtocolError("Unsupported BSaj frame type")
        total, index = (
            int.from_bytes(payload[:4], "big"),
            int.from_bytes(payload[4:6], "big"),
        )
        if index != self.next_index or self.total_length not in (None, total):
            raise SajLocalProtocolError("Out-of-order BSaj fragment")
        self.total_length = total
        self.next_index += 1
        self.data.extend(payload[6:])
        if len(self.data) > total:
            raise SajLocalProtocolError("BSaj fragment overflow")
        return bytes(self.data) if len(self.data) == total else None


def build_reading_device_request(
    *,
    session_uuid: str,
    emanager_serial: str,
    data_ids: tuple[str, ...],
    timestamp: datetime,
) -> bytes:
    """Build only one of the two exact, captured read-only EMS batches."""
    if data_ids not in (REALTIME_EMS_DATA_IDS, ENERGY_EMS_DATA_IDS):
        raise SajLocalSafetyError("EMS batch is outside the read-only allowlist")
    if not data_ids or any(item not in ALLOWED_EMS_DATA_IDS for item in data_ids):
        raise SajLocalSafetyError("EMS data ID is outside the read-only allowlist")
    payload = {
        "time": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "function": "readingDevice",
        "context": {
            "UUID": session_uuid,
            "readingDevice": [{"SN": emanager_serial, "dataId": list(data_ids)}],
        },
    }
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"0AT+SETTINGDEVICE={compact}\r\n".encode()


def parse_device_discovery_response(payload: bytes) -> str:
    """Return the online HS3 selector from the confirmed device-list response."""
    text = payload.decode("utf-8")
    start, end = text.find("{"), text.rfind("}") + 1
    if start < 0 or end <= start:
        raise SajLocalProtocolError("Device discovery response contains no JSON")
    try:
        message = json.loads(text[start:end])
        devices = message["devices"]
    except (KeyError, TypeError, json.JSONDecodeError) as err:
        raise SajLocalProtocolError("Invalid device discovery response") from err
    if not isinstance(devices, list):
        raise SajLocalProtocolError("Invalid device discovery device list")
    matches = [
        item
        for item in devices
        if isinstance(item, dict)
        and item.get("devicetype") == "pcs"
        and item.get("state") == "1"
        and isinstance(item.get("sn"), str)
        and str(item.get("ddf", "")).startswith("1610_")
    ]
    if len(matches) != 1:
        raise SajLocalProtocolError("No unique online HS3 target was discovered")
    return str(matches[0]["sn"])


def build_transmodbus_read_request(
    *,
    session_uuid: str,
    device_serial: str,
    function_code: str,
    address: str,
    count: int,
    timestamp: datetime,
) -> bytes:
    """Build only an exact, previously observed read-only transModbus block."""
    if (function_code, address, count) not in TRANSMODBUS_READ_BLOCKS:
        raise SajLocalSafetyError(
            "transModbus block is outside the read-only allowlist"
        )
    payload = {
        "time": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "function": "transModbus",
        "context": {
            "UUID": session_uuid,
            "transModbus": [
                {
                    "SN": device_serial,
                    "funcCode": function_code,
                    "regAddr": [address],
                    "regNum": [str(count)],
                }
            ],
        },
    }
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"0AT+SETTINGDEVICE={compact}\r\n".encode()


def parse_transmodbus_response(
    payload: bytes,
    expected_uuid: str,
    expected_block: tuple[str, str, int],
) -> list[int]:
    """Validate and decode one exact allowlisted transModbus response."""
    text = payload.decode("utf-8")
    start, end = text.find("{"), text.rfind("}") + 1
    if start < 0 or end <= start:
        raise SajLocalProtocolError("transModbus response contains no JSON")
    try:
        message = json.loads(text[start:end])
        context = message["context"]
        rows = context["transModbus"]
        row = rows[0]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as err:
        raise SajLocalProtocolError("Invalid transModbus response") from err
    function_code, address, count = expected_block
    if (
        message.get("function") != "transModbus_rsp"
        or str(context.get("UUID")) != expected_uuid
        or len(rows) != 1
        or row.get("funcCode") != function_code
        or row.get("regAddr") != [address]
        or row.get("regNum") != [str(count)]
        or row.get("errCode") != ["0"]
    ):
        raise SajLocalProtocolError("Unexpected transModbus response")
    values = row.get("regValue")
    if not isinstance(values, list) or len(values) != 1:
        raise SajLocalProtocolError("Invalid transModbus register count")
    raw = values[0]
    if not isinstance(raw, str) or len(raw) != count * 4:
        raise SajLocalProtocolError("Invalid transModbus register payload")
    try:
        return [int(raw[index : index + 4], 16) for index in range(0, len(raw), 4)]
    except ValueError as err:
        raise SajLocalProtocolError("Invalid transModbus register value") from err


def normalize_transmodbus_fields(
    block: tuple[str, str, int], words: list[int]
) -> dict[str, float | int | str]:
    """Map only confirmed fields from an exact allowlisted response block."""
    if block == ("03", "0x8F00", 13):
        return {
            "tm_inverter_type": f"0x{words[0]:04X}",
            "tm_inverter_rated_power": words[1],
            "tm_inverter_protocol_version": words[2] / 1000,
        }
    if block == ("03", "0x4055", 76):

        def signed(value: int) -> int:
            return value - 0x10000 if value & 0x8000 else value

        return {
            "tm_backup_voltage_l1": words[0] / 10,
            "tm_backup_current_l1": signed(words[1]) / 100,
            "tm_backup_frequency": words[2] / 100,
            "tm_backup_power_l1": words[4],
            "tm_backup_voltage_l2": words[6] / 10,
            "tm_backup_current_l2": signed(words[7]) / 100,
            "tm_backup_power_l2": words[10],
            "tm_backup_voltage_l3": words[12] / 10,
            "tm_backup_current_l3": signed(words[13]) / 100,
            "tm_backup_power_l3": words[16],
            "tm_pv1_voltage": words[28] / 10,
            "tm_pv1_current": words[29] / 100,
            "tm_pv1_power": words[30],
            "tm_pv2_voltage": words[31] / 10,
            "tm_pv2_current": words[32] / 100,
            "tm_pv2_power": words[33],
        }
    if block == ("33", "0x0400", 2):
        return {"tm_battery_capacity": ((words[0] << 16) | words[1]) / 1000}
    if block == ("35", "0x6506", 4):
        signed_current = words[2] - 0x10000 if words[2] & 0x8000 else words[2]
        return {
            "tm_battery_current": signed_current / 10,
            "tm_battery_voltage": words[3] / 10,
        }
    raise SajLocalSafetyError("transModbus block is outside the read-only allowlist")


def parse_sinfo_response(payload: bytes) -> str:
    """Extract only the serial needed for subsequent captured read requests."""
    text = payload.decode("utf-8")
    start, end = text.find("{"), text.rfind("}") + 1
    if start < 0 or end <= start:
        raise SajLocalProtocolError("SINFO response contains no JSON")
    try:
        message = json.loads(text[start:end])
        information = message["module information"]
        if information.get("model") != "eManager":
            raise SajLocalProtocolError("SINFO target is not an eManager")
        serial = information["sn"]
    except (KeyError, TypeError, json.JSONDecodeError) as err:
        raise SajLocalProtocolError("Invalid SINFO response") from err
    if not isinstance(serial, str) or not serial.strip():
        raise SajLocalProtocolError("SINFO contains no eManager identifier")
    return serial.strip()


def parse_reading_device_response(payload: bytes, expected_uuid: str) -> dict[str, Any]:
    """Parse and validate a matching readingDevice response."""
    text = payload.decode("utf-8")
    start, end = text.find("{"), text.rfind("}") + 1
    if start < 0 or end <= start:
        raise SajLocalProtocolError("Response contains no JSON")
    try:
        message = json.loads(text[start:end])
    except json.JSONDecodeError as err:
        raise SajLocalProtocolError("Response contains invalid JSON") from err
    context = message.get("context")
    if message.get("function") != "readingDevice_rsp" or not isinstance(context, dict):
        raise SajLocalProtocolError("Unexpected local response")
    if str(context.get("UUID")) != expected_uuid:
        raise SajLocalProtocolError("Response UUID mismatch")
    rows = context.get("readingDevice")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise SajLocalProtocolError("Invalid readingDevice response structure")
    row = rows[0]
    ids, values, errors = row.get("dataId"), row.get("dataValue"), row.get("errCode")
    if (
        not isinstance(ids, list)
        or not isinstance(values, list)
        or not isinstance(errors, list)
    ):
        raise SajLocalProtocolError("Invalid readingDevice field arrays")
    if not (len(ids) == len(values) == len(errors)):
        raise SajLocalProtocolError("Mismatched readingDevice field arrays")
    result: dict[str, Any] = {}
    for data_id, value, error in zip(ids, values, errors, strict=True):
        if data_id in ALLOWED_EMS_DATA_IDS and str(error) == "0":
            result[str(data_id)] = _parse_value(str(data_id), value)
    return result


def _parse_value(data_id: str, value: Any) -> Any:
    if data_id == "102":
        try:
            parsed = json.loads(value)
            return parsed["energyManager"]["currentMode"]
        except (KeyError, TypeError, json.JSONDecodeError) as err:
            raise SajLocalProtocolError("Invalid EMS mode value") from err
    try:
        number = float(value)
    except (TypeError, ValueError) as err:
        raise SajLocalProtocolError("Invalid numeric EMS value") from err
    return abs(number) if data_id in {"40", "44", "92"} else number
