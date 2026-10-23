"""
Arena: Leuchtenreihe (3 x SIRIUS 1000, Abstand 6 m) strahlt in die Halle, Zuschauer sitzen
dahinter und schauen in die Halle.

    python arena.py [ordner]

1. Beleuchtungsstärke auf dem Feld vor der Leuchtenreihe (horizontal, Direktlicht aus der LVK,
   mit Wartungsfaktor) gegen EN 12193 (Hallensport, z. B. Handball/Basketball/Volleyball).
2. Blendung der Zuschauer: Glare Rating GR (CIE 112) auf einem Raster von Zuschauerplätzen
   hinter der Leuchtenreihe, Blick in die Halle, für beide Blenden und beide Montagehöhen.
"""

import math
import os
import sys

import numpy as np

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DATA_DIR)
from blendung import LVK  # noqa: E402

LUM_X = [-6.0, 0.0, 6.0]          # Leuchtenreihe, Abstand 6 m
MOUNT_HEIGHTS = [5.0, 8.0]
VARIANTS = [("heute", "Blende heute (Lochung 3,4 %)", "sirius1000.ies"),
            ("perf50", "Lochung 50 %", "sirius1000_perf50.ies")]
MF = 0.8                           # Wartungsfaktor (LED-Flutlicht, Halle)
FIELD_X, FIELD_Y = (-9.0, 9.0), (0.0, 8.0)   # Feld vor der Reihe: 18 m x 8 m
MAP_Y = (0.0, 20.0)                # Darstellung bis 20 m in die Halle
SPECT_X, SPECT_Y = (-9.0, 9.0), (-12.0, -1.0)  # Zuschauerbereich hinter der Reihe
EYE_HEIGHT = 1.2
VIEW_DOWN_DEG = 2.0
RHO = 0.2                          # Reflexionsgrad Hallenboden für L_ve
SPECTATOR = (0.0, -8.0)            # bisherige Person
# EN 12193, Hallensport (Handball, Basketball, Volleyball, Hallenfußball): E_h, U0
CLASSES = [("Klasse I (Wettkampf national/international)", 750, 0.7),
           ("Klasse II (Wettkampf regional)", 500, 0.7),
           ("Klasse III (Training, Schulsport)", 200, 0.5)]


def eh_grid(lvk, h, xs, ys):
    gx, gy = np.meshgrid(xs, ys)
    pts = np.stack([gx, gy, np.zeros_like(gx)], -1)
    e = np.zeros_like(gx)
    for lx in LUM_X:
        light = np.array([lx, 0.0, h])
        i, d, _, _ = lvk.toward(light, pts)
        e += i * (h / d) / d ** 2
    return e * MF


def gr_grid(lvk, h, xs, ys, eh_field_mean):
    view = np.array([0.0, math.cos(math.radians(VIEW_DOWN_DEG)),
                     -math.sin(math.radians(VIEW_DOWN_DEG))])
    gx, gy = np.meshgrid(xs, ys)
    eyes = np.stack([gx, gy, np.full_like(gx, EYE_HEIGHT)], -1)
    l_vl = np.zeros_like(gx)
    parts = []
    for lx in LUM_X:
        light = np.array([lx, 0.0, h])
        i, d, _, _ = lvk.toward(light, eyes)
        i = i * MF
        to_lum = (light - eyes) / d[..., None]
        theta = np.degrees(np.arccos(np.clip(to_lum @ view, -1, 1)))
        e_eye = i * np.cos(np.radians(theta)) / d ** 2
        contrib = 10.0 * e_eye / np.maximum(theta, 1.5) ** 2
        parts.append(contrib)
        l_vl += contrib
    l_ve = 0.035 * RHO * eh_field_mean / math.pi
    gr = 27 + 24 * np.log10(np.maximum(l_vl, 1e-9) / l_ve ** 0.9)
    # Negative Werte (Leuchte praktisch außerhalb des Blickfelds) als 0 = keine Blendung
    gr = np.maximum(gr, 0.0)
    return gr, l_vl, l_ve, parts


