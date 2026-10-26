"""
Vergleich von vier Lichtverteilungen des SIRIUS 1000 (ein Modul, gleicher Lichtstrom 111.246 lm):

  V2      außenliegende Blende V2, Lochung 3,4 %   (gemessene LDT)
  V2-50   außenliegende Blende V2, Lochung 50 %    (aus V2 abgeschätzt, perforation.py)
  B2      ohne externe Blende, LDT "SIRIUS BLENDE 2" (relativ, auf 111.246 lm gesetzt, C90 -> C0)
  B3      ohne externe Blende, LDT "SIRIUS BLENDE 3" (relativ, auf 111.246 lm gesetzt, C90 -> C0)

    python vergleich_blenden.py [ordner]

Ausgewertet für 5 m und 8 m Montagehöhe:
  * Person 8 m hinter einer Leuchte (wie blendung.py): Lichtstärke, E_v, GR
  * Rückwand 10 m hinter der Leuchte: E_v-Verteilung (Direktlicht, Reflexion 0 %)
  * Arena mit 3 Leuchten / durchgehender Reihe (wie arena.py): Feld-E_h, U0, GR der Zuschauer
"""

import csv
import os
import sys

import numpy as np

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DATA_DIR)
import arena  # noqa: E402
from blendung import LVK, PERSON_DISTANCE, evaluate, floor_eh_mean  # noqa: E402
from perforation import D_OLD, d_for_open_area  # noqa: E402

# (Kürzel, Beschriftung, IES, Lochdurchmesser der außenliegenden Blende oder None = keine)
VARIANTS = [
    ("V2", "Blende V2, Lochung 3,4 %", "sirius1000.ies", D_OLD),
    ("V2-50", "Blende V2, Lochung 50 % (geschätzt)", "sirius1000_perf50.ies", d_for_open_area(0.5)),
    ("B2", "ohne ext. Blende – Blende 2", "sirius1000_b2.ies", None),
    ("B3", "ohne ext. Blende – Blende 3", "sirius1000_b3.ies", None),
]
COLORS = {"V2": "#17202b", "V2-50": "#a35a00", "B2": "#0b5cad", "B3": "#2f9a46"}
HEIGHTS = [5.0, 8.0]
WALL_Y, WALL_W = -10.0, 12.0


def rear_wall(lvk, h, step=0.05):
    height = h + 2.0
    xs = np.arange(-WALL_W / 2 + step / 2, WALL_W / 2, step)
    zs = np.arange(step / 2, height, step)
    gx, gz = np.meshgrid(xs, zs)
    pts = np.stack([gx, np.full_like(gx, WALL_Y), gz], -1)
    light = np.array([0.0, 0.0, h])
    i, d, _, _ = lvk.toward(light, pts)
    v = pts - light
    cos_eps = np.clip(-v[..., 1] / d, 0, None)  # Wandnormale +Y (zur Leuchte)
    return xs, zs, i * cos_eps / d ** 2


def main():
    results = {}
    for key, label, ies, d_hole in VARIANTS:
        lvk = LVK(os.path.join(DATA_DIR, ies))
        for h in HEIGHTS:
            r = {"label": label, "lvk": lvk}
            # Person (eine Leuchte, wie blendung.py; ohne ext. Blende ganze Glasfläche sichtbar)
            eh_room = floor_eh_mean(lvk, h)[0]
            r["person"] = evaluate(lvk, h, PERSON_DISTANCE, eh_mean=eh_room,
                                   d_hole=d_hole)
            # Rückwand
            xs, zs, ew = rear_wall(lvk, h)
            r["wall"] = (xs, zs, ew)
            # Arena (3 Leuchten und durchgehende Reihe)
            step = 0.25
            fx = np.arange(arena.FIELD_X[0] + step / 2, arena.FIELD_X[1], step)
            fy = np.arange(arena.FIELD_Y[0] + step / 2, arena.FIELD_Y[1], step)
            ef = arena.eh_grid(lvk, h, fx, fy)
            em = float(ef.mean())
            r["field3"] = (em, float(ef.min() / em))
            r["row"] = arena.continuous_row(lvk, h)
            sx = np.arange(arena.SPECT_X[0], arena.SPECT_X[1] + 1e-9, 0.25)
            sy = np.arange(arena.SPECT_Y[0], arena.SPECT_Y[1] + 1e-9, 0.25)
            gr, _, _, _ = arena.gr_grid(lvk, h, sx, sy, em)
            r["arena_gr"] = (sx, sy, gr)
            r["arena_pv"] = arena.point_values(lvk, h, *arena.SPECTATOR, em)
            results[(key, h)] = r
    write_summary(results)
    plot_lvk(results)
    plot_person(results)
    plot_wall(results)
    plot_arena(results)


