"""Validation anchor: computed inverter losses vs ORNL dynamometer measurements.

Compares semiconductor loss model predictions against 428 operating points
from ORNL/TM-2006/423 Table B-1 (2004 Toyota Prius MG2 inverter).

Physics assumptions:
- 3-phase bridge, 6 switch positions, 2 parallel IGBT+diode die per position
- Per-die loss computed at I_phase/2, scaled by 12 for full bridge
- Tj from a self-consistent LPTN solve per die: T_coolant 55 degC (ORNL
  test condition), per-die path = FEM Rth_j-coolant 0.386 K/W split
  into Rth_jc + Rth_cs at the die attach (see _fem_split_rth). A fixed
  Tj = 125 degC variant is kept for comparison.
- f_sw = 5 kHz, dead time 1 us

Thermal feedback result: the LPTN puts Tj at 58-89 degC (median 66)
across the map, so losses fall relative to the old Tj = 125 assumption
and the median |error| moves 36% -> 41%, 89% -> 92% underpredicting.
The Tj assumption was masking the gap, not causing it; the missing loss
is elsewhere (switching-energy estimates, parasitic path resistance,
analyzer uncertainty at low current).

Gap structure (with thermal feedback on): measured minus predicted
fits ~200 W + 1.1 mOhm * 3 I^2 with ~265 W rms residual, but the 200 W
is not uniform. Binned by speed, |pred - meas| as a fraction of P_dc is
2.7% / 1.2% / 0.38% / 0.21% for <1000 / 1000-2000 / 2000-4000 / >4000
rpm. Above 2000 rpm the model sits at the level of the power-analyzer
uncertainty ORNL themselves flagged (§3.3.2 "higher-than-expected
inverter efficiency"); below 2000 rpm there is a real unexplained loss
of 1-2.5% of throughput at I ~ 85-95 A and V_dc ~ 500 V. Ruled out as
the cause, with thermal feedback on: Tj (above), total thermal path in
[0, 0.66] K/W (< 1 point), R_path up to 2 mOhm/die (~2 points),
and coolant temperature (0 degC makes it worse). Conduction at the
CM100DU-12F max V_ce(sat) (2.2 V vs 1.6 V typ, both tables scaled)
takes the median to ~32% and over-corrects the I^2 term
(-1.3 mOhm), so the typ/max band brackets the current-dependent part
but not the low-speed residual. The device TOML stays at typ; no new
measured data supports a change.

A later refinement of the same gap. Two separate things were mixed
together in the "low-speed residual" above.

(1) A distinct subset of 35 measured points is not usable as loss data.
Every point at torque >= 300 Nm (all of them fall at 468-1307 rpm; no
point above 1400 rpm reaches that torque) shows measured inverter
efficiency 2-4 points ABOVE the trend of its own speed band, and
measured loss that FALLS as current rises: at 700 rpm, 147 A -> 159 A
takes measured loss 1282 W -> 489 W, and at 900 rpm, 149 A -> 153 A
takes it 1756 W -> 1016 W. No loss mechanism decreases with current at
fixed speed and voltage, so these points carry a measurement or test-
condition artefact, not physics. They are exactly the region ORNL
describes as intermittent duty requiring the coolant to be dropped to
0 degC (§3.3.2, and the 400 Nm / 1-1200 rpm peak-torque envelope of
Fig 3.17), which answers which points ran cold: the CSV does not flag
them, but torque >= 300 Nm selects them. Cold coolant alone cannot
produce the step (it would move loss by ~10%, not 60%), so these are
most likely also where the CT noise/EMI ORNL investigated did the most
damage. See `is_intermittent_duty`. The model OVERpredicts on 63% of
them, against 3% on the rest of the map. The step does not land on
exactly 300 Nm in every band (337 Nm at 500 rpm, 308 at 700, 307 at
900, 302 at 1100), so a flat 300 Nm cutoff also drops three or four
points at ~500 rpm that look normal. That is the conservative
direction: it discards a little good data rather than retaining bad.

(2) With those 35 excluded, the remaining 393 points underpredict
uniformly: 100% below 2000 rpm, 96.9% overall (up from 92.1%). The
residual then scales with current, and its size expressed as an
equivalent series resistance per phase (gap = R_eff * 3 * I^2) falls
monotonically with speed:

    300 rpm 19.1 | 500 14.4 | 700 14.5 | 900 15.1 | 1100 15.4
    1300 13.2 | 1650 11.8 | 2100 10.0 | 2700 6.7 | 3750 5.1 | 5750 4.0
    (mOhm/phase)

A real conductor resistance rises with frequency (skin/proximity), so
this is not bus-bar or wire-bond I^2R. The shape matches the
freewheeling-duty weight (1 - pi*m*cos(phi)/4) that multiplies the
anti-parallel diode conduction term, whose value falls 4.8x over the
same range as m*cos(phi) goes 0.10 -> 1.00; but reproducing the
magnitude needs ~83 mOhm of diode slope resistance per die, 10-20x any
plausible value for a 40.7 mm^2 die, so it is not a missing conduction
term in the semiconductor model either. Speed and modulation index are
collinear in this dataset (back-EMF is proportional to speed), so
"falls with speed" and "falls with modulation index" cannot be
separated from these 428 points alone.

A later session bounded PWM ripple and both Costa 2023
modulation-dependent terms, using the L_d = 1.92 mH / L_q = 5 mH from
TM-2006/423 §4. All three are ruled out,
by orders of magnitude, at the 297 rpm row (V_dc 498 V, I 129.8 A,
m*cos(phi) 0.198, f_out 19.8 Hz, residual 322 W/phase).

- PWM ripple conduction. A time-domain SPWM simulation with a floating
  load neutral gives I_ripple = 0.53 A rms at f_sw = 5 kHz on L_d, so
  the extra I^2*r_ce is under 0.01 W/phase. Even an absurd worst case
  — half-saturated L_d, the 1.25 kHz carrier, and m at the ripple peak
  — reaches only 11 A rms and 0.5 W/phase, 0.16% of the residual.
  Closing the gap would take 284 A rms of ripple against a 130 A
  fundamental. The bound survives the saturation estimate derived
  below: at 0.387 x L_d = 0.74 mH the same worst case gives 0.84
  W/phase, 0.26%.
- The measured current is not the anomaly either. The L22 MTPA law with
  lam_af = 0.173 Wb puts the current needed for 269.7 Nm between
  183.9 A rms (no saliency) and 94.6 A rms (static 1.92/5 mH); the
  measured 129.8 A sits between them, so the machine is using
  reluctance torque with effective inductances ~0.4x static. The gap
  is in the loss accounting, not in the current. See
  ORNL/TM-2006/423 §4 (motor parameters).
- The premise in the earlier note was also wrong: ripple does **not**
  grow as the modulation index falls. In a 3-phase floating-neutral
  inverter it grows *with* m (0.56 A at m = 0.2, 1.41 A at m = 1.0),
  because as m falls all three legs approach 50% duty and switch
  nearly in phase, so the common mode cancels and little differential
  ripple voltage remains. The half-bridge d(1-d) intuition, which is
  what a half-bridge analysis teaches,
  does not carry over to a 3-phase floating neutral.
- Costa 2023 conduction term, (1 + THD^2): with the simulated THD of
  0.4-2.9%, this adds at most 0.17 W/phase, 0.05% of the residual.
- Costa 2023 parasitic-capacitance term: reproducing the residual would
  need C_oss = 130 nF/die, against 1-3 nF for a 40.7 mm^2 600 V IGBT
  die; at 5 nF/die it supplies 3.8%. It is also the wrong regime — the
  C_T/deadtime mechanism bites at light load, where the current cannot
  commutate the node during deadtime, and these residual points are at
  130 A. Note both Costa terms are *ratios* to output power, so they
  rise as m falls because P_o shrinks, not because the loss grows; a
  ratio cannot supply the absolute watts this gap needs.

Candidates still not quantified: fundamental-frequency Tj cycling at
low f_out, which needs the transient solve; gate-driver and control
power (small, and ORNL disabled the 12 V converter and A/C inverter
during these runs, §3.3.1). DC-link capacitor ESR was checked and
rejected: the 3-phase capacitor ripple current goes to zero as the
modulation index falls, which is the wrong direction. Boost-converter
loss is outside the measurement boundary (P_dc is taken at the inverter
DC input, downstream of the boost).

Derivation approach:
- The SPWM conduction formulas depend on m and cos(phi) only through
  the product m*cos(phi). This product is derived directly from the
  true power measurement: m*cos(phi) = P_ac * 2*sqrt(2) / (3*V_dc*I).
  This avoids v_ac_V, which is total RMS including PWM harmonics and
  cannot yield a reliable fundamental modulation index or displacement
  power factor.
- The OperatingPoint encodes m*cos(phi) as m_index with pf=1.0; the
  conduction loss formulas consume m*pf, so the result is identical.
- 18/428 points have m*cos(phi) slightly above 1.0 (max 1.08),
  clamped to 1.0 (error < 2% on the modulation-dependent conduction
  correction, negligible vs overall model uncertainty).

Known limitations:
- IGBT switching energies are estimated (no measured data exists)
- Q_rr characterized at 25C/300V, actual operating conditions higher
- Conduction params from comparable devices, not measured on Prius die
- No R_g scaling (gate resistance unknown)
- Switching loss integral assumes every PWM period commutates; in
  overmodulation the actual switching loss is lower (conservative)
"""

