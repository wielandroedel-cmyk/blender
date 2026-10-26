"""
Entwurf einer außenliegenden Blende für die SIRIUS-1000-Optik (wie V2 gemessen), deren
Lichtverteilung nach hinten der LDT "SIRIUS BLENDE 3" (ohne externe Blende) entspricht.

    python visor_design.py [ordner]

1. Optik ohne außenliegende Blende: aus der gemessenen V2-LVK zurückgerechnet (perforation.free_lvk).
2. Parametrische Blende im Leuchtensystem (a nach vorn/C0, b quer/C90, h nach unten, Glas bei h = 0):
     - Stirnblech an der hinteren Glaskante (a = -0.396 m), Tiefe D unter dem Glas,
       geneigt um beta (beta > 0: Unterkante weiter nach hinten, beta < 0: unter das Glas),
       Lochanteil p (Raster 12 mm, Blech 1,5 mm; 0 = geschlossen)
     - Seitenwangen b = +-0.167 m, Länge 237 mm, wie V2: 211 mm am Stirnblech, 89 mm vorn,
       gleiche Lochung. Tiefere Wangen schneiden das Licht zur Seite (C90/C270) ab und kosten
       in der Arena-Reihe die Gleichmäßigkeit für Klasse I (siehe variant_study.py).
   Innenseite matt schwarz angenommen: Reflexionen an der neuen Blende werden nicht addiert,
   Reflexionen der V2-Blende bleiben wie gemessen enthalten (konservativ).
3. Gittersuche über D, beta, p: kleinste Abweichung zur Blende 3 im hinteren Halbraum
   Neigung nur >= 0 (Unterkante nicht unter dem Glas), sonst schattet das Blech senkrecht nach
   unten ab und es gehen ~7 % Lichtstrom verloren.
   (C 90…270°, gamma 0…85°, d. h. auch ohne Verlust im Hauptlicht, logarithmisch, raumwinkelgewichtet). Bei fast gleicher
   Abweichung (2 %) gewinnt die tiefste Blende bis 450 mm: mehr Tiefe senkt die Blendung bei
   5 m Montagehöhe deutlich, die Abweichung zur Blende 3 kaum.
4. Ausgabe: LVK als IES und LDT (EULUMDAT), Kenndaten, Diagramm, Maßzeichnung.
"""

import math
import os
import sys

import numpy as np

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DATA_DIR)
from ldt2ies import read_ies  # noqa: E402
from perforation import (GLASS_A, GLASS_B, d_for_open_area, free_lvk,  # noqa: E402
                         hole_transmission, lumen, lvk_directions)

A_BACK = -0.396          # hintere Kante (Lage des V2-Stirnblechs)
PLATE_HALF_W = 0.168     # Stirnblech bis an die Wangen
CHEEK_B = 0.167
CHEEK_LEN = 0.237
CHEEK_FRONT_RATIO = 0.089 / 0.211
CHEEK_DEPTH = 0.211     # Wangen wie V2
MAX_DEPTH = 0.45
SOLID_TOP = 0.035        # ungelochter Streifen am Glas (wie V2)
MARGIN = 0.012           # ungelochter Rand

TARGET_IES = "sirius1000_b3.ies"
SOURCE_IES = "sirius1000.ies"


