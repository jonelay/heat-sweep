# ORNL HEV Benchmarking — Design Comparison

Cross-vehicle design and packaging comparison data from ORNL
benchmarking of Toyota hybrid electric drive systems.

## Source

> T. A. Burress, S. L. Campbell, C. L. Coomer, C. W. Ayers,
> A. A. Wereszczak, J. P. Cunningham, L. D. Marlino, L. E. Seiber,
> and H. T. Lin, "Evaluation of the 2010 Toyota Prius Hybrid Synergy
> Drive System," ORNL/TM-2010/253, Oak Ridge National Laboratory,
> March 2011.

U.S. Department of Energy publication, contract DE-AC05-00OR22725.
Public domain.

Available from OSTI.gov.

## Files

### design_comparison.csv

Tables 2.1 and 4.1 (pp. 5, 58). Key design parameters across four
Toyota HEVs: 2010 Prius, 2008 Lexus LS 600h, 2007 Camry Hybrid, and
2004 Prius. Motor, PCU, inverter, and boost converter specs.

### die_packaging.csv

Table 2.5 (p. 23). IGBT and diode die count, bond count, individual
die area, and total silicon area for motor inverter and boost converter
across the four vehicles.

| Column | Unit | Description |
|--------|------|-------------|
| `vehicle` | — | Vehicle model |
| `subsystem` | — | motor_inverter or boost_converter |
| `component` | — | IGBT or diode |
| `n_devices` | — | Number of dies |
| `bond_count_per_device` | — | Wire/ribbon bonds per die (blank if not reported) |
| `a_die_mm2` | mm² | Silicon area per die |
| `a_total_mm2` | mm² | Total silicon area (n × a_die) |

### motor_design.csv

Traction motor lamination geometry, assembly masses, stator winding,
casing, and magnet dimensions across seven machines. Long format: one
row per parameter, one column per machine.

**Two publications back this file.** ORNL/TM-2010/253 Table 2.7 (p. 46)
covers the four Toyota/Lexus machines. ORNL/SPR-2014/532 Table 1 (p. 21)
reprints those four columns and adds the 2012 Nissan LEAF, the 2014
Accord generator (`accord_g`), and the 2014 Accord motor (`accord_m`),
plus a magnet-mass-per-kW row. All 20 rows the two tables share are
identical, verified value by value — so this is one table extended, not
two tables merged, and neither publication owns a fact the other
contradicts.

> "Electrical and Electronics Systems Research Division FY 2014 Annual
> Progress Report," ORNL/SPR-2014/532, Oak Ridge National Laboratory.

Available from OSTI.gov.

| Column | Unit | Description |
|--------|------|-------------|
| `parameter` | — | Parameter name |
| `unit` | — | Unit, or `-` for dimensionless counts |
| `2010_prius`, `ls_600h`, `camry`, `2004_prius`, `leaf_2012`, `accord_g`, `accord_m` | varies | Value per machine; blank where the source leaves the cell empty |
| `source` | — | `both`, `TM-2010/253 T2.7`, or `SPR-2014/532 T1` |
| `comments` | — | ORNL's own comment, plus notes on approximate or non-numeric cells |

### magnet_hysteresis.csv

§2.3.3 (p. 49). Remanent flux density and intrinsic coercivity of the
2010 Prius motor magnet, measured on a Walker Scientific AMH-40
hysteresisgraph.

| Column | Unit | Description |
|--------|------|-------------|
| `vehicle`, `component` | — | Which magnet |
| `temperature_C` | degC | Magnet temperature during the test |
| `br_kG`, `br_T` | kG, T | Remanent flux density, as published and in SI |
| `hci_kOe`, `hci_kAm` | kOe, kA/m | Intrinsic coercivity, as published and in SI |
| `source_figure` | — | Figure the value came from |
| `basis` | — | Provenance of the value |

## Notes

- The 2010 Prius uses trench-gate IGBTs with ribbon bonds (3 per device);
  the 2004 Prius uses planar-gate IGBTs with wire bonds (20 per device).
- The 2010 Prius thermal path is 3.8 mm (DBA brazed directly to cooling
  infrastructure, no baseplate); the 2004 Prius is 9.0 mm (DBA → solder →
  baseplate → thermal paste → cast heat sink).
- The LS 600h bond count is not reported (devices are similar to Camry
  boost converter dies).
- No tabulated efficiency data exists for the 2010 Prius — efficiency maps
  are published only as contour plots (Figs. 3.11-3.21).
- The 2010 Prius motor is 48-slot / 8-pole (4 pole pairs) with V-shaped
  NdFeB magnets, one magnet per pole along the axial length, 16 total.
  Core steel is M19. ORNL attributes the magnets to Hitachi Metals
  (Neomax) but does not confirm it.
- **`magnet_hysteresis.csv` carries only two temperature points.** The
  full Br and Hci versus temperature relationships (Figs. 2.70, 2.72,
  2.73) are plots with no tabulated values; only the 114 and 215 degC
  points appear as numbers in the text.
- **ORNL's own list of figures gives 121 degC for Fig. 2.68; the body
  text and the figure caption on p. 50 both say 114 degC.** 114 is used
  here. Verified against the PDF, not the markdown conversion.
- Coercivity in Table 2.7's source section is *intrinsic* coercivity
  (Hci) — ORNL reads it where the intrinsic curve crosses the H axis,
  not the normal curve. Do not use it as Hcb.
- Continuous load duration and stator thermal data from the same report
  live in `../ornl_prius_2010_thermal_duty/`. LEAF parameters that
  Table 1 does not carry live in `../ornl_leaf_2012_motor/`.
- **SPR-2014/532 Table 1 is a raster image on p. 21, not text.** No
  text extractor recovers it; it was transcribed by reading the
  embedded image. Re-verify visually rather than by grepping the PDF.
- **`magnet_dimensions_raw` is the authoritative magnet geometry row.**
  The split `magnet_length` / `magnet_width` / `magnet_thickness` rows
  are a convenience populated only for the four Toyota/Lexus machines,
  where ORNL states L x W x H consistently. They are blank for the LEAF
  and Accord: the LEAF has two different magnet segments per pole
  (21.3x8.34x2.29 and 28.9x8.36x3.79 mm) and the Accord entries put the
  stack-length-like dimension last rather than first, so splitting them
  on the same convention would misassign axes.
- Non-numeric source cells are left blank with a note in `comments`:
  Accord G stator core mass and copper mass are given as "Est", and
  Accord M turns per coil as "11?".
- ORNL warns that specific power and power density are not
  apples-to-apples across these machines, because the LEAF and Sonata
  have continuous capability near their published rated power while the
  hybrids do not.
