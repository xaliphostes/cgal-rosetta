#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


def sanitize(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^\w.\-]+", "_", name)
    return name or "surface"


def parse_multi_tsurf(path: Path):
    """
    Returns a list of surfaces:
      {"name": str|None, "verts": {id:(x,y,z)}, "faces":[(a,b,c),...]}
    Supports: VRTX, PVRTX, ATOM, TRGL
    Splits by: 'GOCAD TSurf' ... 'END' (or next GOCAD TSurf)
    """
    lines = path.read_text(errors="ignore").splitlines()

    surfaces = []
    cur = None
    in_header = False

    def flush():
        nonlocal cur
        if cur is not None:
            surfaces.append(cur)
            cur = None

    for line in lines:
        s = line.strip()
        low = s.lower()

        # Start of a new surface
        if low.startswith("gocad") and "tsurf" in low:
            flush()
            cur = {"name": None, "verts": {}, "faces": []}
            in_header = False
            continue

        if cur is None:
            continue

        # Header name
        if s.startswith("HEADER"):
            in_header = True
            continue
        if in_header:
            if s.startswith("}"):
                in_header = False
                continue
            m = re.search(r"name\s*=\s*(.*)$", s, flags=re.IGNORECASE)
            if m:
                cur["name"] = m.group(1).strip()
            continue

        # Vertices
        if s.startswith(("VRTX", "PVRTX")):
            parts = s.split()
            vid = int(parts[1])
            x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
            cur["verts"][vid] = (x, y, z)
            continue

        # Vertex aliasing
        if s.startswith("ATOM"):
            parts = s.split()
            vid = int(parts[1])
            ref = int(parts[2])
            if ref in cur["verts"]:
                cur["verts"][vid] = cur["verts"][ref]
            continue

        # Triangles
        if s.startswith("TRGL"):
            parts = s.split()
            a, b, c = int(parts[1]), int(parts[2]), int(parts[3])
            cur["faces"].append((a, b, c))
            continue

        # End of this surface
        if s == "END":
            flush()
            in_header = False
            continue

    flush()
    return surfaces


def write_obj(surface: dict, out_path: Path):
    verts = surface["verts"]
    faces = surface["faces"]

    # OBJ vertex indices must be contiguous: map original ids -> 1..N
    ids = sorted(verts.keys())
    id2i = {vid: i + 1 for i, vid in enumerate(ids)}

    with out_path.open("w", encoding="utf-8") as f:
        obj_name = surface.get("name") or out_path.stem
        f.write(f"o {obj_name}\n")

        for vid in ids:
            x, y, z = verts[vid]
            f.write(f"v {x:.15g} {y:.15g} {z:.15g}\n")

        for a, b, c in faces:
            if a in id2i and b in id2i and c in id2i:
                f.write(f"f {id2i[a]} {id2i[b]} {id2i[c]}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gocadTSurfFile", type=Path, help="Input .ts .gcd (Gocad TSurf)")
    ap.add_argument("-o", "--outdir", type=Path, default=Path("out_obj"))
    args = ap.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    surfaces = parse_multi_tsurf(args.ts)
    if not surfaces:
        raise SystemExit("No surfaces found (no 'GOCAD TSurf' blocks detected).")

    used = set()
    for idx, surf in enumerate(surfaces, start=1):
        base = sanitize(surf.get("name") or f"surface_{idx:03d}")
        fname = f"{base}.obj"
        # ensure unique filenames
        k = 1
        while fname in used or (args.outdir / fname).exists():
            fname = f"{base}_{k:02d}.obj"
            k += 1
        used.add(fname)

        write_obj(surf, args.outdir / fname)

    print(f"Saved {len(surfaces)} surfaces as separate OBJ files in: {args.outdir.resolve()}")


if __name__ == "__main__":
    main()
