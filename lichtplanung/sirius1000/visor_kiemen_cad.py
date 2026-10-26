"""
CAD der Kiemenblende (Ergebnis von visor_kiemen.py): ein Blech unter dem Glas über die ganze
Leuchtenfläche, Lamellen ausgeklinkt und an der hinteren Schlitzkante nach unten gedrückt.
Ersetzt im Leuchtenmodell die Blende V2.

    python visor_kiemen_cad.py <leuchte.stp> [ordner]

Koordinaten wie visor_cad.py: X = 184 + b, Y = a (C0 nach vorn), Z = -48 - h [mm]. Das Blech
liegt mit der Oberseite 14 mm unter dem Glas (1 mm unter dem Gehäuserahmen bei Z = -61), ist
792 x 340 mm groß und an den Längsseiten 15 mm nach oben gekantet (Befestigung am Gehäuse).

Ausgabe: kiemenblende.stp (nur Blende), sirius1000_kiemenblende.stp, sirius1000_kiemen.glb
"""

import math
import os
import sys

import numpy as np

DATA_DIR = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DATA_DIR)
from visor_cad import X0, Z_GLASS, prism, replace_visor, write_step  # noqa: E402
from visor_kiemen import SHEET  # noqa: E402

from OCP.BRep import BRep_Builder  # noqa: E402
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse  # noqa: E402
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox  # noqa: E402
from OCP.TopoDS import TopoDS_Compound  # noqa: E402
from OCP.gp import gp_Pnt  # noqa: E402

PLATE_LEN, PLATE_W = 792.0, 340.0
Z_TOP = Z_GLASS - 14.0          # Oberseite des Blechs
FLANGE_H = 15.0
MARGIN_A = 12.0                 # ungelochter Rand vorn/hinten


def build(length, theta_deg, web, slot_w, bridge_w):
    th = math.radians(theta_deg)
    y_min = -PLATE_LEN / 2
    x_min = X0 - PLATE_W / 2
    zb = Z_TOP - SHEET
    plate = BRepPrimAPI_MakeBox(gp_Pnt(x_min, y_min, zb), PLATE_W, PLATE_LEN, SHEET).Shape()
    for x0 in (x_min, x_min + PLATE_W - SHEET):
        plate = BRepAlgoAPI_Fuse(plate, BRepPrimAPI_MakeBox(gp_Pnt(x0, y_min, zb), SHEET,
                                                            PLATE_LEN, FLANGE_H).Shape()).Shape()
    # Schlitzraster: Reihen in a (Teilung length + web), Felder in b (slot_w + bridge_w)
    pitch = length + web
    n_rows = int((PLATE_LEN - 2 * MARGIN_A + web) // pitch)
    y0s = y_min + (PLATE_LEN - (n_rows * pitch - web)) / 2 + np.arange(n_rows) * pitch
    n_fields = int((PLATE_W - 2 * 10.0 + bridge_w) // (slot_w + bridge_w))
    span = n_fields * (slot_w + bridge_w) - bridge_w
    x0s = X0 - span / 2 + np.arange(n_fields) * (slot_w + bridge_w)
    builder = BRep_Builder()
    slots = TopoDS_Compound()
    builder.MakeCompound(slots)
    tongues = TopoDS_Compound()
    builder.MakeCompound(tongues)
    for y0 in y0s:
        for x0 in x0s:
            builder.Add(slots, BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, zb - 1), slot_w, length,
                                                   SHEET + 2).Shape())
            # Lamelle: an der hinteren Kante (y0) um theta nach unten gedreht, Dicke SHEET
            dy, dz = length * math.cos(th), -length * math.sin(th)
            ny, nz = SHEET * math.sin(th), SHEET * math.cos(th)   # Dickenrichtung (nach oben-vorn)
            pts = [(x0, y0, zb), (x0, y0 + dy, zb + dz), (x0, y0 + dy + ny, zb + dz + nz),
                   (x0, y0 + ny, zb + nz)]
            builder.Add(tongues, prism(pts, (slot_w, 0, 0)))
    plate = BRepAlgoAPI_Cut(plate, slots).Shape()
    return BRepAlgoAPI_Fuse(plate, tongues).Shape(), n_rows, n_fields


def main():
    k = np.load(os.path.join(DATA_DIR, "visor_kiemen.npy"))
    length, theta, web, slot_w, bridge_w = (float(x) for x in k[:5])
    shape, n_rows, n_fields = build(length, theta, web, slot_w, bridge_w)
    print(f"Kiemenblende: {n_rows} Reihen x {n_fields} Felder = {n_rows * n_fields} Lamellen "
          f"{length:.0f} x {slot_w:.0f} mm, {theta:.0f}°, Blech {SHEET:g} mm")
    write_step(shape, os.path.join(DATA_DIR, "kiemenblende.stp"))
    replace_visor(sys.argv[1], shape, "Kiemenblende RAL 9010 (berechnet)",
                  os.path.join(DATA_DIR, "sirius1000_kiemenblende.stp"),
                  os.path.join(DATA_DIR, "sirius1000_kiemen.glb"))


if __name__ == "__main__":
    main()
