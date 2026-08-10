# SAJ HS3 / Elekeeper for Home Assistant

> **Alpha / experimental.** This repository currently provides an installable,
> read-only integration shell. It does not yet communicate with SAJ equipment
> or the Elekeeper Open Platform and therefore creates no sensors.

`ha-saj-hs3` targets SAJ HS3 installations connected through an
eManager. It prepares two strictly separated future data sources:

- **Local eManager** via the still-to-be-confirmed read-only eManager/BSaj
  transport;
- **Elekeeper Open Platform** via official App ID/App Secret token
  authentication.

The integration does not use an Elekeeper username/password. It does not use
ordinary Modbus TCP as the HS3 local client and contains no write or control
functionality.

## Current capabilities

- installation as a HACS custom repository;
- configuration through the Home Assistant UI;
- selection of Local eManager and/or Elekeeper Open Platform;
- secure password-style input for an Open Platform App Secret;
- privacy-safe diagnostics containing only integration status;
- an inactive entity-description model without source IDs or register mappings.

No credential test, cloud request, BSaj request, Modbus request, entity or
device is active in this alpha.

## Installation through HACS

This public repository can be added to HACS as a custom integration repository.

1. Open HACS.
2. Open **Custom repositories**.
3. Add `https://github.com/harkoijkema/ha-saj-hs3`.
4. Select repository type **Integration**.
5. Download **SAJ HS3 / Elekeeper**.
6. Restart Home Assistant.
7. Go to **Settings → Devices & services → Add integration**.
8. Select **SAJ HS3 / Elekeeper**.

The domain changed from the earlier, non-configurable skeleton
`saj_elekeeper` to `saj_hs3`. Remove a manually copied old skeleton directory
before installing this alpha.

## Configuration

The first screen describes both future sources. A Local eManager-only entry is
allowed as an explicit placeholder and requests no unconfirmed host, port or
unit ID. Open Platform configuration stores only the approved App ID and App
Secret credential types in the Home Assistant config entry. Connectivity is
not tested yet and this is stated in the UI.

## Known limitations

- No actual SAJ communication is implemented.
- No sensors or Home Assistant devices are created.
- The local read-only BSaj request/session transport is not yet sufficiently
  confirmed.
- The production Open Platform client is not yet connected to the integration.
- No device control or write operation is planned for this read-only phase.

Technical research, captures, credentials and source/register mappings remain
in a separate private research repository and must never be committed here.

## Development checks

```bash
python -m pytest
ruff check .
ruff format --check .
mypy custom_components/saj_hs3
```

GitHub workflows additionally run HACS validation and hassfest. No GitHub
release is created by this project setup.
