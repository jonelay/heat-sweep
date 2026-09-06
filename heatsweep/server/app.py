"""FastAPI app factory: settings and domain lifespan on top of the
view-sweep app factory.

view-sweep owns the generic layer -- WebSocket connection manager, local-
only Host/Origin guard, logging, static mounts. This module owns what is
heat-sweep's: the device catalogue, the result store, and the dashboard
tree.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import structlog
from fastapi import FastAPI
from view_sweep_server import AppConfig
from view_sweep_server import create_app as create_view_sweep_app

from heatsweep.components.device import Device, load_device_toml
from heatsweep.result_store import ResultStore
from heatsweep.server.routes import api

log = structlog.get_logger()


@dataclass(frozen=True)
class ServerSettings:
    devices_dir: Path = Path("devices")
    output_dir: Path = Path("results")
    log_json: bool = False
    extra_allowed_hosts: tuple[str, ...] = ()


class DeviceEntry(NamedTuple):
    """One catalogue entry: the loaded Device, its TOML, and the optional
    FEM thermal stack that lives beside it."""

    device: Device
    path: Path
    stack_path: Path | None


def load_device_catalogue(devices_dir: Path) -> dict[str, DeviceEntry]:
    """Devices keyed by TOML filename stem.

    Accepts both layouts heat-sweep uses: ``<dir>/<name>/<name>.toml``
    (bundled devices, with README and thermal_stack.toml beside it) and
    flat ``<dir>/<name>.toml``. Invalid files are skipped with a warning
    so one bad TOML cannot keep the server from starting.
    """
    devices_dir = Path(devices_dir)
    out: dict[str, DeviceEntry] = {}
    if not devices_dir.is_dir():
        log.warning("devices_dir_missing", path=str(devices_dir))
        return out
    candidates = sorted(devices_dir.glob("*.toml"))
    candidates += sorted(p / f"{p.name}.toml" for p in devices_dir.iterdir() if p.is_dir())
    for p in candidates:
        if not p.is_file():
            continue
        try:
            dev = load_device_toml(p)
        except (KeyError, ValueError, TypeError) as e:
            log.warning("device_skipped", file=str(p), error=str(e))
            continue
        stack = p.parent / "thermal_stack.toml"
        out[p.stem] = DeviceEntry(dev, p, stack if stack.is_file() else None)
    return out


def create_app(settings: ServerSettings | None = None) -> FastAPI:
    settings = settings or ServerSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.devices = load_device_catalogue(settings.devices_dir)
        app.state.store = ResultStore(settings.output_dir)
        # app.state.ws_manager is created by view-sweep before we run.
        log.info("server_started", devices=len(app.state.devices),
                 output_dir=str(settings.output_dir))
        try:
            yield
        finally:
            log.info("server_stopped")

    dashboard = Path(__file__).resolve().parent.parent / "dashboard"
    app: FastAPI = create_view_sweep_app(AppConfig(
        title="heat-sweep server",
        routers=[api],
        lifespan=lifespan,
        static_dir=dashboard,
        allowed_hosts=settings.extra_allowed_hosts,
        log_json=settings.log_json,
    ))
    return app