from __future__ import annotations

import csv
import dataclasses
import itertools
import math
from dataclasses import dataclass
from pathlib import Path

import pytest

from heatsweep.components.assembly import Assembly, DevicePosition
from heatsweep.components.device import load_device_toml
from heatsweep.components.operating_point import OperatingPoint
from heatsweep.fem import load_stack_toml
from heatsweep.models.semiconductor_loss import _compute_device_losses
from heatsweep.models.thermal import solve_thermal_steady_state

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEVICE_DIR = Path(__file__).resolve().parent.parent / "devices"
STACK_TOML = DEVICE_DIR / "prius_2004_igbt" / "thermal_stack.toml"

POLE_PAIRS = 4  # MG2: 8-pole PMSM
# One of MG2's two carrier modes (Toyota HV ECU data list: 1.25 or 5 kHz;
# powertrain ref §8). No ORNL report states a carrier frequency for the
# 2004 motor inverter and Table B-1 does not label the mode per point, so
# applying 5 kHz to all 428 is an assumption. Sweeping 1.25-15 kHz leaves
# the residual's rms at 110-111 W throughout -- it moves the level of
# predicted loss, not the shape -- so the low-speed gap does not turn on
# this value. 1.25 kHz would widen it (100% underpredicting, sub-1000 rpm
# band 2.98% -> 3.76% of P_dc).
F_SW_HZ = 5000.0
N_PARALLEL = 2  # parallel die per switch position
N_POSITIONS = 6  # 3-phase bridge
TJ_ASSUMED_C = 125.0  # fixed-Tj comparison variant only
T_DEAD_S = 1.0e-6

