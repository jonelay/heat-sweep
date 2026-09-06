# ORNL 2012 Nissan LEAF — Motor Parameters and Performance

LEAF traction motor data that does not fit the cross-vehicle design
table in `../ornl_hev_benchmarking/motor_design.csv`.

## Sources

**There is no ORNL benchmarking report for the LEAF equivalent to
ORNL/TM-2010/253 for the Prius.** The LEAF evaluation was published
across a conference presentation and two annual progress reports, so
the provenance here is weaker than for the Toyota vehicles. Treat these
values as presentation-grade unless stated otherwise.

> T. A. Burress, "Benchmarking State-of-the-Art Technologies,"
> DOE Vehicle Technologies Program Annual Merit Review, project APE006,
> Oak Ridge National Laboratory, May 2013.

Cited as `APE006`. A slide deck: values appear as bullets, not numbered
tables, and no uncertainty is stated.

> "Electrical and Electronics Systems Research Division FY 2013 Annual
> Progress Report," ORNL/TM-2013/498, Oak Ridge National Laboratory.

Cited as `TM-2013/498 T1` for the Table 1 benchmark summary.
Available from OSTI.gov.

> "Electrical and Electronics Systems Research Division FY 2014 Annual
> Progress Report," ORNL/SPR-2014/532, Oak Ridge National Laboratory.

Available from OSTI.gov. Its Table 1 is the
source of the LEAF and Accord columns in
`../ornl_hev_benchmarking/motor_design.csv`.

U.S. Department of Energy publications. Public domain.

## Files

### motor_parameters.csv

Design and rating parameters. Long format: `parameter`, `unit`, `value`,
`source`, `basis`. Values that also appear in SPR-2014/532 Table 1 are
noted in `basis` where the two disagree on rounding.

### performance.csv

Efficiency and continuous capability. Test conditions are carried on
each row (`dc_link_V`, `coolant_C`, speed range) because the efficiency
figures are only meaningful with them.

| Column | Description |
|--------|-------------|
| `quantity` | What was measured |
| `value`, `unit` | The value as published |
| `speed_rpm_low`, `speed_rpm_high` | Speed range the value applies over, blank if unstated |
| `dc_link_V`, `coolant_C` | Test conditions, blank if unstated |
| `source` | Publication |
| `evidence` | `measured` for ORNL dynamometer results; `published by Nissan` for the manufacturer duty points |

## Notes

- **Efficiency values are floors, not points.** ORNL states them as
  "above 97%", "above 99%", "above 96%". The CSV carries the bound; do
  not read them as peak values.
- **The four `published_duty_*` rows are Nissan's, not ORNL's.** They
  come from the Nissan LEAF special edition of *SAE Vehicle
  Electrification* (Feb 2011, p. 17), reproduced on an APE006 slide.
  They are the manufacturer's published duty curve, not a measurement.
  The one ORNL continuous measurement is the 80 kW / 7,000 rpm row.
- **No efficiency map data exists in tabular form.** APE006 shows motor,
  inverter, and combined efficiency contours as plots only — the same
  limitation as the 2010 Prius.
- **No LEAF air gap is published** in either Table 1 or APE006. Stator
  ID and rotor OD are given to 2-3 significant figures (13.10 and
  13.0 cm), which is not enough resolution to derive it. Left blank
  rather than computed.
- **TM-2013/498 Table 1 labels the column "2011 LEAF"** where its body
  text and every other source say 2012. Treated as the 2012 vehicle.
- The LEAF motor is designed for continuous EV duty, which is why its
  specific power is low relative to the hybrids in the comparison.
  ORNL flags this explicitly: the SP/PD columns across vehicles are not
  apples-to-apples.
- Cooling is three water-ethylene-glycol loops in the stator housing,
  versus the Prius oil-plus-single-loop arrangement.

## Not extracted

The LEAF power electronics module thermal stack is documented in APE006
(0.361 mm IGBT, 0.180 mm solder, 2.55 mm Cu-Mo spacer, 0.208 mm solder,
3.17 mm Cu base plate, non-isolated with a silicone insulator and two
grease layers; 15x15 mm IGBT and 14x14 mm diode dies; 3 IGBTs and 3
diodes per switch, separate module per phase). That is inverter data
rather than motor data and belongs with a `thermal_stack.toml` under
`devices/`, not here. Note that APE006 writes "Co-Mo spacer" in one
bullet and "Cu-Mo heat spreader" in the adjacent figure label; Cu-Mo
(copper-molybdenum) is the CTE-matching material.
