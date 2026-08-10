"""Constants for SAJ HS3 / Elekeeper."""

from enum import StrEnum
from typing import Final

DOMAIN: Final = "saj_hs3"
INTEGRATION_NAME: Final = "SAJ HS3 / Elekeeper"
INTEGRATION_VERSION: Final = "0.2.0-alpha.1"

CONF_ENABLED_SOURCES: Final = "enabled_sources"
CONF_ENABLE_LOCAL_EMANAGER: Final = "enable_local_emanager"
CONF_ENABLE_OPEN_PLATFORM: Final = "enable_open_platform"
CONF_APP_ID: Final = "app_id"
CONF_APP_SECRET: Final = "app_secret"

SOURCE_LOCAL_EMANAGER: Final = "local_emanager"
SOURCE_OPEN_PLATFORM: Final = "open_platform"

COMMUNICATION_NOT_IMPLEMENTED: Final = "not_implemented"

OPEN_PLATFORM_BASE_URL: Final = "https://developer.saj-electric.com/prod-api"
OPEN_PLATFORM_TOKEN_ENDPOINT: Final = "/open/api/access_token"
OPEN_PLATFORM_PLANTS_ENDPOINT: Final = "/open/api/developer/plant/page"
TOKEN_REFRESH_MARGIN_SECONDS: Final = 300
OPEN_PLATFORM_UPDATE_INTERVAL_SECONDS: Final = 3600


class SAJHS3DeviceRole(StrEnum):
    """Future device roles; these values are not device identifiers."""

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
