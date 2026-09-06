# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Physics-invariant tests across the loss, thermal, and FEM layers.**
  Each checks a property against an independent computation rather than a
  pinned value, so none needs reference data — which matters most for the
  loss model, where no external anchor exists.
  - `TestIgbtConductionInvariants` — the IGBT conduction closed form had no
    numerical counterpart, though every validation anchor runs it (the
    existing closed-form check covers only the sync-rect MOSFET). Direct
    integration of the duty-weighted drop agrees to ~2e-11 over 16 (m, pf)
    combinations; a sign error on the diode's duty complement moves the
    total 14-16%. Adds the m -> 0 limit, where duty is a flat 1/2 and every
    cos(phi) term must drop out.
  - `TestThermalLinearity` — with Tj-independent losses the fixed-point
    solver must reproduce `Tj = T_amb + P*sum(Rth)` exactly, and scaling
    every Rth by lambda must scale every rise above ambient by lambda.
    With the tempco restored, the rise must exceed that linear prediction,
    which is the thermal feedback the ORNL inverter anchor result rests on.
  - `TestConductivityScaling` — scales every layer conductivity by lambda
    and checks the Elmer solve against the convective film, 1/(h*A_plate)
    = 0.125 K/W, which is analytic and independent of k. The film is a hard
    lower bound at every lambda and the limit at lambda = 1000 (0.1253 vs
    0.1250 K/W, 0.2%). Rth is *not* affine in 1/lambda: scaling k at fixed
    h moves the Biot number, so the spreading share drifts 1.4% across
    three decades. The test bounds that drift instead of asserting the
    affine law, which the physics does not support.
- **2012 LEAF PEM thermal stack, and a second FEM case.**
  `devices/leaf_2012_igbt/thermal_stack.toml` — 8 layers, one 15x15 mm
  IGBT die, junction to chassis face. Five thicknesses are ORNL-measured
  (die, die attach, Cu-Mo spacer, spacer solder, Cu base plate); the
  grease/insulator/grease group below the non-isolated base plate is
  described by ORNL but never dimensioned, so those are declared
  estimates. No `total_path_m`: ORNL publishes no path length for the
  LEAF and inventing one would defeat the check. Elmer 26.2 gives
  0.376 K/W at the default mesh (converged ~0.380), inside the 1-D
  bracket [0.229, 1.625], pinned with a mesh-convergence and sensitivity
  table. **The near-equality with the 2004 Prius 0.381 K/W is not a
  hardware result** — the convective film is a third of both totals and
  identical by construction, and the LEAF's conduction penalty sits
  entirely in the estimated insulator group, which alone swings the
  answer 0.344-0.439 K/W. The device README carries that decomposition.
  The directory has no device TOML, so the catalogue skips it by design.
- **2012 Nissan LEAF motor data, and three more machines in the design
  table.** ORNL/SPR-2014/532 Table 1 reprints TM-2010/253 Table 2.7 and
  extends it with the LEAF and both 2014 Accord machines, so
  `ornl_hev_benchmarking/motor_design.csv` now covers seven machines
  with a per-row `source` column; all 20 shared rows were verified
  identical between the two publications before merging. New
  `ornl_leaf_2012_motor/` holds LEAF ratings, geometry, efficiency
  floors, and continuous capability from the APE006 AMR presentation
  and ORNL/TM-2013/498. There is no LEAF benchmarking report equivalent
  to TM-2010/253 — the provenance is a slide deck and two annual
  progress reports, and the READMEs say so. Manufacturer-published duty
  points are tagged as Nissan's rather than ORNL measurements.
- **ORNL 2010 Prius motor and thermal-duty data.** Three tables from
  ORNL/TM-2010/253 that the earlier extraction left behind:
  `ornl_hev_benchmarking/motor_design.csv` (Table 2.7 — lamination
  geometry, assembly masses, stator winding, magnet dimensions for all
  four vehicles), `ornl_hev_benchmarking/magnet_hysteresis.csv` (§2.3.3
  — Br and intrinsic Hc at 114 and 215 degC), and a new
  `ornl_prius_2010_thermal_duty/` directory with `continuous_duration.csv`
  (time to stator temperature limit, 25-60 kW, 3000-7000 rpm, 25-65 degC
  coolant) and `stator_steady_state.csv`. Values verified against the
  source PDF rather than the markdown conversion; ORNL's list of figures
  misstates the Fig. 2.68 magnet temperature as 121 degC where the body
  and caption say 114 degC. Duration rows carry a `basis` column
  separating the four exact mm:ss values from values ORNL narrates off a
  plot, and the README records the report's self-contradiction at
  25 kW / 5000 rpm / 50 degC coolant rather than resolving it.
