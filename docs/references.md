# References

Canonical sources for the models and data used in heatsweep. Organized by
topic. Where a model module cites a source in its docstring, that citation
is authoritative; this file collects them in one place and adds context.

---

## Semiconductor Loss Modeling

### Costa et al. (2023) — three-phase inverter loss formulation
**Costa, F. C., Sanchez, J. O., & Bueno, E. J. (2023).** "A Novel
Analytical Formulation of SiC-MOSFET Losses to Size High-Efficiency
Three-Phase Inverters." *Energies*, 16(2), 818.
https://doi.org/10.3390/en16020818

Closed-form three-phase inverter loss with two terms absent from the
current `semiconductor_loss` model: a conduction term scaling as
`(1 + THD²)` and a parasitic-capacitance switching term that grows
quadratically as modulation index falls. Both are candidates for the
low-speed loss residual.

### Mantooth & Hefner (1997) — electrothermal IGBT simulation
**Mantooth, H. A., & Hefner, A. R. (1997).** "Electrothermal Simulation
of an IGBT PWM Inverter." *IEEE Trans. Power Electronics*, 12(3),
474–484. https://doi.org/10.1109/63.575675

Reports 20.5 W with self-heating versus 15.3 W at constant Tj for a
TO-247 IGBT at 60 Hz — the reference for the magnitude of thermal
feedback on loss. Within-cycle Tj ripple (±5 °C at switching frequency)
is the mechanism the transient thermal solve is intended to capture.
Cited only; full text not vendored (IEEE copyright).

### Infineon AN2019-05 — gate driver loss calculation
**Infineon Technologies AG.** "MOSFET and IGBT Gate Driver Loss
Calculation," application note AN2019-05.

Referenced in the `semiconductor_loss` module docstring. Gate driver
loss is not implemented but the note's loss decomposition informs the
model's structure.

### Semikron Application Manual, Chapter 5
General reference for conduction and switching loss averaging over a
sinusoidal PWM fundamental cycle. Referenced in both the
`semiconductor_loss` and `thermal` module docstrings.
https://shop.semikron-danfoss.com/out/pictures/wysiwigpro/application_manual_complete.pdf

---

## Thermal Modeling

### Infineon AN2008-03 — thermal equivalent circuit models
**Schuetze, T. (2008).** "Thermal Equivalent Circuit Models," Infineon
Technologies AG, application note AN2008-03, v1.0, 2008-06-16
(supersedes AN2001-05), 10 pp.

Origin of the standing rule that a datasheet Foster Zth_jc must not be
concatenated with external Rth_cs/Rth_sa. Its published Foster parameter
set anchors `tests/test_anchor_infineon_thermal.py`. Manufacturer
copyright — the PDF is not vendored; only the numeric Foster pairs are
transcribed with citation.
https://www.infineon.com/dgdl/Infineon+-+AN2008-03+-+Thermal+equivalent+circuit+models.pdf?folderId=db3a304412b407950112b4095b0601e3&fileId=db3a30431a5c32f2011aa65358394dd2

### Schweitzer & Pape — thermal modelling
**Schweitzer, D., & Pape, H.** "Thermal Modelling."

Foster/Cauer equivalence and the continued-fraction expansion used in
`foster_to_cauer()`. Referenced in the `thermal` module docstring.

### Plesca (2020) — thermal analysis of power rectifiers
**Plesca, A. (2020).** "Thermal Analysis of Power Rectifiers in
Steady-State Conditions." *Energies*, 13(8), 1942.
https://doi.org/10.3390/en13081942

Three-way analytic/FEM/measured reconciliation within 2 °C on a
three-phase bridge rectifier. Kept as a validation methodology reference
— attributes residual discrepancies by cause (FEM: distributed-vs-concentrated
loss; experiment: non-uniform airflow).

---

## Dead-Time and Current Measurement

### Ji et al. (2019) — dead-time mitigation overview
**Ji, S., Zhang, Z., & Wang, F. (2019).** "Control Strategies of
Mitigating Dead-time Effect on Power Converters: An Overview."
*Electronics*, 8(2), 196. https://doi.org/10.3390/electronics8020196

Dead-time voltage error is roughly speed-independent, so its share of
the fundamental grows as speed falls. Surveyed as a candidate for the
low-speed residual.

### Cheng et al. (2020) — dead-time in high-power IGBT/IGCT converters
**Cheng, T., Lu, D. D. C., Siwakoti, Y. P., & Blaabjerg, F. (2020).**
"Modeling and Compensation for Dead-Time Effect in High Power IGBT/IGCT
Converters with SHE-PWM Modulation." *Energies*, 13(17), 4348.
https://doi.org/10.3390/en13174348

Models dead-time effect across modulation ratio and power-factor angle
for high-power converters.

### Song et al. (2025) — current measurement errors
**Song, Z., Li, Y., Zhang, J., & Li, Q. (2025).** "Analysis and
Compensation of Current Measurement Errors in Machine Drive Systems —
A Review." *Energies*, 18(6), 1367.
https://doi.org/10.3390/en18061367

Relevant to the ORNL current-transducer/EMI artefact flagged in the
dyno data.

---

## Motor Parameter Identification

### Zhu et al. (2021) — PMSM online parameter estimation
**Zhu, Z. Q., Liang, D., & Liu, K. (2021).** "Online Parameter
Estimation for Permanent Magnet Synchronous Machines: An Overview."
*IEEE Access*, 9, 59059–59084.
https://doi.org/10.1109/access.2021.3072959

Rank-deficiency result: the PMSM electrical model has rank two, so more
than two parameters cannot be identified without added excitation.
Formalises incremental versus apparent inductance under saturation.

