"""
CAD der Blende V2f: V2s (Original-V2, Wangen zurückgeschnitten, Eckwinkel) mit seitlichen Flügeln
statt der seitlichen Kantungen nach hinten. Die Flügel sind an den Seitenkanten des Stirnblechs um
beta gegen die Blechebene nach vorn-außen gebogen (visor_v2f.py), gelocht wie das Stirnblech
(Ø 2,5 mm, Teilung 12 mm), Oberkante 14 mm unter dem Glas. Die Unterkante bleibt 15 mm nach hinten
gekantet.

    python visor_v2f_cad.py <leuchte.stp> [ordner]

Ausgabe: blende_v2f.stp (nur Blende), sirius1000_blende_v2f.stp, sirius1000_v2f.glb
"""

import math
import os
import sys

import numpy as np

DATA_DIR = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DATA_DIR)
from perforation import D_OLD, PITCH, SHEET  # noqa: E402
from visor_cad import X0, Z_GLASS, prism, replace_visor, write_step  # noqa: E402
from visor_v2f import EDGE_A, EDGE_B, WING_TOP  # noqa: E402
from visor_v2s import V2Sides  # noqa: E402
from visor_v2s_cad import FLANGE, PLATE_BOTTOM, PLATE_HALF_X, trim, v2_global  # noqa: E402

from OCP.BRep import BRep_Builder  # noqa: E402
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse  # noqa: E402
from OCP.BRepBndLib import BRepBndLib  # noqa: E402
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder  # noqa: E402
from OCP.Bnd import Bnd_Box  # noqa: E402
from OCP.TopoDS import TopoDS_Compound  # noqa: E402
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt  # noqa: E402


def wing(sign, beta, length, depth, ratio):
    """Ein Flügel als gelochtes Blech; Rückgabe Form und Anzahl Löcher."""
    ux, uy = sign * math.cos(beta), math.sin(beta)          # Richtung in X (quer), Y (vorn)
    nx, ny = -uy * sign, ux * sign                          # Normale nach innen/vorn (Blechdicke)
    ex, ey = X0 + sign * EDGE_B * 1000, EDGE_A * 1000
    L, D, top = length * 1000, depth * 1000, WING_TOP * 1000
    # Seitenansicht des Flügels: oben gerade, unten von D an der Kante auf r*D vorn
    pts = []
    for ell, h in ((0, top), (L, top), (L, D * ratio), (0, D)):
        pts.append((ex + ell * ux, ey + ell * uy, Z_GLASS - h))
    shape = prism(pts, (nx * SHEET, ny * SHEET, 0))
    builder = BRep_Builder()
    tools = TopoDS_Compound()
    builder.MakeCompound(tools)
    r = D_OLD / 2
    n = 0
    for ell in np.arange(12 + r, L - 12 - r + 1e-6, PITCH):
        dep = D * (1 - (1 - ratio) * ell / L)
        for h in np.arange(35 + r, dep - 6 - r + 1e-6, PITCH):
            cx, cy, cz = ex + ell * ux - nx * 5, ey + ell * uy - ny * 5, Z_GLASS - h
            builder.Add(tools, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(cx, cy, cz), gp_Dir(nx, ny, 0)),
                                                        r, SHEET + 10).Shape())
            n += 1
    return BRepAlgoAPI_Cut(shape, tools).Shape(), n


def add_bottom_flange(shape):
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    y_rear = box.CornerMin().Y()
    x0 = X0 - PLATE_HALF_X
    flange = BRepPrimAPI_MakeBox(gp_Pnt(x0, y_rear - FLANGE, PLATE_BOTTOM), 2 * PLATE_HALF_X,
                                 FLANGE + 0.5, 1.5).Shape()
    return BRepAlgoAPI_Fuse(shape, flange).Shape()


def main():
    vs = np.load(os.path.join(DATA_DIR, "visor_v2s.npy"))
    vf = np.load(os.path.join(DATA_DIR, "visor_v2f.npy"))
    v = V2Sides(float(vs[0]), float(vs[1]), float(vs[2]), float(vs[3]))
    beta, length, depth, ratio = math.radians(float(vf[0])), float(vf[1]), float(vf[2]), float(vf[3])
    shape = add_bottom_flange(trim(v2_global(sys.argv[1]), v))
    holes = 0
    for sign in (-1, 1):
        w, n = wing(sign, beta, length, depth, ratio)
        shape = BRepAlgoAPI_Fuse(shape, w).Shape()
        holes += n
    print(f"V2f: Flügel {math.degrees(beta):.0f}°, {length * 1000:.0f} x {depth * 1000:.0f} mm, "
          f"{holes} Löcher Ø {D_OLD} mm")
    write_step(shape, os.path.join(DATA_DIR, "blende_v2f.stp"))
    replace_visor(sys.argv[1], shape, "Blende V2f mit Flügeln (berechnet)",
                  os.path.join(DATA_DIR, "sirius1000_blende_v2f.stp"),
                  os.path.join(DATA_DIR, "sirius1000_v2f.glb"))


if __name__ == "__main__":
    main()
