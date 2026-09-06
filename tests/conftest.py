"""Shared test fixtures for heatsweep tests."""

from __future__ import annotations

import pytest

from heatsweep.components.assembly import Assembly, DevicePosition
from heatsweep.components.device import Device, FosterPair, TableEntry
from heatsweep.components.operating_point import OperatingPoint


def make_mosfet(
    name: str = "TEST_FET",
    rds_tj: tuple[tuple[float, ...], tuple[float, ...]] | None = None,
    e_on_i: tuple[tuple[float, ...], tuple[float, ...]] | None = None,
    e_off_i: tuple[tuple[float, ...], tuple[float, ...]] | None = None,
    tj_max: float = 175.0,
    rth_jc: float = 0.5,
    foster: tuple[FosterPair, ...] | None = None,
    q_rr: float = 50e-9,
    v_f: float = 0.7,
) -> Device:
    """Create a test MOSFET device with sensible defaults."""
    if rds_tj is None:
        rds_tj = ((25.0, 100.0, 150.0), (0.010, 0.015, 0.020))
    if e_on_i is None:
        e_on_i = ((5.0, 10.0, 20.0, 40.0), (50e-6, 120e-6, 300e-6, 700e-6))
    if e_off_i is None:
        e_off_i = ((5.0, 10.0, 20.0, 40.0), (30e-6, 80e-6, 200e-6, 500e-6))
    if foster is None:
        foster = (FosterPair(R=0.3, tau=0.01), FosterPair(R=0.2, tau=0.1))

    return Device(
        name=name,
        device_type="mosfet",
        package="TO-247",
        manufacturer="TestCo",
        V_max=600.0,
        I_max=50.0,
        Tj_max=tj_max,
        R_ds_on_vs_Tj=TableEntry(
            x=rds_tj[0], y=rds_tj[1],
            x_label="Tj", y_label="R_ds_on",
            conditions={"V_gs": 10.0, "I_d": 20.0},
        ),
        E_on_vs_I=TableEntry(
            x=e_on_i[0], y=e_on_i[1],
            x_label="I", y_label="E_on",
            conditions={"V_dc": 400.0, "R_g": 10.0, "Tj": 25.0},
        ),
        E_off_vs_I=TableEntry(
            x=e_off_i[0], y=e_off_i[1],
            x_label="I", y_label="E_off",
            conditions={"V_dc": 400.0, "R_g": 10.0, "Tj": 25.0},
        ),
        V_f=v_f,
        Q_rr=q_rr,
        V_f_conditions={"Tj": 25.0},
        Rth_jc=rth_jc,
        Zth_jc_foster=foster,
    )


def make_igbt(
    name: str = "TEST_IGBT",
    v_ce0: float = 0.8,
    r_ce: float = 0.008,
    v_f: float = 1.8,
    rth_jc: float = 0.35,
) -> Device:
    """Create a test IGBT with constant (Tj-independent) conduction terms.

    No V_ce0_vs_Tj / r_ce_vs_Tj tables, so conduction depends only on the
    operating point. Tests that need the Tj dependence add the tables.
    """
    return Device(
        name=name,
        device_type="igbt",
        package="module",
        manufacturer="TestCo",
        V_max=600.0,
        I_max=100.0,
        Tj_max=175.0,
        V_ce0=v_ce0,
        r_ce=r_ce,
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
        V_f=v_f,
        Q_rr=2.0e-6,
        V_f_conditions={"Tj": 25.0},
        Rth_jc=rth_jc,
    )


def make_assembly(
    name: str = "test_bridge",
    n_devices: int = 6,
    **kwargs: object,
) -> Assembly:
    """Create a test three-phase bridge assembly."""
    dev = make_mosfet(**kwargs)  # type: ignore[arg-type]
    positions = ["Q1_high", "Q2_high", "Q3_high", "Q1_low", "Q2_low", "Q3_low"]
    devices = tuple(
        DevicePosition(position=positions[i], device=dev, Rth_cs=0.2)
        for i in range(min(n_devices, len(positions)))
    )
    return Assembly(
        name=name,
        topology="three_phase_bridge",
        devices=devices,
        T_amb_C=25.0,
    )


def make_op(**overrides: object) -> OperatingPoint:
    """Create a test operating point with sensible defaults."""
    defaults = {
        "f_sw_Hz": 20000.0,
        "V_dc": 400.0,
        "I_phase_rms": 10.0,
        "f_out_Hz": 50.0,
        "pf": 0.9,
        "m_index": 0.8,
        "modulation": "spwm",
        "t_dead_s": 1e-6,
        "R_g_on": 10.0,
        "R_g_off": 10.0,
        "T_amb_C": 25.0,
        "Tj_assumed_C": 100.0,
    }
    defaults.update(overrides)
    return OperatingPoint(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def mosfet() -> Device:
    return make_mosfet()


@pytest.fixture
def assembly() -> Assembly:
    return make_assembly()


@pytest.fixture
def op() -> OperatingPoint:
    return make_op()
