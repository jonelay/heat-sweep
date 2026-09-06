"""Semiconductor device model loaded from TOML.

A Device carries datasheet-derived conduction, switching, body-diode, and
thermal parameters. Every curve table carries its test conditions; the
loader validates completeness and physical consistency.
"""

from __future__ import annotations

import hashlib
import json
import math
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TableEntry:
    """A 1-D lookup table with test conditions."""

    x: tuple[float, ...]
    y: tuple[float, ...]
    x_label: str
    y_label: str
    conditions: dict[str, float]

    def __post_init__(self) -> None:
        if len(self.x) != len(self.y):
            raise ValueError(
                f"Table {self.y_label} vs {self.x_label}: x and y lengths differ "
                f"({len(self.x)} vs {len(self.y)})"
            )
        if len(self.x) < 2:
            raise ValueError(f"Table {self.y_label} vs {self.x_label}: need >= 2 rows, got {len(self.x)}")
        for i, v in enumerate(self.x):
            if not math.isfinite(v):
                raise ValueError(f"Table {self.x_label}[{i}] is not finite: {v}")
        for i, v in enumerate(self.y):
            if not math.isfinite(v):
                raise ValueError(f"Table {self.y_label}[{i}] is not finite: {v}")
        for i in range(1, len(self.x)):
            if self.x[i] <= self.x[i - 1]:
                raise ValueError(
                    f"Table {self.x_label} not strictly increasing at index {i}: "
                    f"{self.x[i - 1]} >= {self.x[i]}"
                )
        if not self.conditions:
            raise ValueError(f"Table {self.y_label}: missing test conditions")


@dataclass(frozen=True)
class FosterPair:
    """One term in a Foster thermal impedance model."""

    R: float  # K/W
    tau: float  # s


