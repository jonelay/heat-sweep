"""Validation anchor: Foster thermal model against Infineon AN2008-03.

The only external reference values in the thermal test suite. Every Foster
set in `test_thermal.py` is invented round numbers (R = 0.3, tau = 0.01 and
similar), which pins self-consistency -- round-trip, monotonicity, steady
state -- but cannot catch a systematically wrong conversion, because nothing
outside the code says what the answer should be. This file supplies that.

Source
------
T. Schuetze, "Thermal equivalent circuit models," Infineon Technologies AG,
application note AN2008-03, v1.0, 2008-06-16 (supersedes AN2001-05), p. 4.
The note gives one worked partial-fraction (Foster) parameter set for an
IGBT and its anti-parallel diode, tabulated as r_i [K/kW] and tau_i [s].

Only the numeric values are reproduced here; the note itself is Infineon
copyright and is not vendored into this repository. The English original
governs -- the copy consulted was the Chinese translation, which carries an
explicit clause deferring to the English text on any discrepancy. The
tabulated numbers are language-independent (the original uses decimal
commas: "1,56" for 1.56).

What this anchor pins
---------------------
1. The published Foster sets evaluate to the note's stated steady-state
   values: sum(r_i) = 8.51 K/kW for the IGBT, 17.00 K/kW for the diode.
2. Foster-to-Cauer conversion stays physical and Zth-preserving on a real
   datasheet time-constant spread (0.0068 s to 2.0212 s, a ratio of ~297).
   The invented fixtures in `test_thermal.py` span 100:1 and 1000:1 with
   round tau values; the conversion is numerically delicate, and real
   datasheet spacing is the case that matters.
3. The diode chain is the IGBT chain scaled by ~2.0 at identical taus --
   a structural property of the published data, and a cheap transcription
   check: a mistyped digit breaks the ratio.

What it does NOT pin
--------------------
AN2008-03 publishes the Foster side only. It gives no worked Cauer table,
so there is no external reference for the converted R and C values
themselves -- test 2 above is still a self-consistency check, just on
authoritative inputs rather than invented ones. An external Cauer anchor
needs a different source.

Why the note matters beyond these numbers
-----------------------------------------
AN2008-03 is the origin of the standing rule that a Foster Zth_jc must
never be concatenated with an external Rth_cs/Rth_sa. Its
argument: the datasheet partial-fraction model is *measured with a specific
heat sink attached*, so its coefficients already encode a boundary
condition, and the network nodes carry no physical meaning. The note adds
that Infineon characterises modules on a water-cooled sink deliberately --
constrained heat spreading yields a higher, conservative Rth_jc, where an
air-cooled sink spreads heat more widely and measures lower. See
`TestFosterConcatenationIsWrong` for the failure this predicts.
"""

from __future__ import annotations

import numpy as np
import pytest

from heatsweep.components.device import FosterPair
from heatsweep.models.thermal import foster_to_cauer, zth_cauer, zth_foster

# ---------------------------------------------------------------------------
# AN2008-03 p. 4, transcribed. r_i given in K/kW; converted to K/W here.
# ---------------------------------------------------------------------------

_TAU_S = (0.0068, 0.0642, 0.3209, 2.0212)
_R_IGBT_K_PER_KW = (1.56, 4.25, 1.26, 1.44)
_R_DIODE_K_PER_KW = (3.11, 8.49, 2.52, 2.88)

AN2008_03_IGBT = tuple(
    FosterPair(R=r / 1000.0, tau=tau) for r, tau in zip(_R_IGBT_K_PER_KW, _TAU_S, strict=True)
)
AN2008_03_DIODE = tuple(
    FosterPair(R=r / 1000.0, tau=tau) for r, tau in zip(_R_DIODE_K_PER_KW, _TAU_S, strict=True)
)

# Stated in the note as the sum of the tabulated r_i.
RTH_JC_IGBT_K_PER_W = 8.51e-3
RTH_JC_DIODE_K_PER_W = 17.00e-3