def point_values(lvk, h, x, y, eh_field_mean):
    gr, l_vl, l_ve, parts = gr_grid(lvk, h, np.array([x]), np.array([y]), eh_field_mean)
    eye = np.array([x, y, EYE_HEIGHT])
    ev = 0.0
    imax = 0.0
    for lx in LUM_X:
        light = np.array([lx, 0.0, h])
        i, d, _, _ = lvk.toward(light, eye)
        i = float(i) * MF
        imax = max(imax, i)
        to_lum = (light - eye) / d
        ev += i * math.sqrt(to_lum[0] ** 2 + to_lum[1] ** 2) / d ** 2
    return dict(GR=float(gr[0, 0]), L_vl=float(l_vl[0, 0]), L_ve=l_ve, E_v=ev, I_max=imax,
                parts=[float(p[0, 0]) for p in parts])


def continuous_row(lvk, h, depth=8.0, step=0.25):
    """Durchgehende Reihe (Leuchten alle 6 m): repräsentativer Abschnitt zwischen zwei Leuchten."""
    global LUM_X
    saved = LUM_X
    LUM_X = list(np.arange(-48.0, 48.1, 6.0))
    cx = np.arange(-3 + step / 2, 3, step)
    cy = np.arange(step / 2, depth, step)
    e = eh_grid(lvk, h, cx, cy)
    LUM_X = saved
    return float(e.mean()), float(e.min()), float(e.min() / e.mean())


def classify(em, u0):
    # Vergleich mit der Genauigkeit der Normwerte (U0 auf zwei Stellen gerundet)
    u0 = round(u0, 2)
    return next((c[0].split(" (")[0] for c in CLASSES if em >= c[1] and u0 >= c[2]), "keine Klasse")


