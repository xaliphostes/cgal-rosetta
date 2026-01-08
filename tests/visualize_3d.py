#!/usr/bin/env python3
import argparse
import glob
from pathlib import Path
from itertools import cycle

import pyvista as pv


def expand_inputs(inputs):
    """Expand globs and directories into a sorted list of mesh files."""
    files = []
    for item in inputs:
        matches = glob.glob(item)
        if matches:
            for m in matches:
                p = Path(m)
                if p.is_dir():
                    files.extend([f for f in p.rglob("*") if f.is_file()])
                else:
                    files.append(p)
            continue

        p = Path(item)
        if p.exists() and p.is_dir():
            files.extend([f for f in p.rglob("*") if f.is_file()])
        else:
            files.append(p)

    allowed = {".stl", ".obj", ".ply", ".off", ".vtp", ".vtk", ".vtu", ".glb", ".gltf"}
    out = []
    for f in files:
        f = Path(f)
        if f.exists() and f.is_file() and f.suffix.lower() in allowed:
            out.append(f)

    return sorted(set(out))


def load_mesh(path: Path) -> pv.PolyData:
    """Load with PyVista and ensure we end up with triangulated PolyData for display."""
    mesh = pv.read(str(path))
    if not isinstance(mesh, pv.PolyData):
        mesh = mesh.extract_surface()
    mesh = mesh.triangulate()
    return mesh


def compute_global_center(meshes):
    """Compute global bbox center over a list of meshes."""
    bounds = [float("inf"), -float("inf"),
              float("inf"), -float("inf"),
              float("inf"), -float("inf")]
    for m in meshes:
        b = m.bounds  # (xmin, xmax, ymin, ymax, zmin, zmax)
        bounds[0] = min(bounds[0], b[0])
        bounds[1] = max(bounds[1], b[1])
        bounds[2] = min(bounds[2], b[2])
        bounds[3] = max(bounds[3], b[3])
        bounds[4] = min(bounds[4], b[4])
        bounds[5] = max(bounds[5], b[5])

    return (
        0.5 * (bounds[0] + bounds[1]),
        0.5 * (bounds[2] + bounds[3]),
        0.5 * (bounds[4] + bounds[5]),
    )


