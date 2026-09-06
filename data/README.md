# data/

Measured and reference data for model validation.

## Organization

Each subdirectory groups data by **provenance** (who collected it) and
**test scope** (what was measured under what conditions). A directory
holds one or more CSV files, each corresponding to a single table or
test run from the source. The directory README documents the source
publication, test conditions, column definitions, and extraction
validation.

Device parameter files (TOML model inputs) live in `devices/`, not here.

## Directories

- `ornl_prius_2004_dyno/` — ORNL/TM-2006/423, full-envelope
  dynamometer performance mapping of the 2004 Prius motor and inverter
  (297-6005 rpm, 19-375 Nm, ~500 Vdc)
- `ornl_prius_2004_motor_thermal/` — ORNL/TM-2005/33, motor thermal
  management report, 900 rpm line-fed motor tests at four coolant
  temperatures (35-105 degC)
- `ornl_prius_2004_drivetrain/` — ORNL/TM-2004/247, drivetrain loss
  decomposition and back-EMF vs speed; mechanical losses at 6 oil
  temperatures (28-80 degC, 502-6006 rpm)
- `ornl_hev_benchmarking/` — ORNL/TM-2010/253 and ORNL/SPR-2014/532,
  cross-vehicle design comparison (2004 Prius, 2010 Prius, Camry,
  LS 600h, 2012 LEAF, 2014 Accord motor and generator): die packaging,
  inverter/PCU specs, thermal path lengths, motor lamination and
  winding geometry, magnet hysteresis
- `ornl_leaf_2012_motor/` — DOE AMR APE006 and ORNL/TM-2013/498,
  2012 Nissan LEAF traction motor ratings, geometry, efficiency floors,
  and continuous capability
- `ornl_prius_2010_thermal_duty/` — ORNL/TM-2010/253 §3.4-3.5,
  continuous load duration of the 2010 Prius motor (25-60 kW,
  3000-7000 rpm, 25-65 degC coolant) and stator steady-state points

## License

All data in this directory is transcribed from U.S. Department of Energy
publications and is in the public domain. Source citations are in each
subdirectory README.
