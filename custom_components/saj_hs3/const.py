"""Constants for SAJ HS3 / Elekeeper."""

from enum import StrEnum
from typing import Final

DOMAIN: Final = "saj_hs3"
INTEGRATION_NAME: Final = "SAJ HS3 / Elekeeper"
INTEGRATION_VERSION: Final = "0.9.0-alpha.1"

CONF_ENABLED_SOURCES: Final = "enabled_sources"
CONF_ENABLE_LOCAL_EMANAGER: Final = "enable_local_emanager"
CONF_ENABLE_OPEN_PLATFORM: Final = "enable_open_platform"
CONF_APP_ID: Final = "app_id"
CONF_APP_SECRET: Final = "app_secret"
CONF_BLUETOOTH_ADDRESS: Final = "bluetooth_address"
CONF_EMANAGER_NAME: Final = "emanager_name"

SOURCE_LOCAL_EMANAGER: Final = "local_emanager"
SOURCE_OPEN_PLATFORM: Final = "open_platform"

OPEN_PLATFORM_BASE_URL: Final = "https://developer.saj-electric.com/prod-api"
OPEN_PLATFORM_TOKEN_ENDPOINT: Final = "/open/api/access_token"
OPEN_PLATFORM_PLANTS_ENDPOINT: Final = "/open/api/developer/plant/page"
TOKEN_REFRESH_MARGIN_SECONDS: Final = 300
OPEN_PLATFORM_UPDATE_INTERVAL_SECONDS: Final = 3600
LOCAL_UPDATE_INTERVAL_SECONDS: Final = 60

EMANAGER_LOCAL_NAME_PREFIX: Final = "eManager:"
SERVICE_UUID: Final = "0000ffff-0000-1000-8000-00805f9b34fb"
WRITE_UUID: Final = "0000ff01-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID: Final = "0000ff02-0000-1000-8000-00805f9b34fb"
GATT_WRITE_LIMIT: Final = 182

# Exact read-only batches recovered byte-for-byte from normal Elekeeper traffic.
REALTIME_EMS_DATA_IDS: Final = (
    "39",
    "33",
    "40",
    "92",
    "34",
    "41",
    "44",
    "35",
    "45",
    "36",
)
ENERGY_EMS_DATA_IDS: Final = ("55", "59", "63", "79", "71", "75", "67", "83", "102")
ALLOWED_EMS_DATA_IDS: Final = frozenset(REALTIME_EMS_DATA_IDS + ENERGY_EMS_DATA_IDS)

# Exact read-only blocks already observed in normal Elekeeper traffic. These are
# deliberately not user-configurable and do not form a general Modbus surface.
TRANSMODBUS_READ_BLOCKS: Final = (
    ("03", "0x8F00", 13),
    ("03", "0x4031", 19),
    ("03", "0x4055", 76),
    ("33", "0x0400", 2),
    ("35", "0x6506", 4),
)

FORBIDDEN_MODBUS_FUNCTION_CODES: Final = frozenset({"05", "06", "15", "16", "22", "23"})


class SAJHS3DeviceRole(StrEnum):
    """Logical device roles."""

    EMANAGER = "emanager"
    INVERTER = "inverter"
    BATTERY_SYSTEM = "battery_system"
    EV_CHARGER = "ev_charger"


DEVICE_ROLE_NAMES: Final[dict[SAJHS3DeviceRole, str]] = {
    SAJHS3DeviceRole.EMANAGER: "SAJ eManager",
    SAJHS3DeviceRole.INVERTER: "SAJ HS3 inverter",
    SAJHS3DeviceRole.BATTERY_SYSTEM: "SAJ Battery System",
    SAJHS3DeviceRole.EV_CHARGER: "SAJ EV Charger",
}
