"""
Blende mit größerer Lochung: Geometrie (STEP/glTF) und daraus abgeleitete LVK (IES).

    python perforation.py <step_datei> <ordner> [offene_flaeche]   (Standard 0.5 = 50 %)

Ist-Zustand der außenliegenden Blende V2 (aus der STEP-Datei ermittelt):
    Löcher Ø 2,5 mm im Quadratraster 12 mm, Blech 1,5 mm -> 3,4 % offene Fläche,
    gelocht sind das Stirnblech (325 Löcher) und beide Seitenwangen (je 141 Löcher).
Neu: gleiches Raster, Lochdurchmesser so, dass die offene Fläche im Lochfeld dem Zielwert
entspricht (50 % -> Ø 9,57 mm).

1. Geometrie: Die Löcher werden an denselben Mittelpunkten im CAD-Modell aufgebohrt
   (Boolesche Operation), Ausgabe als STEP (nur Blende) und glTF (ganze Leuchte).
2. LVK: Die gemessene LDT gilt für die Ist-Lochung. Für jede Richtung wird mit einem
   Strahlenmodell (Punkte auf der Lichtaustrittsfläche, Schnitt mit Stirnblech und Wangen)
   die Transmission der Blende T berechnet, bei schrägem Durchgang durch die Lochung mit
   der Überlappung der Lochkreise auf Ober- und Unterseite des Blechs.
       I_neu = I_gemessen + I_frei * (T_neu - T_alt)
   I_frei (Lichtstärke ohne Blende) = I_gemessen / T_alt; wo die Blende fast alles verdeckt
   (T_alt < 0,2), begrenzt auf den Abfall der unverdeckten C0-Seite der LVK. Reflexionen an der Blende bleiben wie gemessen.
   Das ist eine Abschätzung, keine Messung.
"""

import math
import os
import pickle
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ldt2ies import read_ies  # noqa: E402

PITCH = 12.0          # mm
D_OLD = 2.5           # mm
SHEET = 1.5           # mm

# Geometrie im Leuchtensystem (Meter), Ursprung Glasmitte:
#   a: Richtung C0 (nach vorn), Blende am hinteren Ende (a < 0)
#   b: quer (C90-Achse), h: Tiefe unter dem Glas (nach unten positiv)
GLASS_A, GLASS_B = 0.383, 0.152            # halbe Öffnung 766 x 304 mm
END_PLATE = dict(a=-0.396, b=(-0.164, 0.164), h=(-0.064, 0.211),
                 field_b=(-0.150, 0.150), field_h=(0.035, 0.191))
# Wangen: Trapez, am Stirnblech 211 mm tief, zur Mitte hin flacher (Fase aus dem CAD)
CHEEKS = [dict(b=-0.167, a=(-0.394, -0.157), perforated=True),
          dict(b=0.167, a=(-0.394, -0.157), perforated=True)]
CHEEK_FIELD_A, CHEEK_FIELD_H = (-0.3835, -0.1795), (0.035, 0.191)


def d_for_open_area(p):
    return PITCH * math.sqrt(4.0 * p / math.pi)


def open_area(d):
    return math.pi * d * d / 4.0 / PITCH ** 2


def hole_transmission(d, cos_inc):
    """Anteil des Lochfelds, den ein schräger Strahl passiert (Überlappung zweier Kreise)."""
    cos_inc = np.clip(np.abs(cos_inc), 1e-6, 1.0)
    s = SHEET * np.sqrt(1.0 - cos_inc ** 2) / cos_inc  # Versatz Ober-/Unterseite [mm]
    r = d / 2.0
    x = np.clip(s / (2 * r), 0.0, 1.0)
    overlap = 2 * r * r * np.arccos(x) - (s / 2) * np.sqrt(np.maximum(4 * r * r - s * s, 0))
    overlap = np.where(s >= 2 * r, 0.0, overlap)
    return overlap / PITCH ** 2


def cheek_depth(a):
    # 211 mm am Stirnblech (a = -0.394), Fase mit Steigung 0.517 zur Mitte hin
    return 0.211 - 0.517 * (a + 0.394)