- **Local server and dashboard (optional).** `heatsweep[server]` installs
  a FastAPI app (`uv run heatsweep-server`) built on the shared
  view-sweep-server toolkit: `GET /api/models`, `GET /api/assemblies`
  (device catalogue), `GET /api/results` and `GET /api/results/{id}`
  (result store), `POST /api/jobs` (synchronous registry-model run with a
  `job_complete` / `job_failed` WebSocket frame), local-only Host/Origin
  guard. The dashboard at `/` lists results and charts the loss breakdown
  or per-position Tj; Plotly loads from its CDN with a table fallback.
  Post-audit: `POST /api/jobs` answers 200 `failed` (not 201) when the
  model raised, `/api/assemblies` paths are relative to the catalogue
  directory, and the dashboard selects the new result from the POST
  response so a job submitted while the WebSocket is connecting still
  shows up (the `job_complete` frame is de-duplicated by job id).
  `--host` help now states the Host guard stays local-only.
- **FEM thermal path (optional).** `heatsweep.fem`: layered thermal stack
  TOML (`load_stack_toml`), analytic 1-D Rth bracket (`rth_1d_bounds`),
  gmsh mesh generation (`heatsweep[fem]` extra), and Elmer steady-state
  conduction case writer/runner. First stack: 2004 Prius IPEM, one IGBT
  die on a cold-plate unit cell (`devices/prius_2004_igbt/thermal_stack.toml`).
- Guard test that bundled `heatsweep/devices/` stays byte-identical to
  `devices/`.

## [0.1.0] - 2026-09-06

Initial release: device parameter loading from TOML, semiconductor loss
models for MOSFET and IGBT topologies, lumped-parameter thermal networks,
and an append-only result store shared with phase-sweep.

### Added
- **Device TOML format.** `load_device_toml` reads conduction parameters,
  switching energy tables, body diode characteristics, and thermal impedance
  data with explicit test conditions and provenance. Validation at load:
  Foster sum vs Rth_jc, Tj range checks, table monotonicity.
  See `docs/device-toml.md` for the full schema.
- **`semiconductor_loss` model (v1).** Per-device conduction, switching,
  and diode losses for half-bridge and full-bridge topologies under
  sinusoidal PWM. MOSFET conduction loss via closed-form and numerical
  integration paths. IGBT conduction loss via linearized V_ce(I_c) with
  temperature dependence. Switching loss interpolated from energy tables,
  averaged over a fundamental cycle. Body diode reverse recovery loss.
- **`thermal` model (v1).** Steady-state junction temperature per device
  with iterative loss-temperature coupling. Foster and Cauer RC chain
  evaluation (transient impedance Zth). Foster-to-Cauer conversion via
  continued-fraction expansion. Per-device Tj in multi-device assemblies
  with explicit Rth_cs per position.
- **Assembly and operating point types.** `Assembly` groups devices with
  per-position case-to-sink resistance. `OperatingPoint` carries switching
  frequency, DC bus, phase current, output frequency, power factor, and
  modulation index.
- **Model registry with validation and dispatch.** `MODEL_REGISTRY`
  declares what each model produces and which fields it needs; missing
  fields fail validation before computation.
- **Append-only JSONL result store** with content-addressed run IDs.
  Shared contract with phase-sweep (`docs/result-store-contract.md`,
  `tests/staleness_vectors.json`).
- **Prius NHW20 IGBT device dataset.** Estimated parameters for the 2004
  Toyota Prius THS-II motor inverter IGBT, derived from ORNL teardown
  reports and comparable commercial devices. No measured switching data
  exists for this custom silicon; assumptions and limitations documented.
- **Prius NHW20 powertrain reference.** Consolidated ORNL report data
  for the thermal stack (ORNL/TM-2010/253, TM-2006/423).
- **Defaults system.** `defaults.toml` provides baseline operating-point
  and thermal parameters; `defaults.py` loads and merges them.
- Public API in `heatsweep/__init__.py` with `__version__` and `py.typed`.
- CI: GitHub Actions and GitLab CI.
