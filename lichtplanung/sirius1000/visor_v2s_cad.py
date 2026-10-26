"""
CAD der Blende V2s: Die Original-Blende V2 aus der STEP-Datei wird beibehalten, nur die Seitenwangen
unterhalb der Glasebene werden auf die neue Form (visor_v2s.py) zurückgeschnitten. Stirnblech,
Lochung und die Wangenteile oberhalb des Glases (Befestigung am Lichtkopf) bleiben unverändert.
Zur Versteifung werden Seiten- und Unterkante des Stirnblechs unterhalb des Gehäuses 15 mm nach
hinten gekantet (v2s_final.py: Durchbiegung 0,29 statt 1,13 mm bei V2, Eigenfrequenz 75 statt 40 Hz).

    python visor_v2s_cad.py <leuchte.stp> [ordner]

Ausgabe: blende_v2s.stp (nur Blende), sirius1000_blende_v2s.stp, sirius1000_v2s.glb
"""

import os
import sys

import numpy as np

DATA_DIR = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DATA_DIR)
from visor_cad import V2_PART, X0, Z_GLASS, prism, replace_visor, write_step  # noqa: E402
from visor_v2s import A_START, CHEEK_B, V2Sides  # noqa: E402

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse  # noqa: E402
from OCP.BRepBndLib import BRepBndLib  # noqa: E402
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox  # noqa: E402
from OCP.Bnd import Bnd_Box  # noqa: E402
from OCP.gp import gp_Pnt  # noqa: E402
from OCP.IFSelect import IFSelect_RetDone  # noqa: E402
from OCP.STEPCAFControl import STEPCAFControl_Reader  # noqa: E402
from OCP.TCollection import TCollection_ExtendedString  # noqa: E402
from OCP.TDataStd import TDataStd_Name  # noqa: E402
from OCP.TDF import TDF_Label  # noqa: E402
from OCP.TDocStd import TDocStd_Document  # noqa: E402
from OCP.XCAFDoc import XCAFDoc_DocumentTool  # noqa: E402
from OCP.collections import Sequence_TDF_Label as Seq  # noqa: E402

CUT_FROM_H = 1.0      # mm unter der Glasebene: darüber bleibt die Wange als Befestigung
CUT_TO_A = -100.0     # mm: Ende der Original-Wangen liegt bei -157
FLANGE = 15.0         # Kantung nach hinten [mm]
PLATE_HALF_X = 164.0  # Stirnblech quer (END_PLATE b)
PLATE_BOTTOM = Z_GLASS - 211.0
FLANGE_TOP = -62.0    # Kantungen nur unterhalb des Gehäuses (Unterkante Lichtkopf Z = -61)


def v2_global(step_in):
    """Form der Blende V2 in Leuchtenkoordinaten (mit Einbaulage)."""
    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    if reader.ReadFile(step_in) != IFSelect_RetDone:
        sys.exit("STEP konnte nicht gelesen werden")
    reader.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    labels = Seq()
    st.GetShapes(labels)
    for i in range(1, labels.Length() + 1):
        comps = Seq()
        st.GetComponents_s(labels.Value(i), comps)
        for j in range(1, comps.Length() + 1):
            ref = TDF_Label()
            attr = TDataStd_Name()
            if (st.GetReferredShape_s(comps.Value(j), ref) and
                    ref.FindAttribute(TDataStd_Name.GetID_s(), attr) and
                    V2_PART in attr.Get().ToExtString()):
                return st.GetShape_s(comps.Value(j))
    sys.exit("Blende V2 nicht gefunden")


def trim(shape, v):
    """Wangen unterhalb der neuen Kontur abschneiden (Schnittkörper je Seite, 20 mm breit)."""
    a0, length = A_START * 1000, v.length * 1000
    a = np.linspace(a0, a0 + length, 12)
    contour = [(y, Z_GLASS - max(float(v.cheek_depth(y / 1000)) * 1000, CUT_FROM_H)) for y in a]
    # Polygon: neue Unterkante, dann bis zum Ende der alten Wange und tief darunter zurück
    poly_yz = contour + [(CUT_TO_A, Z_GLASS - CUT_FROM_H), (CUT_TO_A, Z_GLASS - 300.0),
                         (a0, Z_GLASS - 300.0)]
    for sign in (-1, 1):
        x = X0 + sign * CHEEK_B * 1000 - 10.0
        tool = prism([(x, y, z) for y, z in poly_yz], (20.0, 0, 0))
        shape = BRepAlgoAPI_Cut(shape, tool).Shape()
    return shape


def add_flanges(shape):
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    y_rear = box.CornerMin().Y()           # Rückseite des Stirnblechs
    x0, x1 = X0 - PLATE_HALF_X, X0 + PLATE_HALF_X
    parts = [BRepPrimAPI_MakeBox(gp_Pnt(x0, y_rear - FLANGE, PLATE_BOTTOM), x1 - x0, FLANGE + 0.5,
                                 1.5).Shape()]
    for x in (x0, x1 - 1.5):
        parts.append(BRepPrimAPI_MakeBox(gp_Pnt(x, y_rear - FLANGE, PLATE_BOTTOM), 1.5, FLANGE + 0.5,
                                         FLANGE_TOP - PLATE_BOTTOM).Shape())
    for part in parts:
        shape = BRepAlgoAPI_Fuse(shape, part).Shape()
    return shape


def main():
    vs = np.load(os.path.join(DATA_DIR, "visor_v2s.npy"))
    v = V2Sides(float(vs[0]), float(vs[1]), float(vs[2]), float(vs[3]))
    shape = add_flanges(trim(v2_global(sys.argv[1]), v))
    print(f"V2s: Wangen auf {v.depth * 1000:.0f} mm / {v.front * 1000:.0f} mm, "
          f"{v.length * 1000:.0f} mm Länge zurückgeschnitten, Kantungen {FLANGE:.0f} mm")
    write_step(shape, os.path.join(DATA_DIR, "blende_v2s.stp"))
    replace_visor(sys.argv[1], shape, "Blende V2s seitlich (berechnet)",
                  os.path.join(DATA_DIR, "sirius1000_blende_v2s.stp"),
                  os.path.join(DATA_DIR, "sirius1000_v2s.glb"))


if __name__ == "__main__":
    main()
