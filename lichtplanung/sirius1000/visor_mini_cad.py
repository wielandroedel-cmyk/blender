"""
CAD der kompakten Blende B3k (Ergebnis von visor_mini.py) und Austausch gegen die Blende V2.

    python visor_mini_cad.py <leuchte.stp> [ordner]

Koordinaten wie visor_cad.py: X = 184 + b, Y = a, Z = -48 - h [mm].
  - Stirnblech senkrecht an der hinteren Glaskante, Tiefe d, oben bis Z = +16 (Befestigung wie V2),
    10 % gelocht, Unter- und Seitenkanten 20 mm nach hinten gekantet
  - Lamelle(n) geschlossen, 1,5 mm, von 15 mm unter dem Glas (unter dem Gehäuserahmen) bis zur Tiefe
    d, nach vorn geneigt, quer über die Breite des Stirnblechs
  - Die Befestigung der Lamelle an den Stirnseiten des Gehäuses ist nicht konstruiert.

Ausgabe: blende_b3k_kompakt.stp, sirius1000_blende_b3k.stp, sirius1000_visor_b3k.glb
"""

import math
import os
import sys

import numpy as np

DATA_DIR = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DATA_DIR)
from perforation import PITCH, SHEET  # noqa: E402
from visor_cad import FLANGE, X0, Z_GLASS, Z_TOP, prism, replace_visor, write_step  # noqa: E402
from visor_design import A_BACK, MARGIN, PLATE_HALF_W, SOLID_TOP  # noqa: E402
from visor_mini import BLADE_TOP, CompactVisor  # noqa: E402

from OCP.BRep import BRep_Builder  # noqa: E402
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse  # noqa: E402
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder  # noqa: E402
from OCP.TopoDS import TopoDS_Compound  # noqa: E402
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt  # noqa: E402


def build(v):
    d = v.d * 1000
    y_back = A_BACK * 1000
    half_w = PLATE_HALF_W * 1000
    tb = math.tan(v.beta)

    def z(h):
        return Z_GLASS - h

    # Stirnblech mit Kantung
    shape = BRepPrimAPI_MakeBox(gp_Pnt(X0 - half_w, y_back - SHEET, z(d)), 2 * half_w, SHEET,
                                Z_TOP - z(d)).Shape()
    yb = y_back - SHEET
    parts = [BRepPrimAPI_MakeBox(gp_Pnt(X0 - half_w, yb - FLANGE, z(d)), 2 * half_w, FLANGE + SHEET,
                                 SHEET).Shape()]
    for x0 in (X0 - half_w, X0 + half_w - SHEET):
        parts.append(BRepPrimAPI_MakeBox(gp_Pnt(x0, yb - FLANGE, z(d)), SHEET, FLANGE,
                                         Z_TOP - z(d)).Shape())
    # Lamellen: Parallelogramm im Schnitt a-h, Dicke senkrecht zur Lamelle
    h0 = BLADE_TOP * 1000
    ta = SHEET / math.cos(v.beta)  # Dicke in a-Richtung
    for a0 in v.blades:
        a0 *= 1000
        top, bot = a0 + h0 * tb, a0 + d * tb
        parts.append(prism([(X0 - half_w, top, z(h0)), (X0 - half_w, top + ta, z(h0)),
                            (X0 - half_w, bot + ta, z(d)), (X0 - half_w, bot, z(d))],
                           (2 * half_w, 0, 0)))
    for part in parts:
        shape = BRepAlgoAPI_Fuse(shape, part).Shape()

    # Lochung im Stirnblech (Lamellen geschlossen)
    builder = BRep_Builder()
    tools = TopoDS_Compound()
    builder.MakeCompound(tools)
    r = v.d_hole / 2
    m, hs = MARGIN * 1000, SOLID_TOP * 1000
    n = 0
    for bx in np.arange(-(half_w - m) + r, half_w - m - r + 1e-6, PITCH):
        for hh in np.arange(hs + r, d - m - r + 1e-6, PITCH):
            c = gp_Pnt(X0 + bx, y_back + 5, z(hh))
            builder.Add(tools, BRepPrimAPI_MakeCylinder(gp_Ax2(c, gp_Dir(0, -1, 0)), r,
                                                        SHEET + 10).Shape())
            n += 1
    cut = BRepAlgoAPI_Cut(shape, tools)
    cut.Build()
    return cut.Shape(), n


def main():
    vm = np.load(os.path.join(DATA_DIR, "visor_mini.npy"))
    v = CompactVisor(float(vm[0]), int(vm[1]), float(vm[2]), float(vm[3]),
                     ("kurz", "lang", "keine")[int(vm[4])])
    if v.cheek != "keine":
        sys.exit("CAD nur für die Ausführung ohne Wangen")
    shape, n = build(v)
    print(f"B3k: Tiefe {v.d * 1000:.1f} mm, {v.n} Lamelle(n) {math.degrees(v.beta):.0f}°, "
          f"{n} Löcher Ø {v.d_hole:.2f} mm")
    write_step(shape, os.path.join(DATA_DIR, "blende_b3k_kompakt.stp"))
    replace_visor(sys.argv[1], shape, "Blende B3k kompakt (berechnet)",
                  os.path.join(DATA_DIR, "sirius1000_blende_b3k.stp"),
                  os.path.join(DATA_DIR, "sirius1000_visor_b3k.glb"))


if __name__ == "__main__":
    main()
