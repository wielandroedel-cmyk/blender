"""
CAD der neuen außenliegenden Blende (Ergebnis von visor_design.py) im Koordinatensystem der
SIRIUS-STEP-Datei und Austausch gegen die Blende V2.

    python visor_cad.py <leuchte.stp> [ordner]

STEP-Koordinaten [mm]: X = 184 + b (quer), Y = a (C0 nach vorn, Stirnblech bei Y = -396),
Z = -48 - h (Glas bei Z = -48, nach unten negativ). Blech 1,5 mm, Lochraster 12 mm.
Wangen wie V2 (211 mm am Stirnblech, 89 mm vorn). Unterkante und Seitenkanten des Stirnblechs 20 mm nach hinten gekantet (Versteifung). Stirnblech und Wangen reichen wie bei V2 bis Z = +16 (Befestigung am Lichtkopf).

Ausgabe: blende_b3_aussen.stp (nur Blende), sirius1000_blende_b3.stp (Leuchte mit neuer Blende),
sirius1000_visor_b3.glb (für Blender).
"""

import math
import os
import sys

import numpy as np

DATA_DIR = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DATA_DIR)
from perforation import PITCH, SHEET  # noqa: E402
from visor_design import (A_BACK, CHEEK_B, CHEEK_FRONT_RATIO, CHEEK_LEN, MARGIN,  # noqa: E402
                          PLATE_HALF_W, SOLID_TOP, Visor)

from OCP.BRep import BRep_Builder  # noqa: E402
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse  # noqa: E402
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon,  # noqa: E402
                                BRepBuilderAPI_Transform)
from OCP.BRepMesh import BRepMesh_IncrementalMesh  # noqa: E402
from OCP.BRepPrimAPI import (BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder,  # noqa: E402
                             BRepPrimAPI_MakePrism)
from OCP.IFSelect import IFSelect_RetDone  # noqa: E402
from OCP.Message import Message_ProgressRange  # noqa: E402
from OCP.RWGltf import RWGltf_CafWriter  # noqa: E402
from OCP.STEPCAFControl import STEPCAFControl_Reader, STEPCAFControl_Writer  # noqa: E402
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer  # noqa: E402
from OCP.TCollection import TCollection_AsciiString, TCollection_ExtendedString  # noqa: E402
from OCP.TDataStd import TDataStd_Name  # noqa: E402
from OCP.TDF import TDF_Label  # noqa: E402
from OCP.TDocStd import TDocStd_Document  # noqa: E402
from OCP.TopoDS import TopoDS_Compound  # noqa: E402
from OCP.XCAFDoc import XCAFDoc_DocumentTool  # noqa: E402
from OCP.collections import (IndexedDataMap_TCollection_AsciiString_TCollection_AsciiString  # noqa: E402
                             as FileInfo, Sequence_TDF_Label as Seq)
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec  # noqa: E402

X0, Z_GLASS, Z_TOP = 184.0, -48.0, 16.0
V2_PART = "10166330"
FLANGE = 20.0  # Kantung zur Versteifung [mm]


def prism(points, vec):
    poly = BRepBuilderAPI_MakePolygon()
    for p in points:
        poly.Add(gp_Pnt(*p))
    poly.Close()
    return BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(poly.Wire()).Face(), gp_Vec(*vec)).Shape()


