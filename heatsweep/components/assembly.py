"""Power stage assembly: topology + devices + thermal interfaces."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from heatsweep.components.device import Device


@dataclass(frozen=True)
class DevicePosition:
    """A device in a specific position within the assembly."""

    position: str  # e.g. "Q1_high", "Q2_low"
    device: Device
    Rth_cs: float = 0.0  # K/W case-to-sink
    R_path: float = 0.0  # Ohm parasitic (wire bond + trace + bus bar)


@dataclass(frozen=True)
class Assembly:
    """Power stage assembly: topology + device positions + thermal interface.

    topology -- e.g. "three_phase_bridge", "half_bridge", "full_bridge"
    name -- human-readable assembly name
    devices -- list of (position, device, Rth_cs) entries
    T_amb_C -- default ambient temperature (degC)
    """

    name: str
    topology: str
    devices: tuple[DevicePosition, ...] = ()
    T_amb_C: float = 25.0
    Rth_sa: float = 0.0  # K/W sink-to-ambient
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def config_id(self) -> str:
        """Stable hash of all assembly parameters."""
        d = self.to_dict()
        raw = json.dumps(d, sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "topology": self.topology,
            "devices": [
                {
                    "position": dp.position,
                    "device": dp.device.to_dict(),
                    "Rth_cs": dp.Rth_cs,
                    "R_path": dp.R_path,
                }
                for dp in self.devices
            ],
            "T_amb_C": self.T_amb_C,
            "Rth_sa": self.Rth_sa,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Assembly:
        devices = tuple(
            DevicePosition(
                position=dp["position"],
                device=Device.from_dict(dp["device"]),
                Rth_cs=dp.get("Rth_cs", 0.0),
                R_path=dp.get("R_path", 0.0),
            )
            for dp in d.get("devices", [])
        )
        return cls(
            name=d["name"],
            topology=d["topology"],
            devices=devices,
            T_amb_C=d.get("T_amb_C", 25.0),
            Rth_sa=d.get("Rth_sa", 0.0),
            metadata=d.get("metadata", {}),
        )
