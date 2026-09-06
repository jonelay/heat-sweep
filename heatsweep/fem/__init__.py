"""Optional finite-element thermal path: layer stack -> gmsh mesh -> Elmer.

``heatsweep.fem.stack`` needs nothing beyond the standard library and is
always importable. ``heatsweep.fem.mesh`` needs the ``gmsh`` wheel
(``pip install heatsweep[fem]``). ``heatsweep.fem.elmer`` writes a solver
input file with no dependencies and runs ``ElmerGrid``/``ElmerSolver``
only if they are on PATH, raising ``ElmerNotAvailable`` otherwise.
"""

from __future__ import annotations

from heatsweep.fem.stack import Layer, ThermalStack, load_stack_toml, rth_1d_bounds

__all__ = ["Layer", "ThermalStack", "load_stack_toml", "rth_1d_bounds"]
