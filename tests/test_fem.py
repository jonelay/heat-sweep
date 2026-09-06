"""FEM path tests: stack loading, 1-D bounds, mesh generation, Elmer solve.

Mesh tests skip without gmsh; the solve test skips without Elmer binaries.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import itertools
from pathlib import Path

import pytest

from heatsweep.fem import ThermalStack, load_stack_toml, rth_1d_bounds
from heatsweep.fem.elmer import BC_COOLANT, BC_DIE_TOP, FemResult, elmer_available, write_sif

STACK_TOML = Path(__file__).resolve().parent.parent / "devices" / "prius_2004_igbt" / "thermal_stack.toml"
LEAF_STACK_TOML = Path(__file__).resolve().parent.parent / "devices" / "leaf_2012_igbt" / "thermal_stack.toml"
HAS_GMSH = importlib.util.find_spec("gmsh") is not None


@pytest.fixture(scope="module")
def prius_stack() -> ThermalStack:
    return load_stack_toml(STACK_TOML)


@pytest.fixture(scope="module")
def leaf_stack() -> ThermalStack:
    return load_stack_toml(LEAF_STACK_TOML)


class TestStack:
    def test_load_prius_stack(self, prius_stack: ThermalStack) -> None:
        assert len(prius_stack.layers) == 9
        assert prius_stack.layers[0].name == "die"
        assert prius_stack.layers[-1].name == "heat_sink"
        # ORNL measured 9.0 mm junction-to-coolant path; TOML enforces this
        assert prius_stack.thickness_m == pytest.approx(9.0e-3, rel=1e-6)

    def test_z_bounds_contiguous(self, prius_stack: ThermalStack) -> None:
        zb = prius_stack.z_bounds()
        assert zb[0][1] == pytest.approx(prius_stack.thickness_m)
        assert zb[-1][0] == pytest.approx(0.0, abs=1e-12)
        for (lo_a, _), (_, hi_b) in itertools.pairwise(zb):
            assert lo_a == pytest.approx(hi_b)

    def test_total_path_mismatch_rejected(self, prius_stack: ThermalStack) -> None:
        with pytest.raises(ValueError, match="total_path_m"):
            dataclasses.replace(prius_stack, total_path_m=12.0e-3)

    def test_footprint_nesting_rejected(self, prius_stack: ThermalStack) -> None:
        with pytest.raises(ValueError, match="nest"):
            dataclasses.replace(prius_stack, tile_w_m=prius_stack.plate_w_m * 2)

    def test_1d_bounds_bracket_reference_estimate(self, prius_stack: ThermalStack) -> None:
        """ORNL/TM-2010/253 estimates Rth_j-coolant at 0.8-1.5 K/W per IGBT
        die. The analytic bracket must contain that range's lower edge at
        least; the upper (no-spreading) bound is dominated by 1/(h*A_die)."""
        lower, upper = rth_1d_bounds(prius_stack)
        assert 0 < lower < upper
        assert lower < 0.8 < upper
        # sanity: no-spreading film alone is 1/(5000 * 132.4e-6) ~ 1.51 K/W
        assert upper > 1.51


class TestLeafStack:
    """2012 LEAF PEM stack. Unlike the Prius stack it declares no
    total_path_m -- ORNL publishes no junction-to-coolant path length for
    the LEAF -- so there is no thickness check to assert against."""

    def test_load(self, leaf_stack: ThermalStack) -> None:
        assert len(leaf_stack.layers) == 8
        assert leaf_stack.layers[0].name == "die"
        assert leaf_stack.layers[-1].name == "grease_lower"
        assert leaf_stack.thickness_m == pytest.approx(6.769e-3, rel=1e-6)

    def test_no_total_path_declared(self, leaf_stack: ThermalStack) -> None:
        """Guards the deliberate omission: if someone adds a total_path_m
        they must have found a published path length, and the README's
        assumption 4 needs updating with it."""
        assert leaf_stack.total_path_m is None

    def test_ornl_measured_thicknesses(self, leaf_stack: ThermalStack) -> None:
        """The five layers ORNL actually measured. Estimated layers below
        the base plate are deliberately not pinned here."""
        t = {lay.name: lay.t_m for lay in leaf_stack.layers}
        assert t["die"] == pytest.approx(0.361e-3)
        assert t["die_attach"] == pytest.approx(0.180e-3)
        assert t["spacer"] == pytest.approx(2.55e-3)
        assert t["spacer_solder"] == pytest.approx(0.208e-3)
        assert t["baseplate"] == pytest.approx(3.17e-3)
        assert leaf_stack.die_area_m2 == pytest.approx(225.0e-6)

    def test_z_bounds_contiguous(self, leaf_stack: ThermalStack) -> None:
        zb = leaf_stack.z_bounds()
        assert zb[0][1] == pytest.approx(leaf_stack.thickness_m)
        assert zb[-1][0] == pytest.approx(0.0, abs=1e-12)
        for (lo_a, _), (_, hi_b) in itertools.pairwise(zb):
            assert lo_a == pytest.approx(hi_b)

    def test_1d_bounds_bracket_fem_result(self, leaf_stack: ThermalStack) -> None:
        lower, upper = rth_1d_bounds(leaf_stack)
        assert lower == pytest.approx(0.2285, rel=1e-3)
        assert upper == pytest.approx(1.6246, rel=1e-3)
        assert lower < 0.376 < upper

    def test_insulator_group_dominates_conduction(self, leaf_stack: ThermalStack) -> None:
        """The grease/insulator/grease group is estimated, not measured, and
        is over half the conduction path. If a future edit makes it a small
        correction instead, the README's sensitivity section is stale."""
        by_name = {lay.name: lay for lay in leaf_stack.layers}
        r_of = lambda lay: lay.t_m / (lay.k_W_mK * leaf_stack.plate_area_m2)  # noqa: E731
        r_est = sum(r_of(by_name[n]) for n in ("grease_upper", "insulator", "grease_lower"))
        r_cond = sum(
            lay.t_m / (lay.k_W_mK * (lambda wl: wl[0] * wl[1])(leaf_stack.footprint_dims(lay.footprint)))
            for lay in leaf_stack.layers
        )
        assert r_est / r_cond > 0.5


