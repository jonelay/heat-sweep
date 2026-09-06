"""Type-safe, validated configuration and result objects for thermal runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from heatsweep.components.assembly import Assembly

Status = Literal["OK", "TIMEOUT", "ERROR"]
Source = Literal["computed", "measured", "published"]


@dataclass(frozen=True)
class RunConfig:
    """Run configuration composing an Assembly with operating point and model.

    assembly -- power stage assembly (devices + thermal interfaces)
    model -- registry key ("semiconductor_loss", ...)
    op -- operating point dict (serialized OperatingPoint fields)
    mission_profile -- optional time-varying load profile
    dataset_id -- identity of an imported measured dataset
    """

    assembly: Assembly
    model: str
    op: dict[str, Any] = field(default_factory=dict)
    mission_profile: tuple[tuple[float, ...], ...] | None = None
    dataset_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "assembly": self.assembly.to_dict(),
            "model": self.model,
            "op": self.op,
        }
        if self.mission_profile is not None:
            d["mission_profile"] = [list(seg) for seg in self.mission_profile]
        if self.dataset_id is not None:
            d["dataset_id"] = self.dataset_id
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RunConfig:
        from heatsweep.components.assembly import Assembly as AssemblyCls

        assembly = AssemblyCls.from_dict(d["assembly"])
        mission_profile = None
        if d.get("mission_profile") is not None:
            mission_profile = tuple(tuple(float(v) for v in seg) for seg in d["mission_profile"])
        return cls(
            assembly=assembly,
            model=d["model"],
            op=d.get("op", {}),
            mission_profile=mission_profile,
            dataset_id=d.get("dataset_id"),
        )


@dataclass
class RunResult:
    """Result from a single thermal run.

    metrics keys/units are model-specific (see MODEL_REGISTRY produces
    and units); elapsed_s -- wall-clock solve time (s).
    """

    config: RunConfig
    model: str
    status: Status
    metrics: dict[str, Any] | None
    elapsed_s: float
    error_msg: str | None = None
    source: Source = "computed"
    tolerances: dict[str, float] | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    model_version: int | None = None
    schema_version: str = "v1.0"

    @property
    def assembly_config_id(self) -> str:
        return self.config.assembly.config_id

    def to_dict(self) -> dict[str, Any]:
        d = {
            "config": self.config.to_dict(),
            "model": self.model,
            "source": self.source,
            "assembly_config_id": self.assembly_config_id,
            "status": self.status,
            "metrics": self.metrics,
            "elapsed_s": self.elapsed_s,
            "error_msg": self.error_msg,
            "timestamp": self.timestamp,
            "model_version": self.model_version,
            "schema_version": self.schema_version,
        }
        if self.tolerances:
            d["tolerances"] = self.tolerances
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RunResult:
        return cls(
            config=RunConfig.from_dict(d["config"]),
            model=d["model"],
            status=d["status"],
            metrics=d.get("metrics"),
            elapsed_s=d["elapsed_s"],
            error_msg=d.get("error_msg"),
            source=d.get("source", "computed"),
            tolerances=d.get("tolerances"),
            timestamp=d.get("timestamp", ""),
            model_version=d.get("model_version"),
            schema_version=d.get("schema_version", "v1.0"),
        )


def compute_run_id(
    rc: RunConfig, needs: frozenset[str] | None = None,
) -> str:
    """Model-aware run ID. Hashes assembly.config_id + model + relevant op params.

    When needs is None, looks up hash_fields from MODEL_REGISTRY automatically.
    Falls back to hashing all op params for unknown models.
    Includes the registry model-code version (when > 1) so results from a
    superseded physics convention cannot serve from the store.
    """
    from heatsweep.registry import MODEL_REGISTRY

    info = MODEL_REGISTRY.get(rc.model)
    if needs is None and info is not None:
        needs = info.hash_fields

    parts = [rc.assembly.config_id, rc.model]
    if info is not None and info.version > 1:
        parts.append(f"model_v={info.version}")
    if rc.dataset_id is not None:
        parts.append(f"dataset={rc.dataset_id}")

    op_params: dict[str, str] = {}
    for k, v in sorted(rc.op.items()):
        if isinstance(v, float):
            op_params[k] = f"{v:.10g}"
        else:
            op_params[k] = str(v)

    if rc.mission_profile is not None:
        op_params["mission_profile"] = json.dumps(
            [list(seg) for seg in rc.mission_profile], sort_keys=True,
        )

    if needs is not None:
        op_params = {k: v for k, v in op_params.items() if k in needs}

    for k in sorted(op_params):
        parts.append(f"{k}={op_params[k]}")

    key = "|".join(parts)
    return hashlib.md5(key.encode()).hexdigest()[:12]
