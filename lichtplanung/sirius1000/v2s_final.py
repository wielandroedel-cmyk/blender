"""
Ausarbeitung der Blende V2s: Lochung des Stirnblechs, Befestigung/Steifigkeit, endgültige LVK.

    python v2s_final.py [ordner]

1. Lochung: Stirnblech mit offener Fläche 0-40 % bei Teilung 12 mm (Werkzeug wie V2) und 8 mm
   (feiner, kleinere Löcher wirken bei 1,5 mm Blech stärker winkelabhängig). Wangen wie V2s
   (Eckwinkel 60 mm / 80 mm). Bewertet: Wirkungsgrad der Blende, GR der Person (5 m / 8 m),
   größtes GR der Zuschauer, Rückwand, Arena-Reihe. Zulässig ist eine Lochung, wenn Person und
   Zuschauer nicht stärker geblendet werden als mit der heutigen V2 und die Löcher stanzbar bleiben
   (Ø und Steg >= Blechdicke 1,5 mm). Der Wirkungsgrad ändert sich über alle Lochungen um weniger
   als einen Prozentpunkt; gewählt wird deshalb die kleinste noch durchscheinende Lochung mit dem
   vorhandenen Werkzeug (Teilung 12 mm).
2. Befestigung: Trägerrost-Modell (Kirchhoff-Platte als Balkenrost, 8 mm Raster) des Stirnblechs
   von 64 mm über bis 211 mm unter dem Glas. Lager: L-Winkel hinten (Linie u = -100…100 mm,
   v = -40 mm), Wangenstreifen oberhalb des Glases (Seitenkanten bis v = 0), darunter die Wangen
   bzw. Eckwinkel bis zu ihrer Tiefe. Versteifung durch 15 mm nach hinten gekantete Seiten- und
   Unterkanten. Stahlblech 1,5 mm (E 210 GPa), Last 0,5 kN/m² (Wind/Reinigung, Referenz).
   Ausgewertet: größte Durchbiegung und erste Eigenfrequenz.
3. Endgültige V2s: IES/LDT, Polardiagramme, Maßzeichnung.

Ausgabe: v2s_final.txt, v2s_lochung.csv, v2s_final.npy, sirius1000_v2s.ies,
SIRIUS1000_Blende_V2s_berechnet.ldt, v2s_lochung.png, v2s_befestigung.png, v2s_polar.png,
v2s_zeichnung.png
"""

import math
import os
import sys

import numpy as np

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DATA_DIR)
from perforation import D_OLD, free_lvk, lumen  # noqa: E402
from visor_design import SOURCE_IES, write_ies, write_ldt  # noqa: E402
from visor_v2s import V2Sides, assess  # noqa: E402
from vergleich_blenden import rear_wall  # noqa: E402
from blendung import LVK  # noqa: E402

CHEEK = (0.06, 0.0, 0.08, 0.034)          # Eckwinkel V2s: Tiefe, vorn, Länge, Lochung
SHEET = 1.5
FLANGE = 15.0


# ------------------------------------------------------------------ Lichttechnik
def lvk_obj(c, g, table):
    lvk = LVK.__new__(LVK)
    lvk.c, lvk.g, lvk.t = np.array(c), np.array(g), np.array(table)
    lvk.flux, lvk.name = lumen(c, g, table), "variante"
    return lvk


def run_variant(v, base):
    r = assess(v, base)
    lvk = lvk_obj(base[0], base[1], r["i"])
    for h in (5.0, 8.0):
        _, _, ew = rear_wall(lvk, h)
        r[f"wall{h:.0f}"] = float(ew.mean())
    return r