class TestPublishedFosterSets:
    """The transcribed sets must reproduce AN2008-03's stated totals."""

    @pytest.mark.parametrize(
        ("foster", "expected"),
        [(AN2008_03_IGBT, RTH_JC_IGBT_K_PER_W), (AN2008_03_DIODE, RTH_JC_DIODE_K_PER_W)],
        ids=["igbt", "diode"],
    )
    def test_sum_matches_stated_rth_jc(
        self, foster: tuple[FosterPair, ...], expected: float
    ) -> None:
        """sum(R_i) is the datasheet Rth_jc -- the runtime invariant, on real data."""
        assert sum(fp.R for fp in foster) == pytest.approx(expected, rel=1e-12)

    @pytest.mark.parametrize(
        ("foster", "expected"),
        [(AN2008_03_IGBT, RTH_JC_IGBT_K_PER_W), (AN2008_03_DIODE, RTH_JC_DIODE_K_PER_W)],
        ids=["igbt", "diode"],
    )
    def test_zth_reaches_rth_jc(
        self, foster: tuple[FosterPair, ...], expected: float
    ) -> None:
        """Zth(t) -> sum(R_i) once t greatly exceeds the slowest tau."""
        z = zth_foster(100.0 * max(_TAU_S), foster)
        assert z == pytest.approx(expected, rel=1e-6)

    def test_diode_chain_is_igbt_chain_scaled(self) -> None:
        """Published diode R_i are ~2.0x the IGBT R_i at identical taus.

        A structural property of the note's data (the diode die is smaller),
        and a transcription check: a mistyped digit breaks the ratio.
        """
        for igbt, diode in zip(AN2008_03_IGBT, AN2008_03_DIODE, strict=True):
            assert diode.tau == igbt.tau
            assert pytest.approx(2.0, abs=0.01) == diode.R / igbt.R


class TestConversionOnDatasheetTimeConstants:
    """Foster-to-Cauer must hold up on real datasheet tau spacing."""

    @pytest.mark.parametrize(
        "foster", [AN2008_03_IGBT, AN2008_03_DIODE], ids=["igbt", "diode"]
    )
    def test_cauer_pairs_physical(self, foster: tuple[FosterPair, ...]) -> None:
        cauer = foster_to_cauer(foster)
        assert len(cauer) == len(foster)
        for i, cp in enumerate(cauer):
            assert cp.R > 0, f"Cauer R[{i}] = {cp.R}"
            assert cp.C > 0, f"Cauer C[{i}] = {cp.C}"

    @pytest.mark.parametrize(
        "foster", [AN2008_03_IGBT, AN2008_03_DIODE], ids=["igbt", "diode"]
    )
    def test_zth_preserved_across_conversion(self, foster: tuple[FosterPair, ...]) -> None:
        """Cauer Zth(t) must track Foster Zth(t) over the full tau range."""
        cauer = foster_to_cauer(foster)
        t = np.logspace(np.log10(_TAU_S[0] / 10.0), np.log10(_TAU_S[-1] * 10.0), 24)
        z_foster = np.asarray(zth_foster(t, foster))
        z_cauer = np.asarray(zth_cauer(t, cauer))
        np.testing.assert_allclose(z_cauer, z_foster, rtol=0.01)

    @pytest.mark.parametrize(
        ("foster", "expected"),
        [(AN2008_03_IGBT, RTH_JC_IGBT_K_PER_W), (AN2008_03_DIODE, RTH_JC_DIODE_K_PER_W)],
        ids=["igbt", "diode"],
    )
    def test_cauer_steady_state_matches(
        self, foster: tuple[FosterPair, ...], expected: float
    ) -> None:
        """Series R of the Cauer ladder is the same Rth_jc."""
        cauer = foster_to_cauer(foster)
        assert sum(cp.R for cp in cauer) == pytest.approx(expected, rel=1e-6)


class TestFosterConcatenationIsWrong:
    """Demonstrate the error AN2008-03 warns about, so the rule has a guard.

    The note's point: a Foster chain has Zth(0+) = 0, so hanging a bare
    Rth_cs on the end makes case temperature respond to a power step with no
    delay at all -- heat appears at the sink instantly. A Cauer ladder has
    Zth(0+) > 0 and the thermal capacitance in the right places.
    """

    RTH_CS = 0.05  # K/W, a plausible grease + sink path -- far larger than Rth_jc

    def test_foster_zth_starts_at_zero(self) -> None:
        assert zth_foster(0.0, AN2008_03_IGBT) == pytest.approx(0.0, abs=1e-15)

    def test_naive_concatenation_gives_instant_sink_response(self) -> None:
        """At t = tau_min/100 the naive sum is ~all Rth_cs: unphysical."""
        t_early = _TAU_S[0] / 100.0
        naive = float(zth_foster(t_early, AN2008_03_IGBT)) + self.RTH_CS
        # The junction has barely begun to heat, yet the concatenated model
        # already reports the full external path.
        assert naive == pytest.approx(self.RTH_CS, rel=0.05)
        assert naive > 5.0 * RTH_JC_IGBT_K_PER_W

    def test_steady_state_concatenation_is_legitimate(self) -> None:
        """The sum is valid at steady state -- only the transient is wrong."""
        z_inf = float(zth_foster(100.0 * max(_TAU_S), AN2008_03_IGBT))
        assert z_inf + self.RTH_CS == pytest.approx(RTH_JC_IGBT_K_PER_W + self.RTH_CS, rel=1e-6)
