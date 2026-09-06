"""Operating point for power electronics loss calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OperatingPoint:
    """Electrical and thermal operating point for loss calculations.

    All currents are rms unless the field name says _peak.
    Temperatures in degC for absolute values.
    """

    f_sw_Hz: float  # switching frequency
    V_dc: float  # DC bus voltage
    I_phase_rms: float  # phase current (rms)
    f_out_Hz: float  # output fundamental frequency
    pf: float  # power factor (cos phi)
    m_index: float  # modulation index (0..1 for linear)
    modulation: str = "spwm"  # modulation scheme
    t_dead_s: float = 1e-6  # dead time
    R_g_on: float = 10.0  # gate resistance turn-on (Ohm)
    R_g_off: float = 10.0  # gate resistance turn-off (Ohm)
    T_amb_C: float = 25.0  # ambient temperature
    Tj_assumed_C: float = 100.0  # assumed junction temperature for loss calc

    def __post_init__(self) -> None:
        for name in ("f_sw_Hz", "V_dc", "I_phase_rms", "f_out_Hz", "pf",
                     "m_index", "t_dead_s", "R_g_on", "R_g_off",
                     "T_amb_C", "Tj_assumed_C"):
            v = getattr(self, name)
            if not math.isfinite(v):
                raise ValueError(f"{name} must be finite, got {v}")
        if self.f_sw_Hz <= 0:
            raise ValueError(f"f_sw_Hz must be > 0, got {self.f_sw_Hz}")
        if self.V_dc <= 0:
            raise ValueError(f"V_dc must be > 0, got {self.V_dc}")
        if self.I_phase_rms < 0:
            raise ValueError(f"I_phase_rms must be >= 0, got {self.I_phase_rms}")
        if not (-1.0 <= self.pf <= 1.0):
            raise ValueError(f"pf must be in [-1, 1], got {self.pf}")
        if self.m_index < 0:
            raise ValueError(f"m_index must be >= 0, got {self.m_index}")
        if self.modulation == "spwm" and self.m_index > 1.0:
            raise ValueError(
                f"m_index must be <= 1.0 for SPWM (linear range), got {self.m_index}; "
                f"use a different modulation scheme for overmodulation"
            )
        if self.t_dead_s < 0:
            raise ValueError(f"t_dead_s must be >= 0, got {self.t_dead_s}")
        if self.R_g_on <= 0:
            raise ValueError(f"R_g_on must be > 0, got {self.R_g_on}")
        if self.R_g_off <= 0:
            raise ValueError(f"R_g_off must be > 0, got {self.R_g_off}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "f_sw_Hz": self.f_sw_Hz,
            "V_dc": self.V_dc,
            "I_phase_rms": self.I_phase_rms,
            "f_out_Hz": self.f_out_Hz,
            "pf": self.pf,
            "m_index": self.m_index,
            "modulation": self.modulation,
            "t_dead_s": self.t_dead_s,
            "R_g_on": self.R_g_on,
            "R_g_off": self.R_g_off,
            "T_amb_C": self.T_amb_C,
            "Tj_assumed_C": self.Tj_assumed_C,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> OperatingPoint:
        return cls(
            f_sw_Hz=d["f_sw_Hz"],
            V_dc=d["V_dc"],
            I_phase_rms=d["I_phase_rms"],
            f_out_Hz=d["f_out_Hz"],
            pf=d["pf"],
            m_index=d["m_index"],
            modulation=d.get("modulation", "spwm"),
            t_dead_s=d.get("t_dead_s", 1e-6),
            R_g_on=d.get("R_g_on", 10.0),
            R_g_off=d.get("R_g_off", 10.0),
            T_amb_C=d.get("T_amb_C", 25.0),
            Tj_assumed_C=d.get("Tj_assumed_C", 100.0),
        )
