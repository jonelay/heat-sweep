"""heatsweep -- power-electronics thermal design exploration.

Public API: device/assembly types, TOML loaders, the model registry,
and run/result types.
"""

from heatsweep.components.assembly import Assembly
from heatsweep.components.device import Device, load_device_toml
from heatsweep.components.operating_point import OperatingPoint
from heatsweep.devices import bundled_device_path
from heatsweep.models.thermal import CauerPair, foster_to_cauer, zth_cauer, zth_foster
from heatsweep.registry import MODEL_REGISTRY, ModelInfo
from heatsweep.result_store import ResultStore
from heatsweep.run_types import RunConfig, RunResult, compute_run_id

__version__ = "0.1.0"

_DEBUG_DEPS = ("numpy", "scipy", "gmsh", "matplotlib", "fastapi")


def _dep_version(module: str) -> str:
    import importlib

    try:
        mod = importlib.import_module(module)
    except ModuleNotFoundError:
        return "not installed"
    except Exception as e:
        return f"broken ({type(e).__name__}: {e})"
    return getattr(mod, "__version__", "installed")


def debug_info() -> None:
    """Print environment info for bug reports."""
    import platform

    print(f"heatsweep  : {__version__}")
    print(f"python     : {platform.python_version()} ({platform.python_implementation()})")
    print(f"platform   : {platform.platform()}")
    for dep in _DEBUG_DEPS:
        print(f"{dep:<11}: {_dep_version(dep)}")


__all__ = [
    "MODEL_REGISTRY",
    "Assembly",
    "CauerPair",
    "Device",
    "ModelInfo",
    "OperatingPoint",
    "ResultStore",
    "RunConfig",
    "RunResult",
    "__version__",
    "bundled_device_path",
    "compute_run_id",
    "debug_info",
    "foster_to_cauer",
    "load_device_toml",
    "zth_cauer",
    "zth_foster",
]