def main():
    ap = argparse.ArgumentParser(
        description="Load and visualize multiple 3D meshes (.stl/.obj/...) in one scene (PyVista/VTK). "
                    "Double-click a surface to display its name and highlight it."
    )
    ap.add_argument("inputs", nargs="+", help="Files, directories, or globs (e.g. *.stl data/ mesh.obj)")
    ap.add_argument("--opacity", type=float, default=1.0, help="Base mesh opacity (0..1)")
    ap.add_argument("--edges", action="store_true", help="Show triangle edges (base)")
    ap.add_argument("--wireframe", action="store_true", help="Wireframe rendering (base)")
    ap.add_argument("--smooth", action="store_true", help="Smooth shading")
    ap.add_argument("--scale", type=float, default=1.0, help="Uniform scale applied to all meshes")
    ap.add_argument("--no-legend", action="store_true", help="Disable legend")
    args = ap.parse_args()

    paths = expand_inputs(args.inputs)
    if not paths:
        raise SystemExit("No mesh files found. Provide files/dirs/globs like: *.stl models/ mesh.obj")

    plotter = pv.Plotter()
    plotter.add_axes()
    plotter.show_grid()

    # Robust color cycle (works even if plotter.theme.color_cycler is None)
    palette = getattr(plotter.theme, "color_cycler", None)
    if palette is None:
        palette = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        ]
    color_cycle = cycle(palette)

    # -------- Load all meshes first --------
    meshes = []
    mesh_paths = []
    for p in paths:
        try:
            mesh = load_mesh(p)
            if args.scale != 1.0:
                mesh = mesh.copy(deep=True)
                mesh.points *= float(args.scale)

            meshes.append(mesh)
            mesh_paths.append(p)
            print(f"Loaded: {p}  (points={mesh.n_points}, cells={mesh.n_cells})")
        except Exception as e:
            print(f"Skip:   {p}  ({e})")

    if not meshes:
        raise SystemExit("All files failed to load.")

    # -------- Center scene (global bbox center -> origin) --------
    center = compute_global_center(meshes)
    print(f"Global center: {center}")
    for mesh in meshes:
        mesh.translate([-center[0], -center[1], -center[2]], inplace=True)

    # -------- Add meshes, keep actor->name mapping --------
    actor_to_name = {}
    actor_base_style = {}  # store base properties to restore after highlight
    labels = []

    base_style = "wireframe" if args.wireframe else "surface"

    for mesh, p in zip(meshes, mesh_paths):
        color = next(color_cycle)
        actor = plotter.add_mesh(
            mesh,
            name=str(p),
            color=color,
            opacity=float(args.opacity),
            show_edges=bool(args.edges),
            smooth_shading=bool(args.smooth),
            style=base_style,
            pickable=True,
        )
        actor_to_name[actor] = p.name

        prop = actor.GetProperty()
        actor_base_style[actor] = {
            "color": prop.GetColor(),
            "opacity": prop.GetOpacity(),
            "edge_visibility": prop.GetEdgeVisibility(),
            "line_width": prop.GetLineWidth(),
            "representation": prop.GetRepresentation(),  # 2=surface, 1=wireframe in VTK
        }

        labels.append([p.name, color])

    if labels and not args.no_legend:
        plotter.add_legend(labels, bcolor=None)

    # Text overlay for picked name
    text_actor = plotter.add_text("Double-click a surface", position="upper_left", font_size=12)

    # Use a VTK prop picker for reliable actor picking
    picker = pv._vtk.vtkPropPicker()

    # Highlight state
    highlighted_actor = {"actor": None}

    def restore_actor(actor):
        if actor is None:
            return
        base = actor_base_style.get(actor)
        if not base:
            return
        prop = actor.GetProperty()
        prop.SetColor(base["color"])
        prop.SetOpacity(base["opacity"])
        prop.SetEdgeVisibility(base["edge_visibility"])
        prop.SetLineWidth(base["line_width"])
        prop.SetRepresentation(base["representation"])

    def highlight_actor(actor):
        if actor is None:
            return
        prop = actor.GetProperty()
        # Keep original color but make it "pop":
        prop.SetOpacity(1.0)
        prop.SetEdgeVisibility(True)
        prop.SetLineWidth(max(3.0, prop.GetLineWidth()))
        # Force surface representation for highlight (even if base was wireframe)
        prop.SetRepresentationToSurface()

    def pick_actor_under_cursor():
        x, y = plotter.iren.get_event_position()
        picker.Pick(x, y, 0, plotter.renderer)
        return picker.GetActor()

    def on_double_click():
        actor = pick_actor_under_cursor()

        # Un-highlight previous
        restore_actor(highlighted_actor["actor"])

        if actor in actor_to_name:
            name = actor_to_name[actor]
            highlight_actor(actor)
            highlighted_actor["actor"] = actor

            msg = f"Picked: {name}"
            text_actor.SetText(0, msg)
            print(msg)
        else:
            highlighted_actor["actor"] = None
            text_actor.SetText(0, "Picked: (none)")

        plotter.render()

    # Detect double click via VTK RepeatCount on LeftButtonPressEvent
    def left_button_press(iren, event):
        # RepeatCount == 1 means "second press" => double-click
        if iren.GetRepeatCount() == 1:
            on_double_click()
        return

    plotter.iren.add_observer("LeftButtonPressEvent", left_button_press)

    # Nice initial view
    plotter.camera_position = "iso"
    plotter.reset_camera()
    plotter.show(title="Mesh Viewer (PyVista) - double-click to pick & highlight")


if __name__ == "__main__":
    main()
