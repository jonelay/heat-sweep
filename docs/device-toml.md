# Device TOML schema

A Device TOML file describes one semiconductor device (MOSFET or IGBT) with
its conduction, switching, body-diode, and thermal parameters. Every curve
table carries test conditions; the loader rejects files that violate the
invariants below.

## Sections

### `[device]`

| Field          | Type   | Unit  | Description              |
|----------------|--------|-------|--------------------------|
| `name`         | string |       | Device part number       |
| `type`         | string |       | `"mosfet"` or `"igbt"`   |
| `package`      | string |       | Package type             |
| `manufacturer` | string |       | Manufacturer name        |
| `V_max`        | float  | V     | Maximum rated voltage    |
| `I_max`        | float  | A     | Maximum rated current    |
| `Tj_max`       | float  | degC  | Maximum junction temp    |

### `[conduction]`

**MOSFET**: `Tj` and `R_ds_on` arrays (R_ds_on vs junction temperature).

**IGBT**: `V_ce0` (threshold voltage, V) and `r_ce` (slope resistance, Ohm).

Both require a `[conduction.conditions]` sub-table with the test conditions
(e.g. `V_gs`, `I_d` for MOSFET; `I_c` for IGBT).

### `[body_diode]`

| Field | Type  | Unit | Description                |
|-------|-------|------|----------------------------|
| `V_f` | float | V    | Forward voltage            |
| `Q_rr`| float | C    | Reverse recovery charge    |

Requires `[body_diode.conditions]` sub-table.

### `[switching]`

| Field   | Type       | Unit | Description                     |
|---------|------------|------|---------------------------------|
| `I`     | float[]    | A    | Current values (x axis)         |
| `E_on`  | float[]    | J    | Turn-on energy at each I        |
| `E_off` | float[]    | J    | Turn-off energy at each I       |
| `scaling`| string    |      | Scaling rule name (`"linear"`)  |

Requires `[switching.conditions]` with at least `V_dc`, `R_g`, `Tj`.

### `[thermal]`

| Field          | Type  | Unit | Description                     |
|----------------|-------|------|---------------------------------|
| `Rth_jc`       | float | K/W  | Junction-to-case resistance     |

Optional `[[thermal.Zth_jc_foster]]` array of `{R, tau}` pairs for transient
thermal impedance (Foster model).

## Validation rules

The loader (`load_device_toml`) rejects files that violate:

1. **Table size**: all `x`/`y` arrays must have >= 2 entries
2. **Monotonicity**: `x` values must be strictly increasing
3. **Finite values**: all numeric entries must be finite (no inf, nan)
4. **Conditions**: every table must have a non-empty `conditions` block
5. **Tj_max consistency**: `Tj_max` must be >= the maximum Tj in any table
6. **Foster sum**: `sum(R_i)` must match `Rth_jc` within 5%

## Example

```toml
[device]
name = "IPW60R045CP"
type = "mosfet"
package = "TO-247"
manufacturer = "Infineon"
V_max = 600.0
I_max = 60.0
Tj_max = 150.0

[conduction]
Tj = [25.0, 100.0, 150.0]
R_ds_on = [0.045, 0.072, 0.099]
[conduction.conditions]
V_gs = 10.0
I_d = 31.0

[body_diode]
V_f = 0.9
Q_rr = 3.9e-6
[body_diode.conditions]
Tj = 25.0

[switching]
I = [5.0, 10.0, 20.0, 40.0, 60.0]
E_on = [27e-6, 70e-6, 190e-6, 500e-6, 870e-6]
E_off = [7e-6, 20e-6, 59e-6, 170e-6, 310e-6]
scaling = "linear"
[switching.conditions]
V_dc = 400.0
R_g = 6.8
Tj = 25.0

[thermal]
Rth_jc = 0.31
[[thermal.Zth_jc_foster]]
R = 0.05
tau = 0.0005
[[thermal.Zth_jc_foster]]
R = 0.10
tau = 0.005
[[thermal.Zth_jc_foster]]
R = 0.16
tau = 0.08
```
