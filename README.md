# heat-sweep

Power-electronics thermal design exploration. Semiconductor loss models
(MOSFET and IGBT), lumped thermal networks (Foster and Cauer), device
parameter loading from TOML, and an append-only result store.

Sister project of [phase-sweep](https://github.com/jonelay/phase-sweep);
same registry / result-store / crossval architecture.

## What it does

heat-sweep reads a device definition from TOML and runs loss and thermal
models against it. A device TOML carries conduction parameters, switching
energy tables, body diode characteristics, and thermal impedance data -
all with explicit test conditions and provenance. The loss model computes
conduction and switching losses for MOSFET and IGBT topologies across an
operating point (switching frequency, DC bus, phase current, modulation
index, power factor). The thermal model solves for steady-state junction
temperature using Foster-to-Cauer conversion and iterative loss-temperature
coupling.

## Features

**Semiconductor loss**
- MOSFET conduction loss: closed-form and numerical integration paths
- IGBT conduction loss: linearized V_ce(I_c) model with temperature dependence
- Switching loss: interpolated from energy tables, averaged over a fundamental cycle
- Body diode reverse recovery loss
- Half-bridge and full-bridge topologies

**Thermal networks**
- Foster and Cauer RC chain evaluation (transient impedance Zth)
- Foster-to-Cauer conversion via continued-fraction expansion
- Iterative steady-state solve with loss-temperature coupling
- Per-device junction temperature in multi-device assemblies

**Device TOML format**
- Conduction, switching, diode, and thermal sections with explicit test conditions
- Validation at load: Foster sum vs Rth_jc, Tj range checks, table monotonicity
- See [docs/device-toml.md](docs/device-toml.md) for the full schema

**Infrastructure**
- Model registry with validation and dispatch
- Append-only JSONL result store with content-addressed run IDs
- Shared contract with phase-sweep ([docs/result-store-contract.md](docs/result-store-contract.md))

## Scope and limitations

The loss models are sinusoidal PWM only. No SVPWM, six-step, or
discontinuous modulation.

Gate driver loss, parallel current sharing, and R_g scaling are not
implemented.

Transient thermal solve (mission-profile Cauer ODE) is not yet
implemented - only steady-state with iterative coupling.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/jonelay/heat-sweep.git
cd heat-sweep
uv sync                    # core (numpy + scipy)
uv sync --extra test       # + pytest, ruff, mypy
uv sync --extra server     # + FastAPI server and dashboard
uv sync --extra dev        # everything (adds matplotlib)
```

Run the tests:

```bash
uv run pytest -m "not slow" -q
```

## Quick start

Compute semiconductor losses for the Prius 2004 inverter IGBT:

```python
from heatsweep import load_device_toml, bundled_device_path
from heatsweep.components.assembly import Assembly, DevicePosition
from heatsweep.components.operating_point import OperatingPoint
from heatsweep.models.semiconductor_loss import run_semiconductor_loss
from heatsweep.run_types import RunConfig

dev = load_device_toml(bundled_device_path("prius_2004_igbt"))

asm = Assembly(
    name="half_bridge",
    topology="half_bridge",
    devices=(
        DevicePosition(position="Q_high", device=dev, Rth_cs=0.2),
        DevicePosition(position="Q_low", device=dev, Rth_cs=0.2),
    ),
)

op = OperatingPoint(
    f_sw_Hz=20000, V_dc=400, I_phase_rms=10,
    f_out_Hz=50, pf=0.9, m_index=0.8,
)

config = RunConfig(assembly=asm, model="semiconductor_loss", op=op.to_dict())
results = run_semiconductor_loss(config)
print(f"Total loss: {results['p_total_W']:.2f} W")
```

## Available models

`RunConfig(assembly=..., model=<key>)` dispatches through `MODEL_REGISTRY`.
Each model declares what it produces and which device/assembly fields it
needs; missing fields fail validation before any computation.

| Key | Computes | Requires |
|-----|----------|----------|
| `semiconductor_loss` | Per-device conduction, switching, and diode losses; total assembly loss | Device with conduction + switching tables, operating point |
| `thermal` | Steady-state Tj per device with loss-temperature coupling | Device with Rth_jc (and optionally Foster chain), assembly with Rth_cs per position |

The FEM thermal path (`heatsweep.fem`) is not a registry model: it turns a
layered stack TOML into a gmsh mesh and an Elmer conduction case and
returns junction-to-coolant Rth, bracketed by analytic 1-D bounds that
need no optional dependencies.

## Local server and dashboard

`heatsweep[server]` adds a single-user FastAPI server and a browser
dashboard built on the shared [view-sweep](https://github.com/jonelay/view-sweep)
toolkit (theme, widgets, data providers, WebSocket protocol).

```bash
uv sync --extra server
uv run heatsweep-server            # http://127.0.0.1:8010
uv run heatsweep-server --devices-dir devices --output-dir results --port 8010
```

Endpoints (all under `/api`, JSON; NaN/inf serialize as `null`):

| Endpoint | Returns |
|----------|---------|
| `GET /models` | registry models: produces, needs, units, version |
| `GET /assemblies` | device catalogue from `--devices-dir` (flat `*.toml` or `<name>/<name>.toml`), with the FEM `thermal_stack.toml` beside each when present, and the topologies a job can build |
| `GET /results` | current (non-stale) results, slim; filter by `model`, `assembly_config_id`, `source` |
| `GET /results/{id}` | one full stored record including its `RunConfig` |
| `POST /jobs` | run a registry model synchronously on `device` placed in every position of `topology` (`half_bridge`, `full_bridge`, `three_phase_bridge`) at `op`; the result is saved and a `job_complete` / `job_failed` frame is broadcast on `/ws` to subscribers of `job_id` |

The dashboard at `/` lists results, shows one result's stat strip and
provenance, and charts the assembly loss breakdown (`semiconductor_loss`)
or per-position junction temperature (`thermal`). Plotly is a peer
dependency of view-sweep and is not bundled; the page loads it from the
Plotly CDN and falls back to a table when the CDN is unreachable. The
server only accepts local `Host`/`Origin` values.

## Device TOML format

Devices are TOML files with `[device]`, `[conduction]`, `[switching]`,
`[body_diode]`, and `[thermal]` sections. Each section carries its test
conditions so scaling and interpolation have a traceable basis.

See [docs/device-toml.md](docs/device-toml.md) for the full schema. The
bundled [`devices/prius_2004_igbt/`](devices/prius_2004_igbt/) is a worked
example with provenance comments.

## Reference data

The `devices/prius_2004_igbt/` directory contains estimated parameters for
the 2004 Toyota Prius THS-II motor inverter IGBT, derived from ORNL
teardown reports and comparable commercial devices. No measured switching
data exists for this custom silicon - see
[`devices/prius_2004_igbt/README.md`](devices/prius_2004_igbt/README.md) for
sources and declared assumptions.

## Dependencies

| Package | Purpose | License |
|---------|---------|---------|
| [NumPy](https://numpy.org/) / [SciPy](https://scipy.org/) | Numerical computation | BSD-3-Clause |
| [Matplotlib](https://matplotlib.org/) (optional) | Plotting | PSF (BSD-compatible) |
| [gmsh](https://gmsh.info/) (optional, `heatsweep[fem]`) | Mesh generation for the FEM thermal path | GPL-2.0-or-later |
| [FastAPI](https://fastapi.tiangolo.com/) / [uvicorn](https://www.uvicorn.org/) / [structlog](https://www.structlog.org/) (optional, `heatsweep[server]`) | Local server | MIT / BSD-3-Clause / MIT or Apache-2.0 |
| [view-sweep-server](https://github.com/jonelay/view-sweep) (optional, `heatsweep[server]`) | Dashboard toolkit: app factory, WebSocket manager, browser assets | Apache-2.0 |
| [Elmer](https://www.elmerfem.org/) (optional, external binaries) | Steady-state conduction solve | GPL-2.0 / LGPL-2.1 |

## Package layout

```
heatsweep/
├── components/        # device, assembly, operating point
├── devices/           # bundled device parameter files (shipped in wheel)
├── models/            # semiconductor_loss, thermal
├── server/            # FastAPI app, REST routes, uvicorn entry (server extra)
├── dashboard/         # browser dashboard served at / by the server
├── registry.py        # model metadata and dispatch
├── run_types.py       # run configuration and results
└── result_store.py    # append-only JSONL result store
devices/               # device parameter files (source checkout)
data/                  # measured/reference data for validation
tests/                 # pytest suite
docs/                  # device TOML schema, result-store contract
```

## Contributing

Bug reports, documentation fixes, and new device datasets are welcome.
See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and process.

Questions and discrepancy reports:
[GitHub Issues](https://github.com/jonelay/heat-sweep/issues).

## License

Code is licensed under the [Apache License 2.0](LICENSE).

Data files contain parameter values transcribed from cited publications
or estimated from comparable devices, and are covered by the same
Apache-2.0 license. [NOTICE](NOTICE) attributes the ORNL reports and
manufacturer datasheets those values come from; if you redistribute
`heatsweep`, Apache-2.0 §4(d) requires you to carry NOTICE with it.

`heatsweep` itself contains no code under a copyleft license. The
optional `heatsweep[fem]` extra installs gmsh (GPL-2.0-or-later), which
is imported as a Python module; installing it forms a combined work
whose redistribution is governed by that license. Elmer is invoked only
as an external binary through `subprocess` and is never linked or
redistributed here. The core install — numpy and scipy only — is
unaffected.

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).
