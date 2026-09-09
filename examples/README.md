# Live Energy Topology example mapping

[`live_energy_topology.yaml`](live_energy_topology.yaml) is an exported,
privacy-safe copy of the approved responsive `Live energietopologie` card. Its
desktop/laptop, phone/mobile and iPad/tablet-landscape geometry is preserved.
The file also retains CSS Motion Path animation and the Safari 15/iPadOS 15 SVG
SMIL fallback.

The example is a `custom:button-card` configuration. Install
[`button-card`](https://github.com/custom-cards/button-card), copy the YAML into
your dashboard and replace every `sensor.example_*` placeholder. Do not expect
the complete dashboard to work from `saj_hs3` alone: the developer installation
combines SAJ data with a P1 meter, an external battery, vehicle SOC and custom
accounting/template entities.

Home Assistant entity IDs are language- and installation-dependent and can be
renamed. Match by the stable `saj_hs3` entity key shown below rather than copying
an entity ID blindly.

## Live topology inputs

| Dashboard function | Placeholder | Required source / meaning | Directly from `saj_hs3`? |
|---|---|---|---|
| P1 active power | `sensor.example_p1_active_power` | Contract-boundary meter; template expects the installation's existing sign convention | No |
| P1 import total | `sensor.example_p1_energy_import_total` | Cumulative P1 import | No |
| P1 export total | `sensor.example_p1_energy_export_total` | Cumulative P1 export | No |
| SAJ grid power | `sensor.example_saj_grid_power` | Entity key `grid_power`, non-negative W magnitude | Yes |
| SAJ grid direction | `sensor.example_saj_grid_direction_code` | Entity key `grid_direction_code`; `-1` import, `+1` export on the validated HS3 | Yes |
| SAJ battery power | `sensor.example_saj_battery_power` | Entity key `battery_power`, non-negative W magnitude | Yes |
| SAJ battery direction | `sensor.example_saj_battery_direction_code` | Entity key `battery_direction_code`; `-1` charge, `+1` discharge | Yes |
| SAJ battery SOC | `sensor.example_saj_battery_soc` | Entity key `battery_soc` | Yes |
| SAJ battery charge total | `sensor.example_saj_battery_charge_energy_total` | Entity key `battery_charge_energy_total` | Yes |
| SAJ battery discharge total | `sensor.example_saj_battery_discharge_energy_total` | Entity key `battery_discharge_energy_total` | Yes |
| SAJ PV power | `sensor.example_saj_pv_power` | Entity key `pv_power` | Yes |
| SAJ PV total | `sensor.example_saj_pv_energy_total` | Entity key `pv_energy_total` | Yes |
| SAJ load power | `sensor.example_saj_load_power` | Entity key `load_power`; broad SAJ load which can include integrated EV charging | Yes |
| SAJ load total | `sensor.example_saj_load_energy_total` | Entity key `load_energy_total`; broad cumulative SAJ load | Yes |
| EV charging power | `sensor.example_saj_ev_charger_power` | Entity key `ev_charger_power`, optional CHARGERINFO entity | Yes, optional |
| EV charging total | `sensor.example_saj_ev_charger_total_energy` | Entity key `ev_charger_total_energy`, optional CHARGERINFO entity | Yes, optional |
| Vehicle battery SOC | `sensor.example_ev_battery_level` | Vehicle/telematics integration SOC | No |
| Derived house power | `sensor.example_house_power` | User template/accounting sensor; do not equate automatically with SAJ EMS ID 45 | No |
| External battery power | `sensor.example_external_battery_power` | Dedicated meter for the example installation's second battery | No |
| External battery SOC | `sensor.example_external_battery_soc` | External battery integration/template | No |
| External battery charge total | `sensor.example_external_battery_charge_energy_total` | Dedicated cumulative charge/import counter | No |
| External battery discharge total | `sensor.example_external_battery_discharge_energy_total` | Dedicated cumulative discharge/export counter | No |

## Daily energy and accounting inputs

These placeholders feed the summary tiles rendered below the topology. Create
them with your own validated utility meters/templates, or remove the summary
section and the corresponding `triggers_update` entries.

| Placeholder | Meaning | Directly from `saj_hs3`? |
|---|---|---|
| `sensor.example_grid_import_energy_today` | P1/grid import today | No |
| `sensor.example_grid_import_cost_today` | Grid-import cost today | No |
| `sensor.example_grid_import_cost_total` | Cumulative grid-import cost | No |
| `sensor.example_grid_export_energy_today` | P1/grid export today | No |
| `sensor.example_grid_export_revenue_today` | Grid-export revenue today | No |
| `sensor.example_grid_export_revenue_total` | Cumulative grid-export revenue | No |
| `sensor.example_house_energy_today` | House/load energy today | No, derived |
| `sensor.example_house_cost_today` | House/load cost today | No, derived |
| `sensor.example_accounted_house_energy_today` | Validated accounted house energy today | No, derived |
| `sensor.example_accounted_house_cost_today` | Validated accounted house cost today | No, derived |
| `sensor.example_accounted_ev_energy_today` | Accounted EV energy today | No, derived |
| `sensor.example_accounted_ev_cost_today` | Accounted EV cost today | No, derived |
| `sensor.example_saj_grid_import_energy_today` | Daily delta from SAJ grid import total | No, derive from `grid_import_energy_total` |
| `sensor.example_saj_grid_export_energy_today` | Daily delta from SAJ grid export total | No, derive from `grid_export_energy_total` |
| `sensor.example_saj_battery_charge_energy_today` | Daily delta from SAJ battery charge total | No, derive from `battery_charge_energy_total` |
| `sensor.example_saj_pv_energy_today` | Daily delta from SAJ PV total | No, derive from `pv_energy_total` |
| `sensor.example_external_battery_charge_energy_today` | External battery charge today | No |
| `sensor.example_external_battery_discharge_energy_today` | External battery discharge today | No |
| `sensor.example_external_battery_result_today` | External battery financial/result metric | No |

## Adaptation rules

- Replace placeholders only; the shipped geometry is the visual baseline.
- Keep the direction-code logic together with each non-negative SAJ magnitude.
- Keep the modern Motion Path and SMIL fallback paths identical.
- The example uses green `#0ff804` for source/discharge/export, red `#ff032d`
  for import/charge/consumption and `#6a6465` for idle.
- Validate your own meter signs, energy boundaries and firmware before using the
  dashboard for accounting or control decisions.
