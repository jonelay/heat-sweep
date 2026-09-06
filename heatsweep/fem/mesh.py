"""gmsh mesh generation for a ThermalStack (requires the ``gmsh`` wheel).

Geometry: each layer is a box centred on the origin in x-y, with the
layer's footprint (die / tile / plate) as its x-y extent and its z range
from ``ThermalStack.z_bounds``. Boxes are fragmented so shared faces are
conformal. Physical groups:

- volume tag ``i+1`` named after layer ``i`` (Elmer body id)
- surface tag ``BC_DIE_TOP`` (heat input, die top face)
- surface tag ``BC_COOLANT`` (convective face, bottom of last layer)

All other exterior faces carry no physical group and are therefore
adiabatic in Elmer. Mesh is written in MSH 2.2 for ElmerGrid.
"""

from __future__ import annotations

from pathlib import Path

from heatsweep.fem.stack import ThermalStack

BC_DIE_TOP = 101
BC_COOLANT = 102


class GmshNotAvailable(ImportError):
    pass


def _import_gmsh():  # type: ignore[no-untyped-def]  # gmsh ships no stubs
    try:
        import gmsh
    except ImportError as e:
        raise GmshNotAvailable("gmsh is not installed; pip install heatsweep[fem]") from e
    return gmsh


def build_mesh(
    stack: ThermalStack,
    out_path: str | Path,
    size_max_m: float = 2.0e-3,
    size_min_m: float = 0.3e-3,
    die_divisions: int = 8,
) -> Path:
    """Generate and write a tetrahedral mesh for ``stack``. Returns path.

    Element size is ``size_max_m`` globally and ``die_w / die_divisions``
    on die-footprint volumes, both floored at ``size_min_m``.
    """
    gmsh = _import_gmsh()
    out_path = Path(out_path)
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add(stack.name)
        occ = gmsh.model.occ

        boxes: list[int] = []
        for layer, (z0, z1) in zip(stack.layers, stack.z_bounds(), strict=True):
            w, length = stack.footprint_dims(layer.footprint)
            boxes.append(occ.addBox(-w / 2, -length / 2, z0, w, length, z1 - z0))
        occ.fragment([(3, b) for b in boxes], [])
        occ.synchronize()

        # Map fragmented volumes back to layers by centroid z.
        z_bounds = stack.z_bounds()
        vols_by_layer: dict[int, list[int]] = {i: [] for i in range(len(stack.layers))}
        for _, tag in gmsh.model.getEntities(3):
            _, _, zc = occ.getCenterOfMass(3, tag)
            for i, (z0, z1) in enumerate(z_bounds):
                if z0 < zc < z1:
                    vols_by_layer[i].append(tag)
                    break
            else:
                raise RuntimeError(f"volume {tag} centroid z={zc} matches no layer")

        for i, layer in enumerate(stack.layers):
            if not vols_by_layer[i]:
                raise RuntimeError(f"layer {layer.name!r} produced no volume")
            gmsh.model.addPhysicalGroup(3, vols_by_layer[i], i + 1, name=layer.name)

        # OCC pads entity bounding boxes by ~1e-7; eps must exceed that but
        # stay below the thinnest layer so faces are not double-matched.
        eps = min(1e-5, 0.1 * min(layer.t_m for layer in stack.layers))
        z_top = stack.thickness_m
        dw, dl = stack.die_w_m / 2, stack.die_l_m / 2
        top = gmsh.model.getEntitiesInBoundingBox(-dw - eps, -dl - eps, z_top - eps, dw + eps, dl + eps, z_top + eps, 2)
        pw, pl = stack.plate_w_m / 2, stack.plate_l_m / 2
        bottom = gmsh.model.getEntitiesInBoundingBox(-pw - eps, -pl - eps, -eps, pw + eps, pl + eps, eps, 2)
        if not top or not bottom:
            raise RuntimeError("could not locate die-top or coolant faces")
        gmsh.model.addPhysicalGroup(2, [t for _, t in top], BC_DIE_TOP, name="die_top")
        gmsh.model.addPhysicalGroup(2, [t for _, t in bottom], BC_COOLANT, name="coolant")

        # Global size everywhere, refined only on die-footprint volumes
        # (the heat source and steepest gradients). Thin plate-wide layers
        # (TIM, solder) are left one linear element thick: through-thickness
        # conduction in a thin layer is linear in z, which a single linear
        # tet layer represents exactly; refining them by thickness would
        # flood the whole plate footprint with sub-100 um elements.
        gmsh.option.setNumber("Mesh.MeshSizeMax", size_max_m)
        gmsh.option.setNumber("Mesh.MeshSizeMin", size_min_m)
        die_size = max(size_min_m, min(size_max_m, min(stack.die_w_m, stack.die_l_m) / die_divisions))
        for i, layer in enumerate(stack.layers):
            if layer.footprint == "die":
                for v in vols_by_layer[i]:
                    pts = gmsh.model.getBoundary([(3, v)], recursive=True)
                    gmsh.model.mesh.setSize(pts, die_size)

        gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
        gmsh.model.mesh.generate(3)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        gmsh.write(str(out_path))
    finally:
        gmsh.finalize()
    return out_path
