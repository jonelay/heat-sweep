"""Tests for device TOML loading and validation traps."""

from __future__ import annotations

import tempfile
import tomllib
from pathlib import Path

import pytest

from heatsweep.components.device import TableEntry, load_device_toml

# ---------------------------------------------------------------------------
# TableEntry validation
# ---------------------------------------------------------------------------


class TestTableEntryValidation:
    """Test that TableEntry rejects each validation trap."""

    def test_fewer_than_2_rows(self) -> None:
        with pytest.raises(ValueError, match="need >= 2 rows"):
            TableEntry(x=(1.0,), y=(2.0,), x_label="x", y_label="y",
                       conditions={"Tj": 25.0})

    def test_non_increasing_x(self) -> None:
        with pytest.raises(ValueError, match="not strictly increasing"):
            TableEntry(x=(1.0, 1.0, 3.0), y=(1.0, 2.0, 3.0),
                       x_label="x", y_label="y", conditions={"Tj": 25.0})

    def test_decreasing_x(self) -> None:
        with pytest.raises(ValueError, match="not strictly increasing"):
            TableEntry(x=(3.0, 2.0, 1.0), y=(1.0, 2.0, 3.0),
                       x_label="x", y_label="y", conditions={"Tj": 25.0})

    def test_non_finite_x(self) -> None:
        with pytest.raises(ValueError, match="not finite"):
            TableEntry(x=(1.0, float("inf")), y=(1.0, 2.0),
                       x_label="x", y_label="y", conditions={"Tj": 25.0})

    def test_non_finite_y_nan(self) -> None:
        with pytest.raises(ValueError, match="not finite"):
            TableEntry(x=(1.0, 2.0), y=(1.0, float("nan")),
                       x_label="x", y_label="y", conditions={"Tj": 25.0})

    def test_missing_conditions(self) -> None:
        with pytest.raises(ValueError, match="missing test conditions"):
            TableEntry(x=(1.0, 2.0), y=(1.0, 2.0),
                       x_label="x", y_label="y", conditions={})

    def test_mismatched_lengths(self) -> None:
        with pytest.raises(ValueError, match="lengths differ"):
            TableEntry(x=(1.0, 2.0, 3.0), y=(10.0, 20.0),
                       x_label="x", y_label="y", conditions={"Tj": 25.0})

    def test_valid_table(self) -> None:
        t = TableEntry(x=(1.0, 2.0, 3.0), y=(10.0, 20.0, 30.0),
                       x_label="x", y_label="y", conditions={"Tj": 25.0})
        assert len(t.x) == 3


# ---------------------------------------------------------------------------
# TOML loader validation
# ---------------------------------------------------------------------------

_VALID_TOML = """\
[device]
name = "TEST_FET"
type = "mosfet"
package = "TO-247"
manufacturer = "TestCo"
V_max = 600.0
I_max = 50.0
Tj_max = 175.0

[conduction]
Tj = [25.0, 100.0, 150.0]
R_ds_on = [0.010, 0.015, 0.020]
[conduction.conditions]
V_gs = 10.0
I_d = 20.0

[body_diode]
V_f = 0.7
Q_rr = 50e-9
[body_diode.conditions]
Tj = 25.0

[switching]
I = [5.0, 10.0, 20.0, 40.0]
E_on = [50e-6, 120e-6, 300e-6, 700e-6]
E_off = [30e-6, 80e-6, 200e-6, 500e-6]
scaling = "linear"
[switching.conditions]
V_dc = 400.0
R_g = 10.0
Tj = 25.0

[thermal]
Rth_jc = 0.5
[[thermal.Zth_jc_foster]]
R = 0.3
tau = 0.01
[[thermal.Zth_jc_foster]]
R = 0.2
tau = 0.1
"""


def _write_toml(content: str) -> Path:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(content)
    return Path(f.name)