def main():
    step = 0.25
    fx = np.arange(FIELD_X[0] + step / 2, FIELD_X[1], step)
    fy = np.arange(FIELD_Y[0] + step / 2, FIELD_Y[1], step)
    mx = np.arange(-12 + step / 2, 12, step)
    my = np.arange(MAP_Y[0] + step / 2, MAP_Y[1], step)
    sx = np.arange(SPECT_X[0], SPECT_X[1] + 1e-9, 0.25)
    sy = np.arange(SPECT_Y[0], SPECT_Y[1] + 1e-9, 0.25)

    res = {}
    lines = [f"Arena: {len(LUM_X)} x SIRIUS 1000 bei x = {LUM_X} m, Wartungsfaktor {MF}, "
             f"Feld {FIELD_X[1] - FIELD_X[0]:g} x {FIELD_Y[1] - FIELD_Y[0]:g} m vor der Reihe, "
             f"GR mit Boden-Reflexionsgrad {RHO:.0%}", ""]
    for key, label, ies in VARIANTS:
        lvk = LVK(os.path.join(DATA_DIR, ies))
        for h in MOUNT_HEIGHTS:
            ef = eh_grid(lvk, h, fx, fy)
            em, emin, emax = float(ef.mean()), float(ef.min()), float(ef.max())
            u0 = emin / em
            emap = eh_grid(lvk, h, mx, my)
            gr, l_vl, l_ve, _ = gr_grid(lvk, h, sx, sy, em)
            pv = point_values(lvk, h, *SPECTATOR, em)
            cls = next((c for c in CLASSES if em >= c[1] and round(u0, 2) >= c[2]), None)
            cls_eh = next((c for c in CLASSES if em >= c[1]), None)
            row = continuous_row(lvk, h)
            res[(key, h)] = dict(ef=ef, emap=emap, gr=gr, em=em, emin=emin, emax=emax, u0=u0,
                                 pv=pv, label=label, cls=cls, cls_eh=cls_eh, row=row)
            lines += [f"{label}, Montagehöhe {h:g} m:",
                      f"  Feld E_h: Mittel {em:.0f} lx, Min {emin:.0f} lx, Max {emax:.0f} lx, "
                      f"U0 {u0:.2f} -> " + (cls[0] if cls else
                                             f"keine Klasse (E_h reicht für "
                                             f"{cls_eh[0] if cls_eh else '-'}, U0 zu gering)"),
                      f"  durchgehende Reihe (alle 6 m), Streifen 8 m tief: Mittel {row[0]:.0f} lx, "
                      f"Min {row[1]:.0f} lx, U0 {row[2]:.2f} -> {classify(row[0], row[2])}",
                      f"  Zuschauer-GR: min {gr.min():.1f}, max {gr.max():.1f}, "
                      f"Mittel {gr.mean():.1f}; an x=0/y=-8: GR {pv['GR']:.1f}, "
                      f"E_v {pv['E_v']:.0f} lx, Anteile L_vl " +
                      ", ".join(f"{p:.2f}" for p in pv["parts"]), ""]
    for l in lines:
        print(l)
    with open(os.path.join(DATA_DIR, "arena.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    write_maps(res, fx, fy, mx, my, sx, sy)


def write_maps(res, fx, fy, mx, my, sx, sy):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap

    # ---------- Blendungskarten der Zuschauer
    # fein im relevanten Bereich, grob darüber bis "störend"
    gr_levels = [0, 4, 8, 10, 12, 14, 16, 18, 20, 25, 30, 40, 50, 60]
    gr_colors = ["#17305e", "#1d4f91", "#2f6fb7", "#4a90c9", "#5fb0c4", "#7ccaa5", "#a6dc8a",
                 "#d2e778", "#f4e36b", "#f6b84c", "#ef8a3a", "#d9542a", "#a8231f"]
    cmap = ListedColormap(gr_colors)
    norm = BoundaryNorm(gr_levels, cmap.N)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10.5), dpi=130, sharex=True, sharey=True)
    for r, h in enumerate([5.0, 8.0]):
        for c, (key, label, _) in enumerate(VARIANTS):
            ax = axes[r, c]
            d = res[(key, h)]
            im = ax.contourf(sx, sy, d["gr"], levels=gr_levels, cmap=cmap, norm=norm, extend="max")
            cs = ax.contour(sx, sy, d["gr"], levels=[10, 15, 20], colors="k", linewidths=0.6)
            ax.clabel(cs, fmt="%g", fontsize=8)
            for lx in [-6, 0, 6]:
                ax.plot(lx, -0.5, marker="s", ms=10, color="k")
                ax.text(lx, -0.85, "Leuchte", ha="center", va="top", fontsize=7)
            ax.plot(*SPECTATOR, marker="o", ms=8, mfc="w", mec="k")
            ax.text(SPECTATOR[0] + 0.3, SPECTATOR[1] + 0.3, f"GR {d['pv']['GR']:.1f}",
                    fontsize=9, weight="bold")
            ax.set_title(f"{label} · Montagehöhe {h:g} m\nGR Zuschauer: max {d['gr'].max():.0f}, "
                         f"Mittel {d['gr'].mean():.0f}", fontsize=11)
            ax.set_aspect("equal")
            ax.set_ylim(-12.2, 0.2)
            if r == 1:
                ax.set_xlabel("x [m] (quer, Leuchten bei −6 / 0 / +6 m)")
            if c == 0:
                ax.set_ylabel("y [m] hinter der Leuchtenreihe")
    cb = fig.colorbar(im, ax=axes, ticks=gr_levels, fraction=0.025, pad=0.02)
    cb.set_label("Glare Rating GR (CIE 112)")
    fig.suptitle("Blendung der Zuschauer hinter der Leuchtenreihe (3 × SIRIUS 1000, Abstand 6 m), "
                 "Blick in die Halle\nAugenhöhe 1,2 m, Blick 2° nach unten, Hallenboden ρ 20 %, "
                 f"Wartungsfaktor {MF}. GR-Skala: 10 unmerklich · 30 merklich · 50 störend · "
                 "70 unzumutbar", fontsize=12)
    fig.savefig(os.path.join(DATA_DIR, "arena_blendung.png"), bbox_inches="tight")
    plt.close(fig)

    # ---------- Beleuchtungsstärke in der Halle
    e_levels = [0, 50, 100, 200, 300, 500, 750, 1000, 1500, 2000, 3000, 5000]
    e_colors = ["#0e1a3a", "#1d3f7a", "#2c63b0", "#3f8fd0", "#5cbfcf", "#7fd39a", "#b8e36f",
                "#f1e05a", "#f6b047", "#ec7a35", "#c9392a"]
    cmap = ListedColormap(e_colors)
    norm = BoundaryNorm(e_levels, cmap.N)
    fig, axes = plt.subplots(1, 2, figsize=(14, 7.6), dpi=130, sharey=True)
    for c, h in enumerate([5.0, 8.0]):
        ax = axes[c]
        d = res[("heute", h)]
        im = ax.contourf(mx, my, d["emap"], levels=e_levels, cmap=cmap, norm=norm, extend="max")
        cs = ax.contour(mx, my, d["emap"], levels=[200, 500, 750], colors="k", linewidths=0.8)
        ax.clabel(cs, fmt="%g lx", fontsize=8)
        ax.add_patch(plt.Rectangle((FIELD_X[0], FIELD_Y[0]), FIELD_X[1] - FIELD_X[0],
                                   FIELD_Y[1] - FIELD_Y[0], fill=False, ec="w", lw=1.6, ls="--"))
        ax.text(FIELD_X[0] + 0.2, FIELD_Y[1] - 0.25, "Bewertungsfeld 18 × 8 m", color="w",
                fontsize=9, va="top")
        for lx in LUM_X:
            ax.plot(lx, 0, marker="s", ms=9, color="w", mec="k")
        p = res[("perf50", h)]
        cl = d["cls"][0].split(" (")[0] if d["cls"] else "keine Klasse"
        rw = d["row"]
        ax.set_title(f"Montagehöhe {h:g} m · 3 Leuchten: Ē {d['em']:.0f} lx, U0 {d['u0']:.2f} → {cl}\n"
                     f"durchgehende Reihe: Ē {rw[0]:.0f} lx, U0 {rw[2]:.2f} → "
                     f"{classify(rw[0], rw[2])}  (50 %: Ē {p['em']:.0f} lx)", fontsize=10)
        ax.set_aspect("equal")
        ax.set_xlabel("x [m]")
        if c == 0:
            ax.set_ylabel("y [m] in die Halle (Leuchtenreihe bei y = 0)")
    cb = fig.colorbar(im, ax=axes, ticks=e_levels, fraction=0.03, pad=0.02)
    cb.set_label("E_h [lx], Direktlicht, Wartungsfaktor 0,8")
    fig.suptitle("Horizontale Beleuchtungsstärke in der Halle – 3 × SIRIUS 1000, Abstand 6 m "
                 "(Blende heute)\nEN 12193 Hallensport: Klasse I 750 lx / U0 0,7 · Klasse II "
                 "500 lx / U0 0,7 · Klasse III 200 lx / U0 0,5", fontsize=12)
    fig.savefig(os.path.join(DATA_DIR, "arena_beleuchtung.png"), bbox_inches="tight")
    plt.close(fig)

    # ---------- Schnitt: GR entlang der Mittelachse und E_h entlang der Hallenachse
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2), dpi=130)
    colors = {5.0: "#1f6fd1", 8.0: "#d1491f"}
    styles = {"heute": "-", "perf50": "--"}
    ix = int(np.argmin(np.abs(sx - 0.0)))
    for (key, h), d in res.items():
        axes[0].plot(-sy, d["gr"][:, ix], color=colors[h], ls=styles[key], lw=2,
                     label=f"{h:g} m, {d['label']}")
    axes[0].axhline(50, color="k", ls=":", lw=0.8)
    axes[0].text(1.1, 50.6, "GR 50: störend / Grenzwert Wettkampf", fontsize=8)
    axes[0].set_xlabel("Abstand hinter der Leuchtenreihe [m] (Mittelachse, x = 0)")
    axes[0].set_ylabel("GR")
    axes[0].set_ylim(0, 60)
    axes[0].set_title("Blendung der Zuschauer entlang der Mittelachse")
    axes[0].grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    jx = int(np.argmin(np.abs(mx - 0.0)))
    for h in MOUNT_HEIGHTS:
        axes[1].plot(my, res[("heute", h)]["emap"][:, jx], color=colors[h], lw=2,
                     label=f"{h:g} m, Mittelachse")
        jx3 = int(np.argmin(np.abs(mx - 3.0)))
        axes[1].plot(my, res[("heute", h)]["emap"][:, jx3], color=colors[h], lw=1.2, ls=":",
                     label=f"{h:g} m, zwischen zwei Leuchten (x = 3 m)")
    for name, e, _ in CLASSES:
        axes[1].axhline(e, color="k", ls="--", lw=0.7)
        axes[1].text(19.8, e + 25, name.split(" (")[0] + f" {e} lx", fontsize=8, ha="right")
    axes[1].axvspan(*FIELD_Y, color="#e3eef9", zorder=0)
    axes[1].set_xlabel("y [m] in die Halle")
    axes[1].set_ylabel("E_h [lx]")
    axes[1].set_title("Beleuchtungsstärke entlang der Hallenachse (Blende heute)")
    axes[1].grid(alpha=0.3)
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(DATA_DIR, "arena_schnitte.png"), bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