@dataclass(frozen=True)
class Device:
    """Semiconductor device with datasheet parameters.

    Fields mirror the Device TOML schema sections:
    [device], [conduction], [body_diode], [switching], [thermal].
    """

    # Identity
    name: str
    device_type: str  # "mosfet" or "igbt"
    package: str
    manufacturer: str

    # Absolute maximum ratings
    V_max: float  # V
    I_max: float  # A
    Tj_max: float  # degC

    # Conduction -- MOSFET
    R_ds_on_vs_Tj: TableEntry | None = None  # R_ds_on(Tj) table
    # Conduction -- IGBT
    V_ce0: float | None = None  # V (threshold voltage)
    r_ce: float | None = None  # Ohm (slope resistance)
    V_ce0_conditions: dict[str, float] = field(default_factory=dict)
    V_ce0_vs_Tj: TableEntry | None = None  # V_ce0(Tj) table
    r_ce_vs_Tj: TableEntry | None = None  # r_ce(Tj) table

    # Body diode
    V_f: float = 0.7  # V (forward voltage)
    Q_rr: float = 0.0  # C (reverse recovery charge)
    V_f_conditions: dict[str, float] = field(default_factory=dict)

    # Switching
    E_on_vs_I: TableEntry | None = None
    E_off_vs_I: TableEntry | None = None
    switching_scaling: str = "linear"  # scaling rule name
    E_on_k_Tj: float = 0.0  # /K — linear tempco for E_on
    E_off_k_Tj: float = 0.0  # /K — linear tempco for E_off
    Q_rr_k_Tj: float = 0.0  # /K — linear tempco for Q_rr

    # Thermal
    Rth_jc: float = 0.0  # K/W (junction to case)
    Zth_jc_foster: tuple[FosterPair, ...] = ()

    def __post_init__(self) -> None:
        for fp in self.Zth_jc_foster:
            if not (math.isfinite(fp.R) and fp.R > 0):
                raise ValueError(f"Foster R must be positive and finite, got {fp.R}")
            if not (math.isfinite(fp.tau) and fp.tau > 0):
                raise ValueError(f"Foster tau must be positive and finite, got {fp.tau}")
        if self.Zth_jc_foster and self.Rth_jc > 0:
            foster_sum = sum(p.R for p in self.Zth_jc_foster)
            if abs(foster_sum - self.Rth_jc) / self.Rth_jc > 0.05:
                raise ValueError(
                    f"Foster sum {foster_sum:.4f} K/W does not match "
                    f"Rth_jc {self.Rth_jc:.4f} K/W (tolerance 5%)"
                )
        tj_tables = [t for t in [self.R_ds_on_vs_Tj, self.V_ce0_vs_Tj,
                                   self.r_ce_vs_Tj] if t is not None]
        for t in tj_tables:
            if t.x_label == "Tj" and max(t.x) > self.Tj_max:
                raise ValueError(
                    f"Table {t.y_label}: max Tj in table ({max(t.x)}) "
                    f"exceeds device Tj_max ({self.Tj_max})"
                )

    @property
    def config_id(self) -> str:
        """Stable hash of all device parameters."""
        d = self.to_dict()
        raw = json.dumps(d, sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "device_type": self.device_type,
            "package": self.package,
            "manufacturer": self.manufacturer,
            "V_max": self.V_max,
            "I_max": self.I_max,
            "Tj_max": self.Tj_max,
            "V_f": self.V_f,
            "Q_rr": self.Q_rr,
            "switching_scaling": self.switching_scaling,
            "E_on_k_Tj": self.E_on_k_Tj,
            "E_off_k_Tj": self.E_off_k_Tj,
            "Q_rr_k_Tj": self.Q_rr_k_Tj,
            "Rth_jc": self.Rth_jc,
        }
        if self.R_ds_on_vs_Tj is not None:
            d["R_ds_on_vs_Tj"] = {
                "x": list(self.R_ds_on_vs_Tj.x),
                "y": list(self.R_ds_on_vs_Tj.y),
                "conditions": self.R_ds_on_vs_Tj.conditions,
            }
        if self.V_ce0 is not None:
            d["V_ce0"] = self.V_ce0
            d["r_ce"] = self.r_ce
            d["V_ce0_conditions"] = self.V_ce0_conditions
        if self.V_ce0_vs_Tj is not None:
            d["V_ce0_vs_Tj"] = {
                "x": list(self.V_ce0_vs_Tj.x),
                "y": list(self.V_ce0_vs_Tj.y),
                "conditions": self.V_ce0_vs_Tj.conditions,
            }
        if self.r_ce_vs_Tj is not None:
            d["r_ce_vs_Tj"] = {
                "x": list(self.r_ce_vs_Tj.x),
                "y": list(self.r_ce_vs_Tj.y),
                "conditions": self.r_ce_vs_Tj.conditions,
            }
        if self.E_on_vs_I is not None:
            d["E_on_vs_I"] = {
                "x": list(self.E_on_vs_I.x),
                "y": list(self.E_on_vs_I.y),
                "conditions": self.E_on_vs_I.conditions,
            }
        if self.E_off_vs_I is not None:
            d["E_off_vs_I"] = {
                "x": list(self.E_off_vs_I.x),
                "y": list(self.E_off_vs_I.y),
                "conditions": self.E_off_vs_I.conditions,
            }
        if self.Zth_jc_foster:
            d["Zth_jc_foster"] = [{"R": p.R, "tau": p.tau} for p in self.Zth_jc_foster]
        if self.V_f_conditions:
            d["V_f_conditions"] = self.V_f_conditions
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Device:
        rds = None
        if "R_ds_on_vs_Tj" in d:
            t = d["R_ds_on_vs_Tj"]
            rds = TableEntry(
                x=tuple(t["x"]), y=tuple(t["y"]),
                x_label="Tj", y_label="R_ds_on",
                conditions=t.get("conditions", {}),
            )
        e_on = None
        if "E_on_vs_I" in d:
            t = d["E_on_vs_I"]
            e_on = TableEntry(
                x=tuple(t["x"]), y=tuple(t["y"]),
                x_label="I", y_label="E_on",
                conditions=t.get("conditions", {}),
            )
        e_off = None
        if "E_off_vs_I" in d:
            t = d["E_off_vs_I"]
            e_off = TableEntry(
                x=tuple(t["x"]), y=tuple(t["y"]),
                x_label="I", y_label="E_off",
                conditions=t.get("conditions", {}),
            )
        v_ce0_vs_tj = None
        if "V_ce0_vs_Tj" in d:
            t = d["V_ce0_vs_Tj"]
            v_ce0_vs_tj = TableEntry(
                x=tuple(t["x"]), y=tuple(t["y"]),
                x_label="Tj", y_label="V_ce0",
                conditions=t.get("conditions", {}),
            )
        r_ce_vs_tj = None
        if "r_ce_vs_Tj" in d:
            t = d["r_ce_vs_Tj"]
            r_ce_vs_tj = TableEntry(
                x=tuple(t["x"]), y=tuple(t["y"]),
                x_label="Tj", y_label="r_ce",
                conditions=t.get("conditions", {}),
            )
        foster: tuple[FosterPair, ...] = ()
        if "Zth_jc_foster" in d:
            foster = tuple(FosterPair(R=p["R"], tau=p["tau"]) for p in d["Zth_jc_foster"])
        return cls(
            name=d["name"],
            device_type=d["device_type"],
            package=d["package"],
            manufacturer=d["manufacturer"],
            V_max=d["V_max"],
            I_max=d["I_max"],
            Tj_max=d["Tj_max"],
            R_ds_on_vs_Tj=rds,
            V_ce0=d.get("V_ce0"),
            r_ce=d.get("r_ce"),
            V_ce0_conditions=d.get("V_ce0_conditions", {}),
            V_ce0_vs_Tj=v_ce0_vs_tj,
            r_ce_vs_Tj=r_ce_vs_tj,
            V_f=d.get("V_f", 0.7),
            Q_rr=d.get("Q_rr", 0.0),
            V_f_conditions=d.get("V_f_conditions", {}),
            E_on_vs_I=e_on,
            E_off_vs_I=e_off,
            switching_scaling=d.get("switching_scaling", "linear"),
            E_on_k_Tj=d.get("E_on_k_Tj", 0.0),
            E_off_k_Tj=d.get("E_off_k_Tj", 0.0),
            Q_rr_k_Tj=d.get("Q_rr_k_Tj", 0.0),
            Rth_jc=d.get("Rth_jc", 0.0),
            Zth_jc_foster=foster,
        )


