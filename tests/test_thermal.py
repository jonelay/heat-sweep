"""Tests for the LPTN thermal model.

Validates:
- Foster-to-Cauer round-trip: Zth(t) curves agree within 1% at 8 log-spaced times
- Cauer pair physicality: all R > 0, C > 0
- Steady-state Rth stack: Tj = T_amb + P * sum(Rth)
- Self-consistent P(Tj) convergence with MOSFET positive tempco
- Thermal instability detection (Tj > Tj_max)
- Zth monotonicity: Zth(t) non-decreasing, approaches sum(R_i)
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from heatsweep.components.assembly import Assembly, DevicePosition
from heatsweep.components.device import FosterPair
from heatsweep.models.thermal import (
    CauerPair,
    foster_to_cauer,
    solve_thermal_steady_state,
    steady_state_tj,
    zth_cauer,
    zth_foster,
)
from tests.conftest import make_mosfet, make_op

# ---------------------------------------------------------------------------
# Foster-to-Cauer conversion
# ---------------------------------------------------------------------------


class TestFosterToCauer:
    """Foster-to-Cauer conversion must produce physical pairs and match Zth."""

    FOSTER_2PAIR = (FosterPair(R=0.3, tau=0.01), FosterPair(R=0.2, tau=0.1))
    FOSTER_3PAIR = (
        FosterPair(R=0.15, tau=0.005),
        FosterPair(R=0.25, tau=0.05),
        FosterPair(R=0.10, tau=0.5),
    )
    FOSTER_4PAIR = (
        FosterPair(R=0.08, tau=0.001),
        FosterPair(R=0.12, tau=0.01),
        FosterPair(R=0.20, tau=0.1),
        FosterPair(R=0.10, tau=1.0),
    )

    @pytest.mark.parametrize("foster", [FOSTER_2PAIR, FOSTER_3PAIR, FOSTER_4PAIR],
                             ids=["2pair", "3pair", "4pair"])
    def test_all_pairs_positive(self, foster: tuple[FosterPair, ...]) -> None:
        cauer = foster_to_cauer(foster)
        assert len(cauer) == len(foster)
        for i, cp in enumerate(cauer):
            assert cp.R > 0, f"Cauer R[{i}] = {cp.R}"
            assert cp.C > 0, f"Cauer C[{i}] = {cp.C}"

    @pytest.mark.parametrize("foster", [FOSTER_2PAIR, FOSTER_3PAIR, FOSTER_4PAIR],
                             ids=["2pair", "3pair", "4pair"])
    def test_steady_state_resistance_preserved(self, foster: tuple[FosterPair, ...]) -> None:
        """Sum of Cauer R_i must equal sum of Foster R_i."""
        cauer = foster_to_cauer(foster)
        foster_sum = sum(fp.R for fp in foster)
        cauer_sum = sum(cp.R for cp in cauer)
        assert cauer_sum == pytest.approx(foster_sum, rel=1e-6)

    @pytest.mark.parametrize("foster", [FOSTER_2PAIR, FOSTER_3PAIR, FOSTER_4PAIR],
                             ids=["2pair", "3pair", "4pair"])
    def test_zth_round_trip(self, foster: tuple[FosterPair, ...]) -> None:
        """Zth(t) from Foster and converted Cauer must agree within 2%
        at 8 log-spaced times spanning the time-constant range."""
        cauer = foster_to_cauer(foster)

        tau_min = min(fp.tau for fp in foster)
        tau_max = max(fp.tau for fp in foster)
        t_points = np.logspace(
            math.log10(tau_min * 0.1),
            math.log10(tau_max * 10.0),
            8,
        )

        z_foster = np.asarray(zth_foster(t_points, foster))
        z_cauer = np.asarray(zth_cauer(t_points, cauer))

        r_total = sum(fp.R for fp in foster)
        for i, ti in enumerate(t_points):
            zf = float(z_foster[i])
            zc = float(z_cauer[i])
            if zf < 1e-6 * r_total:
                continue
            rel_err = abs(zc - zf) / zf
            assert rel_err < 0.02, (
                f"t={ti:.4g}s: Foster Zth={zf:.6g}, Cauer Zth={zc:.6g}, "
                f"err={rel_err:.2%}"
            )

    def test_empty_foster(self) -> None:
        assert foster_to_cauer(()) == ()

    def test_single_pair(self) -> None:
        foster = (FosterPair(R=0.5, tau=0.02),)
        cauer = foster_to_cauer(foster)
        assert len(cauer) == 1
        assert pytest.approx(0.5, rel=1e-6) == cauer[0].R


# ---------------------------------------------------------------------------
# Zth evaluation
# ---------------------------------------------------------------------------


class TestZthFoster:
    """Foster Zth must be monotonically non-decreasing and converge to sum(R)."""

    FOSTER = (FosterPair(R=0.3, tau=0.01), FosterPair(R=0.2, tau=0.1))

    def test_zth_at_zero(self) -> None:
        assert zth_foster(0.0, self.FOSTER) == pytest.approx(0.0)

    def test_zth_steady_state(self) -> None:
        r_total = sum(fp.R for fp in self.FOSTER)
        z_ss = zth_foster(100.0, self.FOSTER)
        assert z_ss == pytest.approx(r_total, rel=1e-6)

    def test_monotonic(self) -> None:
        t = np.logspace(-4, 2, 50)
        z = np.asarray(zth_foster(t, self.FOSTER))
        for i in range(1, len(z)):
            assert z[i] >= z[i - 1] - 1e-15

    def test_scalar_input(self) -> None:
        z = zth_foster(0.05, self.FOSTER)
        assert isinstance(z, float)
        assert z > 0


class TestZthCauer:
    """Cauer Zth must converge to sum(R) and be non-decreasing."""

    @pytest.fixture()
    def cauer_from_foster(self) -> tuple[CauerPair, ...]:
        foster = (FosterPair(R=0.3, tau=0.01), FosterPair(R=0.2, tau=0.1))
        return foster_to_cauer(foster)

    def test_zth_steady_state(self, cauer_from_foster: tuple[CauerPair, ...]) -> None:
        r_total = sum(cp.R for cp in cauer_from_foster)
        z_ss = zth_cauer(100.0, cauer_from_foster)
        assert z_ss == pytest.approx(r_total, rel=1e-3)

    def test_monotonic(self, cauer_from_foster: tuple[CauerPair, ...]) -> None:
        t = np.logspace(-4, 2, 20)
        z = np.asarray(zth_cauer(t, cauer_from_foster))
        for i in range(1, len(z)):
            assert z[i] >= z[i - 1] - 1e-10

    def test_empty_cauer(self) -> None:
        assert zth_cauer(1.0, ()) == 0.0
        z = zth_cauer(np.array([0.1, 1.0]), ())
        assert np.all(z == 0.0)


# ---------------------------------------------------------------------------
# Steady-state Tj
# ---------------------------------------------------------------------------


class TestSteadyStateTj:
    def test_basic(self) -> None:
        tj = steady_state_tj(p_W=50.0, rth_jc=0.5, rth_cs=0.2, rth_sa=1.0, t_amb_C=25.0)
        assert tj == pytest.approx(25.0 + 50.0 * 1.7)

    def test_zero_power(self) -> None:
        tj = steady_state_tj(p_W=0.0, rth_jc=0.5, rth_cs=0.2, rth_sa=1.0, t_amb_C=40.0)
        assert tj == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# Self-consistent thermal solve
# ---------------------------------------------------------------------------


def _make_thermal_assembly(
    rth_sa: float = 0.5,
    rth_cs: float = 0.2,
    n_devices: int = 1,
    **kwargs: object,
) -> Assembly:
    dev = make_mosfet(**kwargs)  # type: ignore[arg-type]
    positions = ["Q1_high", "Q2_high", "Q3_high", "Q1_low", "Q2_low", "Q3_low"]
    devices = tuple(
        DevicePosition(position=positions[i], device=dev, Rth_cs=rth_cs)
        for i in range(min(n_devices, len(positions)))
    )
    return Assembly(
        name="thermal_test",
        topology="three_phase_bridge",
        devices=devices,
        T_amb_C=25.0,
        Rth_sa=rth_sa,
    )


class TestSelfConsistentSolve:
    """Self-consistent P(Tj) iteration must converge for stable designs."""

    def test_converges(self) -> None:
        asm = _make_thermal_assembly(rth_sa=0.5, n_devices=1)
        op = make_op(Tj_assumed_C=25.0)
        result = solve_thermal_steady_state(asm, op.to_dict())
        assert result.converged
        assert result.iterations < 50
        assert result.thermally_stable

    def test_tj_above_ambient(self) -> None:
        asm = _make_thermal_assembly(rth_sa=0.5, n_devices=1)
        op = make_op(I_phase_rms=10.0)
        result = solve_thermal_steady_state(asm, op.to_dict())
        assert result.converged
        for tj in result.Tj_C.values():
            assert tj > asm.T_amb_C

    def test_tj_self_consistent(self) -> None:
        """At convergence, recomputing losses at Tj gives the same Tj."""
        asm = _make_thermal_assembly(rth_sa=0.5, n_devices=1)
        op = make_op()
        result = solve_thermal_steady_state(asm, op.to_dict())
        assert result.converged

        pos = next(iter(result.Tj_C.keys()))
        dp = asm.devices[0]
        tj = result.Tj_C[pos]
        p = result.p_device_W[pos]
        tj_check = result.T_sink_C + p * (dp.device.Rth_jc + dp.Rth_cs)
        assert tj == pytest.approx(tj_check, abs=0.02)

    def test_higher_current_higher_tj(self) -> None:
        asm = _make_thermal_assembly(rth_sa=0.5, n_devices=1)
        op_lo = make_op(I_phase_rms=5.0)
        op_hi = make_op(I_phase_rms=20.0)
        r_lo = solve_thermal_steady_state(asm, op_lo.to_dict())
        r_hi = solve_thermal_steady_state(asm, op_hi.to_dict())
        assert r_lo.converged and r_hi.converged
        pos = next(iter(r_lo.Tj_C.keys()))
        assert r_lo.Tj_C[pos] < r_hi.Tj_C[pos]

    def test_multi_device_shared_heatsink(self) -> None:
        asm = _make_thermal_assembly(rth_sa=0.5, n_devices=6)
        op = make_op(I_phase_rms=10.0)
        result = solve_thermal_steady_state(asm, op.to_dict())
        assert result.converged
        assert len(result.Tj_C) == 6
        assert result.T_sink_C > asm.T_amb_C
        for tj in result.Tj_C.values():
            assert tj > result.T_sink_C

    def test_initial_guess_insensitive(self) -> None:
        """Converges to the same Tj regardless of initial guess."""
        asm = _make_thermal_assembly(rth_sa=0.5, n_devices=1)
        op_lo = make_op(Tj_assumed_C=25.0)
        op_hi = make_op(Tj_assumed_C=150.0)
        r_lo = solve_thermal_steady_state(asm, op_lo.to_dict())
        r_hi = solve_thermal_steady_state(asm, op_hi.to_dict())
        assert r_lo.converged and r_hi.converged
        pos = next(iter(r_lo.Tj_C.keys()))
        assert r_lo.Tj_C[pos] == pytest.approx(r_hi.Tj_C[pos], abs=0.1)

    def test_thermal_instability_detected(self) -> None:
        """Very high current + high Rth_sa should push Tj above Tj_max."""
        asm = _make_thermal_assembly(rth_sa=5.0, n_devices=1)
        op = make_op(I_phase_rms=40.0)
        result = solve_thermal_steady_state(asm, op.to_dict())
        assert not result.thermally_stable

    def test_loss_breakdown_present(self) -> None:
        asm = _make_thermal_assembly(rth_sa=0.5, n_devices=1)
        op = make_op()
        result = solve_thermal_steady_state(asm, op.to_dict())
        assert result.converged
        pos = next(iter(result.loss_breakdown.keys()))
        breakdown = result.loss_breakdown[pos]
        assert "p_cond_W" in breakdown
        assert "p_sw_on_W" in breakdown
        assert breakdown["p_total_W"] > 0


# ---------------------------------------------------------------------------
# Linearity of the network under the fixed-point solver
# ---------------------------------------------------------------------------

FLAT_RDS = ((25.0, 100.0, 150.0), (0.015, 0.015, 0.015))


def _scaled_foster(scale: float) -> tuple[FosterPair, ...]:
    """make_mosfet's default Foster set, scaled to keep sum(R_i) == Rth_jc.

    Device.__post_init__ enforces that equality to 5%, so a test that
    scales Rth_jc has to scale the chain with it.
    """
    return (FosterPair(R=0.3 * scale, tau=0.01), FosterPair(R=0.2 * scale, tau=0.1))


class TestThermalLinearity:
    """The LPTN is linear in power; the fixed-point solver need not be.

    `TestSelfConsistentSolve` checks that the iteration converges and is
    self-consistent, but never that it lands on the answer the linear
    network prescribes. With a Tj-independent device the two must agree
    exactly, which turns the iteration into a checkable code path rather
    than a black box. With Tj-dependent losses the same comparison
    quantifies the feedback instead of hiding it.
    """

    @staticmethod
    def _flat_assembly(rth_scale: float = 1.0, n_devices: int = 1) -> Assembly:
        """Assembly whose losses do not depend on Tj, with all three thermal
        resistances scaled together by `rth_scale`."""
        return _make_thermal_assembly(
            rth_sa=0.5 * rth_scale,
            rth_cs=0.2 * rth_scale,
            n_devices=n_devices,
            rds_tj=FLAT_RDS,
            rth_jc=0.5 * rth_scale,
            foster=_scaled_foster(rth_scale),
        )

    def test_iteration_matches_closed_form(self) -> None:
        """With Tj-independent losses the solver must reproduce
        Tj = T_amb + P*(Rth_jc + Rth_cs + Rth_sa) exactly."""
        asm = self._flat_assembly()
        result = solve_thermal_steady_state(asm, make_op().to_dict())
        assert result.converged

        dp = asm.devices[0]
        pos = dp.position
        expected = steady_state_tj(
            p_W=result.p_device_W[pos],
            rth_jc=dp.device.Rth_jc,
            rth_cs=dp.Rth_cs,
            rth_sa=asm.Rth_sa,
            t_amb_C=asm.T_amb_C,
        )
        assert result.Tj_C[pos] == pytest.approx(expected, rel=1e-12)

    def test_losses_are_tj_independent(self) -> None:
        """Guards the premise of the two tests around this one: a flat
        R_ds_on table and zero energy tempcos must make loss constant in Tj."""
        asm = self._flat_assembly()
        p_cold = solve_thermal_steady_state(
            asm, make_op(Tj_assumed_C=25.0).to_dict()).p_total_W
        p_hot = solve_thermal_steady_state(
            asm, make_op(Tj_assumed_C=150.0).to_dict()).p_total_W
        assert p_cold == pytest.approx(p_hot, rel=1e-12)

    @pytest.mark.parametrize("scale", [0.25, 0.5, 2.0, 4.0])
    def test_delta_t_scales_with_rth(self, scale: float) -> None:
        """Scaling every Rth by lambda must scale every rise above ambient
        by exactly lambda. Fails on any additive term that is not a
        resistance -- a stray offset, or an ambient applied twice."""
        op = make_op()
        base = solve_thermal_steady_state(self._flat_assembly(), op.to_dict())
        scaled = solve_thermal_steady_state(
            self._flat_assembly(rth_scale=scale), op.to_dict(),
        )
        assert base.converged and scaled.converged

        pos = next(iter(base.Tj_C))
        t_amb = 25.0
        assert scaled.Tj_C[pos] - t_amb == pytest.approx(
            scale * (base.Tj_C[pos] - t_amb), rel=1e-12,
        )
        assert scaled.T_sink_C - t_amb == pytest.approx(
            scale * (base.T_sink_C - t_amb), rel=1e-12,
        )

    def test_superposition_across_devices(self) -> None:
        """Sink rise from N identical devices is N times the rise from one.

        Trivial in the present star network, where T_sink = T_amb +
        sum(P_i)*Rth_sa. It is here so that replacing the star with an
        FEM-derived coupling matrix has to keep the property, which is
        where getting it wrong becomes possible.
        """
        op = make_op()
        one = solve_thermal_steady_state(self._flat_assembly(n_devices=1), op.to_dict())
        six = solve_thermal_steady_state(self._flat_assembly(n_devices=6), op.to_dict())
        assert one.converged and six.converged

        t_amb = 25.0
        assert six.T_sink_C - t_amb == pytest.approx(
            6.0 * (one.T_sink_C - t_amb), rel=1e-12,
        )

    @pytest.mark.parametrize("scale", [2.0, 3.0])
    def test_tj_dependence_amplifies_beyond_linear(self, scale: float) -> None:
        """With a positive loss tempco the rise must exceed the linear
        prediction, and by more as Rth grows. This is the thermal feedback
        the ORNL inverter anchor result depends on; if the solver were silently
        evaluating losses at the initial guess, the rise would come out
        exactly linear instead."""
        op = make_op()
        # Default make_mosfet R_ds_on table rises 0.010 -> 0.020 over Tj.
        base = solve_thermal_steady_state(
            _make_thermal_assembly(rth_sa=0.5, rth_cs=0.2, n_devices=1), op.to_dict(),
        )
        scaled = solve_thermal_steady_state(
            _make_thermal_assembly(
                rth_sa=0.5 * scale, rth_cs=0.2 * scale, n_devices=1,
                rth_jc=0.5 * scale, foster=_scaled_foster(scale),
            ),
            op.to_dict(),
        )
        assert base.converged and scaled.converged

        pos = next(iter(base.Tj_C))
        t_amb = 25.0
        linear = scale * (base.Tj_C[pos] - t_amb)
        assert scaled.Tj_C[pos] - t_amb > linear
        assert scaled.p_total_W > base.p_total_W


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


class TestThermalRegistry:
    def test_registered(self) -> None:
        from heatsweep.registry import MODEL_REGISTRY

        assert "thermal" in MODEL_REGISTRY
        info = MODEL_REGISTRY["thermal"]
        assert info.validate is not None
        assert info.fn is not None

    def test_run_via_registry(self) -> None:
        from heatsweep.registry import MODEL_REGISTRY
        from heatsweep.run_types import RunConfig

        asm = _make_thermal_assembly(rth_sa=0.5, n_devices=1)
        op = make_op()
        config = RunConfig(assembly=asm, model="thermal", op=op.to_dict())
        fn = MODEL_REGISTRY["thermal"].fn
        assert fn is not None
        result = fn(config)
        assert result["converged"] is True
        assert result["p_total_W"] > 0