def visor_transmission(dirs, d, n_pts=24):
    """Mittlere Transmission der Blende für Richtungen dirs (N,3) im System (a, b, h)."""
    ga = np.linspace(-GLASS_A, GLASS_A, n_pts)
    gb = np.linspace(-GLASS_B, GLASS_B, max(6, n_pts // 2))
    pa, pb = np.meshgrid(ga, gb)
    pa, pb = pa.ravel(), pb.ravel()
    out = np.zeros(len(dirs))
    for k, (da, db, dh) in enumerate(dirs):
        if dh <= 1e-6:
            out[k] = 1.0  # nach oben/horizontal: Blende liegt unter dem Glas, kein Schnitt
            continue
        t = np.ones_like(pa)
        # Stirnblech (Ebene a = const)
        if da < -1e-9:
            s = (END_PLATE["a"] - pa) / da
            hb, hh = pb + s * db, s * dh
            hit = ((s > 0) & (hb >= END_PLATE["b"][0]) & (hb <= END_PLATE["b"][1]) &
                   (hh >= END_PLATE["h"][0]) & (hh <= END_PLATE["h"][1]))
            in_field = ((hb >= END_PLATE["field_b"][0]) & (hb <= END_PLATE["field_b"][1]) &
                        (hh >= END_PLATE["field_h"][0]) & (hh <= END_PLATE["field_h"][1]))
            tau = hole_transmission(d, da)  # Normale des Stirnblechs = a-Achse
            t = t * np.where(hit, np.where(in_field, tau, 0.0), 1.0)
        # Wangen (Ebenen b = const)
        for ch in CHEEKS:
            if abs(db) < 1e-9:
                continue
            s = (ch["b"] - pb) / db
            ha, hh = pa + s * da, s * dh
            hit = ((s > 0) & (ha >= ch["a"][0]) & (ha <= ch["a"][1]) & (hh >= 0.0) &
                   (hh <= cheek_depth(ha)))
            if ch["perforated"]:
                in_field = ((ha >= CHEEK_FIELD_A[0]) & (ha <= CHEEK_FIELD_A[1]) &
                            (hh >= CHEEK_FIELD_H[0]) & (hh <= CHEEK_FIELD_H[1]) &
                            (hh <= cheek_depth(ha) - 0.006))
                tau = hole_transmission(d, db)
                t = t * np.where(hit, np.where(in_field, tau, 0.0), 1.0)
            else:
                t = t * np.where(hit, 0.0, 1.0)
        out[k] = t.mean()
    return out


def new_lvk(ies_in, ies_out, p_new):
    c, g, table, flux, name = read_ies(ies_in)
    c, g, table = np.array(c), np.array(g), np.array(table)
    d_new = d_for_open_area(p_new)
    cc, gg = np.meshgrid(np.radians(c), np.radians(g), indexing="ij")
    # Richtung im System (a, b, h): C0 = +a, C90 = +b, gamma 0 = +h (nach unten)
    dirs = np.stack([np.sin(gg) * np.cos(cc), np.sin(gg) * np.sin(cc), np.cos(gg)], -1)
    flat = dirs.reshape(-1, 3)
    t_old = visor_transmission(flat, D_OLD).reshape(table.shape)
    t_new = visor_transmission(flat, d_new).reshape(table.shape)
    # Lichtstärke ohne Blende: aus der Messung zurückgerechnet (I / T_alt). Wo die Blende fast
    # alles verdeckt (T_alt < 0,2), ist das unsicher; dort ist I_frei höchstens der Wert der
    # vorigen gamma-Stufe, abgemindert im selben Verhältnis wie die unverdeckte C0-Seite.
    c0 = table[int(np.argmin(np.abs(c - 0.0)))]
    decline = np.ones_like(g)
    decline[1:] = np.minimum(1.0, c0[1:] / np.maximum(c0[:-1], 1e-9))
    i_free = np.array(table, dtype=float)
    for j in range(1, len(g)):
        back = table[:, j] / np.maximum(t_old[:, j], 1e-3)
        limit = i_free[:, j - 1] * decline[j]
        i_free[:, j] = np.where(t_old[:, j] > 0.98, table[:, j],
                                np.where(t_old[:, j] >= 0.2, back, np.minimum(back, limit)))
    i_free = np.maximum(i_free, table)
    i_new = table + i_free * np.maximum(t_new - t_old, 0.0)
    # IES schreiben (gleiches Format wie ldt2ies.write_ies)
    lines = open(ies_in, encoding="latin-1").read().splitlines()
    tilt = next(i for i, l in enumerate(lines) if l.startswith("TILT="))
    head = [l for l in lines[:tilt] if not l.startswith("[LUMINAIRE]") and
            not l.startswith("[OTHER]")]
    head.insert(1, f"[LUMINAIRE] {name}_Blende_Lochung_{p_new * 100:.0f}pct")
    head.append(f"[OTHER] Estimated from measured LVK: visor perforation "
                f"{open_area(D_OLD) * 100:.1f}% -> {p_new * 100:.0f}% (hole d {D_OLD:g} -> "
                f"{d_new:.2f} mm, pitch {PITCH:g} mm, sheet {SHEET:g} mm)")
    new_flux = lumen(c, g, i_new)
    tok = " ".join(lines[tilt + 1:]).split()
    tok[1] = f"{new_flux:.0f}"
    nv, nh = int(float(tok[3])), int(float(tok[4]))
    out = head + ["TILT=NONE", " ".join(tok[:10]), " ".join(tok[10:13]),
                  " ".join(f"{x:g}" for x in g), " ".join(f"{x:g}" for x in c)]
    out += [" ".join(f"{v:.2f}" for v in row) for row in i_new]
    assert len(g) == nv and len(c) == nh
    open(ies_out, "w").write("\n".join(out) + "\n")
    return dict(d_new=d_new, flux_old=lumen(c, g, table), flux_new=new_flux, t_old=t_old,
                t_new=t_new, i_old=table, i_new=i_new, c=c, g=g)


def lumen(c, g, table):
    """Lichtstrom aus der Lichtstärkeverteilung (Trapezintegration über die Kugel)."""
    cr, gr = np.radians(c), np.radians(g)
    inner = np.trapezoid(table * np.sin(gr)[None, :], gr, axis=1)
    return float(np.trapezoid(inner, cr))


# ---------------------------------------------------------------------------
# Geometrie
# ---------------------------------------------------------------------------

def enlarge_holes(step_in, out_dir, d_new, holes_cache):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Message import Message_ProgressRange
    from OCP.RWGltf import RWGltf_CafWriter
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
    from OCP.TCollection import TCollection_AsciiString, TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    from OCP.collections import (IndexedDataMap_TCollection_AsciiString_TCollection_AsciiString
                                 as FileInfo, Sequence_TDF_Label as Seq)

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
    label = None
    for i in range(1, labels.Length() + 1):
        lab = labels.Value(i)
        attr = TDataStd_Name()
        if (lab.FindAttribute(TDataStd_Name.GetID_s(), attr) and
                "10166330" in attr.Get().ToExtString() and not st.IsAssembly_s(lab)):
            label = lab
            break
    shape = st.GetShape_s(label)

    holes = pickle.load(open(holes_cache, "rb"))
    seen = set()
    builder = BRep_Builder()
    tools = TopoDS_Compound()
    builder.MakeCompound(tools)
    n = 0
    for rad, _p, d, _area, cm in holes:
        if abs(rad - D_OLD / 2) > 1e-3:
            continue
        ax = np.array(d, dtype=float)
        # Schwerpunkt der Lochwand = Lochmitte im Blech (Löcher mit zwei Halbschalen
        # ergeben denselben Punkt)
        centre = np.array(cm, dtype=float)
        key = tuple(np.round(centre, 1))
        if key in seen:
            continue
        seen.add(key)
        start = centre - ax * 10.0
        cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*start), gp_Dir(*ax)), d_new / 2, 20.0)
        builder.Add(tools, cyl.Shape())
        n += 1
    cut = BRepAlgoAPI_Cut(shape, tools)
    cut.Build()
    new_shape = cut.Shape()
    st.SetShape(label, new_shape)
    st.UpdateAssemblies()
    print(f"{n} Löcher auf Ø {d_new:.2f} mm aufgebohrt")

    w = STEPControl_Writer()
    w.Transfer(new_shape, STEPControl_AsIs)
    w.Write(os.path.join(out_dir, "blende_lochung_50.stp"))

    free = Seq()
    st.GetFreeShapes(free)
    for i in range(1, free.Length() + 1):
        BRepMesh_IncrementalMesh(st.GetShape_s(free.Value(i)), 0.3, False, 0.2, True)
    writer = RWGltf_CafWriter(TCollection_AsciiString(os.path.join(out_dir,
                                                                   "sirius1000_perf50.glb")),
                              True)
    writer.Perform(doc, FileInfo(), Message_ProgressRange())