def _parse_table(section: dict[str, Any], x_key: str, y_key: str,
                 x_label: str, y_label: str) -> TableEntry:
    """Parse a table from TOML section with x, y arrays and conditions."""
    x = tuple(float(v) for v in section[x_key])
    y = tuple(float(v) for v in section[y_key])
    conditions = {k: float(v) for k, v in section.get("conditions", {}).items()}
    return TableEntry(x=x, y=y, x_label=x_label, y_label=y_label, conditions=conditions)


def _validate_foster_sum(foster: tuple[FosterPair, ...], rth_jc: float,
                         tol: float = 0.05) -> None:
    """Validate that sum of Foster R_i matches Rth_jc within tolerance."""
    if not foster:
        return
    foster_sum = sum(p.R for p in foster)
    if rth_jc > 0 and abs(foster_sum - rth_jc) / rth_jc > tol:
        raise ValueError(
            f"Foster sum {foster_sum:.4f} K/W does not match "
            f"Rth_jc {rth_jc:.4f} K/W (tolerance {tol*100:.0f}%)"
        )


def _validate_tj_max(tables: list[TableEntry], tj_max: float) -> None:
    """Validate that Tj_max >= max Tj in any table that uses Tj as x."""
    for t in tables:
        if t.x_label == "Tj" and max(t.x) > tj_max:
            raise ValueError(
                f"Table {t.y_label}: max Tj in table ({max(t.x)}) "
                f"exceeds device Tj_max ({tj_max})"
            )


