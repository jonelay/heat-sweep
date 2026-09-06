# ORNL 2010 Prius — Continuous Load Duration

Thermal duty data from ORNL's continuous load tests on the 2010 Prius
PMSM: how long the motor sustains a power level before the stator
winding reaches a given temperature limit.

## Source

> T. A. Burress, S. L. Campbell, C. L. Coomer, C. W. Ayers,
> A. A. Wereszczak, J. P. Cunningham, L. D. Marlino, L. E. Seiber,
> and H. T. Lin, "Evaluation of the 2010 Toyota Prius Hybrid Synergy
> Drive System," ORNL/TM-2010/253, Oak Ridge National Laboratory,
> March 2011. §3.4-3.5, Figs. 3.22-3.30.

U.S. Department of Energy publication, contract DE-AC05-00OR22725.
Public domain.

Available from OSTI.gov.

## Test conditions

Continuous tests ran at 25 and 50 kW at 3,000, 5,000, and 7,000 rpm
with coolant regulated to 25, 50, and 65 degC by a Bay-Voltex unit.
Motor temperatures were allowed to stabilize before each test began.
Stator temperature is the most extreme of eight winding TCs; ORNL
identifies 'E' (1 o'clock, front) as hottest, with 'C', 'I', 'K', 'L'
next. The ECVT is oil-circulated with an ethylene-glycol coolant loop.

Per the 2010 Prius repair manual, stator temperature is generally kept
below 100 degC in service.

## Files

### continuous_duration.csv

Time to reach a stator temperature limit at a given operating point.

| Column | Unit | Description |
|--------|------|-------------|
| `vehicle` | — | Vehicle model |
| `power_kW` | kW | Mechanical power level held |
| `speed_rpm` | rpm | Motor shaft speed |
| `coolant_C` | degC | Regulated coolant inlet temperature (blank if not stated) |
| `stator_limit_C` | degC | Stator winding temperature limit |
| `duration_s` | s | Time to reach the limit |
| `source_figure` | — | Figure or section the value came from |
| `basis` | — | `stated as mm:ss` for exact values; `approximate` for values ORNL reports in prose as read off a plot |

### stator_steady_state.csv

Operating points where the stator stabilized below any limit, so no
duration applies. These bound the continuous rating from the other
side and are the most useful points for LPTN steady-state validation.

## Notes

- **Only `stated` rows are exact.** ORNL publishes the duration data as
  plots (Figs. 3.25-3.30); the `approximate` rows are values the report
  narrates from those plots, not tabulated data. Four rows are exact
  because ORNL prints mm:ss in the corner of Figs. 3.22-3.24.
- **The report contradicts itself at 25 kW / 5,000 rpm / 50 degC
  coolant.** §4 states the motor sustains that point for about 25
  minutes to a 150 degC limit, but Fig. 3.25 states the stator
  stabilizes near 123 degC at that point, which means a 150 degC limit
  is never reached. Both readings are recorded — the §4 value in
  `continuous_duration.csv`, the stabilization in
  `stator_steady_state.csv`. Do not average them or silently drop one;
  they cannot both be true. Fig. 3.28 gives 25 minutes for the same
  point at a **105 degC** limit, which is consistent with the
  stabilization and suggests the §4 sentence carries a typo in the
  limit.
- The 60 kW / 18 s row is the FCVT peak power rating convention, not a
  continuous test. ORNL fixes 18 s so that peak ratings across
  benchmarked systems stay comparable.
- Coolant fed the PCU first and the ECVT heat exchanger second, so
  motor coolant inlet is the inverter coolant outlet.
- PCU device temperature during the 25 kW / 3,000 rpm / 25 degC test
  settled near 60 degC (on-chip sensor 'AB'), but ORNL puts that
  measurement's accuracy at only 5-10 degC. Not tabulated here.
- High-torque efficiency-map points (§3.4, not in these files) were run
  at ~10 degC coolant to survive the dwell. The same intermittent-duty
  caveat that applies to the 2004 dyno set applies there.