def main():
    step_in, out_dir = sys.argv[1], sys.argv[2]
    p_new = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
    d_new = d_for_open_area(p_new)
    print(f"Lochung alt: Ø {D_OLD} mm, {open_area(D_OLD) * 100:.1f} % offen; "
          f"neu: Ø {d_new:.2f} mm, {p_new * 100:.0f} % offen (Raster {PITCH:g} mm, "
          f"Steg {PITCH - d_new:.2f} mm)")
    res = new_lvk(os.path.join(out_dir, "sirius1000.ies"),
                  os.path.join(out_dir, "sirius1000_perf50.ies"), p_new)
    print(f"Lichtstrom aus LVK: alt {res['flux_old']:.0f} lm, neu {res['flux_new']:.0f} lm "
          f"(+{res['flux_new'] - res['flux_old']:.0f} lm)")
    ci = int(np.argmin(np.abs(res["c"] - 180)))
    for gam in (50, 60, 65, 70, 75, 80, 85, 90):
        gi = int(np.argmin(np.abs(res["g"] - gam)))
        print(f"  C180 gamma {gam:3d}: T alt {res['t_old'][ci, gi]:.3f} neu "
              f"{res['t_new'][ci, gi]:.3f}  I alt {res['i_old'][ci, gi]:8.0f} cd  "
              f"neu {res['i_new'][ci, gi]:8.0f} cd")
    pickle.dump(res, open(os.path.join(out_dir, "perforation_lvk.pkl"), "wb"))
    if "--geometrie" in sys.argv:
        enlarge_holes(step_in, out_dir, d_new, os.path.join(out_dir, "holes.pkl"))


if __name__ == "__main__":
    main()
