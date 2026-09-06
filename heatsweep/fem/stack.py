"""Layered thermal stack description and 1-D analytic bounds.

The stack is the geometry a FEM model is built from and the reference
against which the FEM steady-state result is sanity-checked:

- ``rth_1d_bounds`` returns a (lower, upper) bracket on Rth junction-to-
  coolant. The lower bound assumes perfect spreading (every layer and the
  convective surface use the full modeled plate area); the upper bound
  assumes no spreading (everything confined to the die footprint). A
  converged FEM Rth must fall inside this bracket -- outside means a
  geometry, unit, or boundary-condition mistake, not physics.

Units: lengths m, k W/(m K), h W/(m^2 K), temperatures degC absolute /
K differences.
"""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Footprint = Literal["die", "tile", "plate"]


@dataclass(frozen=True)
class Layer:
    name: str
    material: str
    t_m: float
    k_W_mK: float
    rho_kg_m3: float
    cp_J_kgK: float
    footprint: Footprint

    def __post_init__(self) -> None:
        for f in ("t_m", "k_W_mK", "rho_kg_m3", "cp_J_kgK"):
            v = getattr(self, f)
            if not math.isfinite(v) or v <= 0:
                raise ValueError(f"layer {self.name!r}: {f} must be finite and > 0, got {v}")
        if self.footprint not in ("die", "tile", "plate"):
            raise ValueError(f"layer {self.name!r}: footprint must be die|tile|plate, got {self.footprint!r}")


@dataclass(frozen=True)
class ThermalStack:
    """Layers listed junction (top) to coolant (bottom)."""

    name: str
    layers: tuple[Layer, ...]
    die_w_m: float
    die_l_m: float
    tile_w_m: float
    tile_l_m: float
    plate_w_m: float
    plate_l_m: float
    h_conv_W_m2K: float
    T_coolant_C: float
    total_path_m: float | None = None
    path_tol: float = 0.02

    def __post_init__(self) -> None:
        if not self.layers:
            raise ValueError("stack has no layers")
        if not (self.die_w_m <= self.tile_w_m <= self.plate_w_m and self.die_l_m <= self.tile_l_m <= self.plate_l_m):
            raise ValueError("footprints must nest: die <= tile <= plate in both w and l")
        if self.layers[0].footprint != "die":
            raise ValueError("top layer must be the die (footprint='die')")
        if self.h_conv_W_m2K <= 0:
            raise ValueError("h_conv_W_m2K must be > 0")
        if self.total_path_m is not None:
            t = self.thickness_m
            if abs(t - self.total_path_m) > self.path_tol * self.total_path_m:
                raise ValueError(
                    f"layer thicknesses sum to {t * 1e3:.3f} mm but total_path_m is "
                    f"{self.total_path_m * 1e3:.3f} mm (tol {self.path_tol:.0%})"
                )

    @property
    def thickness_m(self) -> float:
        return sum(layer.t_m for layer in self.layers)

    @property
    def die_area_m2(self) -> float:
        return self.die_w_m * self.die_l_m

    @property
    def plate_area_m2(self) -> float:
        return self.plate_w_m * self.plate_l_m

    def footprint_dims(self, fp: Footprint) -> tuple[float, float]:
        if fp == "die":
            return self.die_w_m, self.die_l_m
        if fp == "tile":
            return self.tile_w_m, self.tile_l_m
        return self.plate_w_m, self.plate_l_m

    def z_bounds(self) -> list[tuple[float, float]]:
        """(z_bottom, z_top) per layer with the coolant face at z=0."""
        out: list[tuple[float, float]] = []
        z_top = self.thickness_m
        for layer in self.layers:
            out.append((z_top - layer.t_m, z_top))
            z_top -= layer.t_m
        return out


def rth_1d_bounds(stack: ThermalStack) -> tuple[float, float]:
    """(lower, upper) bracket on Rth junction-to-coolant in K/W.

    lower: full plate area everywhere (perfect spreading).
    upper: die area everywhere (no spreading).
    Both include the convective film 1/(h*A).
    """
    a_die = stack.die_area_m2
    a_plate = stack.plate_area_m2
    r_cond_die = sum(layer.t_m / (layer.k_W_mK * a_die) for layer in stack.layers)
    r_cond_plate = sum(layer.t_m / (layer.k_W_mK * a_plate) for layer in stack.layers)
    h = stack.h_conv_W_m2K
    lower = r_cond_plate + 1.0 / (h * a_plate)
    upper = r_cond_die + 1.0 / (h * a_die)
    return lower, upper


def load_stack_toml(path: str | Path) -> ThermalStack:
    path = Path(path)
    with open(path, "rb") as f:
        d = tomllib.load(f)
    g = d["geometry"]
    b = d["boundary"]
    layers = tuple(
        Layer(
            name=str(lay["name"]),
            material=str(lay["material"]),
            t_m=float(lay["t_m"]),
            k_W_mK=float(lay["k_W_mK"]),
            rho_kg_m3=float(lay["rho_kg_m3"]),
            cp_J_kgK=float(lay["cp_J_kgK"]),
            footprint=lay["footprint"],
        )
        for lay in d.get("layer", [])
    )
    return ThermalStack(
        name=path.stem,
        layers=layers,
        die_w_m=float(g["die_w_m"]),
        die_l_m=float(g["die_l_m"]),
        tile_w_m=float(g["tile_w_m"]),
        tile_l_m=float(g["tile_l_m"]),
        plate_w_m=float(g["plate_w_m"]),
        plate_l_m=float(g["plate_l_m"]),
        h_conv_W_m2K=float(b["h_conv_W_m2K"]),
        T_coolant_C=float(b["T_coolant_C"]),
        total_path_m=float(g["total_path_m"]) if "total_path_m" in g else None,
    )
