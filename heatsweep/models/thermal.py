"""Lumped-parameter thermal network (LPTN) model.

Physics scope:
- Foster-to-Cauer conversion via polynomial continued-fraction expansion
- Transient thermal impedance Zth(t) evaluation (Foster and Cauer forms)
- Steady-state Rth stack solve: Tj = T_amb + P*(Rth_jc + Rth_cs + Rth_sa)
- Self-consistent P(Tj) fixed-point iteration with thermal-runaway detection

The Foster model (parallel RC pairs) is a curve fit — it cannot be cascaded
with external thermal resistances. The Cauer model (physical RC ladder) can.
The conversion preserves the thermal impedance response; high-frequency
behaviour differs (Foster: Zth(0+)=0; Cauer: Zth(0+)>0) because the Foster
model is unphysical at very short times.

References:
- Infineon AN2008-03, T. Schuetze, "Thermal equivalent circuit models",
  v1.0, 2008 (supersedes AN2001-05). Origin of the rule that a datasheet
  Foster Zth_jc must not be concatenated with an external Rth_cs/Rth_sa:
  the partial-fraction coefficients are measured with a specific heat sink
  attached, so they already carry a boundary condition and the network
  nodes have no physical meaning. Its published Foster set anchors
  tests/test_anchor_infineon_thermal.py.
- Schweitzer & Pape, "Thermal Modelling" (Foster/Cauer equivalence)
- Semikron Application Manual, Chapter 5
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.linalg import expm

from heatsweep.components.assembly import Assembly
from heatsweep.components.device import FosterPair
from heatsweep.components.operating_point import OperatingPoint
from heatsweep.defaults import DEFAULTS

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CauerPair:
    """One stage of a Cauer RC thermal ladder (series R, shunt C)."""

    R: float  # K/W
    C: float  # J/K


@dataclass(frozen=True)
class ThermalResult:
    """Result of a self-consistent thermal solve."""

    converged: bool
    iterations: int
    thermally_stable: bool
    Tj_C: dict[str, float]       # per-position junction temperature
    T_case_C: dict[str, float]   # per-position case temperature
    T_sink_C: float              # shared heatsink temperature
    p_device_W: dict[str, float] # per-position total loss
    p_total_W: float             # assembly total loss
    loss_breakdown: dict[str, dict[str, float]]  # per-position loss detail


# ---------------------------------------------------------------------------
# Foster / Cauer transient impedance
# ---------------------------------------------------------------------------

def zth_foster(
    t: float | NDArray[np.floating[Any]],
    foster: tuple[FosterPair, ...],
) -> float | NDArray[np.floating[Any]]:
    """Evaluate Foster Zth(t) = sum(R_i * (1 - exp(-t/tau_i)))."""
    t_arr = np.asarray(t, dtype=np.float64)
    z = np.zeros_like(t_arr)
    for fp in foster:
        z += fp.R * (1.0 - np.exp(-t_arr / fp.tau))
    if np.ndim(t) == 0:
        return float(z)
    return z


def _cauer_state_space(
    cauer: tuple[CauerPair, ...],
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Build state-space (A, B, C) for a Cauer II RC ladder.

    Topology (Cauer II — shunt C first, then series R):
        P → node₀(C₁) ── R₁ ── node₁(C₂) ── R₂ ── ... ── nodeₙ₋₁(Cₙ) ── Rₙ ── GND

    State vector: x = [T₀, T₁, ..., Tₙ₋₁]  (node temperatures)
    Input: u = P (power into junction = node₀)
    Output: y = T₀ = junction temperature rise above ambient
    """
    n = len(cauer)
    A = np.zeros((n, n), dtype=np.float64)
    B = np.zeros(n, dtype=np.float64)

    for k in range(n):
        ck = cauer[k].C
        rk = cauer[k].R  # series R on the right side of this node

        if k == 0:
            A[0, 0] = -1.0 / (rk * ck)
            if n > 1:
                A[0, 1] = 1.0 / (rk * ck)
            B[0] = 1.0 / ck
        elif k == n - 1:
            r_prev = cauer[k - 1].R
            A[k, k - 1] = 1.0 / (r_prev * ck)
            A[k, k] = -(1.0 / r_prev + 1.0 / rk) / ck
        else:
            r_prev = cauer[k - 1].R
            A[k, k - 1] = 1.0 / (r_prev * ck)
            A[k, k] = -(1.0 / r_prev + 1.0 / rk) / ck
            A[k, k + 1] = 1.0 / (rk * ck)

    C_out = np.zeros(n, dtype=np.float64)
    C_out[0] = 1.0

    return A, B, C_out