def perforation_study(base, flux_free, ref):
    rows = []
    for pitch in (12.0, 8.0):
        for p in (0.0, 0.034, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30, 0.40):
            d = pitch * math.sqrt(4 * p / math.pi) if p > 0 else 0.0
            if pitch == 8.0 and p == 0.0:
                continue
            v = V2Sides(*CHEEK, plate_d=d, plate_pitch=pitch)
            r = run_variant(v, base)
            r.update(pitch=pitch, p=p, d=d, eta=r["flux"] / flux_free)
            punch = p == 0 or (d >= SHEET and pitch - d >= SHEET)
            r["ok"] = (punch and r["gr5"] <= ref["gr5"] + 1e-6 and r["gr8"] <= ref["gr8"] + 1e-6
                       and r["gr_sp"] <= ref["gr_sp"] + 1.0)
            r["punch"] = punch
            rows.append(r)
            print(f"Teilung {pitch:4.0f}  offen {p * 100:4.1f} %  Ø {d:4.2f} | Wirkungsgrad "
                  f"{r['eta'] * 100:5.1f} % | GR {r['gr5']:5.2f} / {r['gr8']:5.2f}  Zusch. "
                  f"{r['gr_sp']:5.1f} | Rückwand {r['wall5']:5.1f} / {r['wall8']:5.1f} lx | Reihe "
                  f"{r['em']:5.0f} U0 {r['u0']:.3f}{'  <- zulässig' if r['ok'] else ''}"
                  f"{'' if punch else '  (nicht stanzbar)'}", flush=True)
    return rows


# ------------------------------------------------------------------ Mechanik (Trägerrost)
def grillage(cheek_depth, side_flange, bottom_flange, p_open, d_hole, pitch, step=8.0,
             E=210000.0, nu=0.3, rho=7.85e-9, q=5e-4):
    """Durchbiegung [mm] und erste Eigenfrequenz [Hz] des Stirnblechs."""
    us = np.arange(-168.0, 168.0 + 1e-6, step)
    vs = np.arange(-64.0, 211.0 + 1e-6, step)
    nu_, nv_ = len(us), len(vs)
    n = nu_ * nv_
    idx = lambda i, j: (j * nu_ + i) * 3  # noqa: E731  w, dw/du, dw/dv
    K = np.zeros((3 * n, 3 * n))
    G = E / (2 * (1 + nu))
    lig = 1.0 - d_hole / pitch if d_hole > 0 else 1.0     # Stegwirkungsgrad der Lochung
    t3 = SHEET ** 3
    i_f = SHEET * FLANGE ** 3 / 3 * 0.7                    # Kantung, mit Neutralachsen-Abminderung

    def add(n1, n2, L, EI, GJ, along_u):
        b = EI / L ** 3 * np.array([[12, 6 * L, -12, 6 * L], [6 * L, 4 * L * L, -6 * L, 2 * L * L],
                                    [-12, -6 * L, 12, -6 * L], [6 * L, 2 * L * L, -6 * L, 4 * L * L]])
        bend = 1 if along_u else 2
        tors = 2 if along_u else 1
        dofs = [n1, n1 + bend, n2, n2 + bend]
        K[np.ix_(dofs, dofs)] += b
        tk = GJ / L * np.array([[1, -1], [-1, 1]])
        td = [n1 + tors, n2 + tors]
        K[np.ix_(td, td)] += tk

    for j in range(nv_):
        for i in range(nu_):
            below = vs[j] > 0
            f = lig if below else 1.0
            if i < nu_ - 1:      # Stab in u-Richtung, steht für Streifenbreite step (Rand halb)
                w = step / 2 if j in (0, nv_ - 1) else step
                EI = E * w * t3 / (12 * (1 - nu ** 2)) * f
                if bottom_flange and j == nv_ - 1:
                    EI += E * i_f
                add(idx(i, j), idx(i + 1, j), step, EI, G * w * t3 / 6 * f, True)
            if j < nv_ - 1:
                w = step / 2 if i in (0, nu_ - 1) else step
                EI = E * w * t3 / (12 * (1 - nu ** 2)) * f
                if side_flange and i in (0, nu_ - 1):
                    EI += E * i_f
                add(idx(i, j), idx(i, j + 1), step, EI, G * w * t3 / 6 * f, False)
    fixed = set()
    for j, v in enumerate(vs):
        for i, u in enumerate(us):
            if abs(v + 40.0) < step / 2 and abs(u) <= 100.0:          # L-Winkel
                fixed.add(idx(i, j))
            if i in (0, nu_ - 1) and v <= cheek_depth + 1e-6:          # Wangen / Eckwinkel
                fixed.add(idx(i, j))
    free = np.array(sorted(set(range(3 * n)) - fixed))
    F = np.zeros(3 * n)
    M = np.zeros(3 * n)
    for j, v in enumerate(vs):
        for i in range(nu_):
            a = step * step * (0.25 if (i in (0, nu_ - 1)) + (j in (0, nv_ - 1)) == 2 else
                               0.5 if (i in (0, nu_ - 1)) or (j in (0, nv_ - 1)) else 1.0)
            por = (1 - p_open) if v > 0 else 1.0
            F[idx(i, j)] = q * a * por
            m = rho * SHEET * a * por
            if side_flange and i in (0, nu_ - 1):
                m += rho * SHEET * FLANGE * step
            if bottom_flange and j == nv_ - 1:
                m += rho * SHEET * FLANGE * step
            M[idx(i, j)] = m
            M[idx(i, j) + 1] = M[idx(i, j) + 2] = m * step * step / 100.0   # kleine Drehträgheit
    Kf = K[np.ix_(free, free)]
    w = np.zeros(3 * n)
    w[free] = np.linalg.solve(Kf, F[free])
    wz = w[0::3].reshape(nv_, nu_)
    mi = 1 / np.sqrt(M[free])
    A = Kf * mi[:, None] * mi[None, :]
    lam = np.linalg.eigvalsh(A)[0]
    return float(np.abs(wz).max()), float(math.sqrt(max(lam, 0)) / (2 * math.pi)), us, vs, wz


