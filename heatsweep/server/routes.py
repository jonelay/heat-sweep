"""REST endpoint handlers. The WebSocket endpoint and connection manager
come from view_sweep_server.ws.

Jobs run synchronously in a worker thread and complete before the POST
returns; the WebSocket path still carries a ``job_complete`` /
``job_failed`` frame so dashboards subscribe and react the same way they
would to a queued runner.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request, Response
from view_sweep_server import FiniteJSONResponse
from view_sweep_server.protocol import ServerMsg

from heatsweep.components.assembly import Assembly, DevicePosition
from heatsweep.components.operating_point import OperatingPoint
from heatsweep.registry import MODEL_REGISTRY, ModelInfo
from heatsweep.result_store import ResultStore
from heatsweep.run_types import RunConfig, RunResult, compute_run_id

log = structlog.get_logger()

api = APIRouter(prefix="/api", default_response_class=FiniteJSONResponse)

TOPOLOGY_POSITIONS: dict[str, tuple[str, ...]] = {
    "half_bridge": ("Q_high", "Q_low"),
    "full_bridge": ("Q1_high", "Q1_low", "Q2_high", "Q2_low"),
    "three_phase_bridge": ("Q1_high", "Q2_high", "Q3_high", "Q1_low", "Q2_low", "Q3_low"),
}


def _store(request: Request) -> ResultStore:
    store: ResultStore = request.app.state.store
    return store


# -- catalogue ----------------------------------------------------------------

def _model_dict(info: ModelInfo) -> dict[str, Any]:
    return {
        "name": info.name,
        "source": info.source,
        "cost": info.cost,
        "version": info.version,
        "produces": sorted(info.produces),
        "needs": sorted(info.needs),
        "needs_runtime": sorted(info.needs_runtime),
        "hash_fields": sorted(info.hash_fields),
        "units": dict(info.units),
    }


@api.get("/models")
async def list_models() -> list[dict[str, Any]]:
    return [_model_dict(info) for info in MODEL_REGISTRY.values()]


@api.get("/assemblies")
async def list_assemblies(request: Request) -> list[dict[str, Any]]:
    """Device catalogue plus the topologies an assembly can be built from.
    heat-sweep has no assembly TOML: an assembly is a device placed in
    every position of a topology (see ``POST /api/jobs``)."""
    root = Path(request.app.state.settings.devices_dir)
    out = []
    for name, entry in request.app.state.devices.items():
        dev = entry.device
        out.append({
            "name": name,
            "path": str(entry.path.relative_to(root)),
            "thermal_stack": str(entry.stack_path.relative_to(root)) if entry.stack_path else None,
            "device": {
                "name": dev.name,
                "device_type": dev.device_type,
                "package": dev.package,
                "manufacturer": dev.manufacturer,
                "V_max": dev.V_max,
                "I_max": dev.I_max,
                "Tj_max": dev.Tj_max,
                "Rth_jc": dev.Rth_jc,
            },
            "topologies": sorted(TOPOLOGY_POSITIONS),
        })
    return out


# -- results ------------------------------------------------------------------

@api.get("/results")
async def list_results(
    request: Request,
    model: str | None = None,
    assembly_config_id: str | None = None,
    source: str | None = None,
) -> list[dict[str, Any]]:
    """Current (non-stale) results, slim: no config payload."""
    slim = _store(request).load_slim(
        model=model, assembly_config_id=assembly_config_id, source=source)
    return [s._asdict() for s in slim.values()]


@api.get("/results/{result_id}")
async def get_result(request: Request, result_id: str) -> dict[str, Any]:
    """Full stored record (config included) for one run id."""
    for d in _store(request).load_all():
        try:
            rid = compute_run_id(RunConfig.from_dict(d["config"]))
        except (KeyError, ValueError, TypeError):
            continue
        if rid == result_id:
            return {"result_id": rid, **d}
    raise HTTPException(404, f"unknown result {result_id!r}")


# -- jobs ---------------------------------------------------------------------

def build_assembly(
    name: str, device: Any, topology: str, Rth_cs: float, Rth_sa: float, T_amb_C: float,
) -> Assembly:
    try:
        positions = TOPOLOGY_POSITIONS[topology]
    except KeyError:
        raise ValueError(
            f"unknown topology {topology!r}; one of {sorted(TOPOLOGY_POSITIONS)}") from None
    return Assembly(
        name=name,
        topology=topology,
        devices=tuple(DevicePosition(position=p, device=device, Rth_cs=Rth_cs) for p in positions),
        T_amb_C=T_amb_C,
        Rth_sa=Rth_sa,
    )


def run_model(info: ModelInfo, config: RunConfig) -> RunResult:
    """Run one registry model to a RunResult; exceptions become ERROR
    records rather than propagating, so the store keeps the attempt."""
    assert info.fn is not None
    t0 = time.perf_counter()
    try:
        metrics = info.fn(config)
        status, err = "OK", None
    except Exception as e:
        metrics, status, err = None, "ERROR", f"{type(e).__name__}: {e}"
    return RunResult(
        config=config, model=info.name, status=status, metrics=metrics,  # type: ignore[arg-type]
        elapsed_s=time.perf_counter() - t0, error_msg=err, model_version=info.version,
    )


@api.post("/jobs", status_code=201)
async def submit_job(request: Request, body: dict[str, Any], response: Response) -> dict[str, Any]:
    """Run a registry model on ``device`` placed in every position of
    ``topology``. Body: ``device`` (catalogue name), ``model`` (registry
    key), ``op`` (OperatingPoint fields), optional ``topology``
    (default half_bridge), ``Rth_cs`` (K/W, default 0.2), ``Rth_sa``
    (K/W, default 0), ``T_amb_C`` (default 25), and ``job_id`` so a
    client can subscribe over WebSocket before the run starts.

    201 when the run completed (OK record stored); 200 with
    ``status: "failed"`` when the model raised (ERROR record stored).
    """
    device_name = body.get("device")
    model = body.get("model")
    if not device_name or not model:
        raise HTTPException(422, "body must have 'device' (catalogue name) and 'model' (registry key)")
    entry = request.app.state.devices.get(device_name)
    if entry is None:
        raise HTTPException(404, f"unknown device {device_name!r}")
    info = MODEL_REGISTRY.get(model)
    if info is None or info.fn is None:
        raise HTTPException(404, f"unknown model {model!r}")
    op = body.get("op")
    if not isinstance(op, dict):
        raise HTTPException(422, "'op' must be an object of OperatingPoint fields")
    job_id = body.get("job_id") or uuid.uuid4().hex[:12]
    if not isinstance(job_id, str):
        raise HTTPException(422, "'job_id' must be a string")

    try:
        op_dict = OperatingPoint.from_dict(op).to_dict()
        assembly = build_assembly(
            name=body.get("name") or f"{device_name}_{body.get('topology', 'half_bridge')}",
            device=entry.device,
            topology=body.get("topology", "half_bridge"),
            Rth_cs=float(body.get("Rth_cs", 0.2)),
            Rth_sa=float(body.get("Rth_sa", 0.0)),
            T_amb_C=float(body.get("T_amb_C", op_dict.get("T_amb_C", 25.0))),
        )
        if info.validate is not None:
            info.validate(assembly)
    except (KeyError, ValueError, TypeError) as e:
        raise HTTPException(400, str(e)) from None

    config = RunConfig(assembly=assembly, model=model, op=op_dict)
    result_id = compute_run_id(config)
    log.info("job_start", job_id=job_id, model=model, device=device_name, result_id=result_id)
    result = await asyncio.to_thread(run_model, info, config)
    _store(request).save(result)

    msg: ServerMsg
    if result.status == "OK":
        msg = {"type": "job_complete", "job_id": job_id, "result_ids": [result_id]}
    else:
        msg = {"type": "job_failed", "job_id": job_id, "error": result.error_msg or "error"}
        response.status_code = 200
    await request.app.state.ws_manager.broadcast(msg)
    log.info("job_done", job_id=job_id, status=result.status, elapsed_s=round(result.elapsed_s, 4))
    return {
        "job_id": job_id,
        "status": "completed" if result.status == "OK" else "failed",
        "result_id": result_id,
        "assembly_config_id": assembly.config_id,
        "metrics": result.metrics,
        "error": result.error_msg,
        "elapsed_s": result.elapsed_s,
    }