# Thermal boundary for the LPTN solve.
T_COOLANT_C = 55.0  # ORNL/TM-2006/423 primary test condition

# Points at or above this torque are the intermittent-duty subset ORNL ran
# with the coolant dropped to 0 degC, and their measured loss is not usable
# (see module docstring, item 1). All 35 of them fall at 468-1307 rpm; the
# torque envelope means no point above 1400 rpm reaches this value, so the
# single torque criterion is sufficient and no speed bound is needed.
INTERMITTENT_DUTY_TORQUE_NM = 300.0


def is_intermittent_duty(torque_Nm: float) -> bool:
    """True for ORNL points in the 0 degC-coolant intermittent-duty region.

    ORNL/TM-2006/423 §3.3.2: "Obtaining certain low-speed, high-torque data
    well into the intermittent-duty portion of the operating window required
    lowering the coolant temperature substantially to 0 degC". Table B-1 does
    not flag which rows those were. This selects them by torque, which is
    what bounds the intermittent-duty window in the report's own Fig 3.17
    peak-torque envelope (400 Nm from 1-1200 rpm).

    The selection is corroborated independently by the data itself: these
    points, and only these, break monotonicity of measured loss in current
    within a speed band (see
    TestIntermittentDutySubset::test_measured_loss_falls_with_current).
    """
    return torque_Nm >= INTERMITTENT_DUTY_TORQUE_NM
# Elmer, Prius stack TOML (MG2 die), 100 W, h = 5000 W/m^2K, 40 x 40 mm
# unit cell, mesh-converged (tests/test_fem.py::TestElmerSolve docstring).
RTH_J_COOLANT_FEM_K_W = 0.386