def main():
    c, g, table, t_old, i_free, _ = free_lvk(os.path.join(DATA_DIR, SOURCE_IES))
    base = (c, g, table, t_old, i_free)
    flux_free = lumen(c, g, i_free)
    ref = run_variant(V2Sides(0.211, 0.0885, 0.237, 0.034), base)       # V2 heute
    ref["eta"] = ref["flux"] / flux_free
    lines = [f"V2 heute: Wirkungsgrad {ref['eta'] * 100:.1f} %, GR {ref['gr5']:.2f} / {ref['gr8']:.2f}, "
             f"Zuschauer {ref['gr_sp']:.1f}, Rückwand {ref['wall5']:.1f} / {ref['wall8']:.1f} lx, "
             f"Reihe {ref['em']:.0f} lx U0 {ref['u0']:.3f}", ""]
    print(lines[0])
    rows = perforation_study(base, flux_free, ref)
    good = [r for r in rows if r["ok"]]
    spread = max(r["eta"] for r in rows) - min(r["eta"] for r in rows)
    lines.append(f"Spannweite Wirkungsgrad über alle Lochungen: {spread * 100:.2f} Prozentpunkte")
    best = min((r for r in good if r["p"] > 0 and r["pitch"] == 12.0), key=lambda r: r["p"])
    for r in rows:
        lines.append(f"Teilung {r['pitch']:.0f} mm, offen {r['p'] * 100:4.1f} %, Ø {r['d']:.2f} mm: "
                     f"Wirkungsgrad {r['eta'] * 100:.1f} %, GR {r['gr5']:.2f} / {r['gr8']:.2f}, "
                     f"Zuschauer {r['gr_sp']:.1f}, Rückwand {r['wall5']:.1f} / {r['wall8']:.1f} lx, "
                     f"U0 {r['u0']:.3f}{' zulässig' if r['ok'] else ''}")
    sel = (f"Lochung gewählt: Teilung {best['pitch']:.0f} mm, offen {best['p'] * 100:.1f} %, Ø "
           f"{best['d']:.2f} mm, Wirkungsgrad {best['eta'] * 100:.1f} % (V2 {ref['eta'] * 100:.1f} %), "
           f"GR {best['gr5']:.2f} / {best['gr8']:.2f}, Zuschauer {best['gr_sp']:.1f}")
    print(sel)
    lines += ["", sel, ""]
    with open(os.path.join(DATA_DIR, "v2s_lochung.csv"), "w") as f:
        f.write("teilung_mm;offen;d_mm;wirkungsgrad;gr5;gr8;gr_zuschauer;rueckwand5;rueckwand8;"
                "reihe_e;reihe_u0;zulaessig\n")
        for r in rows:
            f.write(f"{r['pitch']:.0f};{r['p']:.3f};{r['d']:.2f};{r['eta']:.4f};{r['gr5']:.2f};"
                    f"{r['gr8']:.2f};{r['gr_sp']:.2f};{r['wall5']:.2f};{r['wall8']:.2f};{r['em']:.0f};"
                    f"{r['u0']:.4f};{int(r['ok'])}\n")

    # Mechanik
    mech = []
    variants = [("V2 heute (Wangen 211 mm)", 211.0, False, False, 0.034, D_OLD, 12.0),
                ("V2s ohne Kantung", 60.0, False, False, best["p"], best["d"], best["pitch"]),
                ("V2s + Seitenkanten", 60.0, True, False, best["p"], best["d"], best["pitch"]),
                ("V2s + Seiten- und Unterkante", 60.0, True, True, best["p"], best["d"], best["pitch"]),
                ("V2s, Eckwinkel 100 mm + Kanten", 100.0, True, True, best["p"], best["d"], best["pitch"])]
    for name, cd, sf, bf, p, d, pitch in variants:
        wmax, f1, us, vs, wz = grillage(cd, sf, bf, p, d, pitch)
        mech.append((name, wmax, f1, us, vs, wz))
        line = f"Befestigung {name}: Durchbiegung {wmax:.2f} mm bei 0,5 kN/m², erste Eigenfrequenz {f1:.0f} Hz"
        print(line)
        lines.append(line)
    open(os.path.join(DATA_DIR, "v2s_final.txt"), "w").write("\n".join(lines) + "\n")

    # endgültige LVK
    name = "SIRIUS_1000_Blende_V2s"
    note = (f"Berechnet: Stirnblech wie V2, Lochung {best['p'] * 100:.1f} % (Ø {best['d']:.1f} / "
            f"{best['pitch']:.0f} mm), Eckwinkel 60x80 mm, Kanten 15 mm nach hinten")
    write_ies(os.path.join(DATA_DIR, "sirius1000_v2s.ies"), os.path.join(DATA_DIR, SOURCE_IES),
              c, g, best["i"], best["flux"], name, note)
    write_ldt(os.path.join(DATA_DIR, "SIRIUS1000_Blende_V2s_berechnet.ldt"), c, g, best["i"],
              best["flux"], name, note)
    np.save(os.path.join(DATA_DIR, "visor_v2s.npy"),
            np.array([CHEEK[0], CHEEK[1], CHEEK[2], CHEEK[3], best["flux"]]))
    np.save(os.path.join(DATA_DIR, "v2s_final.npy"),
            np.array([best["p"], best["d"], best["pitch"], best["flux"], best["eta"], FLANGE]))
    plots(c, g, table, i_free, best, ref, rows, mech)


