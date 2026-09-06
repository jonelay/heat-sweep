# 2012 Nissan LEAF PEM IGBT — thermal stack only

Custom bare-die Si IGBT in the LEAF power electronics module (PEM).
Three IGBTs and three diodes per switch position, separate module per
phase. No public datasheet exists.

**This directory carries a thermal stack, not a device.** There is no
`leaf_2012_igbt.toml`: ORNL publishes only a die size and rough voltage
and current ratings, which is not enough to write conduction and
switching models without inventing them. The device catalogue therefore
does not list this entry — `load_device_catalogue` skips a directory
with no `<name>.toml`, by design. Add the device TOML when a defensible
electrical characterization exists.

## Sources

> T. A. Burress, "Benchmarking State-of-the-Art Technologies," DOE
> Vehicle Technologies Program Annual Merit Review, project APE006,
> Oak Ridge National Laboratory, May 2013. PEM analysis credited to
> Zhenxian Liang (ORNL).

Motor-side data from the same source is in
`data/ornl_leaf_2012_motor/`.

**Provenance is a slide deck**, not a benchmarking report. Values are
bullets with no stated uncertainty. This is a weaker evidence class than
the 2004 Prius stack, which rests on ORNL/TM-2010/253 SEM cross-sections.

## ORNL-measured

| Parameter | Value |
|-----------|-------|
| IGBT die | 15 x 15 mm, 0.361 mm thick |
| Diode die | 14 x 14 mm (not modeled) |
| IGBT rating | ~1000 V breakdown, 300 A (estimated by ORNL) |
| Die attach solder | 0.180 mm |
| Cu-Mo spacer | 2.55 mm |
| Spacer solder | 0.208 mm |
| Cu base plate | 3.17 mm, **not electrically isolated** |
| Below base plate | silicone insulator, thermal grease both sides |
| Devices per switch | 3 IGBTs + 3 diodes |

APE006 writes "Co-Mo spacer" in one bullet and "Cu-Mo heat spreader" in
the adjacent figure label. Cu-Mo (copper-molybdenum) is the CTE-matching
material; the stack uses that.

## Declared assumptions

1. **Insulator and grease thicknesses are estimated.** ORNL states the
   layers exist and never dimensions them: grease 0.05 mm each, silicone
   insulator 0.20 mm, k = 3.0 and 2.0 W/(m K). See §Sensitivity — this
   group dominates the conduction path and the estimate dominates the
   answer.
2. **Cu-Mo properties estimated** at k = 170 W/(m K), rho = 10000,
   cp = 280, a 15Cu-85Mo class material. Composition is not published.
3. **Spacer footprint 20 x 20 mm is estimated.** ORNL gives no spreader
   dimension.
4. **No `total_path_m`.** ORNL publishes no junction-to-coolant path
   length for the LEAF, unlike the Prius 9.0 mm. The field is omitted
   rather than invented, so this stack has no runtime path check.
5. **The cooled face is the chassis-side grease surface**, not a
   coolant channel. The chassis itself is not modeled because no
   dimension is published. `rth_j_coolant_K_W` for this stack is
   therefore junction-to-chassis-face, a shorter path than the Prius
   junction-to-coolant.
6. **h = 5000 W/(m^2 K), cell 40 x 40 mm, T = 65 degC** are inherited
   from the 2004 Prius stack so the two are comparable. Only the 65 degC
   is LEAF-specific (ORNL's test coolant temperature). The cell size is
   a modeling choice, not a measurement.

## FEM result

Elmer 26.2, one IGBT die, 100 W, h = 5000, cell 40 x 40 mm.

    size_max 4.0 mm /  1171 nodes  Rth = 0.3739 K/W
    size_max 2.0 mm /  3241 nodes  Rth = 0.3759 K/W  (default)
    size_max 1.0 mm / 14838 nodes  Rth = 0.3789 K/W
    size_max 0.7 mm / 34710 nodes  Rth = 0.3795 K/W

Converged ~0.380 K/W; the default mesh is 0.9% low. The 1-D analytic
bracket is [0.229, 1.625] K/W and contains it.

    h    = 3000 / 5000 / 8000 W/m^2K -> 0.460 / 0.376 / 0.328 K/W
    cell =   30 /   40 /   50 mm     -> 0.517 / 0.376 / 0.319 K/W

## Sensitivity — read this before comparing to the Prius

The LEAF comes out at 0.376 K/W against the 2004 Prius 0.381 K/W. **That
near-equality is not a result.** Two things drive it, and neither is a
property of the LEAF hardware:

**The convective film is a third of both totals and is identical by
construction.** 1/(h*A_plate) = 0.125 K/W for both, because both use the
same assumed h and the same assumed cell size. Compare conduction only:

| | LEAF | 2004 Prius |
|---|---|---|
| conduction sum | 0.1598 | 0.1085 K/W |
| film | 0.1250 | 0.1250 K/W |

**The LEAF's conduction penalty is entirely in the estimated layers.**
Its grease/insulator/grease group is 0.0833 K/W — over half its
conduction total — against 0.0040 K/W for the Prius DBA-on-AlN
insulator, which is measured. Varying the estimate over a plausible
range moves the answer more than any real design difference:

    insulator t=0.20 mm k=2.0 (as built)  0.376 K/W
    insulator t=0.10 mm k=2.0             0.344
    insulator t=0.30 mm k=2.0             0.408
    insulator t=0.20 mm k=1.0             0.439
    insulator t=0.20 mm k=4.0             0.344

So the honest statement is: **the LEAF's measured silicon-to-baseplate
path is 0.0764 K/W against the Prius's 0.0792 K/W** — those are the
parts both reports actually measured — and everything below the base
plate is an open question for the LEAF.

Nissan's non-isolated base plate with a separate insulator is a real
architectural difference from Toyota's isolated DBA substrate, and it
should show up as extra thermal resistance. This model says it does.
It cannot yet say by how much.

## Open

- The insulator and grease layers need a measured thickness and
  conductivity before any LEAF-versus-Prius claim leaves this file.
- **The 2004 Prius stack's `die` layer is 1.2 mm and marked estimated.**
  It contributes 0.0612 of that stack's 0.1085 K/W conduction total —
  56%. Real IGBT dies are 70-200 um; the LEAF's measured die is
  0.361 mm. The Prius value looks too thick by roughly an order of
  magnitude. It is load-bearing for that stack's 9.0 mm `total_path_m`
  check and its pinned 0.381 K/W regression, so it is flagged here
  rather than changed.
