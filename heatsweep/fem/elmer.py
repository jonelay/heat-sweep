"""Elmer solver input (.sif) generation and execution for a ThermalStack.

Steady-state heat conduction, one heat source (uniform flux on the die
top face), one convective face (coolant), all other faces adiabatic.
The result of interest is Rth_j-coolant = (T_max - T_coolant) / P.

Requires ``ElmerGrid`` and ``ElmerSolver`` on PATH to *run*; writing the
case needs nothing.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from heatsweep.fem.mesh import BC_COOLANT, BC_DIE_TOP
from heatsweep.fem.stack import ThermalStack

MESH_DIR = "mesh"
SIF_NAME = "case.sif"
SCALARS_NAME = "scalars.dat"


class ElmerNotAvailable(RuntimeError):
    pass


@dataclass(frozen=True)
class FemResult:
    P_W: float
    T_max_C: float
    T_coolant_C: float
    n_nodes: int

    @property
    def rth_j_coolant_K_W(self) -> float:
        return (self.T_max_C - self.T_coolant_C) / self.P_W


def write_sif(stack: ThermalStack, P_W: float, case_dir: str | Path) -> Path:
    """Write ``case.sif`` for a steady conduction solve with power ``P_W``."""
    if P_W <= 0:
        raise ValueError("P_W must be > 0")
    case_dir = Path(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    q = P_W / stack.die_area_m2

    lines = [
        "Header",
        f'  Mesh DB "." "{MESH_DIR}"',
        "End",
        "",
        "Simulation",
        "  Coordinate System = Cartesian 3D",
        "  Simulation Type = Steady State",
        "  Steady State Max Iterations = 1",
        "  Output Intervals = 1",
        '  Post File = "case.vtu"',
        "End",
        "",
        "Constants",
        "  Stefan Boltzmann = 5.670374419e-8",
        "End",
        "",
    ]
    for i, layer in enumerate(stack.layers, start=1):
        lines += [
            f"Body {i}",
            f'  Name = "{layer.name}"',
            f"  Target Bodies(1) = {i}",
            "  Equation = 1",
            f"  Material = {i}",
            "End",
            "",
            f"Material {i}",
            f'  Name = "{layer.material}"',
            f"  Heat Conductivity = {layer.k_W_mK}",
            f"  Density = {layer.rho_kg_m3}",
            f"  Heat Capacity = {layer.cp_J_kgK}",
            "End",
            "",
        ]
    lines += [
        "Equation 1",
        "  Active Solvers(2) = 1 2",
        "End",
        "",
        "Solver 1",
        '  Equation = "Heat Equation"',
        '  Procedure = "HeatSolve" "HeatSolver"',
        "  Variable = Temperature",
        "  Linear System Solver = Iterative",
        "  Linear System Iterative Method = BiCGStab",
        "  Linear System Max Iterations = 2000",
        "  Linear System Convergence Tolerance = 1.0e-10",
        "  Linear System Preconditioning = ILU1",
        "  Nonlinear System Max Iterations = 1",
        "  Steady State Convergence Tolerance = 1.0e-8",
        "End",
        "",
        "Solver 2",
        '  Equation = "SaveScalars"',
        '  Procedure = "SaveData" "SaveScalars"',
        f'  Filename = "{SCALARS_NAME}"',
        "  Variable 1 = Temperature",
        "  Operator 1 = max",
        "  Variable 2 = Temperature",
        "  Operator 2 = min",
        "End",
        "",
        "Boundary Condition 1",
        '  Name = "die_top"',
        f"  Target Boundaries(1) = {BC_DIE_TOP}",
        f"  Heat Flux = {q}",
        "End",
        "",
        "Boundary Condition 2",
        '  Name = "coolant"',
        f"  Target Boundaries(1) = {BC_COOLANT}",
        f"  Heat Transfer Coefficient = {stack.h_conv_W_m2K}",
        f"  External Temperature = {stack.T_coolant_C}",
        "End",
        "",
    ]
    sif = case_dir / SIF_NAME
    sif.write_text("\n".join(lines))
    (case_dir / "ELMERSOLVER_STARTINFO").write_text(f"{SIF_NAME}\n1\n")
    return sif


def elmer_available() -> bool:
    return shutil.which("ElmerGrid") is not None and shutil.which("ElmerSolver") is not None


def run_case(stack: ThermalStack, P_W: float, msh_path: str | Path, case_dir: str | Path) -> FemResult:
    """Convert ``msh_path`` with ElmerGrid, write the .sif, run ElmerSolver.

    Raises ``ElmerNotAvailable`` if the binaries are not on PATH.
    """
    if not elmer_available():
        raise ElmerNotAvailable("ElmerGrid/ElmerSolver not found on PATH")
    case_dir = Path(case_dir)
    msh_path = Path(msh_path).resolve()
    case_dir.mkdir(parents=True, exist_ok=True)
    write_sif(stack, P_W, case_dir)

    subprocess.run(
        ["ElmerGrid", "14", "2", str(msh_path), "-out", MESH_DIR],
        cwd=case_dir, check=True, capture_output=True, text=True,
    )
    subprocess.run(["ElmerSolver", SIF_NAME], cwd=case_dir, check=True, capture_output=True, text=True)

    header = (case_dir / MESH_DIR / "mesh.header").read_text().split()
    n_nodes = int(header[0])
    t_max, _t_min = _parse_scalars(case_dir / SCALARS_NAME)
    return FemResult(P_W=P_W, T_max_C=t_max, T_coolant_C=stack.T_coolant_C, n_nodes=n_nodes)


def _parse_scalars(path: Path) -> tuple[float, float]:
    """Return (max T, min T) from SaveScalars output using its .names sidecar.

    The sidecar lists one ``<col>: <operator>: <variable>`` line per column;
    relying on it rather than positional columns survives Elmer adding
    bookkeeping columns.
    """
    vals = [float(v) for v in path.read_text().strip().splitlines()[-1].split()]
    cols: dict[str, int] = {}
    for line in Path(f"{path}.names").read_text().splitlines():
        head, sep, rest = line.strip().partition(":")
        if sep and head.strip().isdigit():
            cols[rest.strip().lower()] = int(head) - 1
    try:
        return vals[cols["max: temperature"]], vals[cols["min: temperature"]]
    except KeyError as e:
        raise RuntimeError(f"SaveScalars column not found in {path}.names: {e}") from e