def _fem_split_rth() -> tuple[float, float]:
    """(Rth_jc, Rth_cs) per die in K/W, both from the FEM result.

    The FEM junction-to-coolant value is the whole per-die path. It is
    split at the die-attach/DBA boundary: the 1-D die + die-attach share
    at die area becomes Rth_jc and the remainder becomes Rth_cs, so the
    LPTN path sums back to the FEM total. The device TOML Rth_jc (0.35
    K/W) is NOT used here: it is the CM100DU-12F module figure, junction
    to baseplate bottom, so it already contains the DBC and baseplate
    layers that the FEM remainder would add again (0.35 + 0.31 = 0.66
    K/W). The lower-bound rule (datasheet Rth_jc must not exceed any
    predicted junction-to-case path) does not apply here because no
    datasheet Rth_jc exists for this device. Sensitivity:
    any total path in [0, 0.66] K/W moves the anchor median by < 1 point.

    The 12 IGBT die share the cold plate, but the FEM unit cell has
    adiabatic sides and its own film term, so Rth_sa is 0. The diode's
    loss share (Q_rr, dead-time conduction) is deposited in the IGBT die
    cell instead of the diode's own cell, which biases Tj high by a few
    degrees (conservative).
    """
    stack = load_stack_toml(STACK_TOML)
    a_die = stack.die_area_m2
    r_jc = sum(
        layer.t_m / (layer.k_W_mK * a_die)
        for layer in stack.layers
        if layer.name in ("die", "die_attach")
    )
    return r_jc, RTH_J_COOLANT_FEM_K_W - r_jc


RTH_JC_K_W, RTH_CS_K_W = _fem_split_rth()


@dataclass
class MeasuredPoint:
    speed_rpm: float
    torque_Nm: float
    p_dc_W: float
    p_ac_W: float
    eta_inverter: float
    v_dc_V: float
    i_ac_A: float

    @property
    def p_loss_measured_W(self) -> float:
        return self.p_dc_W - self.p_ac_W


def _load_performance_map() -> list[MeasuredPoint]:
    path = DATA_DIR / "ornl_prius_2004_dyno" / "performance_map.csv"
    points: list[MeasuredPoint] = []
    with open(path) as f:
        for row in csv.DictReader(f):
            points.append(MeasuredPoint(
                speed_rpm=float(row["speed_rpm"]),
                torque_Nm=float(row["torque_Nm"]),
                p_dc_W=float(row["p_dc_W"]),
                p_ac_W=float(row["p_ac_W"]),
                eta_inverter=float(row["eta_inverter"]),
                v_dc_V=float(row["v_dc_V"]),
                i_ac_A=float(row["i_ac_A"]),
            ))
    return points


def _derive_operating_point(mp: MeasuredPoint) -> OperatingPoint | None:
    """Derive OperatingPoint fields from measured data. Returns None if
    the point cannot be modeled (e.g. near-zero current)."""
    if mp.i_ac_A < 1.0:
        return None

    f_out_Hz = mp.speed_rpm * POLE_PAIRS / 60.0

    # Derive m*cos(phi) from true power, bypassing v_ac_V which is total
    # RMS including PWM harmonics.
    # P_ac = 3 * (m * V_dc / (2*sqrt(2))) * I * cos(phi)
    # => m*cos(phi) = P_ac * 2*sqrt(2) / (3 * V_dc * I)
    m_cos_phi = mp.p_ac_W * 2.0 * math.sqrt(2.0) / (3.0 * mp.v_dc_V * mp.i_ac_A)
    m_cos_phi = min(m_cos_phi, 1.0)

    i_per_die = mp.i_ac_A / N_PARALLEL

    # Encode m*cos(phi) as m_index with pf=1: the conduction formulas
    # consume only the product m*cos(phi), never m or phi alone. If a
    # future model term uses them separately, this encoding breaks.
    return OperatingPoint(
        f_sw_Hz=F_SW_HZ,
        V_dc=mp.v_dc_V,
        I_phase_rms=i_per_die,
        f_out_Hz=f_out_Hz,
        pf=1.0,
        m_index=m_cos_phi,
        t_dead_s=T_DEAD_S,
        Tj_assumed_C=TJ_ASSUMED_C,
    )


def _build_single_die_position() -> DevicePosition:
    """Load one Prius IGBT die as a single DevicePosition."""
    dev = load_device_toml(DEVICE_DIR / "prius_2004_igbt" / "prius_2004_igbt.toml")
    return DevicePosition(position="single_die", device=dev)