def write_summary(results):
    rows = [["Variante", "Höhe [m]", "I Person [cd]", "E_v Person [lx]", "GR Person (ρ20 %)",
             "Rückwand Emittel [lx]", "Rückwand Emax [lx]", "Feld 3 Leuchten Ē [lx]", "U0",
             "Reihe Ē [lx]", "Reihe U0", "Klasse Reihe", "GR Zuschauer max", "GR Zuschauer x0/y-8",
             "E_v Zuschauer x0/y-8 [lx]"]]
    lines = ["Vergleich der Lichtverteilungen (SIRIUS 1000, je 111.246 lm)", ""]
    for key, label, _, _ in VARIANTS:
        lines.append(f"=== {key}: {label}")
        for h in HEIGHTS:
            r = results[(key, h)]
            p = r["person"]
            ew = r["wall"][2]
            row = r["row"]
            cls = arena.classify(row[0], row[2])
            gr = r["arena_gr"][2]
            pv = r["arena_pv"]
            rows.append([key, f"{h:g}", f"{p['I']:.0f}", f"{p['E_v']:.1f}", f"{p['GR']:.1f}",
                         f"{ew.mean():.1f}", f"{ew.max():.1f}", f"{r['field3'][0]:.0f}",
                         f"{r['field3'][1]:.2f}", f"{row[0]:.0f}", f"{row[2]:.2f}", cls,
                         f"{gr.max():.1f}", f"{pv['GR']:.1f}", f"{pv['E_v']:.0f}"])
            lines.append(
                f"  {h:g} m: Person I {p['I']:.0f} cd, E_v {p['E_v']:.1f} lx, GR {p['GR']:.1f} | "
                f"Rückwand Ē {ew.mean():.1f} lx, Emax {ew.max():.1f} lx | Feld 3 Leuchten "
                f"Ē {r['field3'][0]:.0f} lx U0 {r['field3'][1]:.2f} | Reihe Ē {row[0]:.0f} lx "
                f"U0 {row[2]:.2f} -> {cls} | Zuschauer GR max {gr.max():.1f}, an x0/y-8 "
                f"{pv['GR']:.1f}, E_v {pv['E_v']:.0f} lx")
        lines.append("")
    with open(os.path.join(DATA_DIR, "vergleich_blenden.csv"), "w", newline="") as f:
        csv.writer(f, delimiter=";").writerows(rows)
    with open(os.path.join(DATA_DIR, "vergleich_blenden.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def plot_lvk(results):
    plt = _plt()
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), dpi=130, sharey=True)
    g = np.linspace(0, 100, 201)
    for ax, (cname, cval) in zip(axes, [("C0 – nach vorn (Hauptstrahl)", 0.0),
                                        ("C90 – zur Seite", 90.0),
                                        ("C180 – nach hinten, zur Person", 180.0)]):
        for key, label, _, _ in VARIANTS:
            lvk = results[(key, 5.0)]["lvk"]
            ax.semilogy(g, np.maximum(lvk.intensity(np.full_like(g, cval), g), 1), lw=2,
                        color=COLORS[key], ls="--" if key == "V2-50" else "-", label=label)
        if cval == 180.0:
            for h, gam in ((5.0, 64.6), (8.0, 49.6)):
                ax.axvline(gam, color="0.5", lw=0.8, ls=":")
                ax.text(gam + 0.8, 2, f"Person bei {h:g} m", rotation=90, fontsize=8, color="0.4")
        ax.set_title(cname, fontsize=11)
        ax.set_xlabel("Ausstrahlungswinkel γ [°] (0 = senkrecht nach unten)")
        ax.grid(alpha=0.3, which="both")
        ax.set_xlim(0, 100)
    axes[0].set_ylabel("Lichtstärke [cd] bei 111.246 lm")
    axes[0].legend(fontsize=8.5, loc="lower left")
    fig.suptitle("Lichtverteilungen im Vergleich – SIRIUS 1000, je 111.246 lm", fontsize=13)
    fig.tight_layout()
    fig.savefig(os.path.join(DATA_DIR, "vergleich_lvk.png"), bbox_inches="tight")
    plt.close(fig)


