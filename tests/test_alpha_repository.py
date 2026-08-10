"""Repository-level safeguards for the installable alpha shell."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "saj_hs3"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_exactly_one_integration_directory() -> None:
    directories = sorted(
        path.name for path in (ROOT / "custom_components").iterdir() if path.is_dir()
    )
    assert directories == ["saj_hs3"]


def test_hacs_required_files_and_manifest() -> None:
    manifest = _load_json(INTEGRATION / "manifest.json")
    assert manifest["domain"] == INTEGRATION.name
    assert manifest["name"] == "SAJ HS3 / Elekeeper"
    assert manifest["config_flow"] is True
    for key in (
        "codeowners",
        "documentation",
        "issue_tracker",
        "name",
        "version",
    ):
        assert manifest[key]

    assert _load_json(ROOT / "hacs.json")["name"] == manifest["name"]
    assert (ROOT / "README.md").is_file()
    assert (ROOT / "LICENSE").is_file()


def test_strings_and_translations_have_matching_structure() -> None:
    strings = _load_json(INTEGRATION / "strings.json")
    english = _load_json(INTEGRATION / "translations" / "en.json")
    dutch = _load_json(INTEGRATION / "translations" / "nl.json")

    assert english.keys() == strings.keys()
    assert dutch.keys() == strings.keys()
    assert english["config"]["step"].keys() == strings["config"]["step"].keys()
    assert dutch["config"]["step"].keys() == strings["config"]["step"].keys()


def test_diagnostics_never_return_secret_values() -> None:
    source = (INTEGRATION / "diagnostics.py").read_text(encoding="utf-8")
    assert "entry.data.get(CONF_APP_SECRET)" in source
    assert '"app_secret": bool(' in source
    assert '"entry_data"' not in source


def test_integration_contains_no_write_transport_calls() -> None:
    python_source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(INTEGRATION.glob("*.py"))
    ).lower()
    forbidden = (
        "write_register",
        "write_registers",
        "transmodbus",
        "at+settingdevice",
        ".post(",
        ".put(",
        ".patch(",
        ".delete(",
    )
    assert not any(term in python_source for term in forbidden)


def test_device_hierarchy_has_no_hardcoded_identifier() -> None:
    source = (INTEGRATION / "entity.py").read_text(encoding="utf-8")
    assert "if descriptor.identifier is None:" in source
    assert "identifiers={(DOMAIN, descriptor.identifier)}" in source


def test_public_alpha_contains_no_research_source_ids() -> None:
    source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
    assert "CANDIDATE_SENSOR_DESCRIPTIONS" in source
    assert 'source_field="' not in source
