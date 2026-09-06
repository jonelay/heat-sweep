# Architecture

heat-sweep turns semiconductor device data and an electrical operating point
into loss and temperature results. A device TOML is loaded into an immutable
`Device`, placed at one or more positions in an `Assembly`, and paired with an
operating-point dictionary in `RunConfig`. The selected registry model computes
losses or a coupled steady-state thermal solution. `RunResult` wraps the
metrics, status, timing, provenance, and model version for append-only storage.

The layered FEM path is adjacent to this registry pipeline rather than part of
it. It loads a separate thermal-stack TOML, builds a gmsh mesh, runs a
steady-state Elmer case, and compares the resulting junction-to-coolant thermal
resistance with dependency-free one-dimensional bounds.

## Module map

- [`components/`](../heatsweep/components/) defines `Device`, `Assembly`,
  `DevicePosition`, and `OperatingPoint`, including serialization and input
  validation.
- [`models/`](../heatsweep/models/) contains the semiconductor-loss model,
  Foster/Cauer utilities, and the coupled steady-state thermal model.
- [`registry.py`](../heatsweep/registry.py) declares the available computed
  models and their metadata, validation hooks, and run functions.
- [`run_types.py`](../heatsweep/run_types.py) defines `RunConfig`, `RunResult`,
  and content-addressed run IDs.
- [`result_store.py`](../heatsweep/result_store.py) implements the JSONL store,
  index, filtering, attachment, and staleness rules.
- [`fem/`](../heatsweep/fem/) describes layered stacks, generates gmsh meshes,
  writes Elmer input, and reads steady-state solver output.
- [`devices/`](../heatsweep/devices/) contains packaged device data and the
  `bundled_device_path` resource helper.
- [`server/`](../heatsweep/server/) builds the FastAPI application and owns the
  heat-sweep REST routes; [`dashboard/`](../heatsweep/dashboard/) is the static
  browser client.
- [`defaults.py`](../heatsweep/defaults.py) loads package defaults from
  [`defaults.toml`](../heatsweep/defaults.toml). The thermal solver reads its
  iteration limit and convergence tolerance there.
- [`__init__.py`](../heatsweep/__init__.py) exposes the supported top-level API:
  component types, loaders, registry and run types, result store, and
  Foster/Cauer functions.

## Data flow

`RunConfig` composes an `Assembly`, a registry model key, and serialized
`OperatingPoint` fields. It can also carry a mission profile or measured
dataset identity. No registered model currently consumes mission profiles or
includes them in its `hash_fields`; they affect identity only for dispatches
whose selected hash-field set contains `mission_profile`.

The caller looks up `RunConfig.model` in `MODEL_REGISTRY`. The model's
`validate` hook constructs and discards the corresponding prepared model state;
for the current models this checks the assembly and device data. Its `fn` then
returns a model-specific metrics dictionary. The server's `run_model` adapter
times that call and converts either the metrics or an exception into an `OK` or
`ERROR` `RunResult`.

`compute_run_id` hashes the assembly configuration ID, model key, relevant
operating-point fields declared by that model and an optional dataset ID.
Mission-profile data is hashed when `mission_profile` survives that model's
field filter. A model version enters the hash when it is greater than one.
Saving appends the complete serialized result to `results.jsonl` and updates
`index.json` under that 12-character ID.

## Device loading

[`device-toml.md`](device-toml.md) specifies the public device format. Its
`[device]`, `[conduction]`, `[body_diode]`, `[switching]`, and `[thermal]`
sections become a frozen `Device`. MOSFET conduction uses an
`R_ds_on`-versus-`Tj` table; IGBT conduction uses `V_ce0` and `r_ce`, with
optional temperature tables. Switching energy tables, diode parameters, and
Foster `R_i`/`tau_i` pairs retain the conditions needed by the models.

`load_device_toml` parses numeric values and constructs `TableEntry` and
`FosterPair` objects. Construction rejects mismatched or short tables,
non-finite values, non-increasing axes, and tables without conditions. It also
checks temperature-table ranges against `Tj_max`, requires IGBT conduction test
conditions, and requires `sum(R_i)` to agree with `Rth_jc` within 5 percent.

`bundled_device_path(name)` resolves
`heatsweep.devices/<name>/<name>.toml` through `importlib.resources`, so packaged
data and source-checkout data use the same loader. The server catalogue also
accepts flat `<name>.toml` files and nested `<name>/<name>.toml` files. It
records a neighboring `thermal_stack.toml` when present and skips invalid
device files with a warning.

## Model registry

`MODEL_REGISTRY` is a plain dictionary of immutable `ModelInfo` records; there
is no abstract base class or plugin discovery layer. Each record declares its
human-readable name, source, expected cost, output keys and units, required
assembly fields, run-ID `hash_fields`, version, and validation and execution
callables. `needs_runtime` and an optional batch callable are available in the
metadata but unused by the two current entries.

The registered keys are `semiconductor_loss` and `thermal`. Registry wrappers
import their implementations lazily. Applicability validation is delegated to
`prepare_semiconductor_loss` or `prepare_thermal`, while dispatch calls
`run_semiconductor_loss` or `run_thermal`. The registry does not itself run or
store work; callers, including the server, perform the lookup and invoke these
hooks.

## Loss model

`prepare_semiconductor_loss` requires at least one device position, supported
MOSFET or IGBT conduction data, and both switching-energy tables. The run path
reconstructs a validated `OperatingPoint`, computes each `DevicePosition`
independently, prefixes per-position metrics, and also returns assembly totals.

For a MOSFET, `R_ds_on` is linearly interpolated at the assumed junction
temperature, clamped to the table range, and combined with the position's
parasitic `R_path`. The synchronous-rectification closed form gives one-device
conduction loss. For an IGBT, fixed or interpolated `V_ce0` and `r_ce` feed the
sinusoidal-PWM transistor expression; the antiparallel-diode half-cycle is
included in the conduction result.

