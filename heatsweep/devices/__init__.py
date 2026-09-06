"""Bundled device parameter files."""

from __future__ import annotations

import importlib.resources
from pathlib import Path


def bundled_device_path(name: str) -> Path:
    """Return the filesystem path to a bundled device TOML.

    >>> from heatsweep.devices import bundled_device_path
    >>> path = bundled_device_path("prius_2004_igbt")
    """
    ref = importlib.resources.files("heatsweep.devices") / name / f"{name}.toml"
    with importlib.resources.as_file(ref) as p:
        return Path(p)