class TestSif:
    def test_write_sif_structure(self, prius_stack: ThermalStack, tmp_path: Path) -> None:
        sif = write_sif(prius_stack, 100.0, tmp_path)
        text = sif.read_text()
        assert text.count("Body ") == 9
        assert text.count("Material ") == 9 + text.count("  Material = ")
        assert f"Target Boundaries(1) = {BC_DIE_TOP}" in text
        assert f"Target Boundaries(1) = {BC_COOLANT}" in text
        q = 100.0 / prius_stack.die_area_m2
        assert f"Heat Flux = {q}" in text
        assert "Heat Transfer Coefficient = 5000.0" in text
        assert (tmp_path / "ELMERSOLVER_STARTINFO").exists()

    def test_write_sif_rejects_nonpositive_power(self, prius_stack: ThermalStack, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            write_sif(prius_stack, 0.0, tmp_path)


@pytest.mark.skipif(not HAS_GMSH, reason="gmsh not installed (pip install heatsweep[fem])")
class TestMesh:
    def test_build_mesh_physical_groups(self, prius_stack: ThermalStack, tmp_path: Path) -> None:
        import gmsh

        from heatsweep.fem.mesh import build_mesh

        msh = build_mesh(prius_stack, tmp_path / "stack.msh", size_max_m=4.0e-3, size_min_m=0.3e-3)
        assert msh.exists() and msh.stat().st_size > 0

        gmsh.initialize()
        try:
            gmsh.option.setNumber("General.Terminal", 0)
            gmsh.open(str(msh))
            vols = {tag for dim, tag in gmsh.model.getPhysicalGroups(3)}
            surfs = {tag for dim, tag in gmsh.model.getPhysicalGroups(2)}
            assert vols == set(range(1, 10))
            assert surfs == {BC_DIE_TOP, BC_COOLANT}
            n_nodes = len(gmsh.model.mesh.getNodes()[0])
            assert n_nodes > 100
        finally:
            gmsh.finalize()


@pytest.fixture(scope="module")
def result(prius_stack: ThermalStack, tmp_path_factory: pytest.TempPathFactory) -> FemResult:
    if not (HAS_GMSH and elmer_available()):
        pytest.skip("gmsh and Elmer binaries both required")
    from heatsweep.fem.elmer import run_case
    from heatsweep.fem.mesh import build_mesh

    d = tmp_path_factory.mktemp("elmer")
    msh = build_mesh(prius_stack, d / "stack.msh")
    return run_case(prius_stack, 100.0, msh, d / "case")


@pytest.mark.skipif(not elmer_available(), reason="ElmerGrid/ElmerSolver not on PATH")
@pytest.mark.skipif(not HAS_GMSH, reason="gmsh not installed")
class TestElmerSolve:
    """Prius IPEM, one MG2 IGBT die (12.73 x 10.4 mm), 100 W, h=5000,
    unit cell 40x40 mm.

    Mesh convergence (Elmer 26.2, 2026-09-06):
        size_max 4.0 mm /  1569 nodes  Rth = 0.3727 K/W
        size_max 2.0 mm /  4154 nodes  Rth = 0.3811 K/W  (default)
        size_max 1.0 mm / 18031 nodes  Rth = 0.3851 K/W
        size_max 0.7 mm / 44475 nodes  Rth = 0.3858 K/W
    Converged value ~0.386 K/W; default mesh is 1.2% low. (The earlier
    0.305 K/W used the 15.1 mm square boost-converter die by mistake.)
    The film term over the unit cell, 1/(h*A_plate) = 0.125 K/W, is a
    third of the total, so the result depends on cell size and h as
    much as on the stack. Sensitivity at the default mesh:
        h = 3000 / 5000 / 8000 W/m^2K  -> 0.466 / 0.381 / 0.333 K/W
        cell = 30 / 40 / 50 mm         -> 0.472 / 0.381 / 0.348 K/W
    """

    def test_rth_within_1d_bracket(self, prius_stack: ThermalStack, result: FemResult) -> None:
        lower, upper = rth_1d_bounds(prius_stack)
        assert lower < result.rth_j_coolant_K_W < upper, (
            f"FEM Rth {result.rth_j_coolant_K_W:.3f} K/W outside 1-D bracket [{lower:.3f}, {upper:.3f}]"
        )
        assert result.T_max_C > prius_stack.T_coolant_C

    def test_rth_regression(self, result: FemResult) -> None:
        """Default-mesh value pinned at 0.381 K/W +/-3%: catches BC, unit,
        or material-assignment regressions, not physics changes (a stack
        TOML edit that moves this must update the docstring table)."""
        assert result.rth_j_coolant_K_W == pytest.approx(0.381, rel=0.03)


@pytest.fixture(scope="module")
def leaf_result(leaf_stack: ThermalStack, tmp_path_factory: pytest.TempPathFactory) -> FemResult:
    if not (HAS_GMSH and elmer_available()):
        pytest.skip("gmsh and Elmer binaries both required")
    from heatsweep.fem.elmer import run_case
    from heatsweep.fem.mesh import build_mesh

    d = tmp_path_factory.mktemp("elmer_leaf")
    msh = build_mesh(leaf_stack, d / "stack.msh")
    return run_case(leaf_stack, 100.0, msh, d / "case")


@pytest.mark.skipif(not elmer_available(), reason="ElmerGrid/ElmerSolver not on PATH")
@pytest.mark.skipif(not HAS_GMSH, reason="gmsh not installed")
class TestLeafElmerSolve:
    """LEAF PEM, one IGBT die (15 x 15 mm), 100 W, h=5000, cell 40x40 mm.

    Mesh convergence (Elmer 26.2, 2026-09-06):
        size_max 4.0 mm /  1171 nodes  Rth = 0.3739 K/W
        size_max 2.0 mm /  3241 nodes  Rth = 0.3759 K/W  (default)
        size_max 1.0 mm / 14838 nodes  Rth = 0.3789 K/W
        size_max 0.7 mm / 34710 nodes  Rth = 0.3795 K/W
    Converged ~0.380 K/W; default mesh is 0.9% low. Sensitivity:
        h = 3000 / 5000 / 8000 W/m^2K -> 0.460 / 0.376 / 0.328 K/W
        cell =  30 /   40 /   50 mm   -> 0.517 / 0.376 / 0.319 K/W

    This lands within 1.5% of the 2004 Prius 0.381 K/W, which is a
    coincidence of two shared modelling assumptions rather than a
    hardware result -- see the device README's sensitivity section
    before quoting the comparison.
    """

    def test_rth_within_1d_bracket(self, leaf_stack: ThermalStack, leaf_result: FemResult) -> None:
        lower, upper = rth_1d_bounds(leaf_stack)
        assert lower < leaf_result.rth_j_coolant_K_W < upper, (
            f"FEM Rth {leaf_result.rth_j_coolant_K_W:.3f} K/W outside 1-D bracket [{lower:.3f}, {upper:.3f}]"
        )
        assert leaf_result.T_max_C > leaf_stack.T_coolant_C

    def test_rth_regression(self, leaf_result: FemResult) -> None:
        """Default-mesh value pinned at 0.376 K/W +/-3%. A stack TOML edit
        that moves this must update the docstring table and the README."""
        assert leaf_result.rth_j_coolant_K_W == pytest.approx(0.376, rel=0.03)


def _scale_conductivity(stack: ThermalStack, lam: float) -> ThermalStack:
    """Same geometry and boundary, every layer conductivity multiplied."""
    return dataclasses.replace(
        stack,
        layers=tuple(
            dataclasses.replace(lay, k_W_mK=lay.k_W_mK * lam) for lay in stack.layers
        ),
    )


K_SCALES = (1.0, 2.0, 4.0, 10.0, 100.0, 1000.0)


@pytest.fixture(scope="module")
def scaled_k_results(
    prius_stack: ThermalStack, tmp_path_factory: pytest.TempPathFactory,
) -> dict[float, float]:
    """Rth at each conductivity multiplier in K_SCALES, sharing one mesh.

    The mesh depends only on geometry, so scaling k does not invalidate it
    and every solve runs on identical elements. That removes discretisation
    as an explanation for any departure from the expected behaviour.
    """
    if not (HAS_GMSH and elmer_available()):
        pytest.skip("gmsh and Elmer binaries both required")
    from heatsweep.fem.elmer import run_case
    from heatsweep.fem.mesh import build_mesh

    d = tmp_path_factory.mktemp("elmer_kscale")
    msh = build_mesh(prius_stack, d / "stack.msh")
    return {
        lam: run_case(
            _scale_conductivity(prius_stack, lam), 100.0, msh, d / f"case_{lam}",
        ).rth_j_coolant_K_W
        for lam in K_SCALES
    }


@pytest.mark.skipif(not elmer_available(), reason="ElmerGrid/ElmerSolver not on PATH")
@pytest.mark.skipif(not HAS_GMSH, reason="gmsh not installed")
class TestConductivityScaling:
    """Scaling every layer conductivity by lambda, against the film limit.

    The existing checks on the Elmer number are the 1-D bracket, which is a
    factor of seven wide, and a regression pin, which says the value has not
    moved rather than that it is right. This class adds a check with an
    analytic target and no reference data.

    The film term is exact and independent of k: all 100 W leaves through
    the coolant face, so h*A*(T_face_mean - T_coolant) = P whatever the
    distribution on that face, giving 1/(h*A_plate) = 0.125 K/W here. As
    lambda grows the solid approaches isothermal and Rth must approach that
    value from above -- so the film is both a hard lower bound at every
    lambda and the limit at large lambda. A wrong BC area, a misapplied h,
    or a coolant boundary on the wrong surface breaks both while leaving
    the 1-D bracket and the regression pin satisfied.

    Rth is *not* exactly affine in 1/lambda. Scaling k at fixed h changes
    the Biot number, so the coolant face grows more isothermal with lambda
    and the spreading share of the conduction drop shifts with it. Measured
    on this stack, (Rth - film)*lambda rises monotonically and saturates:

        lambda      1        2        4       10      100     1000
        Rth      0.3811   0.2539   0.1897   0.1509   0.1276   0.1253
        (R-f)*l  0.25613  0.25772  0.25863  0.25923  0.25960  0.25964

    a total drift of 1.4% across three decades. The tests below assert the
    two exact properties and bound that drift, rather than asserting an
    affine law the physics does not support.
    """

    @staticmethod
    def _film(stack: ThermalStack) -> float:
        return 1.0 / (stack.h_conv_W_m2K * stack.plate_area_m2)

    def test_film_is_a_hard_lower_bound(
        self, prius_stack: ThermalStack, scaled_k_results: dict[float, float],
    ) -> None:
        """No conductivity can take Rth below the convective film."""
        film = self._film(prius_stack)
        for lam, rth in scaled_k_results.items():
            assert rth > film, f"lambda={lam}: Rth {rth:.4f} below film {film:.4f}"

    def test_monotone_decreasing_in_lambda(
        self, scaled_k_results: dict[float, float],
    ) -> None:
        """More conductive solid, less total resistance, at every step."""
        values = [scaled_k_results[lam] for lam in K_SCALES]
        for lo, hi in itertools.pairwise(values):
            assert lo > hi

    def test_approaches_film_at_large_lambda(
        self, prius_stack: ThermalStack, scaled_k_results: dict[float, float],
    ) -> None:
        """At lambda = 1000 the solid is near-isothermal and Rth must be the
        film term. This is the test with an analytic answer: it pins h and
        the coolant-face area directly, with no reference value and no
        dependence on the stack's own thicknesses."""
        film = self._film(prius_stack)
        assert scaled_k_results[1000.0] == pytest.approx(film, rel=5e-3), (
            f"Rth at lambda=1000 is {scaled_k_results[1000.0]:.5f} K/W, "
            f"analytic film {film:.5f} K/W"
        )

    def test_conduction_share_drift_is_bounded(
        self, prius_stack: ThermalStack, scaled_k_results: dict[float, float],
    ) -> None:
        """(Rth - film)*lambda is the conduction-plus-spreading resistance.

        It is not constant -- the Biot number moves with lambda -- but it
        must stay bounded, rise monotonically towards the isothermal-face
        limit, and vary by only a few percent. A sign error or a broken
        material assignment would not hold to that.
        """
        film = self._film(prius_stack)
        r_cond = [(scaled_k_results[lam] - film) * lam for lam in K_SCALES]
        for lo, hi in itertools.pairwise(r_cond):
            assert hi > lo
        assert (max(r_cond) - min(r_cond)) / min(r_cond) < 0.03

        # And the limit must sit inside the 1-D bracket net of the film.
        lower, upper = rth_1d_bounds(prius_stack)
        assert lower - film < r_cond[-1] < upper - film