class Visor:
    def __init__(self, depth, beta_deg, open_area, cheek_depth=None):
        self.D = depth
        self.Dc = depth if cheek_depth is None else cheek_depth  # Wangentiefe am Stirnblech
        self.beta = math.radians(beta_deg)
        self.p = open_area
        self.d_hole = d_for_open_area(open_area) if open_area > 0 else None

    def plate_a(self, h):
        return A_BACK - h * math.tan(self.beta)

    def tau(self, cos_inc):
        return 0.0 if self.d_hole is None else hole_transmission(self.d_hole, cos_inc)

    def transmission(self, dirs, n_pts=24):
        ga = np.linspace(-GLASS_A, GLASS_A, n_pts)
        gb = np.linspace(-GLASS_B, GLASS_B, max(6, n_pts // 2))
        pa, pb = np.meshgrid(ga, gb)
        pa, pb = pa.ravel(), pb.ravel()
        tb = math.tan(self.beta)
        nrm = np.array([1.0, 0.0, tb]) / math.sqrt(1 + tb * tb)
        out = np.ones(len(dirs))
        for k, (da, db, dh) in enumerate(dirs):
            if dh <= 1e-6:
                continue
            t = np.ones_like(pa)
            # Stirnblech: a + h * tan(beta) = A_BACK
            den = da + dh * tb
            if den < -1e-9:
                s = (A_BACK - pa) / den
                hb, hh = pb + s * db, s * dh
                hit = (s > 0) & (np.abs(hb) <= PLATE_HALF_W) & (hh <= self.D)
                field = ((hh >= SOLID_TOP) & (hh <= self.D - MARGIN) &
                         (np.abs(hb) <= PLATE_HALF_W - MARGIN))
                tau = self.tau(abs(da * nrm[0] + dh * nrm[2]))
                t = t * np.where(hit, np.where(field, tau, 0.0), 1.0)
            # Seitenwangen
            if abs(db) > 1e-9:
                for b0 in (-CHEEK_B, CHEEK_B):
                    s = (b0 - pb) / db
                    ha, hh = pa + s * da, s * dh
                    a_start = A_BACK - hh * tb
                    rel = np.clip((ha - a_start) / CHEEK_LEN, 0, 1)
                    depth = self.Dc * (1 - rel * (1 - CHEEK_FRONT_RATIO))
                    hit = ((s > 0) & (ha >= a_start) & (ha <= a_start + CHEEK_LEN) &
                           (hh >= 0) & (hh <= depth))
                    field = (hh >= SOLID_TOP) & (hh <= depth - MARGIN)
                    tau = self.tau(abs(db))
                    t = t * np.where(hit, np.where(field, tau, 0.0), 1.0)
            out[k] = t.mean()
        return out


def design_lvk(visor, base):
    c, g, table, t_old, i_free = base
    flat = lvk_directions(c, g).reshape(-1, 3)
    t_new = visor.transmission(flat).reshape(table.shape)
    # gemessene Reflexionen der V2-Blende bleiben, Abschattung nach neuer Geometrie
    return np.maximum(table + i_free * (t_new - t_old), 0.0), t_new


def target_error(i_new, target, c, g):
    cc, gg = np.meshgrid(c, g, indexing="ij")
    mask = (cc >= 90) & (cc <= 270) & (gg <= 85)
    w = np.sin(np.radians(gg))[mask]
    e = np.log((i_new[mask] + 50.0) / (target[mask] + 50.0))
    return float(np.sqrt(np.sum(w * e * e) / np.sum(w))), float(np.sum(w * e) / np.sum(w))


def write_ldt(path, c, g, table, flux, name, note):
    """EULUMDAT, Isym 2 (symmetrisch zur Ebene C0-C180), Werte in cd/klm."""
    c = list(c[:-1]) if c[-1] == 360 else list(c)
    mc, ng = len(c), len(g)
    rel = table[:mc] / (flux / 1000.0)
    lines = ["Siteco (berechnet)", "2", "2", str(mc), f"{c[1] - c[0]:g}", str(ng),
             f"{g[1] - g[0]:g}", "Berechnung, keine Messung", name[:78], note[:78], note[:78],
             "20261026", "348", "791", "126", "300", "761", "0", "0", "0", "0", "100", "100", "1", "0",
             "1", "1", "LED", f"{flux:.0f}", "5000K", "CRI90", "985.5"]
    lines += ["0"] * 10
    lines += [f"{x:.1f}" for x in c] + [f"{x:.1f}" for x in g]
    for ci in range(mc // 2 + 1):
        lines += [f"{v:.3f}" for v in rel[ci]]
    with open(path, "w", encoding="latin-1") as f:
        f.write("\r\n".join(lines) + "\r\n")


def write_ies(path, template_ies, c, g, table, flux, name, note):
    lines = open(template_ies, encoding="latin-1").read().splitlines()
    tilt = next(i for i, l in enumerate(lines) if l.startswith("TILT="))
    head = [l for l in lines[:tilt] if not l.startswith(("[LUMINAIRE]", "[OTHER]"))]
    head.insert(1, f"[LUMINAIRE] {name}")
    head.append(f"[OTHER] {note}")
    tok = " ".join(lines[tilt + 1:]).split()
    tok[1] = f"{flux:.0f}"
    out = head + ["TILT=NONE", " ".join(tok[:10]), " ".join(tok[10:13]),
                  " ".join(f"{x:g}" for x in g), " ".join(f"{x:g}" for x in c)]
    out += [" ".join(f"{v:.2f}" for v in row) for row in table]
    open(path, "w").write("\n".join(out) + "\n")


def main():
    c, g, table, t_old, i_free, _ = free_lvk(os.path.join(DATA_DIR, SOURCE_IES))
    base = (c, g, table, t_old, i_free)
    tc, tg, target, _, _ = read_ies(os.path.join(DATA_DIR, TARGET_IES))
    target = np.array(target)
    assert list(tc) == list(c) and list(tg) == list(g)

    err_v2 = target_error(table, target, c, g)
    err_bare = target_error(i_free, target, c, g)
    print(f"Ausgangslage: V2 heute Fehler {err_v2[0]:.3f}, ohne Blende {err_bare[0]:.3f}")

    results = []
    for depth in np.arange(0.25, 0.551, 0.025):
        for beta in (0, 10, 20, 30, 40):  # nicht unter das Glas: kein Verlust senkrecht nach unten
            for p in (0.0, 0.034, 0.10, 0.20, 0.30, 0.40):
                v = Visor(round(depth, 3), beta, p, CHEEK_DEPTH)
                i_new, _ = design_lvk(v, base)
                err, bias = target_error(i_new, target, c, g)
                results.append((err, bias, round(depth, 3), beta, p))
    results.sort()
    best_err = results[0][0]
    # tiefste Blende bis MAX_DEPTH innerhalb von 2 % des besten Fehlers
    near = [r for r in results if r[0] <= best_err * 1.02 and r[2] <= MAX_DEPTH + 1e-9]
    chosen = max(near, key=lambda r: (r[2], -abs(r[3]), -r[0]))
    print("beste 8 Kombinationen (Fehler, Tendenz, Tiefe, Neigung, Lochanteil):")
    for r in results[:8]:
        print("  %.3f  %+.3f  D=%.3f m  beta=%+3d°  p=%.0f %%" % (r[0], r[1], r[2], r[3], r[4] * 100))
    err, bias, depth, beta, p = chosen
    print(f"Gewählt: D = {depth * 1000:.0f} mm, Neigung {beta:+d}°, Lochanteil {p * 100:.0f} % "
          f"(Fehler {err:.3f}, Tendenz {bias:+.3f})")

    visor = Visor(depth, beta, p, CHEEK_DEPTH)
    i_new, t_new = design_lvk(visor, base)
    flux = lumen(c, g, i_new)
    name = "SIRIUS_1000_Blende_B3_aussen"
    note = (f"Berechnet: Stirnblech {depth * 1000:.0f} mm tief, Neigung {beta:+d} Grad, Lochung "
            f"{p * 100:.0f} %, Wangen wie V2, innen matt schwarz")
    write_ies(os.path.join(DATA_DIR, "sirius1000_visor_b3.ies"), os.path.join(DATA_DIR, SOURCE_IES),
              c, g, i_new, flux, name, note)
    write_ldt(os.path.join(DATA_DIR, "SIRIUS1000_Blende_B3_aussen_berechnet.ldt"), c, g, i_new,
              flux, name, note)
    np.save(os.path.join(DATA_DIR, "visor_design.npy"),
            np.array([depth, beta, p, flux, err, CHEEK_DEPTH], dtype=float))

    ci180 = int(np.argmin(np.abs(c - 180)))
    print(f"Lichtstrom {flux:.0f} lm (V2 {lumen(c, g, table):.0f} lm)")
    print("C180:   gamma |   V2   | neu    | Blende 3")
    for gam in (45, 50, 55, 60, 65, 70, 75, 80, 85):
        j = int(np.argmin(np.abs(g - gam)))
        print(f"        {gam:3d}   | {table[ci180, j]:6.0f} | {i_new[ci180, j]:6.0f} | {target[ci180, j]:6.0f}")
    plot(c, g, table, i_new, target, visor, err)


def plot(c, g, table, i_new, target, visor, err):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(17, 5.4), dpi=130, gridspec_kw={"width_ratios": [1, 1, 1.05]})
    for ax, cv, title in ((axes[0], 180.0, "C180 – nach hinten"), (axes[1], 150.0, "C150 – schräg hinten")):
        ci = int(np.argmin(np.abs(c - cv)))
        ax.semilogy(g, np.maximum(table[ci], 1), color="#17202b", lw=2, label="V2 heute (gemessen)")
        ax.semilogy(g, np.maximum(target[ci], 1), color="#2f9a46", lw=2, label="Blende 3, ohne ext. Blende")
        ax.semilogy(g, np.maximum(i_new[ci], 1), color="#0b5cad", lw=2.4, ls="--",
                    label="neue außenliegende Blende (berechnet)")
        for gam, lab in ((49.6, "Person 8 m"), (64.6, "Person 5 m")):
            ax.axvline(gam, color="0.6", lw=0.8, ls=":")
            ax.text(gam + 0.8, 2, lab, rotation=90, fontsize=8, color="0.4")
        ax.set_xlim(0, 100)
        ax.set_ylim(1, 2e5)
        ax.set_title(title)
        ax.set_xlabel("γ [°]")
        ax.grid(alpha=0.3, which="both")
    axes[0].set_ylabel("Lichtstärke [cd] bei 111.246 lm")
    axes[0].legend(fontsize=8.5, loc="upper right")

    # Maßskizze Seitenansicht (Schnitt C0-C180)
    ax = axes[2]
    D, tb = visor.D * 1000, math.tan(visor.beta)
    ax.add_patch(plt.Rectangle((-396, -126), 792, 126, fc="#d5dbe1", ec="#5b6673"))
    ax.text(0, -63, "Leuchtengehäuse 792 × 126 mm", ha="center", va="center", fontsize=9)
    ax.plot([-383, 383], [0, 0], color="#0b5cad", lw=4)
    ax.text(150, -10, "Glas 766 mm", ha="center", va="bottom", color="#0b5cad", fontsize=9)
    x0, x1 = -396, -396 - D * tb
    ax.plot([x0, x1], [0, D], color="#17202b", lw=3)
    cheek_end = -396 + 237
    Dc = visor.Dc * 1000
    ax.plot([-396 - Dc * tb, cheek_end], [Dc, Dc * CHEEK_FRONT_RATIO], color="#5b6673", lw=1.5, ls="--")
    ax.plot([cheek_end, cheek_end], [0, Dc * CHEEK_FRONT_RATIO], color="#5b6673", lw=1.5, ls="--")
    ax.annotate("", xy=(x1 - 40, 0), xytext=(x1 - 40, D), arrowprops=dict(arrowstyle="<->"))
    ax.text(x1 - 50, D / 2, f"{D:.0f} mm", ha="right", va="center", fontsize=10, weight="bold")
    ax.text(x1 + 10, D + 18, f"Stirnblech, Neigung {math.degrees(visor.beta):+.0f}°, "
            f"Lochung {visor.p * 100:.0f} %", fontsize=9, va="top")
    ax.text(cheek_end + 8, Dc * CHEEK_FRONT_RATIO + 10, "Wange 237 mm", fontsize=8, color="#5b6673", va="top")
    ax.arrow(250, 150, 90, 120, width=3, color="#a35a00")
    ax.text(250, 140, "Hauptstrahl nach vorn (C0)", fontsize=8, color="#a35a00", ha="center", va="bottom")
    ax.text(-640, -150, "← hinten (C180, zur Person)", fontsize=8, ha="left", va="center")
    ax.set_xlim(-650, 450)
    ax.set_ylim(D + 80, -180)
    ax.set_aspect("equal")
    ax.set_title("Neue außenliegende Blende – Seitenansicht (Schnitt C0–C180)")
    ax.set_xlabel("mm")
    ax.grid(alpha=0.2)
    fig.suptitle(f"Außenliegende Blende mit Lichtverteilung wie „Blende 3“ – Abweichung im hinteren "
                 f"Halbraum {err:.2f} (log) · Optik SIRIUS 1000 wie V2 · berechnet, nicht gemessen", fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(DATA_DIR, "visor_design.png"), bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
