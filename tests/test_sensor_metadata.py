"""Metadata safeguards for enabled local sensors."""

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory

from custom_components.saj_hs3.sensor import LOCAL_SENSOR_DESCRIPTIONS


def test_confirmed_sensor_expansion_is_defined() -> None:
    assert len(LOCAL_SENSOR_DESCRIPTIONS) == 22
    assert all(
        item.evidence
        in {
            "official_definition+live_confirmed",
            "official_definition+exact_live_response",
            "official_definition+live_block_coverage",
        }
        for item in LOCAL_SENSOR_DESCRIPTIONS
    )


def test_working_diagnostics_are_enabled_by_default() -> None:
    strategy = next(
        item
        for item in LOCAL_SENSOR_DESCRIPTIONS
        if item.key == "ems_operating_strategy"
    )
    assert strategy.source_field == "102"
    assert strategy.entity_category == EntityCategory.DIAGNOSTIC
    assert strategy.entity_registry_enabled_default is True
    diagnostics = [
        item
        for item in LOCAL_SENSOR_DESCRIPTIONS
        if item.entity_category == EntityCategory.DIAGNOSTIC
    ]
    assert diagnostics
    assert all(item.entity_registry_enabled_default for item in diagnostics)


def test_sensor_keys_and_source_fields_do_not_create_duplicates() -> None:
    keys = [item.key for item in LOCAL_SENSOR_DESCRIPTIONS]
    assert len(keys) == len(set(keys))
    source_fields = {
        (item.source, item.source_field) for item in LOCAL_SENSOR_DESCRIPTIONS
    }
    assert len(source_fields) == 22


def test_no_placeholder_or_retired_grid_entities_are_offered() -> None:
    keys = {item.key for item in LOCAL_SENSOR_DESCRIPTIONS}
    assert not keys.intersection(
        {
            "grid_voltage_l1",
            "grid_voltage_l2",
            "grid_voltage_l3",
            "grid_current_l1",
            "grid_current_l2",
            "grid_current_l3",
            "grid_power_l1",
            "grid_power_l2",
            "grid_power_l3",
            "grid_frequency",
            "grid_meter_status",
        }
    )


def test_energy_totals_are_not_total_increasing_yet() -> None:
    energy = [
        item
        for item in LOCAL_SENSOR_DESCRIPTIONS
        if item.device_class == SensorDeviceClass.ENERGY
        and item.key.endswith("energy_total")
    ]
    assert len(energy) == 6
    assert all(item.state_class == SensorStateClass.TOTAL for item in energy)