@dataclass
class AnchorResult:
    speed_rpm: float
    torque_Nm: float
    i_ac_A: float
    p_loss_measured_W: float
    p_loss_predicted_W: float
    eta_measured: float
    eta_predicted: float
    tj_C: float
    p_dc_W: float

    @property
    def loss_error_W(self) -> float:
        return self.p_loss_predicted_W - self.p_loss_measured_W

    @property
    def loss_error_pct(self) -> float:
        if self.p_loss_measured_W == 0:
            return float("inf")
        return 100.0 * self.loss_error_W / self.p_loss_measured_W


def _run_anchor(thermal_feedback: bool = True) -> list[AnchorResult]:
    """Run the anchor. With thermal_feedback, Tj per point comes from the
    LPTN fixed-point solve; otherwise Tj is fixed at TJ_ASSUMED_C."""
    points = _load_performance_map()
    dp = _build_single_die_position()
    dp_thermal = DevicePosition(
        position=dp.position,
        device=dataclasses.replace(dp.device, Rth_jc=RTH_JC_K_W),
        Rth_cs=RTH_CS_K_W,
    )
    assembly = Assembly(
        name="prius_2004_single_die",
        topology="three_phase_bridge",
        devices=(dp_thermal,),
        T_amb_C=T_COOLANT_C,
        Rth_sa=0.0,
    )
    results: list[AnchorResult] = []

    for mp in points:
        op = _derive_operating_point(mp)
        if op is None:
            continue

        if thermal_feedback:
            tr = solve_thermal_steady_state(assembly, op.to_dict())
            assert tr.converged, f"LPTN did not converge at {mp.speed_rpm:.0f} rpm"
            p_die = tr.p_total_W
            tj = tr.Tj_C[dp.position]
        else:
            p_die = _compute_device_losses(dp, op)["p_total_W"]
            tj = TJ_ASSUMED_C
        p_bridge = p_die * N_PARALLEL * N_POSITIONS

        eta_predicted = mp.p_ac_W / (mp.p_ac_W + p_bridge) if (mp.p_ac_W + p_bridge) > 0 else 0

        results.append(AnchorResult(
            speed_rpm=mp.speed_rpm,
            torque_Nm=mp.torque_Nm,
            i_ac_A=mp.i_ac_A,
            p_loss_measured_W=mp.p_loss_measured_W,
            p_loss_predicted_W=p_bridge,
            eta_measured=mp.eta_inverter,
            eta_predicted=eta_predicted,
            tj_C=tj,
            p_dc_W=mp.p_dc_W,
        ))

    return results