def plots(c, g, table, i_free, best, ref, rows, mech):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Lochung
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), dpi=130)
    for pitch, col in ((12.0, "#0b5cad"), (8.0, "#a35a00")):
        rs = [r for r in rows if r["pitch"] == pitch]
        axes[0].plot([r["p"] * 100 for r in rs], [r["eta"] * 100 for r in rs], "o-", color=col,
                     label=f"Teilung {pitch:.0f} mm")
        axes[1].plot([r["p"] * 100 for r in rs], [r["gr5"] for r in rs], "o-", color=col,
                     label=f"GR 5 m, Teilung {pitch:.0f} mm")
        axes[1].plot([r["p"] * 100 for r in rs], [r["gr8"] for r in rs], "s--", color=col,
                     label=f"GR 8 m, Teilung {pitch:.0f} mm")
    axes[0].axhline(ref["eta"] * 100, color="#17202b", ls=":", label="V2 heute")
    axes[1].axhline(ref["gr5"], color="#17202b", ls=":", label="V2 heute 5 m")
    axes[1].axhline(ref["gr8"], color="#5b6673", ls=":", label="V2 heute 8 m")
    for ax in axes:
        ax.axvline(best["p"] * 100, color="#2f9a46", lw=1.2)
        ax.set_xlabel("offene Fläche des Stirnblechs [%]")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7.5)
    axes[0].set_ylabel("Wirkungsgrad der Blende [%]")
    axes[1].set_ylabel("GR der Person")
    axes[0].set_title("Wirkungsgrad")
    axes[1].set_title("Blendung der Person")
    fig.suptitle(f"V2s: Lochung des Stirnblechs – gewählt {best['p'] * 100:.1f} % (Ø {best['d']:.1f} mm, "
                 f"Teilung {best['pitch']:.0f} mm)", fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(DATA_DIR, "v2s_lochung.png"), bbox_inches="tight")
    plt.close(fig)

    # Befestigung
    fig, axes = plt.subplots(1, len(mech), figsize=(4 * len(mech), 4.4), dpi=120, sharey=True)
    vmax = max(m[1] for m in mech)
    for ax, (name, wmax, f1, us, vs, wz) in zip(axes, mech):
        im = ax.contourf(us, vs, np.abs(wz), levels=np.linspace(0, vmax, 15), cmap="viridis")
        ax.axhline(0, color="w", lw=1, ls="--")
        ax.set_title(f"{name}\n{wmax:.2f} mm · {f1:.0f} Hz", fontsize=9)
        ax.set_xlabel("quer [mm]")
        ax.invert_yaxis()
    axes[0].set_ylabel("Höhe am Stirnblech [mm] (0 = Glas)")
    fig.colorbar(im, ax=axes, label="Durchbiegung [mm] bei 0,5 kN/m²", shrink=0.9)
    fig.suptitle("Stirnblech: Durchbiegung und erste Eigenfrequenz (Trägerrost, Stahl 1,5 mm)", fontsize=12,
                 y=1.07)
    fig.savefig(os.path.join(DATA_DIR, "v2s_befestigung.png"), bbox_inches="tight")
    plt.close(fig)

    # Polardiagramme
    fig, axes = plt.subplots(1, 2, figsize=(12, 6), dpi=130, subplot_kw={"projection": "polar"})
    cc = np.asarray(c)
    for ax, (ca, cb, title) in zip(axes, ((0, 180, "C0 – C180"), (90, 270, "C90 – C270"))):
        ia, ib = int(np.argmin(np.abs(cc - ca))), int(np.argmin(np.abs(cc - cb)))
        for tab, col, lab, ls in ((table, "#17202b", "V2 heute", "-"),
                                  (best["i"], "#0b5cad", "V2s", "--")):
            k = 1000 / lumen(c, g, tab) * 1.0
            th = np.concatenate([-np.radians(g[::-1]), np.radians(g)])
            r = np.concatenate([tab[ib][::-1], tab[ia]]) * k
            ax.plot(th, r, color=col, ls=ls, lw=1.8, label=lab)
        ax.set_theta_zero_location("S")
        ax.set_thetamin(-180)
        ax.set_thetamax(180)
        ax.set_title(f"{title} [cd/klm]", fontsize=11)
        ax.legend(fontsize=8, loc="upper right")
    fig.suptitle("Lichtstärkeverteilung SIRIUS 1000 V2s (berechnet) – Winkel = γ; je Diagramm rechts C0 "
                 "bzw. C90, links C180 bzw. C270", fontsize=11, y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(DATA_DIR, "v2s_polar.png"), bbox_inches="tight")
    plt.close(fig)
    drawing(best)


