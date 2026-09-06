"""Model registry mapping model keys to metadata and solver functions.

Registry is a plain dict. No Protocol/ABC/plugin system.

Validation uses the prepare_* factories (each living next to its model's
run function) as the single source of truth: they validate Assembly
completeness and derive missing fields via shared utilities.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

    from heatsweep.components.assembly import Assembly
    from heatsweep.run_types import RunConfig


@dataclass(frozen=True)
class ModelInfo:
    """Metadata and execution hooks for one registered model.

    ``needs`` lists assembly fields required for applicability validation.
    ``needs_runtime`` lists additional ``RunConfig`` fields that have no
    usable default and whose absence makes the model runner raise.
    ``units`` maps each output key to its unit string.
    """

    name: str
    source: Literal["computed", "measured"]
    cost: Literal["fast", "medium", "slow", "none"]
    produces: frozenset[str]
    needs: frozenset[str]
    hash_fields: frozenset[str]
    units: Mapping[str, str] = field(default_factory=dict)
    needs_runtime: frozenset[str] = frozenset()
    version: int = 1
    validate: Callable[[Assembly], None] | None = None
    fn: Callable[[RunConfig], dict[str, Any]] | None = None
    batch_fn: Callable[[Sequence[RunConfig]], list[dict[str, Any] | Exception]] | None = None


# ---------------------------------------------------------------------------
# Validation via prepare_* factories (construct and discard)
# ---------------------------------------------------------------------------


def _validate_semiconductor_loss(assembly: Assembly) -> None:
    from heatsweep.models.semiconductor_loss import prepare_semiconductor_loss

    prepare_semiconductor_loss(assembly)


def _run_semiconductor_loss_impl(config: RunConfig) -> dict[str, Any]:
    from heatsweep.models.semiconductor_loss import run_semiconductor_loss

    return run_semiconductor_loss(config)


def _validate_thermal(assembly: Assembly) -> None:
    from heatsweep.models.thermal import prepare_thermal

    prepare_thermal(assembly)


def _run_thermal_impl(config: RunConfig) -> dict[str, Any]:
    from heatsweep.models.thermal import run_thermal

    return run_thermal(config)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

MODEL_REGISTRY: dict[str, ModelInfo] = {
    "semiconductor_loss": ModelInfo(
        name="semiconductor_loss",
        source="computed",
        cost="fast",
        produces=frozenset({
            "p_cond_W", "p_sw_on_W", "p_sw_off_W",
            "p_diode_cond_W", "p_rr_W", "p_total_W",
        }),
        needs=frozenset({"devices", "topology"}),
        hash_fields=frozenset({
            "f_sw_Hz", "V_dc", "I_phase_rms", "f_out_Hz",
            "pf", "m_index", "t_dead_s", "Tj_assumed_C",
        }),
        units={
            "p_cond_W": "W",
            "p_sw_on_W": "W",
            "p_sw_off_W": "W",
            "p_diode_cond_W": "W",
            "p_rr_W": "W",
            "p_total_W": "W",
        },
        version=1,
        validate=_validate_semiconductor_loss,
        fn=_run_semiconductor_loss_impl,
    ),
    "thermal": ModelInfo(
        name="thermal",
        source="computed",
        cost="fast",
        produces=frozenset({
            "converged", "iterations", "thermally_stable",
            "T_sink_C", "p_total_W",
        }),
        needs=frozenset({"devices", "topology"}),
        hash_fields=frozenset({
            "f_sw_Hz", "V_dc", "I_phase_rms", "f_out_Hz",
            "pf", "m_index", "t_dead_s", "T_amb_C",
        }),
        units={
            "T_sink_C": "degC",
            "p_total_W": "W",
        },
        version=1,
        validate=_validate_thermal,
        fn=_run_thermal_impl,
    ),
}
