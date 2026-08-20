# SAJ HS3 / Elekeeper for Home Assistant

> **Alpha / experimental.** This is a strictly read-only custom integration for
> SAJ HS3 installations with an eManager. It exposes only data points supported
> by documented definitions and validation against the developer's own system.

## Current capabilities

- local polling through Home Assistant Bluetooth or an ESPHome Bluetooth Proxy;
- a persistent, read-only BLE/GATT and BSaj session with the eManager;
- confirmed EMS data and a small set of confirmed `transModbus` reads;
- 49 power, energy, three-phase AC, PV, backup-output, battery and diagnostic
  entities;
- configuration and Bluetooth discovery through the Home Assistant UI;
- optional official Elekeeper Open Platform authentication as a secondary source;
- privacy-safe Home Assistant diagnostics;
- automatic recovery from temporary Bluetooth availability problems.

The local route is:

`Home Assistant → Bluetooth/ESPHome proxy → eManager → BSaj → HS3`

The integration contains no controls and does not write inverter, battery,
grid or EV-charger settings. Ordinary Modbus TCP on port 502 is not used for
the HS3 data implemented here.

## Requirements

- Home Assistant 2025.1 or newer;
- a SAJ HS3 installation with eManager;
- Bluetooth coverage from Home Assistant or an ESPHome Bluetooth Proxy;
- the eManager must be advertising and connectable.

An Android phone and the Elekeeper app are not required for normal local
operation. Results can vary with firmware and installation topology; report
unsupported systems through GitHub Issues without including serial numbers,
addresses, credentials or raw captures.

## Installation through HACS

1. Open HACS.
2. Open **Custom repositories**.
3. Add `https://github.com/harkoijkema/ha-saj-hs3`.
4. Select repository type **Integration**.
5. Download **SAJ HS3 / Elekeeper**.
6. Restart Home Assistant.
7. Go to **Settings → Devices & services → Add integration**.
8. Select **SAJ HS3 / Elekeeper**.
9. Choose **Local eManager** and select the discovered eManager.

The domain is `saj_hs3`. Remove an obsolete manually copied
`custom_components/saj_elekeeper` directory before installation.

## Elekeeper Open Platform

Open Platform remains an optional, secondary data source. It uses an official
released App ID/App Secret, stores the secret in the Home Assistant config
entry, keeps access tokens only in memory and currently performs only confirmed
read-only authentication/resource checks. A normal Elekeeper username and
password are never requested.

## Known limitations

- This release supports only the currently confirmed local fields.
- Individual battery modules, temperatures, SOH and EV-charger data are not
  exposed unless their read-only meaning and transport are confirmed.
- Energy totals remain `state_class: total`; reset and rollover semantics must
  be proven before they can safely become Energy Dashboard
  `total_increasing` sources.
- Bluetooth advertisements can temporarily disappear; the integration cannot
  connect until Home Assistant sees the eManager again.
- Alpha releases can change entity availability and configuration behavior.
- No write or control functionality is included.

## Bluetooth Proxy recovery

The eManager advertisement can be very weak and strongly dependent on proxy
placement. The validated installation received it around `-80` to `-84 dBm`;
earlier positions were around `-89 dBm` or weaker and discovery failed.

If the eManager is missing, first confirm that the ESPHome proxy is online and
actively scanning, then use Home Assistant's Bluetooth advertisement monitor
and filter on `eManager`. Move the proxy until a connectable advertisement is
visible before reloading this integration. An eManager reboot is not a normal
recovery step and should not be proposed by default.

## Branding

The bundled `SAJ HS3` project icon is an original, unofficial integration
graphic. It is not an official SAJ logo and does not imply endorsement by SAJ.
SAJ, Elekeeper and related product names belong to their respective owner.

## Development checks

```bash
python -m pytest
ruff check .
ruff format --check .
mypy custom_components/saj_hs3
```

GitHub Actions additionally run HACS validation and hassfest. Private research,
captures, credentials, device identifiers and unpublished register material are
not part of this public repository.
