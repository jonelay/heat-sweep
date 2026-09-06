# ORNL 2004 Prius Motor Thermal Management

Measured motor performance and thermal data from ORNL testing of the
2004 Toyota Prius (NHW20) traction motor at 900 rpm, line-fed (60 Hz,
no inverter), at four coolant inlet temperatures.

## Source

> J. S. Hsu, S. C. Nelson, P. A. Jallouk, C. W. Ayers, R. H. Wiles,
> S. L. Campbell, C. L. Coomer, K. T. Lowe, and T. A. Burress,
> "Report on Toyota Prius Motor Thermal Management,"
> ORNL/TM-2005/33, Oak Ridge National Laboratory, February 2005.

U.S. Department of Energy publication, contract DE-AC05-00OR22725.
Public domain.

Available from OSTI.gov.

## Test conditions

- Speed: 900 rpm (fixed), line-fed at 60 Hz via variac + transformer
- Coolant: water-ethylene glycol, 2.4 gpm, inlet temps 35/50/75/105 degC
- Winding temperature limit: 170 degC
- Oil temperature limit: 158 degC
- No inverter — motor connected directly to 60 Hz mains through
  synchronizing switch, isolating switching losses entirely

## Files

### torque_sweep_35C.csv / torque_sweep_50C.csv / torque_sweep_75C.csv

Tables 4, 5, 6 (pp. 14-15). Motor voltage, torque, power, efficiency,
current, power factor, and winding/oil temperatures at increasing shaft
load. 18/18/15 rows respectively (fewer at higher coolant temps because
the winding limit is reached sooner).

| Column | Unit | Description |
|--------|------|-------------|
| `v_ll_V` | V | Supply line-line voltage (variac setting) |
| `torque_Nm` | Nm | Shaft torque |
| `speed_rpm` | rpm | Shaft speed (constant 900) |
| `p_mech_W` | W | Mechanical shaft power |
| `p_elec_W` | W | Electrical input power |
| `efficiency` | — | P_mech / P_elec |
| `i_a_A` | A | Line current |
| `pf` | — | Power factor |
| `t_winding_C` | degC | Stator winding temperature |
| `t_oil_C` | degC | Lubricating oil temperature |

The 50 degC table contains a duplicate row at 100 Nm, preserved as-is
from the original report (Table 5, p. 14).

### continuous_rating.csv

Table 7 (p. 15). Steady-state continuous rating at each coolant
temperature — the operating point where winding temperature stabilizes
near the 170 degC limit.

Same columns as torque sweep files plus `t_coolant_inlet_C` and
`test_duration_min`.

### loss_breakdown.csv

Table 10 (p. 16). Loss decomposition at the continuous rating point for
each coolant temperature.

| Column | Unit | Description |
|--------|------|-------------|
| `t_coolant_C` | degC | Coolant inlet temperature |
| `v_ll_V` | V | Supply voltage |
| `torque_Nm` | Nm | Shaft torque at continuous rating |
| `p_mech_W` | W | Mechanical power |
| `p_elec_W` | W | Electrical input power |
| `p_loss_total_W` | W | Total loss (P_elec - P_mech) |
| `p_loss_mech_W` | W | Mechanical (friction + windage) loss |
| `p_loss_i2r_W` | W | Stator copper I²R loss |
| `p_loss_core_W` | W | Core (iron) loss |
| `efficiency` | — | P_mech / P_elec |
| `i_a_A` | A | Line current |
| `pf` | — | Power factor |

Loss split: mechanical loss is roughly constant (~160 W), while I²R and
core losses scale with current. Total loss = mech + I²R + core (no
residual — rotor losses are negligible at these conditions).

### thermal_conductivity.csv

Table 15 (p. 30). Material thermal conductivity values used in the ORNL
HEATING 7.3 finite-difference thermal model.

The stator/rotor axial conductivity is 1/10 of radial, reflecting
lamination contact resistance. The stator-rotor gap uses a high
effective conductivity to approximate Couette oil flow.

### winding_temp_validation.csv

Tables 17 and 18 (pp. 32, 35). Measured winding thermocouple
temperatures vs HEATING 7.3 model predictions at each coolant
temperature. Three TCs (W1 upper-left, W2 upper-right, W3 lower-right
of stator, viewed from motor end cap with terminals at upper right).

| Column | Unit | Description |
|--------|------|-------------|
| `t_coolant_C` | degC | Coolant inlet temperature |
| `thermocouple` | — | TC label (W1, W2, W3) |
| `t_measured_C` | degC | Measured winding temperature |
| `t_predicted_min_C` | degC | Model-predicted minimum bundle temperature |
| `t_predicted_max_C` | degC | Model-predicted maximum bundle temperature |

W1 and W3 agree well with predictions. W2 is consistently ~10 degC
above predictions — the report attributes this to oil flow distribution
differences at the radially inner part of the stator copper bundle.

## Extraction method

Transcribed from the PDF tables and verified against the original page
images (pp. 14-16, 30, 32, 35). The markdown conversion was cross-checked
against the PDF for all tables.