def _median_abs_error_pct(results: list[AnchorResult]) -> float:
    errors = sorted(abs(r.loss_error_pct) for r in results)
    return errors[len(errors) // 2]


# ---------------------------------------------------------------------------
# Anchor tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def anchor() -> list[AnchorResult]:
    return _run_anchor(thermal_feedback=True)


@pytest.fixture(scope="module")
def anchor_fixed_tj() -> list[AnchorResult]:
    return _run_anchor(thermal_feedback=False)


@pytest.fixture(scope="module")
def anchor_clean(anchor: list[AnchorResult]) -> list[AnchorResult]:
    """Anchor results with the intermittent-duty subset removed."""
    return [r for r in anchor if not is_intermittent_duty(r.torque_Nm)]


class TestOrnlInverterAnchor:
    """Validate semiconductor loss model against ORNL Prius inverter data."""

    def test_coverage(self, anchor: list[AnchorResult]) -> None:
        """Model must produce results for the majority of operating points."""
        assert len(anchor) >= 400, f"Only {len(anchor)}/428 points modeled"

    def test_m_cos_phi_bounded(self, anchor: list[AnchorResult]) -> None:
        """m*cos(phi) derived from P_ac must be in (0, ~1] at every point.

        Values > 1 are clamped; this test checks the raw derivation
        stays below 4/pi (~1.27), the six-step fundamental ceiling.
        """
        points = _load_performance_map()
        six_step_limit = 4.0 / math.pi
        for mp in points:
            if mp.i_ac_A < 1.0:
                continue
            mc = mp.p_ac_W * 2.0 * math.sqrt(2.0) / (3.0 * mp.v_dc_V * mp.i_ac_A)
            assert mc > 0, f"m*cos(phi) <= 0 at {mp.speed_rpm:.0f} rpm"
            assert mc < six_step_limit, (
                f"m*cos(phi)={mc:.3f} at {mp.speed_rpm:.0f} rpm — "
                f"exceeds six-step ceiling {six_step_limit:.3f}"
            )

    def test_median_loss_error_within_50pct(self, anchor: list[AnchorResult]) -> None:
        """Median absolute loss error must be under 50%.

        The model predicts semiconductor losses only. The gap includes
        parasitic path resistance (bus bar, wire bond, connector I²R)
        at high current, and power-analyzer uncertainty on P_dc - P_ac
        (a small difference of large measurements) at low current.
        50% reflects semiconductor-only accuracy; should tighten as
        parasitic path resistance is added. Observed: 40.6% with LPTN
        thermal feedback (36.0% at fixed Tj = 125).
        """
        median = _median_abs_error_pct(anchor)
        assert median < 50.0, f"Median |loss error| = {median:.1f}%"

    def test_thermal_feedback_tj_range(self, anchor: list[AnchorResult]) -> None:
        """Solved Tj must sit between coolant and Tj_max at every point.

        Observed: 58-89 degC, median 66, at T_coolant = 55. All below the
        old 125 degC assumption, which the ORNL steady-state points (>= 20 s
        holds, 55 degC coolant) never approached.
        """
        dev = _build_single_die_position().device
        for r in anchor:
            assert T_COOLANT_C < r.tj_C < dev.Tj_max, (
                f"Tj={r.tj_C:.1f} at {r.speed_rpm:.0f} rpm / {r.torque_Nm:.0f} Nm"
            )
        assert max(r.tj_C for r in anchor) < TJ_ASSUMED_C

    def test_tj_assumption_is_not_the_dominant_error(
        self, anchor: list[AnchorResult], anchor_fixed_tj: list[AnchorResult],
    ) -> None:
        """Replacing fixed Tj = 125 with the LPTN solve moves the median
        |error| by less than 10 points. If this fails, the thermal path
        (Rth, T_coolant, die area) has become a first-order term in the
        anchor and its inputs need re-examining before the loss model.
        Observed: 36.0% -> 40.6%.
        """
        delta = _median_abs_error_pct(anchor) - _median_abs_error_pct(anchor_fixed_tj)
        assert abs(delta) < 10.0, f"Thermal feedback moved median |error| by {delta:+.1f} points"

    def test_model_is_conservative(self, anchor: list[AnchorResult]) -> None:
        """Semiconductor-only model should underpredict total inverter loss.

        The model omits parasitic path resistance and other non-semiconductor
        losses, so it should predict less loss than measured. If >80% of
        points underpredict, the model is behaving as expected.

        Threshold history: 90% -> 80% when switching-energy Tj scaling was
        added (Q_rr at 125C is ~1.6x its 25C datasheet value, E_off tail
        current rises with Tj). The added diode recovery loss at low
        current pushed some low-loss points from under- to over-prediction,
        where the measured P_dc - P_ac is itself dominated by analyzer
        uncertainty. Observed: 89% underpredicting, median |error| 36% at
        fixed Tj = 125; 92% / 41% with LPTN thermal feedback (lower Tj,
        lower predicted loss).
        """
        under = sum(1 for r in anchor if r.loss_error_pct < 0)
        frac = under / len(anchor)
        assert frac > 0.80, f"Only {frac:.0%} underpredicting — expected >80%"

    def test_no_negative_loss_predictions(self, anchor: list[AnchorResult]) -> None:
        """Predicted loss must be non-negative at every point."""
        negatives = [r for r in anchor if r.p_loss_predicted_W < 0]
        assert len(negatives) == 0

    def test_high_speed_error_within_analyzer_floor(self, anchor: list[AnchorResult]) -> None:
        """Above 2000 rpm, mean |pred - meas| must be under 0.5% of P_dc.

        This is where the measured inverter efficiency is 98-99% and the
        loss is a small difference of two ~28 kW readings; the model's
        residual there (observed 0.38% for 2000-4000 rpm, 0.21% above)
        is at the level of the analyzer uncertainty, so a tighter bound
        would be pinning noise. The 0.5% is a regression pin, not an
        instrument-derived figure. Below 2000 rpm see the module docstring.
        """
        high = [r for r in anchor if r.speed_rpm >= 2000.0]
        assert len(high) >= 100
        frac = sum(abs(r.loss_error_W) / r.p_dc_W for r in high) / len(high)
        assert frac < 0.005, f"Mean |error|/P_dc above 2000 rpm = {100 * frac:.2f}%"

    def test_clean_set_underpredicts_everywhere_below_2000_rpm(
        self, anchor_clean: list[AnchorResult],
    ) -> None:
        """With the intermittent-duty subset removed, every point below
        2000 rpm must underpredict.

        This is the structural payoff of identifying that subset: the
        semiconductor-only model omits real loss, so it should never
        overpredict where the measured loss is large enough to be well
        resolved. On the full 428 points 89% of the <1000 rpm band
        underpredicts; on the clean set it is 100% (n=113 below 1000,
        n=138 for 1000-2000). Overall 96.9% vs 92.1%.

        Above 2000 rpm the measured loss is a small difference of two
        ~28 kW readings and the sign is not meaningful, so that region
        is excluded here rather than pinned.
        """
        low = [r for r in anchor_clean if r.speed_rpm < 2000.0]
        assert len(low) >= 240
        over = [r for r in low if r.loss_error_pct > 0]
        assert not over, (
            f"{len(over)}/{len(low)} points below 2000 rpm overpredict, "
            f"first at {over[0].speed_rpm:.0f} rpm / {over[0].torque_Nm:.0f} Nm"
        )

    def test_residual_equivalent_resistance_falls_with_speed(
        self, anchor_clean: list[AnchorResult],
    ) -> None:
        """The unexplained loss, written as R_eff * 3 * I^2 per phase, must
        be markedly larger at low speed than at high speed.

        Observed R_eff: 19.1 mOhm/phase at 300 rpm falling monotonically to
        4.0 mOhm/phase at 5750 rpm. A physical conductor resistance rises
        with frequency, so this rules out bus-bar and wire-bond I^2R as the
        mechanism. Pinned loosely (low band > 2x high band) because R_eff
        is a summary of a residual, not a measured quantity; the point of
        the test is the direction and the order of magnitude.
        """
        def r_eff(rows: list[AnchorResult]) -> float:
            # Least squares through the origin on basis 3*I^2.
            num = sum((r.p_loss_measured_W - r.p_loss_predicted_W)
                      * 3.0 * r.i_ac_A**2 for r in rows)
            den = sum((3.0 * r.i_ac_A**2) ** 2 for r in rows)
            return num / den

        low = [r for r in anchor_clean if r.speed_rpm < 1200.0]
        high = [r for r in anchor_clean if r.speed_rpm >= 2400.0]
        assert len(low) >= 100 and len(high) >= 90
        r_low, r_high = r_eff(low), r_eff(high)
        assert 0.010 < r_low < 0.025, f"R_eff low speed = {1000 * r_low:.1f} mOhm/phase"
        assert 0.002 < r_high < 0.010, f"R_eff high speed = {1000 * r_high:.1f} mOhm/phase"
        assert r_low > 2.0 * r_high, (
            f"R_eff {1000 * r_low:.1f} -> {1000 * r_high:.1f} mOhm/phase "
            f"is not the observed strong decline with speed"
        )

    def test_loss_monotone_in_current(self, anchor: list[AnchorResult]) -> None:
        """Predicted loss must increase with phase current (monotone on average).

        Bin by I_ac quartiles and check that mean predicted loss increases."""
        sorted_by_current = sorted(anchor, key=lambda r: r.i_ac_A)
        n = len(sorted_by_current)
        q = n // 4
        quartile_means = []
        for i in range(4):
            start = i * q
            end = (i + 1) * q if i < 3 else n
            mean_pred = sum(r.p_loss_predicted_W for r in sorted_by_current[start:end]) / (end - start)
            quartile_means.append(mean_pred)
        for i in range(3):
            assert quartile_means[i] < quartile_means[i + 1], (
                f"Predicted loss not monotone in current: Q{i+1}={quartile_means[i]:.0f} >= "
                f"Q{i+2}={quartile_means[i+1]:.0f}"
            )


class TestIntermittentDutySubset:
    """Evidence that the torque >= 300 Nm points are not usable loss data.

    These tests exist so the exclusion in `is_intermittent_duty` is carried
    by a demonstrated property of the measurements, not by an assertion in
    a docstring. If a future data revision fixes these rows, these tests
    fail and the exclusion should be removed.
    """

    def test_subset_is_low_speed_and_bounded(self) -> None:
        """The torque criterion alone selects a low-speed region.

        No point above 1400 rpm reaches 300 Nm, so a speed bound would be
        redundant. Observed: 35 points spanning 468-1307 rpm.
        """
        points = _load_performance_map()
        subset = [mp for mp in points if is_intermittent_duty(mp.torque_Nm)]
        assert 30 <= len(subset) <= 40, f"{len(subset)} points selected"
        assert max(mp.speed_rpm for mp in subset) < 1400.0
        rest = [mp for mp in points if not is_intermittent_duty(mp.torque_Nm)]
        assert max(mp.torque_Nm for mp in rest) < INTERMITTENT_DUTY_TORQUE_NM

    def test_measured_loss_falls_with_current(self) -> None:
        """Within a low-speed band, measured loss drops sharply as current
        rises — only across the intermittent-duty boundary.

        No loss mechanism decreases with current at fixed speed and bus
        voltage, so a drop of this size is a measurement or test-condition
        artefact. Observed at 700 rpm: 147 A / 1282 W -> 159 A / 489 W.
        Every such drop must involve a point in the excluded subset; if one
        appeared among the retained points the criterion would be wrong.
        """
        points = _load_performance_map()
        found = 0
        for lo, hi in ((450, 520), (680, 720), (880, 920)):
            band = sorted(
                (mp for mp in points if lo <= mp.speed_rpm < hi),
                key=lambda mp: mp.i_ac_A,
            )
            for a, b in itertools.pairwise(band):
                if b.p_loss_measured_W < 0.75 * a.p_loss_measured_W:
                    found += 1
                    assert is_intermittent_duty(b.torque_Nm), (
                        f"Measured loss falls {a.p_loss_measured_W:.0f} -> "
                        f"{b.p_loss_measured_W:.0f} W as current rises "
                        f"{a.i_ac_A:.0f} -> {b.i_ac_A:.0f} A at "
                        f"{b.speed_rpm:.0f} rpm, but {b.torque_Nm:.0f} Nm is "
                        f"not in the excluded subset"
                    )
        assert found >= 5, f"Only {found} monotonicity violations found"

    def test_efficiency_steps_up_inside_the_excluded_region(self) -> None:
        """Measured inverter efficiency jumps 1-3 points inside the subset.

        Efficiency otherwise varies smoothly with torque, so a step this
        size marks a change in test conditions. The step does not land on
        exactly 300 Nm in every band — it is at 337 Nm at 500 rpm, 308 at
        700, 307 at 900 — so the test asserts only that it falls at or
        above the cutoff, which is what makes the cutoff safe.
        """
        points = _load_performance_map()
        for lo, hi in ((450, 520), (680, 720), (880, 920)):
            band = sorted(
                (mp for mp in points if lo <= mp.speed_rpm < hi),
                key=lambda mp: mp.torque_Nm,
            )
            steps = [
                (b.eta_inverter - a.eta_inverter, a.torque_Nm, b.torque_Nm)
                for a, b in itertools.pairwise(band)
            ]
            best = max(steps)
            assert best[0] > 0.008, f"{lo}-{hi} rpm: largest step only {best[0]:.3f}"
            assert best[2] >= INTERMITTENT_DUTY_TORQUE_NM, (
                f"{lo}-{hi} rpm: largest efficiency step is between "
                f"{best[1]:.0f} and {best[2]:.0f} Nm, below the "
                f"{INTERMITTENT_DUTY_TORQUE_NM:.0f} Nm cutoff"
            )

    def test_model_overpredicts_on_the_subset(self, anchor: list[AnchorResult]) -> None:
        """The model overpredicts on most excluded points and almost none
        of the retained ones.

        This is the sign reversal that makes the subset visible to the
        anchor: a semiconductor-only model cannot legitimately overpredict
        total inverter loss. Observed: 63% overpredicting on the subset,
        3% on the rest.
        """
        subset = [r for r in anchor if is_intermittent_duty(r.torque_Nm)]
        rest = [r for r in anchor if not is_intermittent_duty(r.torque_Nm)]
        over_subset = sum(1 for r in subset if r.loss_error_pct > 0) / len(subset)
        over_rest = sum(1 for r in rest if r.loss_error_pct > 0) / len(rest)
        assert over_subset > 0.5, f"Only {over_subset:.0%} of subset overpredicts"
        assert over_rest < 0.10, f"{over_rest:.0%} of retained points overpredict"