class TestDeviceTomlLoader:
    """Test load_device_toml validation traps."""

    def test_valid_loads(self) -> None:
        path = _write_toml(_VALID_TOML)
        dev = load_device_toml(path)
        assert dev.name == "TEST_FET"
        assert dev.device_type == "mosfet"
        assert dev.R_ds_on_vs_Tj is not None
        assert len(dev.R_ds_on_vs_Tj.x) == 3
        path.unlink()

    def test_fewer_than_2_rows_in_conduction(self) -> None:
        bad = _VALID_TOML.replace(
            "Tj = [25.0, 100.0, 150.0]\nR_ds_on = [0.010, 0.015, 0.020]",
            "Tj = [25.0]\nR_ds_on = [0.010]",
        )
        path = _write_toml(bad)
        with pytest.raises(ValueError, match="need >= 2 rows"):
            load_device_toml(path)
        path.unlink()

    def test_non_increasing_x_in_switching(self) -> None:
        bad = _VALID_TOML.replace(
            "I = [5.0, 10.0, 20.0, 40.0]",
            "I = [5.0, 10.0, 10.0, 40.0]",
        )
        path = _write_toml(bad)
        with pytest.raises(ValueError, match="not strictly increasing"):
            load_device_toml(path)
        path.unlink()

    def test_non_finite_value_rejected_by_toml(self) -> None:
        """TOML rejects inf/nan literals; the parser raises before our validator."""
        bad = _VALID_TOML.replace(
            "R_ds_on = [0.010, 0.015, 0.020]",
            "R_ds_on = [0.010, .inf, 0.020]",
        )
        path = _write_toml(bad)
        with pytest.raises(tomllib.TOMLDecodeError):
            load_device_toml(path)
        path.unlink()

    def test_non_finite_value_via_table_entry(self) -> None:
        """Non-finite values are caught at the TableEntry level."""
        with pytest.raises(ValueError, match="not finite"):
            TableEntry(
                x=(25.0, float("inf")), y=(0.01, 0.02),
                x_label="Tj", y_label="R_ds_on", conditions={"V_gs": 10.0},
            )

    def test_missing_conditions_in_conduction(self) -> None:
        # Remove the conditions block from conduction
        bad = _VALID_TOML.replace(
            "[conduction.conditions]\nV_gs = 10.0\nI_d = 20.0",
            "",
        )
        path = _write_toml(bad)
        with pytest.raises(ValueError, match="missing test conditions"):
            load_device_toml(path)
        path.unlink()

    def test_tj_max_violation(self) -> None:
        bad = _VALID_TOML.replace("Tj_max = 175.0", "Tj_max = 100.0")
        path = _write_toml(bad)
        with pytest.raises(ValueError, match="exceeds device Tj_max"):
            load_device_toml(path)
        path.unlink()

    def test_foster_sum_mismatch(self) -> None:
        bad = _VALID_TOML.replace("Rth_jc = 0.5", "Rth_jc = 2.0")
        path = _write_toml(bad)
        with pytest.raises(ValueError, match=r"Foster sum.*does not match"):
            load_device_toml(path)
        path.unlink()

    def test_foster_sum_mismatch_direct_construction(self) -> None:
        """Foster validation fires on direct Device() construction too."""
        from heatsweep.components.device import Device, FosterPair
        with pytest.raises(ValueError, match=r"Foster sum.*does not match"):
            Device(
                name="bad", device_type="mosfet", package="TO-247",
                manufacturer="X", V_max=600, I_max=50, Tj_max=175,
                Rth_jc=2.0,
                Zth_jc_foster=(FosterPair(R=0.3, tau=0.01), FosterPair(R=0.2, tau=0.1)),
            )

    def test_negative_foster_r_rejected(self) -> None:
        from heatsweep.components.device import Device, FosterPair
        with pytest.raises(ValueError, match="Foster R"):
            Device(
                name="bad", device_type="mosfet", package="TO-247",
                manufacturer="X", V_max=600, I_max=50, Tj_max=175,
                Rth_jc=0.5,
                Zth_jc_foster=(FosterPair(R=-0.3, tau=0.01),),
            )

    def test_config_id_stable(self) -> None:
        path = _write_toml(_VALID_TOML)
        d1 = load_device_toml(path)
        d2 = load_device_toml(path)
        assert d1.config_id == d2.config_id
        path.unlink()


class TestBundledDevicesInSync:
    """`devices/` (source of truth) and `heatsweep/devices/` (wheel bundle)
    are maintained by hand; a drift means wheel installs ship stale params."""

    def test_bundled_tomls_match_source(self) -> None:
        root = Path(__file__).resolve().parent.parent
        src_dir = root / "devices"
        if not src_dir.is_dir():
            pytest.skip("source devices/ not present (installed wheel)")
        bundled_dir = root / "heatsweep" / "devices"
        src = sorted(p.relative_to(src_dir) for p in src_dir.rglob("*.toml"))
        assert src, "no device TOMLs under devices/"
        for rel in src:
            b = bundled_dir / rel
            assert b.exists(), f"{rel} missing from heatsweep/devices/"
            assert b.read_bytes() == (src_dir / rel).read_bytes(), (
                f"{rel} differs between devices/ and heatsweep/devices/ — "
                f"copy the source file over the bundled copy"
            )
