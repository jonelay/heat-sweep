"""Semiconductor loss model v1: conduction + switching + body diode.

Physics scope:
- Conduction: closed-form sinusoidal-PWM averages with R_ds_on(Tj) or V_ce0/r_ce
- Switching: numerically integrated over the conduction half-cycle
- Reverse recovery: 0.5 * f_sw * Q_rr * V_dc (half-cycle)
- Body diode conduction over dead time
- Tj fixed (no thermal feedback loop)

MOSFET model assumes synchronous rectification: the channel conducts whenever
its gate is ON (duty d), regardless of current polarity. P_cond = R*I_rms^2/2
per device — the m*cos(phi) terms cancel over a full fundamental period.

References:
- Infineon AN2019-05: MOSFET and IGBT gate driver loss calculation
- Semikron Application Manual, Chapter 5: Thermal design
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.interpolate import interp1d

from heatsweep.components.assembly import Assembly, DevicePosition
from heatsweep.components.device import Device
from heatsweep.components.operating_point import OperatingPoint


def prepare_semiconductor_loss(assembly: Assembly) -> None:
    """Validate that the assembly has the fields needed for loss calculation.

    Construct-and-discard pattern: raises ValueError on problems.
    """
    if not assembly.devices:
        raise ValueError("Assembly has no devices")
    for dp in assembly.devices:
        dev = dp.device
        if dev.device_type == "mosfet":
            if dev.R_ds_on_vs_Tj is None:
                raise ValueError(f"Device {dev.name} (MOSFET): missing R_ds_on_vs_Tj table")
        elif dev.device_type == "igbt":
            if dev.V_ce0 is None or dev.r_ce is None:
                raise ValueError(f"Device {dev.name} (IGBT): missing V_ce0 or r_ce")
        else:
            raise ValueError(f"Device {dev.name}: unknown type '{dev.device_type}'")
        if dev.E_on_vs_I is None or dev.E_off_vs_I is None:
            raise ValueError(f"Device {dev.name}: missing switching energy tables")


def _interp_rds_on(dev: Device, tj: float) -> float:
    """Interpolate R_ds_on at given Tj, clamped to the table domain."""
    assert dev.R_ds_on_vs_Tj is not None
    t = dev.R_ds_on_vs_Tj
    tj_clamped = max(float(t.x[0]), min(float(t.x[-1]), tj))
    f = interp1d(t.x, t.y, kind="linear")
    val = float(f(tj_clamped))
    if val <= 0:
        raise RuntimeError(
            f"R_ds_on interpolation returned {val} at Tj={tj_clamped}; "
            f"table data may be invalid"
        )
    return val


def _interp_v_ce0(dev: Device, tj: float) -> float:
    """Interpolate V_ce0 at given Tj, clamped to the table domain."""
    assert dev.V_ce0_vs_Tj is not None
    t = dev.V_ce0_vs_Tj
    tj_clamped = max(float(t.x[0]), min(float(t.x[-1]), tj))
    f = interp1d(t.x, t.y, kind="linear")
    return float(f(tj_clamped))


def _interp_r_ce(dev: Device, tj: float) -> float:
    """Interpolate r_ce at given Tj, clamped to the table domain."""
    assert dev.r_ce_vs_Tj is not None
    t = dev.r_ce_vs_Tj
    tj_clamped = max(float(t.x[0]), min(float(t.x[-1]), tj))
    f = interp1d(t.x, t.y, kind="linear")
    val = float(f(tj_clamped))
    if val <= 0:
        raise RuntimeError(
            f"r_ce interpolation returned {val} at Tj={tj_clamped}; "
            f"table data may be invalid"
        )
    return val


def _interp_energy(table_entry: Any, i_val: float) -> float:
    """Interpolate switching energy at given current."""
    f = interp1d(table_entry.x, table_entry.y, kind="linear", fill_value="extrapolate")
    return float(max(0.0, f(i_val)))


def conduction_loss_mosfet_closed_form(
    r_ds_on: float, i_rms: float, m: float, phi: float,
) -> float:
    """Closed-form MOSFET conduction loss for sinusoidal PWM (one device).

    Assumes synchronous rectification: the upper device channel conducts
    whenever its gate is ON (duty d = 0.5*(1+m*sin(theta))), regardless
    of current polarity.

    P = R I_p^2 / (2pi) * integral_0^{2pi} sin^2(theta-phi) * d dtheta

    The sin^2 * sin cross term integrates to zero over a full period, so
    the m*cos(phi) terms from positive and negative half-cycles cancel:

        P_cond = R * I_p^2 / 4 = R * I_rms^2 / 2
    """
    return 0.5 * r_ds_on * i_rms**2


def conduction_loss_mosfet_numerical(
    r_ds_on: float, i_rms: float, m: float, phi: float, n_points: int = 10000,
) -> float:
    """Numerical time-domain integration of MOSFET conduction loss.

    Sync-rect model: channel conducts whenever its gate is ON (duty d),
    regardless of current direction.
    """
    i_peak = i_rms * math.sqrt(2.0)
    theta = np.linspace(0, 2.0 * np.pi, n_points, endpoint=False)
    current = i_peak * np.sin(theta - phi)
    duty = 0.5 * (1.0 + m * np.sin(theta))

    p_inst = r_ds_on * current**2 * duty

    return float(np.mean(p_inst))


def _avg_switching_energy(dev: Device, i_peak: float, n_quad: int = 128) -> tuple[float, float]:
    """Average E_on and E_off over the conduction half-cycle [0, pi].

    A half-bridge switch hard-commutates only during the half-cycle it carries
    current. The average per switching period is:
        E_avg = (1/2pi) * integral_0^pi E(I_peak * sin(u)) du
    """
    assert dev.E_on_vs_I is not None and dev.E_off_vs_I is not None
    u = np.linspace(0, np.pi, n_quad, endpoint=False) + np.pi / (2 * n_quad)
    i_vals = i_peak * np.sin(u)
    e_on_sum = sum(_interp_energy(dev.E_on_vs_I, float(iv)) for iv in i_vals)
    e_off_sum = sum(_interp_energy(dev.E_off_vs_I, float(iv)) for iv in i_vals)
    e_on_avg = float(e_on_sum) / (2.0 * n_quad)
    e_off_avg = float(e_off_sum) / (2.0 * n_quad)
    return e_on_avg, e_off_avg


def _compute_device_losses(
    dp: DevicePosition, op: OperatingPoint,
) -> dict[str, float]:
    """Compute all loss components for a single device position."""
    dev = dp.device
    phi = math.acos(op.pf)
    m = op.m_index
    i_rms = op.I_phase_rms
    i_peak = i_rms * math.sqrt(2.0)

    # --- Conduction loss ---
    if dev.device_type == "mosfet":
        r_ds_on = _interp_rds_on(dev, op.Tj_assumed_C) + dp.R_path
        p_cond = conduction_loss_mosfet_closed_form(r_ds_on, i_rms, m, phi)
    else:
        # IGBT: transistor conducts positive half-cycle with duty d.
        assert dev.V_ce0 is not None and dev.r_ce is not None
        v_ce0 = (_interp_v_ce0(dev, op.Tj_assumed_C)
                 if dev.V_ce0_vs_Tj is not None else dev.V_ce0)
        r_ce = (_interp_r_ce(dev, op.Tj_assumed_C)
                if dev.r_ce_vs_Tj is not None else dev.r_ce)
        r_eff = r_ce + dp.R_path
        p_cond_transistor = (
            v_ce0 * i_peak / (2.0 * math.pi) * (1.0 + math.pi * m * math.cos(phi) / 4.0)
            + r_eff * i_rms**2 * (0.25 + 2.0 * m * math.cos(phi) / (3.0 * math.pi))
        )
        # Anti-parallel diode conducts the negative half-cycle with duty (1-d).
        p_cond_diode = (
            dev.V_f * i_peak / (2.0 * math.pi) * (1.0 - math.pi * m * math.cos(phi) / 4.0)
        )
        p_cond = p_cond_transistor + p_cond_diode

    # --- Switching loss ---
    # Numerically average E_on/E_off over the conduction half-cycle
    e_on_avg, e_off_avg = _avg_switching_energy(dev, i_peak)

    # Scale from test V_dc to operating V_dc (linear scaling)
    assert dev.E_on_vs_I is not None
    v_test = dev.E_on_vs_I.conditions.get("V_dc", op.V_dc)
    v_scale = op.V_dc / v_test if v_test > 0 else 1.0

    # Scale switching energy for Tj difference from test conditions
    if dev.E_on_k_Tj != 0.0:
        tj_ref = dev.E_on_vs_I.conditions.get("Tj", op.Tj_assumed_C)
        e_on_avg *= 1.0 + dev.E_on_k_Tj * (op.Tj_assumed_C - tj_ref)
    if dev.E_off_k_Tj != 0.0:
        assert dev.E_off_vs_I is not None
        tj_ref = dev.E_off_vs_I.conditions.get("Tj", op.Tj_assumed_C)
        e_off_avg *= 1.0 + dev.E_off_k_Tj * (op.Tj_assumed_C - tj_ref)

    p_sw_on = op.f_sw_Hz * e_on_avg * v_scale
    p_sw_off = op.f_sw_Hz * e_off_avg * v_scale

    # --- Reverse recovery loss ---
    # Scale Q_rr for Tj difference from test conditions
    q_rr = dev.Q_rr
    if dev.Q_rr_k_Tj != 0.0:
        tj_ref_qrr = dev.V_f_conditions.get("Tj", 25.0)
        q_rr = dev.Q_rr * (1.0 + dev.Q_rr_k_Tj * (op.Tj_assumed_C - tj_ref_qrr))
    # Recovery occurs only during the half-cycle the diode conducts
    p_rr = 0.5 * op.f_sw_Hz * q_rr * op.V_dc

    # --- Body diode conduction loss (dead time only) ---
    # Two dead-time intervals per PWM period; mean rectified current I_peak/pi
    # gives per-device average = V_f * (I_peak/pi) * 2 * t_dead * f_sw
    # which equals V_f * (2*I_peak/pi) * t_dead * f_sw
    i_dt_avg = i_peak * 2.0 / math.pi
    p_diode_cond = dev.V_f * i_dt_avg * op.t_dead_s * op.f_sw_Hz

    p_total = p_cond + p_sw_on + p_sw_off + p_rr + p_diode_cond

    return {
        "p_cond_W": p_cond,
        "p_sw_on_W": p_sw_on,
        "p_sw_off_W": p_sw_off,
        "p_diode_cond_W": p_diode_cond,
        "p_rr_W": p_rr,
        "p_total_W": p_total,
    }


def run_semiconductor_loss(config: Any) -> dict[str, Any]:
    """Run semiconductor loss model for all device positions.

    config.assembly -- Assembly with devices
    config.op -- dict with OperatingPoint fields
    """
    assembly: Assembly = config.assembly
    op = OperatingPoint.from_dict(config.op)

    prepare_semiconductor_loss(assembly)

    results: dict[str, Any] = {}
    total_loss = 0.0
    total_cond = 0.0
    total_sw_on = 0.0
    total_sw_off = 0.0
    total_diode = 0.0
    total_rr = 0.0

    for dp in assembly.devices:
        losses = _compute_device_losses(dp, op)
        for k, v in losses.items():
            results[f"{dp.position}_{k}"] = v
        total_loss += losses["p_total_W"]
        total_cond += losses["p_cond_W"]
        total_sw_on += losses["p_sw_on_W"]
        total_sw_off += losses["p_sw_off_W"]
        total_diode += losses["p_diode_cond_W"]
        total_rr += losses["p_rr_W"]

    results["p_cond_W"] = total_cond
    results["p_sw_on_W"] = total_sw_on
    results["p_sw_off_W"] = total_sw_off
    results["p_diode_cond_W"] = total_diode
    results["p_rr_W"] = total_rr
    results["p_total_W"] = total_loss

    return results
