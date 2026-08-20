"""Confirmed read-only SAJ HS3 sensor entities."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SOURCE_LOCAL_EMANAGER
from .coordinator import SAJHS3DataUpdateCoordinator
from .entity import SAJHS3SensorEntityDescription


def _power(
    key: str, translation_key: str, data_id: str
) -> SAJHS3SensorEntityDescription:
    return SAJHS3SensorEntityDescription(
        key=key,
        translation_key=translation_key,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        source=SOURCE_LOCAL_EMANAGER,
        source_field=data_id,
        evidence="official_definition+live_confirmed",
    )


def _energy(
    key: str, translation_key: str, data_id: str
) -> SAJHS3SensorEntityDescription:
    return SAJHS3SensorEntityDescription(
        key=key,
        translation_key=translation_key,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        source=SOURCE_LOCAL_EMANAGER,
        source_field=data_id,
        evidence="official_definition+live_confirmed",
    )


def _voltage(
    key: str, translation_key: str, source_field: str
) -> SAJHS3SensorEntityDescription:
    return SAJHS3SensorEntityDescription(
        key=key,
        translation_key=translation_key,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        source=SOURCE_LOCAL_EMANAGER,
        source_field=source_field,
        evidence="official_definition+exact_live_read_block",
    )


def _current(
    key: str, translation_key: str, source_field: str
) -> SAJHS3SensorEntityDescription:
    return SAJHS3SensorEntityDescription(
        key=key,
        translation_key=translation_key,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        source=SOURCE_LOCAL_EMANAGER,
        source_field=source_field,
        evidence="official_definition+exact_live_read_block",
    )


LOCAL_SENSOR_DESCRIPTIONS: tuple[SAJHS3SensorEntityDescription, ...] = (
    _power("pv_power", "pv_power", "39"),
    _power("battery_power", "battery_power", "40"),
    _power(
        "battery_power_signed",
        "battery_power_signed",
        "tm_battery_power_signed",
    ),
    SAJHS3SensorEntityDescription(
        key="battery_soc",
        translation_key="battery_state_of_charge",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        source=SOURCE_LOCAL_EMANAGER,
        source_field="41",
        evidence="official_definition+live_confirmed",
    ),
    _power("grid_power", "grid_power", "44"),
    _power("load_power", "house_load_power", "45"),
    _energy("pv_energy_total", "pv_energy_total", "55"),
    _energy("battery_charge_energy_total", "battery_charge_energy_total", "59"),
    _energy("battery_discharge_energy_total", "battery_discharge_energy_total", "63"),
    _energy("grid_import_energy_total", "grid_import_energy_total", "75"),
    _energy("grid_export_energy_total", "grid_export_energy_total", "79"),
    _energy("load_energy_total", "load_energy_total", "83"),
    SAJHS3SensorEntityDescription(
        key="ems_operating_strategy",
        translation_key="ems_operating_strategy",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
        source=SOURCE_LOCAL_EMANAGER,
        source_field="102",
        evidence="official_definition+live_confirmed",
    ),
    SAJHS3SensorEntityDescription(
        key="battery_installed_capacity",
        translation_key="battery_installed_capacity",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        source=SOURCE_LOCAL_EMANAGER,
        source_field="tm_battery_capacity",
        evidence="official_definition+exact_live_response",
    ),
    SAJHS3SensorEntityDescription(
        key="battery_current",
        translation_key="battery_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        source=SOURCE_LOCAL_EMANAGER,
        source_field="tm_battery_current",
        evidence="official_definition+live_block_coverage",
    ),
    SAJHS3SensorEntityDescription(
        key="inverter_type",
        translation_key="inverter_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
        source=SOURCE_LOCAL_EMANAGER,
        source_field="tm_inverter_type",
        evidence="official_definition+exact_live_response",
    ),
    _power(
        "inverter_rated_power",
        "inverter_rated_power",
        "tm_inverter_rated_power",
    ),
    SAJHS3SensorEntityDescription(
        key="inverter_protocol_version",
        translation_key="inverter_protocol_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
        source=SOURCE_LOCAL_EMANAGER,
        source_field="tm_inverter_protocol_version",
        evidence="official_definition+live_block_coverage",
    ),
    SAJHS3SensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        source=SOURCE_LOCAL_EMANAGER,
        source_field="tm_battery_voltage",
        evidence="official_definition+live_block_coverage",
    ),
    _voltage("pv1_voltage", "pv1_voltage", "tm_pv1_voltage"),
    _current("pv1_current", "pv1_current", "tm_pv1_current"),
    _power("pv1_power", "pv1_power", "tm_pv1_power"),
    _voltage("pv2_voltage", "pv2_voltage", "tm_pv2_voltage"),
    _current("pv2_current", "pv2_current", "tm_pv2_current"),
    _power("pv2_power", "pv2_power", "tm_pv2_power"),
    _voltage("grid_voltage_l1", "grid_voltage_l1", "tm_grid_voltage_l1"),
    _current("grid_current_l1", "grid_current_l1", "tm_grid_current_l1"),
    _power("grid_power_l1", "grid_power_l1", "tm_grid_power_l1"),
    _voltage("grid_voltage_l2", "grid_voltage_l2", "tm_grid_voltage_l2"),
    _current("grid_current_l2", "grid_current_l2", "tm_grid_current_l2"),
    _power("grid_power_l2", "grid_power_l2", "tm_grid_power_l2"),
    _voltage("grid_voltage_l3", "grid_voltage_l3", "tm_grid_voltage_l3"),
    _current("grid_current_l3", "grid_current_l3", "tm_grid_current_l3"),
    _power("grid_power_l3", "grid_power_l3", "tm_grid_power_l3"),
    SAJHS3SensorEntityDescription(
        key="grid_frequency",
        translation_key="grid_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        source=SOURCE_LOCAL_EMANAGER,
        source_field="tm_grid_frequency",
        evidence="official_definition+model_condition",
    ),
    _voltage("backup_voltage_l1", "backup_voltage_l1", "tm_backup_voltage_l1"),
    _current("backup_current_l1", "backup_current_l1", "tm_backup_current_l1"),
    _power("backup_power_l1", "backup_power_l1", "tm_backup_power_l1"),
    _voltage("backup_voltage_l2", "backup_voltage_l2", "tm_backup_voltage_l2"),
    _current("backup_current_l2", "backup_current_l2", "tm_backup_current_l2"),
    _power("backup_power_l2", "backup_power_l2", "tm_backup_power_l2"),
    _voltage("backup_voltage_l3", "backup_voltage_l3", "tm_backup_voltage_l3"),
    _current("backup_current_l3", "backup_current_l3", "tm_backup_current_l3"),
    _power("backup_power_l3", "backup_power_l3", "tm_backup_power_l3"),
    SAJHS3SensorEntityDescription(
        key="backup_frequency",
        translation_key="backup_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        source=SOURCE_LOCAL_EMANAGER,
        source_field="tm_backup_frequency",
        evidence="official_definition+exact_live_read_block",
    ),
    *tuple(
        SAJHS3SensorEntityDescription(
            key=f"{key}_direction_code",
            translation_key=f"{key}_direction_code",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=True,
            source=SOURCE_LOCAL_EMANAGER,
            source_field=data_id,
            evidence="official_definition+live_confirmed",
        )
        for key, data_id in (
            ("pv", "33"),
            ("battery", "34"),
            ("grid", "35"),
            ("load", "36"),
        )
    ),
    SAJHS3SensorEntityDescription(
        key="ev_charger_status_raw",
        translation_key="ev_charger_status_raw",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
        source=SOURCE_LOCAL_EMANAGER,
        source_field="ev_charger_status_raw",
        availability_field="ev_charger_available",
        device_role="ev_charger",
        evidence="official_definition+strict_readonly_contract",
    ),
    SAJHS3SensorEntityDescription(
        key="ev_charger_power",
        translation_key="ev_charger_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        source=SOURCE_LOCAL_EMANAGER,
        source_field="ev_charger_power_raw",
        availability_field="ev_charger_available",
        device_role="ev_charger",
        evidence="official_definition+strict_readonly_contract",
    ),
    SAJHS3SensorEntityDescription(
        key="ev_charger_total_energy",
        translation_key="ev_charger_total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        source=SOURCE_LOCAL_EMANAGER,
        source_field="ev_charger_total_energy_kwh",
        availability_field="ev_charger_available",
        device_role="ev_charger",
        evidence="official_definition+live_correlated_scale",
    ),
)

# These keys existed only in one local, unpublished validation build. Its
# A03C block returned valid but all-zero data for this HS3 target, so the
# entities must not remain as orphaned registry records.
_RETIRED_LOCAL_VALIDATION_KEYS = ("grid_meter_status",)
_WORKING_DIAGNOSTIC_KEYS = (
    "ems_operating_strategy",
    "pv_direction_code",
    "battery_direction_code",
    "grid_direction_code",
    "load_direction_code",
)


class SAJHS3Sensor(CoordinatorEntity[SAJHS3DataUpdateCoordinator], SensorEntity):
    """A sensor backed by normalized coordinator fields."""

    entity_description: SAJHS3SensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SAJHS3DataUpdateCoordinator,
        entry: ConfigEntry,
        description: SAJHS3SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        if description.device_role == "ev_charger":
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_ev_charger")},
                manufacturer="SAJ",
                name="SAJ EV Charger",
                model="Integrated HS3 EV Charger",
                via_device=(DOMAIN, entry.entry_id),
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, entry.entry_id)},
                manufacturer="SAJ",
                name="SAJ eManager",
                model="eManager",
            )

    @property
    def native_value(self) -> float | str | None:
        value = self.coordinator.data.fields.get(self.entity_description.source_field)
        return value if isinstance(value, (int, float, str)) else None

    @property
    def available(self) -> bool:
        source_available = (
            super().available
            and self.entity_description.source_field in self.coordinator.data.fields
        )
        availability_field = self.entity_description.availability_field
        return source_available and (
            availability_field is None
            or self.coordinator.data.fields.get(availability_field) is True
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up only sensors backed by the configured local source."""
    coordinator: SAJHS3DataUpdateCoordinator = entry.runtime_data
    if coordinator.local is not None:
        registry = er.async_get(hass)
        for key in _RETIRED_LOCAL_VALIDATION_KEYS:
            entity_id = registry.async_get_entity_id(
                "sensor", DOMAIN, f"{entry.entry_id}_{key}"
            )
            if entity_id is not None:
                registry.async_remove(entity_id)
        for key in _WORKING_DIAGNOSTIC_KEYS:
            entity_id = registry.async_get_entity_id(
                "sensor", DOMAIN, f"{entry.entry_id}_{key}"
            )
            if entity_id is not None:
                registry.async_update_entity(entity_id, disabled_by=None)
        async_add_entities(
            SAJHS3Sensor(coordinator, entry, description)
            for description in LOCAL_SENSOR_DESCRIPTIONS
        )
