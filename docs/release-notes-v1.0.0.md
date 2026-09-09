# v1.0.0 — release notes draft

> Unpublished local draft. This document does not create a Git tag or GitHub
> release.

## First stable release

`v1.0.0` marks the first stable release of the read-only SAJ HS3/eManager Home
Assistant integration.

- Local eManager communication uses Bluetooth GATT/BSaj through Home Assistant
  Bluetooth or an ESPHome Bluetooth Proxy.
- The integration exposes 52 verified local sensors covering EMS totals and
  realtime values, battery and inverter values, PV strings, grid and backup
  three-phase measurements, diagnostics and optional integrated EV monitoring.
- Battery, grid and PV data remain strictly read-only. EV monitoring exposes
  raw charger status, current charging power and cumulative charger energy when
  the eManager supplies a valid `CHARGERINFO` response.
- Privacy-safe diagnostics and documented limitations are included.
- The repository now includes a privacy-safe Live Energy Topology screenshot,
  responsive dashboard example and entity-mapping guide.
- The integration intentionally provides no inverter, battery or EV control,
  and no generic write-command surface.

## Important limitations

- EMS, Modbus and optional EV reads are serial and are not an atomic physical
  snapshot.
- The SAJ load value is a broad load boundary and can include integrated EV
  charging; it is not a proven universal house-only measurement.
- Hardware, wiring and firmware variants can differ. Validate values on your
  own installation before using them for accounting, billing or control.