### Yan et al. (2024) — MTPA parameter identification under saturation
**Yan, L. C., Liao, Y., Lin, H., & Sun, J. B. (2024).** "Parameter
Identification for Maximum Torque per Ampere Control of Permanent Magnet
Synchronous Machines under Magnetic Saturation." *Electronics*, 13(4),
699. https://doi.org/10.3390/electronics13040699

Covers parameter identification under saturation; together with Zhu 2021
argues against deriving MG2 inductance from back-EMF plus the
locked-rotor table alone.

---

## Vehicle Benchmarking — ORNL Teardown Reports

All U.S. government works, public domain.

### ORNL/TM-2006/423 — 2004 Prius evaluation (primary)
**Ayers, C. W., Hsu, J. S., Marlino, L. D., et al. (2006).**
"Evaluation of 2004 Toyota Prius Hybrid Electric Drive System."
Oak Ridge National Laboratory, ORNL/TM-2006/423.
https://www.osti.gov/biblio/890029

Full-envelope dynamometer data (297–6005 rpm), inverter packaging,
die photography, thermal stack. Table B-1 provides the 428 operating
points used in `tests/test_anchor_ornl_inverter.py`. Primary source
for most device and drivetrain parameters.

### ORNL/TM-2010/253 — 2010 Prius evaluation
**Burress, T. A., Coomer, C. L., Campbell, S. L., et al. (2011).**
"Evaluation of the 2010 Toyota Prius Hybrid Synergy Drive System."
Oak Ridge National Laboratory, ORNL/TM-2010/253.
https://www.osti.gov/biblio/1007833

Die measurements (131.9 mm² IGBT, 40.7 mm² diode), SEM cross-sections,
solder EDS analysis, and 2004 vs 2010 thermal comparison. Primary
source for the `thermal_stack.toml` layer thicknesses in
`devices/prius_2004_igbt/`.

### ORNL/TM-2004/247 — 2004 Prius evaluation (interim)
**Staunton, R. H., Ayers, C. W., Marlino, L. D., et al. (2004).**
"Evaluation of 2004 Toyota Prius Hybrid Electric Drive System."
Oak Ridge National Laboratory, ORNL/TM-2004/247.
https://www.osti.gov/biblio/885776

Drivetrain loss decomposition, back-EMF vs speed, gear tooth counts.
Earlier interim report preceding TM-2006/423.

### ORNL/TM-2004/137 — Prius motor design assessment
**Staunton, R. H., Ayers, C. W., Chiasson, J., et al. (2004).**
"Report on Toyota/Prius Motor Design and Manufacturing Assessment."
Oak Ridge National Laboratory, ORNL/TM-2004/137.
https://www.osti.gov/biblio/885676

Motor geometry, slot fill (0.84), winding data.

### ORNL/TM-2004/185 — Prius motor torque capability
**Staunton, R. H., et al. (2004).** "Report on Toyota/Prius Motor
Torque Capability, Torque Property, No-Load Back EMF, and Mechanical
Losses." Oak Ridge National Laboratory, ORNL/TM-2004/185.
https://www.osti.gov/biblio/885669

Back-EMF, locked-rotor torque, mechanical losses.

### FY2005 Motor Thermal — Prius motor thermal management
**Hsu, J. S., et al. (2005).** "Report on Toyota Prius Motor Thermal
Management." Oak Ridge National Laboratory.
https://www.osti.gov/biblio/885987

Motor thermal characterization at 900 rpm line-fed, 35–105 °C coolant.

### DOE AMR APE006 (2013) — LEAF and benchmarking
**Burress, T. A., & Liang, Z. (2013).** "Benchmarking of Competitive
Technologies." DOE Vehicle Technologies Program Annual Merit Review,
project APE006, Oak Ridge National Laboratory.
https://www.energy.gov/sites/prod/files/2014/03/f13/ape006_burress_2013_o.pdf

2012 Nissan LEAF inverter and motor data. Source for
`devices/leaf_2012_igbt/thermal_stack.toml`. Provenance is a slide deck,
not a benchmarking report — weaker evidence class than the 2004 Prius
stack.

### ORNL/TM-2013/498 — benchmarking state-of-the-art
**Burress, T. A. (2014).** "Benchmarking State-of-the-Art Technologies."
Oak Ridge National Laboratory, ORNL/TM-2013/498.
https://www.osti.gov/biblio/1110977

Cross-vehicle design comparison (motor, inverter, thermal).

### ORNL/SPR-2014/532 — EE technical team roadmap
**U.S. DRIVE (2014).** "Electrical and Electronic Technical Team
Roadmap." Oak Ridge National Laboratory, ORNL/SPR-2014/532.
https://www.osti.gov/biblio/1220125

HEV benchmarking context.

---

## Device Data — Manufacturer Datasheets

These are the technology and current-rating analogues used where no
measured Prius device data exists. Attributed in `NOTICE`.

### International Rectifier IRG4PC50U
600 V / 55 A NPT IGBT (Gen 4, ~2000 era). Best technology match for
the Prius IGBT die: same-era non-punch-through silicon. Switching
energy tables in `devices/prius_2004_igbt/prius_2004_igbt.toml` are
scaled from this device's E_on/E_off at 54 A, 480 V, 150 °C.
Gate resistance R_g = 5 Ω is the IRG4PC50U test condition.

### Mitsubishi CM100DU-12F
600 V / 100 A F-series IGBT module (3rd gen, 2000 era).
https://www.mitsubishielectric.com/semiconductors/powerdevices/datasheets/igbt/f_series/cm100du-12f_e.pdf Best
current-rating match. Source for V_ce_sat (1.6 V at 100 A, Tj = 125 °C),
Rth_jc (0.35 K/W per switch), body diode V_f, and Q_rr (1.9 μC at
25 °C, 300 V, 100 A). Planar gate structure matches the ORNL-confirmed
Prius die.