def drawing(best):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon, Rectangle

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.6), dpi=130, gridspec_kw={"width_ratios": [1.15, 1]})
    ink, blue, grey = "#17202b", "#0b5cad", "#5b6673"

    def dim(ax, p1, p2, text, off=(0, 0), **kw):
        ax.annotate("", xy=p1, xytext=p2, arrowprops=dict(arrowstyle="<->", color=ink, lw=0.8))
        ax.text((p1[0] + p2[0]) / 2 + off[0], (p1[1] + p2[1]) / 2 + off[1], text, ha="center",
                va="center", fontsize=8.5, color=ink, bbox=dict(fc="white", ec="none", pad=0.5), **kw)

    # Ansicht von hinten: Stirnblech mit Lochfeld und Kantungen
    ax = axes[0]
    W, top, bot = 336.0, -64.0, 211.0
    ax.add_patch(Rectangle((-W / 2, top), W, bot - top, fc="#f6f7f8", ec=ink, lw=1.4))
    ax.add_patch(Rectangle((-W / 2, bot - FLANGE * 0.0), W, 3, fc=grey, ec=ink, lw=0.6))
    for x in (-W / 2, W / 2 - 3):
        ax.add_patch(Rectangle((x, top), 3, bot - top, fc=grey, ec=ink, lw=0.6))
    pitch, d = best["pitch"], best["d"]
    if d > 0:
        for x in np.arange(-150 + d / 2, 150 - d / 2 + 1e-6, pitch):
            for y in np.arange(35 + d / 2, 191 - d / 2 + 1e-6, pitch):
                ax.add_patch(Circle((x, y), d / 2, fc="white", ec=grey, lw=0.4))
    ax.axhline(0, color=blue, lw=1, ls="--")
    ax.text(W / 2 + 6, 0, "Glasebene", color=blue, fontsize=8, va="center")
    ax.add_patch(Rectangle((-100, -48), 200, 16, fc="none", ec=grey, lw=1, ls="--"))
    for x in (-81, 81):
        ax.add_patch(Circle((x, -40), 4, fc="white", ec=ink, lw=1))
    ax.text(0, -54, "L-Winkel, 2 Schrauben (wie V2)", ha="center", fontsize=8, color=grey)
    dim(ax, (-W / 2, bot + 18), (W / 2, bot + 18), f"{W:.0f}")
    dim(ax, (-W / 2 - 22, 0), (-W / 2 - 22, bot), "211", off=(-2, 0))
    dim(ax, (-W / 2 - 22, top), (-W / 2 - 22, 0), "64", off=(-2, 0))
    ax.text(0, 113, f"Lochfeld 300 × 156 mm\nØ {d:.1f} mm, Teilung {pitch:.0f} mm, "
            f"{best['p'] * 100:.1f} % offen", ha="center", fontsize=8.5,
            bbox=dict(fc="white", ec=grey, lw=0.6))
    ax.text(W / 2 - 8, bot - 8, "Kantung 15 mm\nnach hinten", ha="right", va="bottom", fontsize=7.5,
            color=grey)
    ax.set_xlim(-W / 2 - 50, W / 2 + 55)
    ax.set_ylim(bot + 35, top - 20)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Ansicht von hinten (C180)", fontsize=11)

    # Seitenansicht: Stirnblech, Wangenstreifen, Eckwinkel, Kantung
    ax = axes[1]
    a0 = -396.0
    ax.add_patch(Rectangle((a0 - 1.5, top), 1.5, bot - top, fc=ink, ec=ink))
    ax.add_patch(Rectangle((a0 - 1.5 - FLANGE, bot - 1.5), FLANGE, 1.5, fc=grey, ec=ink, lw=0.6))
    ax.add_patch(Polygon([(a0, top), (-157, top), (-157, 0), (a0, 0)], closed=True, fc="#e3eef9",
                         ec=ink, lw=1))
    ax.add_patch(Polygon([(a0, 0), (a0 + 80, 0), (a0, 60)], closed=True, fc="#e3eef9", ec=ink, lw=1))
    ax.plot([a0, -157], [0, 0], color=blue, lw=2.5)
    ax.plot([a0 + 80, -100], [0, 0], color=blue, lw=2.5, alpha=0.5)
    ax.text(-270, -32, "Wangenstreifen über dem Glas\n(unverändert, Halteblech vorn)", fontsize=8,
            ha="center", va="center")
    ax.plot([a0 + 3, a0 + 80 + 40, -157 + 0], [211, 89, 0], color=grey, lw=1, ls=":")
    ax.text(a0 + 95, 120, "V2-Wange (entfällt)", fontsize=7.5, color=grey, rotation=-48)
    dim(ax, (a0, 10), (a0 + 80, 10), "80", off=(0, 6))
    dim(ax, (a0 + 12, 0), (a0 + 12, 60), "60", off=(8, 0))
    dim(ax, (a0 - 1.5 - FLANGE, bot + 14), (a0, bot + 14), "15", off=(0, 7))
    dim(ax, (a0, top - 10), (-157, top - 10), "239", off=(0, -6))
    ax.text(a0 - 6, 120, "Stirnblech", rotation=90, ha="right", va="center", fontsize=8.5)
    ax.set_xlim(a0 - 40, -120)
    ax.set_ylim(bot + 35, top - 25)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Seitenansicht (Schnitt an der Wange)", fontsize=11)
    fig.suptitle("Blende V2s – Hauptmaße in mm (Stahlblech 1,5 mm; Entwurf, berechnet)", fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(DATA_DIR, "v2s_zeichnung.png"), bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