def zth_cauer(
    t: float | NDArray[np.floating[Any]],
    cauer: tuple[CauerPair, ...],
) -> float | NDArray[np.floating[Any]]:
    """Evaluate Cauer Zth(t) via state-space simulation (unit step response).

    Returns the thermal impedance at each time in t for a unit power step.
    """
    if not cauer:
        if np.ndim(t) == 0:
            return 0.0
        return np.zeros_like(np.asarray(t), dtype=np.float64)

    A, B, C_out = _cauer_state_space(cauer)

    t_arr = np.asarray(t, dtype=np.float64)
    scalar = np.ndim(t) == 0
    t_flat = t_arr.ravel()

    z = np.empty_like(t_flat)
    for i, ti in enumerate(t_flat):
        if ti <= 0.0:
            z[i] = 0.0
        else:
            eAt = expm(A * ti)
            x = np.linalg.solve(A, (eAt - np.eye(len(A))) @ B)
            z[i] = float(C_out @ x)

    if scalar:
        return float(z[0])
    return z.reshape(t_arr.shape)


# ---------------------------------------------------------------------------
# Foster-to-Cauer conversion
# ---------------------------------------------------------------------------

def _poly_trim(p: NDArray[np.float64], tol: float = 1e-12) -> NDArray[np.float64]:
    """Trim leading coefficients that are negligible relative to the largest."""
    if len(p) == 0:
        return np.array([0.0])
    scale = np.max(np.abs(p))
    if scale == 0:
        return np.array([0.0])
    first_sig = 0
    for i in range(len(p)):
        if abs(p[i]) > tol * scale:
            first_sig = i
            break
    result = p[first_sig:]
    return result if len(result) > 0 else np.array([0.0])