def load_device_toml(path: str | Path) -> Device:
    """Load a Device from a TOML file, validating all fields."""
    path = Path(path)
    with open(path, "rb") as f:
        data = tomllib.load(f)

    dev = data["device"]
    cond = data.get("conduction", {})
    diode = data.get("body_diode", {})
    sw = data.get("switching", {})
    therm = data.get("thermal", {})

    device_type = dev["type"]

    # Conduction
    rds = None
    v_ce0 = None
    r_ce = None
    v_ce0_conditions: dict[str, float] = {}
    if device_type == "mosfet":
        rds = _parse_table(cond, "Tj", "R_ds_on", "Tj", "R_ds_on")
    elif device_type == "igbt":
        v_ce0 = float(cond["V_ce0"])
        r_ce = float(cond["r_ce"])
        v_ce0_conditions = {k: float(v) for k, v in cond.get("conditions", {}).items()}
        if not v_ce0_conditions:
            raise ValueError("IGBT conduction: missing test conditions")

    # Optional Tj-dependent IGBT conduction tables
    v_ce0_vs_tj = None
    r_ce_vs_tj = None
    if device_type == "igbt":
        if "V_ce0_vs_Tj" in cond:
            v_ce0_vs_tj = _parse_table(cond["V_ce0_vs_Tj"], "Tj", "V_ce0", "Tj", "V_ce0")
        if "r_ce_vs_Tj" in cond:
            r_ce_vs_tj = _parse_table(cond["r_ce_vs_Tj"], "Tj", "r_ce", "Tj", "r_ce")

    # Switching
    e_on = None
    e_off = None
    if sw:
        e_on = _parse_table(sw, "I", "E_on", "I", "E_on")
        e_off = _parse_table(sw, "I", "E_off", "I", "E_off")

    # Thermal
    foster_pairs: tuple[FosterPair, ...] = ()
    rth_jc = float(therm.get("Rth_jc", 0.0))
    if "Zth_jc_foster" in therm:
        foster_pairs = tuple(
            FosterPair(R=float(p["R"]), tau=float(p["tau"]))
            for p in therm["Zth_jc_foster"]
        )

    tj_max = float(dev["Tj_max"])

    # Validate Tj_max against tables
    tj_tables = [t for t in [rds, v_ce0_vs_tj, r_ce_vs_tj] if t is not None]
    _validate_tj_max(tj_tables, tj_max)

    # Validate Foster sum
    _validate_foster_sum(foster_pairs, rth_jc)

    # Body diode
    v_f = float(diode.get("V_f", 0.7))
    q_rr = float(diode.get("Q_rr", 0.0))
    v_f_conditions = {k: float(v) for k, v in diode.get("conditions", {}).items()}

    return Device(
        name=dev["name"],
        device_type=device_type,
        package=dev["package"],
        manufacturer=dev["manufacturer"],
        V_max=float(dev["V_max"]),
        I_max=float(dev["I_max"]),
        Tj_max=tj_max,
        R_ds_on_vs_Tj=rds,
        V_ce0=v_ce0,
        r_ce=r_ce,
        V_ce0_conditions=v_ce0_conditions,
        V_ce0_vs_Tj=v_ce0_vs_tj,
        r_ce_vs_Tj=r_ce_vs_tj,
        V_f=v_f,
        Q_rr=q_rr,
        V_f_conditions=v_f_conditions,
        E_on_vs_I=e_on,
        E_off_vs_I=e_off,
        switching_scaling=sw.get("scaling", "linear"),
        E_on_k_Tj=float(sw.get("k_Tj_on", 0.0)),
        E_off_k_Tj=float(sw.get("k_Tj_off", 0.0)),
        Q_rr_k_Tj=float(diode.get("k_Tj", 0.0)),
        Rth_jc=rth_jc,
        Zth_jc_foster=foster_pairs,
    )