Turn-on and turn-off energies are linearly interpolated over current and
numerically averaged over the conducting half-cycle. They scale linearly from
the table's DC-bus test condition and, when coefficients are supplied, with
junction temperature. The model adds reverse-recovery loss and dead-time diode
conduction, then reports conduction, turn-on, turn-off, diode, recovery, and
total power in W. Junction temperature is fixed for this model run; thermal
feedback belongs to the thermal model.

## Thermal model

The transient-network utilities evaluate Foster
`Zth(t) = sum(R_i (1 - exp(-t/tau_i)))` and a Cauer II ladder step response.
`foster_to_cauer` converts a Foster fit to positive series-R/shunt-C stages by a
scaled polynomial continued-fraction expansion. This is necessary before a
physical ladder can be cascaded with external thermal elements, but the current
registered thermal run is steady-state and does not call the conversion or
integrate a mission profile.

`prepare_thermal` first applies all loss-model checks, then requires positive
`Rth_jc` for every device. The steady-state solver starts every junction at
`Tj_assumed_C`, recomputes each device's temperature-dependent losses, and
updates a shared sink and each junction:

```
T_sink = T_amb + sum(P_i) Rth_sa
Tj_i   = T_sink + P_i (Rth_jc_i + Rth_cs_i)
```

Iteration stops when the largest junction-temperature change is below `tol_K`
or `max_iter` is reached; package defaults are 0.01 K and 50 iterations. A
separate `thermally_stable` flag is false when any final junction temperature
exceeds that device's `Tj_max`. The result includes convergence state, sink,
case, and junction temperatures, device and assembly power, and the underlying
loss breakdown.

## FEM path

`ThermalStack` describes layers from junction to coolant. Each `Layer` has a
die, tile, or plate footprint plus thickness, conductivity, density, and heat
capacity. Load-time checks require positive physical properties, nested
footprints, a die-footprint top layer, positive convection coefficient, and,
when declared, agreement between the layer sum and `total_path_m`.

`build_mesh` creates one centered box per layer, fragments the boxes into a
conformal three-dimensional geometry, assigns material-volume groups, and
marks the die top and coolant bottom faces. It writes a tetrahedral MSH 2.2
mesh, with refinement around die-footprint volumes. Unmarked exterior faces
are adiabatic in the generated Elmer case.

`write_sif` applies uniform heat flux over the die top and convection to
`T_coolant_C` on the bottom. `run_case` invokes the external `ElmerGrid` and
`ElmerSolver` executables, reads the maximum temperature and node count, and
returns `Rth_j-coolant = (T_max - T_coolant) / P`. `rth_1d_bounds` provides an
independent bracket: perfect spreading uses plate area throughout, while no
spreading confines conduction and convection to die area.

## Result store

`ResultStore` appends one complete JSON object per line to `results.jsonl`; a
malformed trailing line can be skipped without losing earlier records. A
separate `index.json` maps run IDs to status so known-ID checks need not scan
the JSONL history, and is replaced atomically after each append. The design
assumes a single writer.

Computed records serve only when their stamped `model_version` equals the live
registry version. A missing or mismatched stamp is stale. Measured and
published records are exempt because they describe hardware rather than model
code. Computed records attach to an exact assembly configuration ID; measured
and published records may instead follow an assembly name across parameter
changes.

These semantics match the portable
[`result-store-contract.md`](result-store-contract.md) shared with phase-sweep.
That document uses phase-sweep's `motor` terminology; heat-sweep applies the
same version-staleness and source-dependent attachment rules to `Assembly` and
`assembly_config_id`. Version comparison is deliberately outside run-ID
hashing, because recomputing an old record's ID under the current registry
cannot establish which model version originally produced it.

## Server

The optional server builds a heat-sweep domain layer on
`view_sweep_server.create_app`. view-sweep owns the generic app factory,
local-only Host/Origin guard, logging, static mounts, WebSocket connection
manager, and `/ws` endpoint. heat-sweep supplies the device catalogue,
`ResultStore`, REST router, and packaged dashboard.

The `/api/models` and `/api/assemblies` routes expose registry and catalogue
metadata. `/api/results` returns current slim records and supports model,
assembly, and source filters; `/api/results/{id}` returns the full stored
record. `/api/jobs` validates an operating point, places one selected device in
every position of a half bridge, full bridge, or three-phase bridge, and runs
the selected model synchronously in a worker thread. It stores both successful
and failed attempts.

A client may supply a `job_id` and subscribe before posting. Completion
broadcasts a view-sweep `job_complete` frame containing the job ID and result
ID; failure broadcasts `job_failed` with an error. The dashboard treats the
synchronous POST response as authoritative and WebSocket delivery as an
optimization, refreshes on reconnect, and suppresses duplicate notifications.
It uses view-sweep theme, chrome, data-provider, plotting, and widget assets;
the heat-sweep JavaScript supplies the run form, result table, provenance, loss
breakdown, and per-position junction-temperature views.

## Optional dependencies

The core package depends only on NumPy and SciPy. NumPy supplies array and
quadrature operations; SciPy supplies interpolation, matrix exponentials, and
linear algebra used by the model layer.

The `fem` extra installs the gmsh Python package for mesh construction. Running
the resulting case additionally requires external `ElmerGrid` and
`ElmerSolver` executables on `PATH`; stack loading, SIF generation, and analytic
bounds do not require gmsh or Elmer. The `server` extra installs FastAPI,
uvicorn, structlog, and view-sweep-server. The `viz` extra installs Matplotlib,
but the browser dashboard uses Plotly loaded from a CDN and falls back to a
table when it is unavailable.