def _poly_pad_sub(
    a: NDArray[np.float64], b: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Subtract polynomial b from a, padding to match lengths."""
    ml = max(len(a), len(b))
    ap = np.zeros(ml)
    ap[ml - len(a):] = a
    bp = np.zeros(ml)
    bp[ml - len(b):] = b
    return ap - bp


def foster_to_cauer(foster: tuple[FosterPair, ...]) -> tuple[CauerPair, ...]:
    """Convert Foster thermal impedance to Cauer II RC ladder.

    Uses polynomial continued-fraction expansion of Z(s) = N(s)/D(s)
    with frequency scaling for numerical stability.  At each step the
    polynomials are normalized so the largest coefficient is O(1).

    Returns n CauerPairs for n FosterPairs.  The Cauer II topology is:
        node_0(C_1) -- R_1 -- node_1(C_2) -- R_2 -- ... -- R_n -- GND
    """
    if not foster:
        return ()

    n = len(foster)

    # Scale s so the geometric mean time constant maps to 1
    taus = np.array([fp.tau for fp in foster])
    s_scale = float(np.exp(np.mean(np.log(taus))))  # geometric mean

    # Build Z(s') = N(s')/D(s') where s' = s * s_scale
    # Foster: Z = sum R_i/(1 + s'*(tau_i/s_scale))
    scaled_taus = taus / s_scale

    d_poly = np.array([1.0])
    for st in scaled_taus:
        d_poly = np.polymul(d_poly, [st, 1.0])

    n_poly = np.zeros(n + 1)
    rs = np.array([fp.R for fp in foster])
    for i in range(n):
        term = np.array([rs[i]])
        for j in range(n):
            if j != i:
                term = np.polymul(term, [scaled_taus[j], 1.0])
        padded = np.zeros(n + 1)
        padded[len(padded) - len(term):] = term
        n_poly += padded

    n_poly = _poly_trim(n_poly)
    d_poly = _poly_trim(d_poly)

    pairs: list[CauerPair] = []
    for _ in range(n):
        # Admittance step: extract C' (scaled)
        c_scaled = float(d_poly[0] / n_poly[0])

        # remainder = D - C'*s'*N
        cs_times_n = np.asarray(np.polymul([c_scaled, 0.0], n_poly), dtype=np.float64)
        rem = _poly_pad_sub(d_poly, cs_times_n)
        rem = _poly_trim(rem)

        # Impedance step: extract R
        r_val = float(n_poly[0] / rem[0])

        # remainder = N - R*rem
        r_times_rem = r_val * rem
        new_n = _poly_pad_sub(n_poly, r_times_rem)
        new_n = _poly_trim(new_n)

        if c_scaled <= 0 or r_val <= 0:
            raise ValueError(
                f"Foster-to-Cauer produced non-positive element "
                f"(C_scaled={c_scaled}, R={r_val}); "
                "input Foster pairs may be degenerate"
            )

        # Unscale: C_actual = C_scaled * s_scale (since C*s = C'*s')
        c_val = c_scaled * s_scale

        pairs.append(CauerPair(R=r_val, C=c_val))

        d_poly = rem
        n_poly = new_n

    return tuple(pairs)

    return tuple(pairs)


# ---------------------------------------------------------------------------
# Steady-state thermal solve
# ---------------------------------------------------------------------------

def steady_state_tj(
    p_W: float,
    rth_jc: float,
    rth_cs: float,
    rth_sa: float,
    t_amb_C: float,
) -> float:
    """Steady-state junction temperature for a single device.

    Tj = T_amb + P * (Rth_jc + Rth_cs + Rth_sa)
    """
    return t_amb_C + p_W * (rth_jc + rth_cs + rth_sa)


# ---------------------------------------------------------------------------
# Self-consistent P(Tj) fixed-point solver
# ---------------------------------------------------------------------------

def _compute_losses_at_tj(
    assembly: Assembly,
    op_base: dict[str, Any],
    tj_map: dict[str, float],
) -> dict[str, dict[str, float]]:
    """Compute per-device losses at given junction temperatures."""
    from heatsweep.models.semiconductor_loss import _compute_device_losses

    results: dict[str, dict[str, float]] = {}
    for dp in assembly.devices:
        tj = tj_map[dp.position]
        op_dict = dict(op_base)
        op_dict["Tj_assumed_C"] = tj
        op = OperatingPoint.from_dict(op_dict)
        results[dp.position] = _compute_device_losses(dp, op)
    return results


def prepare_thermal(assembly: Assembly) -> None:
    """Validate assembly has the fields needed for thermal solve."""
    from heatsweep.models.semiconductor_loss import prepare_semiconductor_loss

    prepare_semiconductor_loss(assembly)
    for dp in assembly.devices:
        if dp.device.Rth_jc <= 0:
            raise ValueError(
                f"Device {dp.device.name} at {dp.position}: "
                f"Rth_jc must be > 0 for thermal solve, got {dp.device.Rth_jc}"
            )


def solve_thermal_steady_state(
    assembly: Assembly,
    op_dict: dict[str, Any],
    max_iter: int | None = None,
    tol_K: float | None = None,
) -> ThermalResult:
    """Self-consistent P(Tj) fixed-point iteration.

    Shared-heatsink model:
        T_sink = T_amb + sum(P_i) * Rth_sa
        Tj_i   = T_sink + P_i * (Rth_jc_i + Rth_cs_i)

    Convergence: max |Tj_new - Tj_old| < tol_K across all positions.
    Thermal instability: Tj exceeds Tj_max for any device → flag but converge
    if possible.
    """
    thermal_cfg = DEFAULTS.get("thermal", {})
    if max_iter is None:
        max_iter = int(thermal_cfg.get("max_iter", 50))
    if tol_K is None:
        tol_K = float(thermal_cfg.get("tol_K", 0.01))

    prepare_thermal(assembly)

    t_amb = assembly.T_amb_C
    rth_sa = assembly.Rth_sa

    # Initial Tj guess from operating point
    tj_init = float(op_dict.get("Tj_assumed_C", 100.0))
    tj_map = {dp.position: tj_init for dp in assembly.devices}

    converged = False
    thermally_stable = True
    loss_breakdown: dict[str, dict[str, float]] = {}

    for iteration in range(1, max_iter + 1):  # noqa: B007
        loss_breakdown = _compute_losses_at_tj(assembly, op_dict, tj_map)

        p_total = sum(lb["p_total_W"] for lb in loss_breakdown.values())
        t_sink = t_amb + p_total * rth_sa

        tj_new: dict[str, float] = {}
        for dp in assembly.devices:
            p_dev = loss_breakdown[dp.position]["p_total_W"]
            tj_new[dp.position] = t_sink + p_dev * (dp.device.Rth_jc + dp.Rth_cs)

        max_delta = max(abs(tj_new[pos] - tj_map[pos]) for pos in tj_map)

        tj_map = tj_new

        if max_delta < tol_K:
            converged = True
            break

    for dp in assembly.devices:
        if tj_map[dp.position] > dp.device.Tj_max:
            thermally_stable = False

    p_device_W = {pos: loss_breakdown[pos]["p_total_W"] for pos in loss_breakdown}
    p_total = sum(p_device_W.values())
    t_sink = t_amb + p_total * rth_sa

    t_case: dict[str, float] = {}
    for dp in assembly.devices:
        t_case[dp.position] = t_sink + p_device_W[dp.position] * dp.Rth_cs

    return ThermalResult(
        converged=converged,
        iterations=iteration,
        thermally_stable=thermally_stable,
        Tj_C=tj_map,
        T_case_C=t_case,
        T_sink_C=t_sink,
        p_device_W=p_device_W,
        p_total_W=p_total,
        loss_breakdown=loss_breakdown,
    )


# ---------------------------------------------------------------------------
# Registry-compatible run function
# ---------------------------------------------------------------------------

def run_thermal(config: Any) -> dict[str, Any]:
    """Run thermal model for registry dispatch.

    config.assembly -- Assembly with devices and Rth_sa
    config.op -- dict with OperatingPoint fields
    """
    assembly: Assembly = config.assembly
    result = solve_thermal_steady_state(assembly, config.op)

    out: dict[str, Any] = {
        "converged": result.converged,
        "iterations": result.iterations,
        "thermally_stable": result.thermally_stable,
        "T_sink_C": result.T_sink_C,
        "p_total_W": result.p_total_W,
    }
    for pos in result.Tj_C:
        out[f"{pos}_Tj_C"] = result.Tj_C[pos]
        out[f"{pos}_T_case_C"] = result.T_case_C[pos]
        out[f"{pos}_p_total_W"] = result.p_device_W[pos]
    for pos, breakdown in result.loss_breakdown.items():
        for k, v in breakdown.items():
            out[f"{pos}_{k}"] = v

    return out
