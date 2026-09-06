"""Tests for semiconductor_loss model.

Validates:
- Closed-form vs numerical conduction integral (0.1% at 4 operating points)
- Monotonicity invariants: p_sw vs f_sw, p_cond vs I_rms, R_ds_on vs Tj, p_total vs Tj
- compute_run_id stability and sensitivity
- OperatingPoint domain validation
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from heatsweep.components.assembly import DevicePosition
from heatsweep.models.semiconductor_loss import (
    conduction_loss_mosfet_closed_form,
    conduction_loss_mosfet_numerical,
    run_semiconductor_loss,
)
from heatsweep.run_types import RunConfig, compute_run_id
from tests.conftest import make_assembly, make_igbt, make_mosfet, make_op

# ---------------------------------------------------------------------------
# Closed-form vs numerical conduction loss (sync-rect MOSFET)
# ---------------------------------------------------------------------------


class TestConductionClosedForm:
    """Closed-form conduction must agree with numerical integral to 0.1%."""

    @pytest.mark.parametrize("m,phi_deg", [
        (0.8, 25.84),   # pf=0.9
        (0.5, 0.0),     # unity pf, low modulation
        (1.0, 45.0),    # full modulation, pf~0.71
        (0.3, 60.0),    # low modulation, pf=0.5
    ])
    def test_closed_form_vs_numerical(self, m: float, phi_deg: float) -> None:
        r_ds_on = 0.015
        i_rms = 10.0
        phi = math.radians(phi_deg)

        p_cf = conduction_loss_mosfet_closed_form(r_ds_on, i_rms, m, phi)
        p_num = conduction_loss_mosfet_numerical(r_ds_on, i_rms, m, phi, n_points=100000)

        assert p_cf > 0
        assert p_num > 0
        rel_err = abs(p_cf - p_num) / p_num
        assert rel_err < 0.001, f"Closed-form {p_cf:.6f} vs numerical {p_num:.6f}, err={rel_err:.4%}"

    def test_sync_rect_m_independent(self) -> None:
        """Sync-rect P_cond = R*I_rms^2/2, independent of m and phi."""
        r = 0.02
        i_rms = 15.0
        expected = 0.5 * r * i_rms**2
        for m in (0.3, 0.6, 0.9, 1.0):
            for phi in (0.0, 0.5, 1.0):
                p = conduction_loss_mosfet_closed_form(r, i_rms, m, phi)
                assert p == pytest.approx(expected, rel=1e-12)


# ---------------------------------------------------------------------------
# Monotonicity invariants
# ---------------------------------------------------------------------------


class TestMonotonicityInvariants:
    """Loss must increase monotonically with expected parameters."""

    def _run_at_op(self, **op_overrides: object) -> dict:
        asm = make_assembly(n_devices=1)
        op = make_op(**op_overrides)
        config = RunConfig(assembly=asm, model="semiconductor_loss", op=op.to_dict())
        return run_semiconductor_loss(config)

    def test_p_sw_monotone_in_f_sw(self) -> None:
        r1 = self._run_at_op(f_sw_Hz=10000.0)
        r2 = self._run_at_op(f_sw_Hz=20000.0)
        r3 = self._run_at_op(f_sw_Hz=40000.0)
        assert r1["p_sw_on_W"] < r2["p_sw_on_W"] < r3["p_sw_on_W"]
        assert r1["p_sw_off_W"] < r2["p_sw_off_W"] < r3["p_sw_off_W"]

    def test_p_cond_monotone_in_i_rms(self) -> None:
        r1 = self._run_at_op(I_phase_rms=5.0)
        r2 = self._run_at_op(I_phase_rms=10.0)
        r3 = self._run_at_op(I_phase_rms=20.0)
        assert r1["p_cond_W"] < r2["p_cond_W"] < r3["p_cond_W"]

    def test_rds_on_monotone_in_tj(self) -> None:
        """R_ds_on increases with Tj (positive tempco for MOSFETs)."""
        from heatsweep.models.semiconductor_loss import _interp_rds_on
        dev = make_mosfet()
        r25 = _interp_rds_on(dev, 25.0)
        r100 = _interp_rds_on(dev, 100.0)
        r150 = _interp_rds_on(dev, 150.0)
        assert r25 < r100 < r150

    def test_p_total_monotone_in_tj(self) -> None:
        r1 = self._run_at_op(Tj_assumed_C=25.0)
        r2 = self._run_at_op(Tj_assumed_C=100.0)
        r3 = self._run_at_op(Tj_assumed_C=150.0)
        assert r1["p_total_W"] < r2["p_total_W"] < r3["p_total_W"]

    def test_igbt_loss_monotone_in_tj(self) -> None:
        """IGBT loss with Tj-dependent V_ce0/r_ce tables must increase with Tj."""
        from heatsweep.components.device import Device, TableEntry

        dev = Device(
            name="test_igbt", device_type="igbt", package="module",
            manufacturer="TestCo", V_max=600.0, I_max=100.0, Tj_max=175.0,
            V_ce0=0.8, r_ce=0.008,
            V_ce0_vs_Tj=TableEntry(
                x=(25.0, 125.0, 150.0), y=(0.9, 0.8, 0.75),
                x_label="Tj", y_label="V_ce0",
                conditions={"I_c": 100.0, "V_ge": 15.0},
            ),
            r_ce_vs_Tj=TableEntry(
                x=(25.0, 125.0, 150.0), y=(0.005, 0.008, 0.009),
                x_label="Tj", y_label="r_ce",
                conditions={"I_c": 100.0, "V_ge": 15.0},
            ),
            E_on_vs_I=TableEntry(
                x=(25.0, 50.0, 100.0), y=(0.3e-3, 0.6e-3, 1.2e-3),
                x_label="I", y_label="E_on",
                conditions={"V_dc": 400.0, "R_g": 5.0, "Tj": 150.0},
            ),
            E_off_vs_I=TableEntry(
                x=(25.0, 50.0, 100.0), y=(1.0e-3, 2.0e-3, 4.0e-3),
                x_label="I", y_label="E_off",
                conditions={"V_dc": 400.0, "R_g": 5.0, "Tj": 150.0},
            ),
            V_f=1.8, Q_rr=2.0e-6, Rth_jc=0.35,
        )
        dp = DevicePosition(position="Q1", device=dev)
        from heatsweep.models.semiconductor_loss import _compute_device_losses

        # At high current, r_ce*I^2 dominates over V_ce0*I, so total
        # conduction increases with Tj despite V_ce0's negative tempco.
        op_kw = {"I_phase_rms": 50.0, "V_dc": 400.0}
        r25 = _compute_device_losses(dp, make_op(Tj_assumed_C=25.0, **op_kw))
        r125 = _compute_device_losses(dp, make_op(Tj_assumed_C=125.0, **op_kw))
        r150 = _compute_device_losses(dp, make_op(Tj_assumed_C=150.0, **op_kw))
        assert r25["p_cond_W"] < r125["p_cond_W"] < r150["p_cond_W"]

    def test_r_path_increases_conduction(self) -> None:
        """R_path must increase conduction loss proportionally."""
        from heatsweep.models.semiconductor_loss import _compute_device_losses

        dev = make_mosfet()
        dp0 = DevicePosition(position="Q1", device=dev, R_path=0.0)
        dp1 = DevicePosition(position="Q1", device=dev, R_path=0.005)
        op = make_op()
        r0 = _compute_device_losses(dp0, op)
        r1 = _compute_device_losses(dp1, op)
        assert r1["p_cond_W"] > r0["p_cond_W"]
        assert r1["p_total_W"] > r0["p_total_W"]


# ---------------------------------------------------------------------------
# IGBT conduction: closed form vs numerical, and the m -> 0 duty limit
# ---------------------------------------------------------------------------


def _igbt_conduction_numerical(
    v_ce0: float,
    r_ce: float,
    v_f: float,
    i_rms: float,
    m: float,
    phi: float,
    n: int = 200_001,
) -> tuple[float, float]:
    """(transistor, anti-parallel diode) conduction loss by direct integration.

    Independent of the closed forms in semiconductor_loss.py: integrates the
    instantaneous drop over the half-cycle the device conducts, weighted by
    the PWM duty. Phase current i = I_pk*sin(theta) lags the reference by
    phi, so the upper switch duty is d = 0.5*(1 + m*sin(theta + phi)). The
    transistor carries i>0 with duty d; the anti-parallel diode carries the
    same half-cycle with duty (1 - d).
    """
    i_peak = i_rms * math.sqrt(2.0)
    theta = np.linspace(0.0, math.pi, n)
    i = i_peak * np.sin(theta)
    duty = 0.5 * (1.0 + m * np.sin(theta + phi))

    p_transistor = np.trapezoid((v_ce0 * i + r_ce * i**2) * duty, theta) / (2.0 * math.pi)
    p_diode = np.trapezoid(v_f * i * (1.0 - duty), theta) / (2.0 * math.pi)
    return float(p_transistor), float(p_diode)


class TestIgbtConductionInvariants:
    """The IGBT conduction path had no closed-form-vs-numerical check.

    `TestConductionClosedForm` covers the sync-rect MOSFET, but every
    validation anchor in this repo runs the IGBT branch, whose closed form
    was unchecked against an independent integration. These tests supply
    that, then pin the m -> 0 limit the closed form must reduce to.
    """

    I_RMS = 50.0
    V_CE0 = 0.8
    R_CE = 0.008
    V_F = 1.8

    def _model_p_cond(self, m: float, pf: float) -> float:
        from heatsweep.models.semiconductor_loss import _compute_device_losses

        dp = DevicePosition(
            position="Q1",
            device=make_igbt(v_ce0=self.V_CE0, r_ce=self.R_CE, v_f=self.V_F),
        )
        op = make_op(I_phase_rms=self.I_RMS, m_index=m, pf=pf, modulation="svpwm")
        return _compute_device_losses(dp, op)["p_cond_W"]

    @pytest.mark.parametrize("m", [0.0, 0.2, 0.6, 0.95])
    @pytest.mark.parametrize("pf", [1.0, 0.9, 0.5, 0.1])
    def test_closed_form_vs_numerical(self, m: float, pf: float) -> None:
        """Closed form must match direct integration everywhere.

        Observed agreement is ~2e-11; the bound is set at 1e-6 to leave room
        for the trapezoid error without going slack. For scale, writing the
        diode's duty complement with the wrong sign moves the total 14-16%.
        """
        phi = math.acos(pf)
        p_t, p_d = _igbt_conduction_numerical(
            self.V_CE0, self.R_CE, self.V_F, self.I_RMS, m, phi,
        )
        assert self._model_p_cond(m, pf) == pytest.approx(p_t + p_d, rel=1e-6)

    @pytest.mark.parametrize("pf", [1.0, 0.9, 0.5, 0.1])
    def test_conduction_is_pf_independent_at_zero_m(self, pf: float) -> None:
        """At m = 0 the duty is a flat 1/2, so cos(phi) drops out entirely.

        Every m-dependent term in the closed form carries a cos(phi) factor.
        If one were written without it, or with the wrong sign, conduction
        would still vary with pf at zero modulation depth.
        """
        assert self._model_p_cond(0.0, pf) == pytest.approx(
            self._model_p_cond(0.0, 1.0), rel=1e-12,
        )

    def test_duty_splits_evenly_at_zero_m(self) -> None:
        """At m = 0 transistor and diode each conduct at duty exactly 1/2.

        The voltage-drop share of each is then (drop) * I_pk/pi * 1/2, the
        mean rectified current over the half-cycle at half duty. This is
        what fixes the IGBT/diode split in the absence of modulation, and
        it is the limit the (1 +/- pi*m*cos(phi)/4) factors must reduce to.
        """
        i_peak = self.I_RMS * math.sqrt(2.0)
        mean_rectified = i_peak / math.pi
        p_t, p_d = _igbt_conduction_numerical(
            self.V_CE0, self.R_CE, self.V_F, self.I_RMS, 0.0, 0.0,
        )

        # Diode carries a pure voltage drop, so its whole loss is the share.
        assert p_d == pytest.approx(self.V_F * mean_rectified * 0.5, rel=1e-6)
        # Transistor's V_ce0 share is the same duty-1/2 mean rectified term;
        # the remainder is resistive, r_ce * I_rms^2 at duty 1/2 of a half
        # cycle = r_ce * I_rms^2 / 4.
        p_t_resistive = self.R_CE * self.I_RMS**2 * 0.25
        assert p_t - p_t_resistive == pytest.approx(
            self.V_CE0 * mean_rectified * 0.5, rel=1e-6,
        )
        # Both share the same 1/2: the drop-normalised shares are equal.
        assert (p_t - p_t_resistive) / self.V_CE0 == pytest.approx(
            p_d / self.V_F, rel=1e-9,
        )


# ---------------------------------------------------------------------------
# Run ID stability and sensitivity
# ---------------------------------------------------------------------------


class TestRunId:
    """compute_run_id must be stable and sensitive to hash_fields."""

    def test_stable(self) -> None:
        asm = make_assembly()
        op = make_op()
        rc = RunConfig(assembly=asm, model="semiconductor_loss", op=op.to_dict())
        id1 = compute_run_id(rc)
        id2 = compute_run_id(rc)
        assert id1 == id2

    def test_changes_with_f_sw(self) -> None:
        asm = make_assembly()
        op1 = make_op(f_sw_Hz=10000.0)
        op2 = make_op(f_sw_Hz=20000.0)
        rc1 = RunConfig(assembly=asm, model="semiconductor_loss", op=op1.to_dict())
        rc2 = RunConfig(assembly=asm, model="semiconductor_loss", op=op2.to_dict())
        assert compute_run_id(rc1) != compute_run_id(rc2)

    def test_changes_with_assembly(self) -> None:
        asm1 = make_assembly(name="bridge_a")
        asm2 = make_assembly(name="bridge_b")
        op = make_op()
        rc1 = RunConfig(assembly=asm1, model="semiconductor_loss", op=op.to_dict())
        rc2 = RunConfig(assembly=asm2, model="semiconductor_loss", op=op.to_dict())
        assert compute_run_id(rc1) != compute_run_id(rc2)

    def test_insensitive_to_non_hash_field(self) -> None:
        """R_g_on is not in hash_fields, so changing it should not change the ID."""
        asm = make_assembly()
        op1 = make_op(R_g_on=5.0)
        op2 = make_op(R_g_on=20.0)
        rc1 = RunConfig(assembly=asm, model="semiconductor_loss", op=op1.to_dict())
        rc2 = RunConfig(assembly=asm, model="semiconductor_loss", op=op2.to_dict())
        assert compute_run_id(rc1) == compute_run_id(rc2)


# ---------------------------------------------------------------------------
# OperatingPoint validation
# ---------------------------------------------------------------------------


class TestOperatingPointValidation:
    """OperatingPoint must reject invalid inputs."""

    def test_negative_f_sw(self) -> None:
        with pytest.raises(ValueError, match="f_sw_Hz"):
            make_op(f_sw_Hz=-1.0)

    def test_zero_v_dc(self) -> None:
        with pytest.raises(ValueError, match="V_dc"):
            make_op(V_dc=0.0)

    def test_pf_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="pf"):
            make_op(pf=1.5)

    def test_negative_m_index(self) -> None:
        with pytest.raises(ValueError, match="m_index"):
            make_op(m_index=-0.1)

    def test_negative_t_dead(self) -> None:
        with pytest.raises(ValueError, match="t_dead_s"):
            make_op(t_dead_s=-1e-6)

    def test_inf_field(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            make_op(I_phase_rms=float("inf"))

    def test_spwm_overmodulation_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"m_index.*SPWM"):
            make_op(m_index=1.1, modulation="spwm")

    def test_non_spwm_overmodulation_allowed(self) -> None:
        op = make_op(m_index=1.1, modulation="svpwm")
        assert op.m_index == 1.1

    def test_valid_construction(self) -> None:
        op = make_op()
        assert op.f_sw_Hz > 0