def plot_person(results):
    plt = _plt()
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.8), dpi=130)
    metrics = [("I", "Lichtstärke zur Person [cd]", "{:,.0f}"),
               ("E_v", "E_v am Auge der Person [lx]", "{:.0f}"),
               ("GR", "GR Person (Boden ρ 20 %)", "{:.1f}")]
    keys = [v[0] for v in VARIANTS]
    width = 0.38
    xpos = np.arange(len(keys))
    for ax, (m, title, fmt) in zip(axes[:3], metrics):
        for j, h in enumerate(HEIGHTS):
            vals = [results[(k, h)]["person"][m] for k in keys]
            bars = ax.bar(xpos + (j - 0.5) * width, vals, width,
                          color=[COLORS[k] for k in keys], alpha=1.0 if h == 5.0 else 0.55,
                          edgecolor="white")
            for b, v in zip(bars, vals):
                ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                        fmt.format(v).replace(",", "."), ha="center", va="bottom", fontsize=7.5)
        ax.set_xticks(xpos, keys)
        ax.set_title(title, fontsize=10.5)
        ax.grid(alpha=0.3, axis="y")
        ax.text(0.01, 0.98, "kräftig: 5 m · hell: 8 m", transform=ax.transAxes, fontsize=7.5,
                va="top", color="0.35")
    ax = axes[3]
    for key, label, _, _ in VARIANTS:
        xs, zs, ew = results[(key, 5.0)]["wall"]
        ax.plot(zs, ew[:, len(xs) // 2], color=COLORS[key], lw=2,
                ls="--" if key == "V2-50" else "-", label=key)
    ax.set_xlabel("Höhe an der Rückwand [m]")
    ax.set_ylabel("E_v [lx]")
    ax.set_title("Rückwand 10 m hinter der Leuchte, Mitte (5 m)", fontsize=10.5)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.suptitle("Person 8 m hinter der Leuchte und Rückwand – V2 = Blende heute, V2-50 = Lochung 50 %, "
                 "B2/B3 = ohne externe Blende", fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(DATA_DIR, "vergleich_person.png"), bbox_inches="tight")
    plt.close(fig)


def plot_wall(results):
    plt = _plt()
    from matplotlib.colors import BoundaryNorm, ListedColormap
    levels = [0, 0.5, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 40, 50, 60]
    cols = ["#1a1446", "#1d2f8a", "#1f4fc0", "#2f78d6", "#3fa3d6", "#4cc2b5", "#6bd07c",
            "#a9dd5c", "#e6e04c", "#f6b440", "#ef7d34", "#d9442c", "#b51f5a"]
    cmap = ListedColormap(cols)
    norm = BoundaryNorm(levels, cmap.N)
    fig, axes = plt.subplots(2, 4, figsize=(18, 8.6), dpi=120)
    for r, h in enumerate(HEIGHTS):
        for c, (key, label, _, _) in enumerate(VARIANTS):
            ax = axes[r, c]
            xs, zs, ew = results[(key, h)]["wall"]
            im = ax.contourf(xs, zs, ew, levels=levels, cmap=cmap, norm=norm, extend="max")
            ax.contour(xs, zs, ew, levels=[1, 5, 20], colors="k", linewidths=0.5)
            ax.axhline(h, color="w", ls="--", lw=0.7)
            ax.set_title(f"{key} · {h:g} m: Ē {ew.mean():.1f} lx, Emax {ew.max():.0f} lx",
                         fontsize=10)
            ax.set_aspect("equal")
            ax.invert_xaxis()
            if c == 0:
                ax.set_ylabel("Höhe [m]")
            if r == 1:
                ax.set_xlabel("x [m], Blick auf die Rückwand")
    cb = fig.colorbar(im, ax=axes, ticks=levels, fraction=0.02, pad=0.01)
    cb.set_label("E_v [lx], Direktlicht")
    fig.suptitle("Rückwand 10 m hinter der Leuchte (2 m hinter der Person) – vertikale "
                 "Beleuchtungsstärke\nV2 = Blende heute · V2-50 = Lochung 50 % (geschätzt) · "
                 "B2 / B3 = ohne externe Blende · je 111.246 lm", fontsize=12)
    fig.savefig(os.path.join(DATA_DIR, "vergleich_rueckwand.png"), bbox_inches="tight")
    plt.close(fig)


def plot_arena(results):
    plt = _plt()
    from matplotlib.colors import BoundaryNorm, ListedColormap
    gr_levels = [0, 4, 8, 10, 12, 14, 16, 18, 20, 25, 30, 40, 50, 60]
    gr_colors = ["#17305e", "#1d4f91", "#2f6fb7", "#4a90c9", "#5fb0c4", "#7ccaa5", "#a6dc8a",
                 "#d2e778", "#f4e36b", "#f6b84c", "#ef8a3a", "#d9542a", "#a8231f"]
    cmap = ListedColormap(gr_colors)
    norm = BoundaryNorm(gr_levels, cmap.N)
    fig, axes = plt.subplots(2, 4, figsize=(18, 8.8), dpi=120, sharex=True, sharey=True)
    for r, h in enumerate(HEIGHTS):
        for c, (key, label, _, _) in enumerate(VARIANTS):
            ax = axes[r, c]
            res = results[(key, h)]
            sx, sy, gr = res["arena_gr"]
            im = ax.contourf(sx, sy, gr, levels=gr_levels, cmap=cmap, norm=norm, extend="max")
            cs = ax.contour(sx, sy, gr, levels=[10, 15, 20], colors="k", linewidths=0.5)
            ax.clabel(cs, fmt="%g", fontsize=7)
            for lx in arena.LUM_X:
                ax.plot(lx, -0.5, marker="s", ms=7, color="k")
            ax.plot(*arena.SPECTATOR, marker="o", ms=6, mfc="w", mec="k")
            row = res["row"]
            ax.set_title(f"{key} · {h:g} m · GR max {gr.max():.0f}, Platz {res['arena_pv']['GR']:.1f}\n"
                         f"Feld (Reihe): Ē {row[0]:.0f} lx, U0 {row[2]:.2f} → "
                         f"{arena.classify(row[0], row[2])}", fontsize=9.5)
            ax.set_aspect("equal")
            ax.set_ylim(-12.2, 0.2)
            if r == 1:
                ax.set_xlabel("x [m]")
            if c == 0:
                ax.set_ylabel("y [m] hinter der Reihe")
    cb = fig.colorbar(im, ax=axes, ticks=gr_levels, fraction=0.02, pad=0.01)
    cb.set_label("Glare Rating GR (CIE 112)")
    fig.suptitle("Arena: Blendung der Zuschauer und Feldbeleuchtung – 3 × SIRIUS 1000 im Abstand "
                 "von 6 m, Wartungsfaktor 0,8\nV2 = Blende heute · V2-50 = Lochung 50 % · "
                 "B2 / B3 = ohne externe Blende · GR-Skala: 10 unmerklich · 30 merklich · 50 störend",
                 fontsize=12)
    fig.savefig(os.path.join(DATA_DIR, "vergleich_arena.png"), bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
