# 2004 Toyota Prius THS-II MG2 Motor Inverter IGBT - 50 kW traction drive

**MG2 only.** The 2004 Prius PCU holds three power stages on one cold
plate — the MG2 traction inverter (12 IGBTs, 2 parallel per switch
position), the MG1 generator inverter (6 IGBTs, 1 per position), and the
boost converter (larger 228 mm^2 die). This directory describes one MG2
die and nothing else. There is no equivalent for MG1: ORNL/TM-2010/253
Table 2.5 measures die geometry for motor inverters and boost converters
only, so no generator die area is published. See
ORNL/TM-2010/253 §3.

Custom Toyota/Denso bare-die 600V Si IGBT, planar gate, NPT.
2 parallel die per switch position, 6 positions (3-phase 2-level bridge).
No public datasheet exists. This TOML describes one die.

## Sources

All primary data from freely available US government reports:

| Report | Contents |
|--------|----------|
| ORNL/TM-2006/423 | Physical teardown: inverter packaging, die photos, thermal stack |
| ORNL/TM-2010/253 Sec 2.2 | Die measurements, SEM cross-sections, solder EDS, 2004 vs 2010 thermal comparison |

Comparable devices for parameter estimation:
- IR IRG4PC50U (Gen 4 NPT, 600V/55A, ~2000) - best technology match
- Mitsubishi CM100DU-12F (3rd gen F-series, 600V/100A, 2000) - best current-rating match

## Physical characteristics (ORNL measured)

| Parameter | Value | Source |
|-----------|-------|--------|
| IGBT die area | 131.9 mm^2 | TM-2010/253 Table 2.5 |
| Diode die area | 40.7 mm^2 | TM-2010/253 Table 2.5 |
| IGBT dimensions | ~12.7 x 10.4 mm | TM-2010/253 Fig 2.24 |
| Gate structure | Planar (not trench) | TM-2010/253 Sec 2.2.2 |
| Wire bonds/IGBT | 20 (emitter, Al wedge) | TM-2010/253 Table 2.5 |
| Wire bonds/diode | 5 | TM-2010/253 Table 2.5 |
| Substrate | DBA on AlN | TM-2010/253 SEM |
| Die solder | Sn-Al-Ag-N (96.4/1.25/1.2/1.14 wt%) | TM-2010/253 EDS Fig 2.29 |
| Total thermal path | 9.0 mm (junction to coolant) | TM-2010/253 Fig 2.28 |

## Declared assumptions

All electrical parameters estimated from comparable commercial devices.
No measured switching data or V-I curves exist for this custom silicon.

1. **V_max = 600V** - DC bus boosts to 500V max (ORNL measured); 600V device
   class with margin.
   **Tj_max = 175C** - typical for 2004-era automotive Si IGBTs. Infineon,
   Mitsubishi, and IR 600V automotive devices of this period specify 150-175C.
   175C chosen as upper bound; not directly measured on Prius die.

2. **I_max = 125A** - peak phase current 250A (ORNL locked-rotor test at
   400 Nm) / 2 parallel die per switch position.

3. **V_ce0 = 0.8V, r_ce = 0.008 ohm** - linearized conduction model giving
   V_ce_sat = 1.6V at 100A, matching CM100DU-12F at Tj=125C. Prius IGBT is
   planar gate like the CM100DU-12F.

4. **E_on / E_off** - estimated from IRG4PC50U switching energy scaled to
   Prius operating current at Tj=150C. IRG4PC50U is Gen 4 NPT (same era;
   IR supplied the Prius gate driver ICs).
   - IRG4PC50U Ets(54A, 480V, 150C) ~3.0 mJ → scaled linearly to 100A
     and 400V → ~4.2 mJ total per switching event
   - Eon/Eoff split: NPT planar IGBTs have Eoff >> Eon (~3-4x ratio)
     due to minority carrier tail current at turn-off
   - Cross-checked against CM100DU-12F timing-based estimates
   - TOML table values are formula-generated from linear scaling, not
     multi-point measurements

   **R_g = 5 ohm** - IRG4PC50U test condition. Actual Prius gate resistance
   unknown (IR gate driver ICs, custom driver board); 5 ohm is reasonable for
   an automotive gate driver but not measured on the Prius PCU.

5. **Rth_jc = 0.35 K/W** - CM100DU-12F module has 0.35 K/W per switch
   position at comparable die area (junction to case). Prius die is bare-chip
   on DBA, so Rth_jc here covers junction to DBA substrate surface only.
   Remaining thermal path (baseplate, TIM, heatsink) modeled separately.

6. **V_f = 1.8V** - CM100DU-12F Vec ~2.0V typ at 100A, Tj=25C. Prius diode
   die is smaller (40.7 mm^2) so V_f is slightly lower at lower current
   density. Conservative estimate.

7. **Q_rr = 2.0 uC** - CM100DU-12F measured 1.9 uC at Tj=25C, Vcc=300V,
   Ic=100A. Rounded to 2.0 uC. TOML conditions match the source measurement
   (25C/300V). Not rescaled to higher Tj or V_R - actual Q_rr at 125C/400V
   would be larger, so this is a mild underestimate.

## Limitations

Not a validated device characterization. No one has published double-pulse
test results for the actual Toyota custom silicon.

Rth_jc is junction to DBA surface only. The full thermal path to coolant
(baseplate, ZnO thermal paste, cast aluminum heat sink) is modeled
separately in the LPTN or FEA thermal model.

## License

Parameter values transcribed from the cited publications and estimated from
comparable devices. Covered by the project's Apache-2.0 license.