def build(visor):
    D = visor.D * 1000
    y_back = A_BACK * 1000
    half_w = PLATE_HALF_W * 1000
    cheek_x = CHEEK_B * 1000
    length = CHEEK_LEN * 1000
    Dc = visor.Dc * 1000
    d_front = Dc * CHEEK_FRONT_RATIO
    tb = math.tan(visor.beta)

    def z(h):
        return Z_GLASS - h

    # Stirnblech: Profil in der Y-Z-Ebene (Dicke nach hinten), quer über die ganze Breite
    plate = prism([(X0 - half_w, y_back, Z_TOP), (X0 - half_w, y_back - SHEET, Z_TOP),
                   (X0 - half_w, y_back - SHEET - D * tb, z(D)), (X0 - half_w, y_back - D * tb, z(D))],
                  (2 * half_w, 0, 0))
    shape = plate
    # Wangen: Trapez in der Y-Z-Ebene, Dicke nach innen
    for sign in (-1, 1):
        x_out = X0 + sign * cheek_x
        x_in = x_out - sign * SHEET
        prof = [(min(x_out, x_in), y_back, Z_TOP), (min(x_out, x_in), y_back + length, Z_TOP),
                (min(x_out, x_in), y_back + length, z(d_front)),
                (min(x_out, x_in), y_back - Dc * tb, z(Dc))]
        shape = BRepAlgoAPI_Fuse(shape, prism(prof, (SHEET, 0, 0))).Shape()

    # Versteifung: Unterkante und Seitenkanten des Stirnblechs um FLANGE nach hinten gekantet
    # (von der Leuchte weg, liegt damit im Schatten des Blechs und ändert die LVK praktisch nicht)
    if abs(tb) < 1e-9:
        yb = y_back - SHEET
        stiff = [BRepPrimAPI_MakeBox(gp_Pnt(X0 - half_w, yb - FLANGE, z(D)),
                                     2 * half_w, FLANGE + SHEET, SHEET).Shape()]
        for x0 in (X0 - half_w, X0 + half_w - SHEET):
            stiff.append(BRepPrimAPI_MakeBox(gp_Pnt(x0, yb - FLANGE, z(D)), SHEET, FLANGE,
                                             Z_TOP - z(D)).Shape())
        for part in stiff:
            shape = BRepAlgoAPI_Fuse(shape, part).Shape()
    else:
        print("Kantung nur für senkrechtes Stirnblech modelliert")

    # Lochung im Feld wie im Rechenmodell (visor_design.Visor)
    if visor.d_hole is None:
        return shape, 0
    builder = BRep_Builder()
    tools = TopoDS_Compound()
    builder.MakeCompound(tools)
    n = 0
    r = visor.d_hole / 2
    h0, m = SOLID_TOP * 1000, MARGIN * 1000
    # Stirnblech
    nrm = np.array([0.0, -math.cos(visor.beta), -math.sin(visor.beta)])  # nach hinten
    for bx in np.arange(-(half_w - m) + r, half_w - m - r + 1e-6, PITCH):
        for hh in np.arange(h0 + r, D - m - r + 1e-6, PITCH):
            c = np.array([X0 + bx, y_back - hh * tb, z(hh)]) - nrm * 5
            builder.Add(tools, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*c), gp_Dir(*nrm)), r,
                                                        SHEET + 10).Shape())
            n += 1
    # Wangen
    for sign in (-1, 1):
        x_out = X0 + sign * cheek_x
        ax = np.array([sign * 1.0, 0, 0])
        for ay in np.arange(m + r, length - m - r + 1e-6, PITCH):
            depth = Dc - (Dc - d_front) * ay / length
            for hh in np.arange(h0 + r, depth - m - r + 1e-6, PITCH):
                c = np.array([x_out, y_back + ay, z(hh)]) - ax * (SHEET + 5)
                builder.Add(tools, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*c), gp_Dir(*ax)), r,
                                                            SHEET + 10).Shape())
                n += 1
    cut = BRepAlgoAPI_Cut(shape, tools)
    cut.Build()
    return cut.Shape(), n


def main():
    step_in = sys.argv[1]
    vd = np.load(os.path.join(DATA_DIR, "visor_design.npy"))
    visor = Visor(float(vd[0]), float(vd[1]), float(vd[2]), float(vd[5]))
    shape, n = build(visor)
    print(f"Blende: Tiefe {visor.D * 1000:.0f} mm, Neigung {math.degrees(visor.beta):+.0f}°, "
          f"{n} Löcher Ø {visor.d_hole:.2f} mm ({visor.p * 100:.0f} %)")
    w = STEPControl_Writer()
    w.Transfer(shape, STEPControl_AsIs)
    w.Write(os.path.join(DATA_DIR, "blende_b3_aussen.stp"))

    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    if reader.ReadFile(step_in) != IFSelect_RetDone:
        sys.exit("STEP konnte nicht gelesen werden")
    reader.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    labels = Seq()
    st.GetShapes(labels)
    # Einbaulage der Blende im Lichtkopf: Bauteil liegt lokal, die Komponente trägt die Lage
    loc = None
    for i in range(1, labels.Length() + 1):
        comps = Seq()
        st.GetComponents_s(labels.Value(i), comps)
        for j in range(1, comps.Length() + 1):
            ref = TDF_Label()
            attr = TDataStd_Name()
            if (st.GetReferredShape_s(comps.Value(j), ref) and
                    ref.FindAttribute(TDataStd_Name.GetID_s(), attr) and
                    V2_PART in attr.Get().ToExtString()):
                loc = st.GetLocation_s(comps.Value(j))
    # Geometrie selbst verschieben (nicht nur Location setzen, die ignoriert der glTF-Export)
    local = shape if loc is None else \
        BRepBuilderAPI_Transform(shape, loc.Inverted().Transformation(), True).Shape()
    for i in range(1, labels.Length() + 1):
        lab = labels.Value(i)
        attr = TDataStd_Name()
        if (lab.FindAttribute(TDataStd_Name.GetID_s(), attr) and
                V2_PART in attr.Get().ToExtString() and not st.IsAssembly_s(lab)):
            st.SetShape(lab, local)
            TDataStd_Name.Set_s(lab, TCollection_ExtendedString("Blende B3 aussen (berechnet)"))
            break
    else:
        sys.exit("Blende V2 nicht gefunden")
    st.UpdateAssemblies()

    sw = STEPCAFControl_Writer()
    sw.SetColorMode(True)
    sw.SetNameMode(True)
    sw.Transfer(doc, STEPControl_AsIs)
    sw.Write(os.path.join(DATA_DIR, "sirius1000_blende_b3.stp"))

    free = Seq()
    st.GetFreeShapes(free)
    for i in range(1, free.Length() + 1):
        BRepMesh_IncrementalMesh(st.GetShape_s(free.Value(i)), 0.3, False, 0.2, True)
    RWGltf_CafWriter(TCollection_AsciiString(os.path.join(DATA_DIR, "sirius1000_visor_b3.glb")),
                     True).Perform(doc, FileInfo(), Message_ProgressRange())


if __name__ == "__main__":
    main()
