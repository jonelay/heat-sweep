# ORNL 2004 Prius Dynamometer Performance Mapping

Measured motor and inverter performance data from ORNL dynamometer
testing of the 2004 Toyota Prius (NHW20) hybrid electric drive system.
Motor directly coupled to dynamometer (speed-reduction gears removed).

## Source

> R. H. Staunton, C. W. Ayers, L. D. Marlino, J. N. Chiasson, and
> T. A. Burress, "Evaluation of 2004 Toyota Prius Hybrid Electric Drive
> System," ORNL/TM-2006/423, Oak Ridge National Laboratory, May 2006.

U.S. Department of Energy publication, contract DE-AC05-00OR22725.
Public domain.

Available from OSTI.gov.

## Test conditions

- DC link voltage: ~496-505 V (boost converter output)
- Modulation: sine-triangle PWM / SVPWM (best performance used)
- Coolant temperature: primarily 55 degC; reduced to ~0 degC for
  low-speed high-torque points to permit extended data collection
- Coolant flow rate: ~7-10 L/min
- Each operating point held steady state >= 20 s, 5-10 samples averaged
- Speed range: 297-6005 rpm
- Torque range: 19.0-374.8 Nm

**Switching frequency is not recorded in Table B-1.** TM-2006/423 does
not state one, and neither does any other ORNL report in this repo.
Toyota's own HV ECU data list gives MG2 two carrier modes, 1.25 kHz and
5 kHz, so the 5 kHz that `tests/test_anchor_ornl_inverter.py` uses is
one of the two real modes rather than a free assumption — but which mode
each of the 428 points ran in is unlabelled, and the low-carrier mode is
most plausible in the low-speed high-torque region. See
ORNL/TM-2006/423 §4. Sweeping the anchor over
1.25-15 kHz leaves the rms residual at 110-111 W throughout, so the
choice sets the level of predicted loss but not the structure of the
disagreement.

## Files

### performance_map.csv

Table B-1, Appendix B (pp. 70-85). 428 operating points, sorted by
increasing speed then increasing torque.

| Column | Unit | Description |
|--------|------|-------------|
| `speed_rpm` | rpm | Motor shaft speed |
| `torque_Nm` | Nm | Shaft torque (Himmelstein torque cell) |
| `p_dc_W` | W | DC power input to inverter (Yokogawa PZ4000) |
| `p_mech_W` | W | Mechanical shaft power |
| `p_ac_W` | W | Three-phase AC power output from inverter |
| `eta_inverter` | — | Inverter efficiency (P_ac / P_dc) |
| `eta_motor` | — | Motor efficiency (P_mech / P_ac) |
| `eta_total` | — | Combined efficiency (P_mech / P_dc) |
| `v_dc_V` | V rms | DC bus voltage at inverter input |
| `i_dc_A` | A rms | DC bus current at inverter input |
| `v_ac_V` | V rms | Phase (line-to-neutral) voltage, averaged over phases |
| `i_ac_A` | A rms | Phase (line) current, averaged over phases |
| `t_stator_C` | degC | Stator winding temperature (highest of three TCs) |

The DC and AC power columns are true power measurements. V_rms × I_rms
does not equal P for AC (power factor) and may differ for DC at low
speeds where bus ripple is significant. The power columns are the
authoritative loss data; V and I are supplementary.

`v_ac_V` is inferred to be line-to-neutral (phase) RMS, not
line-to-line: `pf = P_ac / (3 * V * I)` stays <= 1 at all 428 points
while the line-to-line formula gives pf > 1 at 193 points. However,
`v_ac_V` is total RMS including PWM switching harmonics, not
fundamental-only: computing `m = V * sqrt(2) / (V_dc/2)` yields
m > 4/pi (six-step ceiling) at 198 points, which is unphysical for
the fundamental. Therefore `v_ac_V` should not be used to derive
modulation index or displacement power factor. The product
m*cos(phi) can instead be derived from `P_ac`, `V_dc`, and `I`:
`m*cos(phi) = P_ac * 2*sqrt(2) / (3 * V_dc * I)`.

`p_dc_W` is a true power channel, not the product of `v_dc_V` and
`i_dc_A` (median relative difference 4.4%).

The stator temperature column reflects the hottest of three embedded TCs
and is strongly dependent on prior operating history. It should not be
interpreted as a steady-state thermal measurement.

## The intermittent-duty rows are not usable as loss data

The report states that low-speed, high-torque points required dropping
the coolant to 0 degC, but Table B-1 does not flag which rows those
were. They are identifiable as **torque >= 300 Nm** — 35 rows, all
between 468 and 1307 rpm, since the torque envelope means no point
above 1400 rpm reaches 300 Nm.

Two independent properties mark them:

- Measured inverter efficiency steps up 1-3 points above the trend of
  its own speed band (337 Nm at 500 rpm, 308 at 700, 307 at 900).
- Measured loss `p_dc_W - p_ac_W` *falls* as current rises. At 700 rpm,
  147 A gives 1282 W and 159 A gives 489 W. At 900 rpm, 149 A gives
  1756 W and 153 A gives 1016 W.

No loss mechanism decreases with current at fixed speed and bus
voltage, and 0 degC coolant would move loss by roughly 10%, not 60%.
So the cold coolant identifies the region but does not explain the
step; these rows most likely also carry the CT noise/EMI error that
Section 3.3.2 documents ORNL investigating. Treat `p_dc_W`, `p_ac_W`,
and `eta_inverter` on these rows as unreliable. The speed, torque,
current, and voltage columns are unaffected.

Applied in `tests/test_anchor_ornl_inverter.py::is_intermittent_duty`,
with the evidence pinned in `TestIntermittentDutySubset`. Excluding
them takes the anchor from 92.1% to 96.9% underpredicting overall, and
to 100% below 2000 rpm.

## Extraction method

Transcribed from the PDF table and verified against the original page
images. Validation checks:
- eta_total = eta_inverter * eta_motor (all 428 rows, max error < 0.001)
- P_mech vs torque * omega (all 428 rows, max error < 0.5%)
- P_dc > P_ac > P_mech (zero energy conservation violations)
- First, last, and sampled interior rows verified against PDF pages
- Speed range and inverter efficiency band match report text
  (Section 3.3.3: "98-99% efficiencies above ~1800 rpm")
