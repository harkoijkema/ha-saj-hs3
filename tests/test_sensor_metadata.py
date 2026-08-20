"""Metadata safeguards for enabled local sensors."""

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory

from custom_components.saj_hs3.sensor import LOCAL_SENSOR_DESCRIPTIONS


def test_confirmed_sensor_expansion_is_defined() -> None:
    assert len(LOCAL_SENSOR_DESCRIPTIONS) == 52
    assert all(
        item.evidence
        in {
            "official_definition+live_confirmed",
            "official_definition+exact_live_response",
            "official_definition+live_block_coverage",
            "official_definition+exact_live_read_block",
            "official_definition+model_condition",
            "official_definition+strict_readonly_contract",
            "official_definition+live_correlated_scale",
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
    assert len(source_fields) == 52


def test_ev_entities_are_isolated_on_the_charger_device() -> None:
    ev = [
        item for item in LOCAL_SENSOR_DESCRIPTIONS if item.device_role == "ev_charger"
    ]
    assert {item.key for item in ev} == {
        "ev_charger_status_raw",
        "ev_charger_power",
        "ev_charger_total_energy",
    }
    assert all(item.availability_field == "ev_charger_available" for item in ev)


def test_confirmed_pv_and_backup_block_entities_are_offered() -> None:
    keys = {item.key for item in LOCAL_SENSOR_DESCRIPTIONS}
    assert {
        "pv1_voltage",
        "pv1_current",
        "pv1_power",
        "pv2_voltage",
        "pv2_current",
        "pv2_power",
        "backup_voltage_l1",
        "backup_current_l1",
        "backup_power_l1",
        "backup_voltage_l2",
        "backup_current_l2",
        "backup_power_l2",
        "backup_voltage_l3",
        "backup_current_l3",
        "backup_power_l3",
        "backup_frequency",
    }.issubset(keys)


def test_confirmed_ac_phase_entities_are_offered_without_meter_placeholder() -> None:
    keys = {item.key for item in LOCAL_SENSOR_DESCRIPTIONS}
    assert {
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
    }.issubset(keys)
    assert "grid_meter_status" not in keys


def test_energy_totals_are_not_total_increasing_yet() -> None:
    energy = [
        item
        for item in LOCAL_SENSOR_DESCRIPTIONS
        if item.device_class == SensorDeviceClass.ENERGY
        and item.key.endswith("energy_total")
    ]
    assert len(energy) == 6
    assert all(item.state_class == SensorStateClass.TOTAL for item in energy)
