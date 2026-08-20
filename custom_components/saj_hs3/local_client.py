"""Home Assistant-native, strictly read-only eManager BLE client."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from .const import (
    ENERGY_EMS_DATA_IDS,
    GATT_WRITE_LIMIT,
    NOTIFY_UUID,
    REALTIME_EMS_DATA_IDS,
    SERVICE_UUID,
    TRANSMODBUS_READ_BLOCKS,
    WRITE_UUID,
)
from .local_protocol import (
    DEVICE_DISCOVERY_READ_REQUEST,
    SINFO_READ_REQUEST,
    FrameAssembler,
    SajLocalProtocolError,
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

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

_CONNECT_TIMEOUT = 20.0
_RESPONSE_TIMEOUT = 15.0
_PRE_REQUEST_RETRY_DELAY = 5.0
_LOGGER = logging.getLogger(__name__)


class SajLocalConnectionError(Exception):
    """A redacted BLE connection error."""

    def __init__(self, message: str, *, stage: str) -> None:
        super().__init__(message)
        self.stage = stage


class SajLocalClient:
    """Read only the two captured EMS batches over one serialized BLE session."""

    def __init__(
        self,
        ble_device_provider: Callable[[], BLEDevice | None],
        address: str,
        name: str,
        scanner_source_provider: Callable[[], str | None] | None = None,
    ) -> None:
        self._device_provider = ble_device_provider
        self._scanner_source_provider = scanner_source_provider
        self._address = address
        self._name = name
        self._lock = asyncio.Lock()
        self._last_connection_source: str | None = None
        self._cycle_started_at: str | None = None
        self._last_cycle_duration: float | None = None
        self._last_cycle_result = "not_started"
        self._last_cycle_stage = "idle"
        self._last_request_count = 0
        self._last_connection_attempts = 0
        self._consecutive_failures = 0
        self._last_cleanup_warning = False
        self._client: Any | None = None
        self._active_batch_reader: Callable[[], Awaitable[dict[str, Any]]] | None = None
        self._direction_observations: dict[str, dict[str, dict[str, float | int]]] = {}

    @property
    def last_connection_source(self) -> str | None:
        """Return the HA scanner source selected for the latest attempt."""
        return self._last_connection_source

    @property
    def cycle_diagnostics(self) -> dict[str, Any]:
        """Return privacy-safe lifecycle metrics for Home Assistant diagnostics."""
        return {
            "started_at": self._cycle_started_at,
            "duration_seconds": round(self._last_cycle_duration, 3)
            if self._last_cycle_duration is not None
            else None,
            "result": self._last_cycle_result,
            "stage": self._last_cycle_stage,
            "request_count": self._last_request_count,
            "connection_attempts": self._last_connection_attempts,
            "consecutive_failures": self._consecutive_failures,
            "cleanup_warning": self._last_cleanup_warning,
            "active_session": self._client is not None,
            "direction_observations": self._direction_observations,
        }

    def _set_stage(self, stage: str) -> None:
        self._last_cycle_stage = stage

    async def async_read_confirmed_fields(self) -> dict[str, Any]:
        """Read the exact realtime and total-energy allowlisted batches."""
        async with self._lock:
            started = time.monotonic()
            self._cycle_started_at = datetime.now(UTC).isoformat()
            self._last_cycle_result = "running"
            self._last_request_count = 0
            self._last_connection_attempts = 0
            self._last_cleanup_warning = False
            self._set_stage("resolve_route")
            if self._client is not None and self._active_batch_reader is not None:
                try:
                    self._set_stage("reuse_session")
                    result = await self._active_batch_reader()
                except Exception as err:
                    failure_stage = (
                        err.stage
                        if isinstance(err, SajLocalConnectionError)
                        else self._last_cycle_stage
                    )
                    await self._async_close_session()
                    self._set_stage(failure_stage)
                    self._record_failure(started)
                    if isinstance(
                        err, (SajLocalConnectionError, SajLocalProtocolError)
                    ):
                        raise
                    raise SajLocalConnectionError(
                        "eManager BLE session failed", stage=failure_stage
                    ) from err
                self._record_success(started)
                return result

            device = self._device_provider()
            if device is None:
                self._record_failure(started)
                raise SajLocalConnectionError(
                    "eManager is temporarily unavailable", stage=self._last_cycle_stage
                )
            if self._scanner_source_provider is not None:
                self._last_connection_source = self._scanner_source_provider()

            def _resolve_best_device() -> BLEDevice:
                """Let HA choose the current best host or proxy path on retry."""
                refreshed = self._device_provider()
                if refreshed is not None:
                    if self._scanner_source_provider is not None:
                        self._last_connection_source = self._scanner_source_provider()
                    return refreshed
                return device

            for attempt in range(2):
                self._last_connection_attempts = attempt + 1
                try:
                    result = await self._async_read_once(device, _resolve_best_device)
                    self._record_success(started)
                    return result
                except SajLocalProtocolError:
                    self._record_failure(started)
                    raise
                except Exception as err:
                    retryable = (
                        attempt == 0
                        and self._last_request_count == 0
                        and self._last_cycle_stage
                        in {
                            "connect",
                            "connected",
                            "gatt_service_discovery",
                            "notify_setup",
                        }
                    )
                    if retryable:
                        await asyncio.sleep(_PRE_REQUEST_RETRY_DELAY)
                        continue
                    self._record_failure(started)
                    if isinstance(err, SajLocalConnectionError):
                        raise
                    if isinstance(err, TimeoutError):
                        raise SajLocalConnectionError(
                            "eManager request timed out", stage=self._last_cycle_stage
                        ) from err
                    raise SajLocalConnectionError(
                        "eManager BLE connection failed", stage=self._last_cycle_stage
                    ) from err

            raise AssertionError("bounded eManager retry loop exhausted")

    def _record_success(self, started: float) -> None:
        self._last_cycle_duration = time.monotonic() - started
        self._last_cycle_result = "success"
        self._set_stage("complete")
        self._consecutive_failures = 0

    async def _async_read_once(
        self,
        device: BLEDevice,
        resolve_best_device: Callable[[], BLEDevice],
    ) -> dict[str, Any]:
        """Start one clean BLE/GATT/BSaj session and retain it on success."""
        self._set_stage("connect")
        client = await establish_connection(
            BleakClientWithServiceCache,
            device,
            self._name,
            max_attempts=1,
            ble_device_callback=resolve_best_device,
            use_services_cache=True,
        )
        self._set_stage("connected")
        result: dict[str, Any] | None = None
        batch_reader: Callable[[], Awaitable[dict[str, Any]]] | None = None
        read_error: BaseException | None = None
        read_error_stage: str | None = None
        try:
            result, batch_reader = await self._start_session(client)
        except BaseException as err:
            read_error = err
            read_error_stage = (
                err.stage
                if isinstance(err, SajLocalConnectionError)
                else self._last_cycle_stage
            )
        if read_error is not None:
            self._set_stage("disconnect")
            try:
                await client.disconnect()
            except Exception:
                self._last_cleanup_warning = True
                _LOGGER.debug("eManager disconnect reported a cleanup warning")
            assert read_error_stage is not None
            self._set_stage(read_error_stage)
            raise read_error
        assert result is not None
        assert batch_reader is not None
        self._client = client
        self._active_batch_reader = batch_reader
        return result

    def _record_failure(self, started: float) -> None:
        self._last_cycle_duration = time.monotonic() - started
        self._last_cycle_result = "temporarily_unavailable"
        self._consecutive_failures += 1

    async def _start_session(
        self, client: Any
    ) -> tuple[dict[str, Any], Callable[[], Awaitable[dict[str, Any]]]]:
        self._set_stage("gatt_service_discovery")
        services = client.services
        if services.get_service(SERVICE_UUID) is None:
            raise SajLocalProtocolError("Required eManager service is unavailable")
        write_char = services.get_characteristic(WRITE_UUID)
        notify_char = services.get_characteristic(NOTIFY_UUID)
        if write_char is None or notify_char is None:
            raise SajLocalProtocolError(
                "Required eManager characteristics are unavailable"
            )
        if (
            "write" not in write_char.properties
            or "notify" not in notify_char.properties
        ):
            raise SajLocalProtocolError("Required safe GATT properties are unavailable")

        key: bytes | None = None
        assembler = FrameAssembler()
        future: asyncio.Future[bytes] | None = None

        def on_notify(_: Any, data: bytearray) -> None:
            nonlocal assembler
            try:
                encrypted = assembler.add(bytes(data))
                if (
                    encrypted is not None
                    and key is not None
                    and future is not None
                    and not future.done()
                ):
                    future.set_result(decrypt_payload(encrypted, key))
            except Exception as err:
                if future is not None and not future.done():
                    future.set_exception(err)

        self._set_stage("notify_setup")
        await client.start_notify(NOTIFY_UUID, on_notify)
        self._set_stage("session_seed")
        seed = bytes(await client.read_gatt_char(NOTIFY_UUID))
        key = derive_session_key(seed)
        sequence = 0

        # Elekeeper's normal read cycle first uses this exact query to obtain
        # the identifier required by readingDevice. It is a fixed query and
        # is not exposed as a general AT-command interface.
        identity_frames = encode_frames(
            encrypt_payload(SINFO_READ_REQUEST, key), sequence, GATT_WRITE_LIMIT
        )
        assembler = FrameAssembler()
        future = asyncio.get_running_loop().create_future()
        self._set_stage("sinfo")
        self._last_request_count += 1
        for frame in identity_frames:
            await client.write_gatt_char(WRITE_UUID, frame, response=True)
        identity_response = await self._await_response(future, stage="sinfo")
        emanager_serial = parse_sinfo_response(identity_response)
        sequence = (sequence + len(identity_frames)) & 0xFF

        # This fixed read-only discovery query is the captured source of the
        # online HS3 selector needed by transModbus. It is executed once per
        # persistent session and is never exposed as a raw command surface.
        discovery_frames = encode_frames(
            encrypt_payload(DEVICE_DISCOVERY_READ_REQUEST, key),
            sequence,
            GATT_WRITE_LIMIT,
        )
        assembler = FrameAssembler()
        future = asyncio.get_running_loop().create_future()
        self._set_stage("device_discovery")
        self._last_request_count += 1
        for frame in discovery_frames:
            await client.write_gatt_char(WRITE_UUID, frame, response=True)
        discovery_response = await self._await_response(
            future, stage="device_discovery"
        )
        inverter_serial = parse_device_discovery_response(discovery_response)
        sequence = (sequence + len(discovery_frames)) & 0xFF

        async def read_batches() -> dict[str, Any]:
            nonlocal assembler, future, sequence
            result: dict[str, Any] = {}
            for batch_number, batch in enumerate(
                (REALTIME_EMS_DATA_IDS, ENERGY_EMS_DATA_IDS), start=1
            ):
                request_uuid = str(int(time.time() * 1000))
                request = build_reading_device_request(
                    session_uuid=request_uuid,
                    emanager_serial=emanager_serial,
                    data_ids=batch,
                    timestamp=datetime.now().astimezone(),
                )
                frames = encode_frames(
                    encrypt_payload(request, key), sequence, GATT_WRITE_LIMIT
                )
                assembler = FrameAssembler()
                future = asyncio.get_running_loop().create_future()
                self._set_stage(f"reading_device_batch_{batch_number}")
                self._last_request_count += 1
                for frame in frames:
                    await client.write_gatt_char(WRITE_UUID, frame, response=True)
                response = await self._await_response(
                    future, stage=f"reading_device_batch_{batch_number}"
                )
                result.update(parse_reading_device_response(response, request_uuid))
                sequence = (sequence + len(frames)) & 0xFF
            for function_code, address, count in TRANSMODBUS_READ_BLOCKS:
                request_uuid = str(int(time.time() * 1000))
                block = (function_code, address, count)
                request = build_transmodbus_read_request(
                    session_uuid=request_uuid,
                    device_serial=inverter_serial,
                    function_code=function_code,
                    address=address,
                    count=count,
                    timestamp=datetime.now().astimezone(),
                )
                frames = encode_frames(
                    encrypt_payload(request, key), sequence, GATT_WRITE_LIMIT
                )
                assembler = FrameAssembler()
                future = asyncio.get_running_loop().create_future()
                self._set_stage(f"transmodbus_{function_code}_{address}")
                self._last_request_count += 1
                for frame in frames:
                    await client.write_gatt_char(WRITE_UUID, frame, response=True)
                response = await self._await_response(
                    future, stage=f"transmodbus_{function_code}_{address}"
                )
                words = parse_transmodbus_response(response, request_uuid, block)
                result.update(normalize_transmodbus_fields(block, words))
                sequence = (sequence + len(frames)) & 0xFF
            self._record_direction_observations(result)
            return result

        return await read_batches(), read_batches

    def _record_direction_observations(self, fields: dict[str, Any]) -> None:
        """Correlate natural direction codes with magnitudes without inference."""
        for name, code_id, magnitude_id in (
            ("pv", "33", "39"),
            ("battery", "34", "40"),
            ("grid", "35", "44"),
            ("load", "36", "45"),
        ):
            code = fields.get(code_id)
            magnitude = fields.get(magnitude_id)
            if not isinstance(code, (int, float)) or not isinstance(
                magnitude, (int, float)
            ):
                continue
            code_key = str(int(code)) if float(code).is_integer() else str(code)
            observation = self._direction_observations.setdefault(name, {}).setdefault(
                code_key,
                {
                    "samples": 0,
                    "minimum_magnitude": float(magnitude),
                    "maximum_magnitude": float(magnitude),
                },
            )
            observation["samples"] = int(observation["samples"]) + 1
            observation["minimum_magnitude"] = min(
                float(observation["minimum_magnitude"]), float(magnitude)
            )
            observation["maximum_magnitude"] = max(
                float(observation["maximum_magnitude"]), float(magnitude)
            )

    async def async_close(self) -> None:
        """Release the persistent proxy/GATT session on unload or reload."""
        async with self._lock:
            await self._async_close_session()

    async def _async_close_session(self) -> None:
        client = self._client
        self._client = None
        self._active_batch_reader = None
        if client is None:
            return
        self._set_stage("disconnect")
        try:
            await client.disconnect()
        except Exception:
            self._last_cleanup_warning = True
            _LOGGER.debug("eManager disconnect reported a cleanup warning")

    async def _await_response(
        self, future: asyncio.Future[bytes], *, stage: str
    ) -> bytes:
        """Wait once and retain the actual request stage across cleanup."""
        try:
            return await asyncio.wait_for(future, timeout=_RESPONSE_TIMEOUT)
        except TimeoutError as err:
            raise SajLocalConnectionError(
                "eManager request timed out", stage=stage
            ) from err
