"""
Kompakte außenliegende Blende (B3k): gleiche Wirkung nach hinten wie B3a (450 mm Stirnblech),
aber deutlich flacher.

    python visor_mini.py [ordner]

Ein einzelnes Stirnblech muss so tief sein, dass es Strahlen ab dem Grenzwinkel gamma_c von der
ganzen Glaslänge L abfängt: D = L / tan(gamma_c), bei 766 mm Glas und 60° also ~440 mm. Kürzer
geht es nur, wenn die Lichtaustrittsfläche unterteilt wird: N Lamellen quer zur Ausstrahlrichtung
(parallel zu C90) teilen das Glas in N + 1 Felder, jede Lamelle braucht nur noch D / (N + 1).
Die Lamellen sind nach vorn geneigt (Unterkante Richtung C0), damit der Hauptstrahl der Optik
(C0, gamma ~35°) zwischen ihnen hindurchgeht.

Modell im Leuchtensystem wie visor_design.py (a nach vorn/C0, b quer, h nach unten, Glas h = 0):
  - Stirnblech senkrecht an der hinteren Glaskante a = -0.396 m, Tiefe d
  - N Lamellen von 15 mm unter dem Glas (unter dem Gehäuserahmen) bis zur Tiefe d, Neigung beta
    (Unterkante nach vorn), Oberkanten gleichmäßig über das Glas verteilt, quer über die ganze Breite
  - Seitliche Form: Wangen b = +-0.167 m, Tiefe hinten d, vorn d * Verhältnis, Länge wählbar
    (nur hinterer Bereich wie V2, oder über alle Lamellen)
  - Lochung p in Stirnblech und Wangen, Lamellen geschlossen (Lochung in der Lamelle ließe nach
    hinten Licht durch, genau wo sie wirken soll)
  - Innenseiten matt schwarz, Blechdicke der Lamellen 1,5 mm (verdeckter Glasanteil)

Bewertet wird jede Variante wie B3a: Lichtstrom, GR der Person 8 m hinter der Leuchte bei 5 m und
8 m, Arena-Reihe bei 8 m (EN 12193), Abweichung zur Blende 3. Gewählt wird die flachste Blende,
die die GR-Werte von B3a höchstens um 1,5 (5 m) bzw. 1 (8 m) übertrifft und höchstens 5 %
Lichtstrom kostet. Klasse I (U0 >= 0,70) erreicht keine Lamellen-Variante: Lamellen schatten
etwas Licht nach unten ab, und am vorderen Feldrand direkt unter der Reihe liegt schon V2 nur bei
U0 0,699. Als Grenze gilt deshalb U0 >= 0,66 (Blende 3: 0,69, Blende 2: 0,64).

Ausgabe: sirius1000_visor_b3k.ies, SIRIUS1000_Blende_B3k_kompakt_berechnet.ldt, visor_mini.npy,
visor_mini.txt, visor_mini.png, visor_mini_studie.csv
"""

import math
import os
import sys

import numpy as np

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DATA_DIR)
import arena  # noqa: E402
from blendung import LVK, PERSON_DISTANCE, evaluate, floor_eh_mean  # noqa: E402
from ldt2ies import read_ies  # noqa: E402
from perforation import (GLASS_A, GLASS_B, SHEET, d_for_open_area, free_lvk,  # noqa: E402
                         hole_transmission, lumen)
from visor_design import (A_BACK, CHEEK_B, MARGIN, PLATE_HALF_W, SOLID_TOP,  # noqa: E402
                          SOURCE_IES, TARGET_IES, design_lvk, target_error, write_ies, write_ldt)

BLADE_TOP = 0.015                    # Lamelle beginnt unter dem Gehäuserahmen (13 mm unter Glas)
B3A = dict(gr5=5.4, gr8=15.1)        # Referenz: B3a (450 mm), vergleich_blenden.txt
FLUX_V2 = 111141.0


class CompactVisor:
    def __init__(self, depth, n_blades, beta_deg, open_area=0.10, cheek="kurz", cheek_ratio=0.42):
        self.d = depth
        self.n = n_blades
        self.beta = math.radians(beta_deg)
        self.p = open_area
        self.d_hole = d_for_open_area(open_area) if open_area > 0 else None
        self.cheek = cheek
        self.cheek_ratio = cheek_ratio
        span = GLASS_A - A_BACK
        # Oberkanten der Lamellen gleichmäßig zwischen Stirnblech und vorderer Glaskante
        self.blades = [A_BACK + span * (k + 1) / (n_blades + 1) for k in range(n_blades)]
        if cheek == "kurz":
            self.cheek_len = 0.237
        elif cheek == "lang":
            self.cheek_len = (self.blades[-1] - A_BACK + depth * math.tan(self.beta)
                              if n_blades else 0.237)
        else:
            self.cheek_len = 0.0

    @property
    def D(self):  # für blendung.evaluate und Beschriftungen
        return self.d

    def tau(self, cos_inc):
        return 0.0 if self.d_hole is None else hole_transmission(self.d_hole, cos_inc)

    def transmission(self, dirs, n_pts=24):
        ga = np.linspace(-GLASS_A, GLASS_A, n_pts)
        gb = np.linspace(-GLASS_B, GLASS_B, max(6, n_pts // 2))
        pa, pb = np.meshgrid(ga, gb)
        pa, pb = pa.ravel(), pb.ravel()
        tb = math.tan(self.beta)
        cb = math.cos(self.beta)
        out = np.ones(len(dirs))
        for k, (da, db, dh) in enumerate(dirs):
            if dh <= 1e-6:
                continue
            t = np.ones_like(pa)
            # Stirnblech (senkrecht, gelocht)
            if da < -1e-9:
                s = (A_BACK - pa) / da
                hb, hh = pb + s * db, s * dh
                hit = (np.abs(hb) <= PLATE_HALF_W) & (hh <= self.d)
                field = ((hh >= SOLID_TOP) & (hh <= self.d - MARGIN) &
                         (np.abs(hb) <= PLATE_HALF_W - MARGIN))
                t = t * np.where(hit, np.where(field, self.tau(abs(da)), 0.0), 1.0)
            # Lamellen: Ebene a - h * tan(beta) = a0 (Unterkante nach vorn), geschlossen,
            # (Blechdicke als verdeckter Glasanteil am Ende)
            den = da - dh * tb
            for a0 in self.blades:
                if abs(den) > 1e-9:
                    s = (a0 - pa) / den
                    hh, hb = s * dh, pb + s * db
                    hit = (s > 0) & (hh >= BLADE_TOP) & (hh <= self.d) & (np.abs(hb) <= PLATE_HALF_W)
                    t = t * np.where(hit, 0.0, 1.0)
            # Wangen
            if self.cheek_len > 0 and abs(db) > 1e-9:
                for b0 in (-CHEEK_B, CHEEK_B):
                    s = (b0 - pb) / db
                    ha, hh = pa + s * da, s * dh
                    rel = np.clip((ha - A_BACK) / self.cheek_len, 0, 1)
                    depth = self.d * (1 - rel * (1 - self.cheek_ratio))
                    hit = ((s > 0) & (ha >= A_BACK) & (ha <= A_BACK + self.cheek_len) &
                           (hh >= 0) & (hh <= depth))
                    field = (hh >= SOLID_TOP) & (hh <= depth - MARGIN)
                    t = t * np.where(hit, np.where(field, self.tau(abs(db)), 0.0), 1.0)
            # Blechdicke der Lamellen: Anteil der Glaslänge unter den Stirnkanten
            out[k] = t.mean() * (1 - self.n * SHEET * 1e-3 / cb / (2 * GLASS_A))
        return out


def lvk_obj(c, g, table):
    lvk = LVK.__new__(LVK)
    lvk.c, lvk.g, lvk.t = np.array(c), np.array(g), np.array(table)
    lvk.flux, lvk.name = lumen(c, g, table), "variante"
    return lvk


def assess(v, base, target):
    c, g = base[0], base[1]
    i_new, _ = design_lvk(v, base)
    lvk = lvk_obj(c, g, i_new)
    gr = [evaluate(lvk, h, PERSON_DISTANCE, eh_mean=floor_eh_mean(lvk, h)[0], d_hole=v)["GR"]
          for h in (5.0, 8.0)]
    em, _, u0 = arena.continuous_row(lvk, 8.0)
    err, _ = target_error(i_new, target, c, g)
    return dict(i=i_new, flux=lvk.flux, loss=1 - lvk.flux / FLUX_V2, gr5=gr[0], gr8=gr[1], em=em,
                u0=u0, cls=arena.classify(em, u0), err=err)


U0_MIN = 0.66


def ok(r):
    return (r["gr5"] <= B3A["gr5"] + 1.5 and r["gr8"] <= B3A["gr8"] + 1 and r["u0"] >= U0_MIN
            and r["loss"] <= 0.05)


def main():
    c, g, table, t_old, i_free, _ = free_lvk(os.path.join(DATA_DIR, SOURCE_IES))
    base = (c, g, table, t_old, i_free)
    target = np.array(read_ies(os.path.join(DATA_DIR, TARGET_IES))[2])

    rows, lines = [], []
    head = "N  Tiefe  Neig.  Wangen  Loch | Lm-Verl.  GR 5 m  GR 8 m | Reihe 8 m: E   U0     | Fehler"
    print(head)
    lines.append(head)
    coarse = [(n, round(d, 3), beta, cheek) for n in (0, 1, 2, 3)
              for d in np.arange(0.10, 0.301, 0.025)
              for beta in ((0,) if n == 0 else (0, 15, 25, 35, 45))
              for cheek in ("kurz", "lang", "keine") if not (n == 0 and cheek == "lang")]
    fine = [(n, round(d, 4), beta, cheek) for n in (1, 2)
            for d in np.arange(0.125, 0.2251, 0.0125) for beta in (30, 35, 40, 45)
            for cheek in ("kurz", "keine")]
    for n, depth, beta, cheek in coarse + [f for f in fine if f not in coarse]:
        v = CompactVisor(depth, n, beta, 0.10, cheek)
        r = assess(v, base, target)
        r.update(n=n, d=depth, beta=beta, cheek=cheek)
        rows.append(r)
        line = (f"{n}  {depth * 1000:4.0f}  {beta:+3d}°  {cheek:6s}  10 % | "
                f"{r['loss'] * 100:5.1f} %  {r['gr5']:6.1f}  {r['gr8']:6.1f} | "
                f"{r['em']:6.0f}  {r['u0']:.3f} {r['cls'][-3:]:>3s} | {r['err']:.3f}"
                f"{'  <- erfüllt' if ok(r) else ''}")
        lines.append(line)
        print(line, flush=True)

    good = [r for r in rows if ok(r)]
    if not good:
        sys.exit("keine Variante erfüllt die Kriterien")
    # flachste, dann wenigste Lamellen, dann geringster Lichtstromverlust
    best = min(good, key=lambda r: (r["d"], r["n"], r["loss"]))
    v = CompactVisor(best["d"], best["n"], best["beta"], 0.10, best["cheek"])
    summary = (f"Gewählt: {best['n']} Lamelle(n), Tiefe {best['d'] * 1000:.1f} mm, Neigung "
               f"{best['beta']:+d}°, Wangen {best['cheek']} ({v.cheek_len * 1000:.0f} mm), "
               f"Lochung Stirnblech/Wangen 10 % | Lichtstrom {best['flux']:.0f} lm "
               f"({-best['loss'] * 100:+.1f} %), GR {best['gr5']:.1f} / {best['gr8']:.1f}, Reihe "
               f"{best['em']:.0f} lx U0 {best['u0']:.3f} {best['cls']}")
    print(summary)
    lines += ["", summary]
    open(os.path.join(DATA_DIR, "visor_mini.txt"), "w").write("\n".join(lines) + "\n")
    with open(os.path.join(DATA_DIR, "visor_mini_studie.csv"), "w") as f:
        f.write("lamellen;tiefe_mm;neigung_grad;wangen;lichtstromverlust;gr5;gr8;reihe_e;reihe_u0;"
                "klasse;fehler_b3\n")
        for r in rows:
            f.write(f"{r['n']};{r['d'] * 1000:.0f};{r['beta']};{r['cheek']};{r['loss']:.4f};"
                    f"{r['gr5']:.2f};{r['gr8']:.2f};{r['em']:.0f};{r['u0']:.4f};{r['cls']};"
                    f"{r['err']:.4f}\n")

    name = "SIRIUS_1000_Blende_B3k_kompakt"
    note = (f"Berechnet: {best['n']} Lamellen {best['d'] * 1000:.0f} mm, Neigung {best['beta']:+d} "
            f"Grad, Stirnblech {best['d'] * 1000:.0f} mm 10 % gelocht, innen matt schwarz")
    write_ies(os.path.join(DATA_DIR, "sirius1000_visor_b3k.ies"),
              os.path.join(DATA_DIR, SOURCE_IES), c, g, best["i"], best["flux"], name, note)
    write_ldt(os.path.join(DATA_DIR, "SIRIUS1000_Blende_B3k_kompakt_berechnet.ldt"), c, g,
              best["i"], best["flux"], name, note)
    cheek_code = {"kurz": 0, "lang": 1, "keine": 2}[best["cheek"]]
    np.save(os.path.join(DATA_DIR, "visor_mini.npy"),
            np.array([best["d"], best["n"], best["beta"], 0.10, cheek_code, best["flux"]]))
    plot(rows, best, c, g, table, target)


def plot(rows, best, c, g, table, target):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(17, 5.2), dpi=130)
    ax = axes[0]
    colors = {0: "#17202b", 1: "#0b5cad", 2: "#2f9a46", 3: "#a35a00"}
    for n in (0, 1, 2, 3):
        pts = {}
        for r in rows:
            if r["n"] == n and r["u0"] >= U0_MIN and r["loss"] <= 0.05:
                pts[r["d"]] = min(pts.get(r["d"], 99), r["gr5"])
        if pts:
            ds = sorted(pts)
            ax.plot([d * 1000 for d in ds], [pts[d] for d in ds], "o-", color=colors[n],
                    label=f"{n} Lamelle{'n' if n != 1 else ''}" if n else "nur Stirnblech")
    ax.axhline(B3A["gr5"] + 1.5, color="0.5", ls="--", lw=1)
    ax.text(105, B3A["gr5"] + 1.8, "Ziel: B3a + 1,5", fontsize=8, color="0.4")
    ax.set_xlabel("Bautiefe unter dem Glas [mm]")
    ax.set_ylabel("bestes GR der Person, 5 m Montagehöhe")
    ax.set_title("Bautiefe gegen Blendung (U0 ≥ 0,66, ≤ 5 % Lichtverlust)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)

    ci = int(np.argmin(np.abs(c - 180)))
    ax = axes[1]
    b3a = np.array(read_ies(os.path.join(DATA_DIR, "sirius1000_visor_b3.ies"))[2])
    for arr, lab, col, ls in ((table, "V2 heute", "#17202b", "-"), (target, "Blende 3", "#2f9a46", "-"),
                              (b3a, "B3a (450 mm)", "#7a4fb0", "-"),
                              (best["i"], "B3k kompakt", "#0b5cad", "--")):
        ax.semilogy(g, np.maximum(arr[ci], 1), color=col, ls=ls, lw=2, label=lab)
    for gam, lab in ((49.6, "Person 8 m"), (64.6, "Person 5 m")):
        ax.axvline(gam, color="0.6", lw=0.8, ls=":")
        ax.text(gam + 0.8, 2, lab, rotation=90, fontsize=8, color="0.4")
    ax.set_xlim(0, 100)
    ax.set_ylim(1, 2e5)
    ax.set_xlabel("γ [°]")
    ax.set_title("C180 – nach hinten")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=8, loc="upper right")

    # Seitenansicht
    ax = axes[2]
    v = CompactVisor(best["d"], best["n"], best["beta"], 0.10, best["cheek"])
    d, tb = v.d * 1000, math.tan(v.beta)
    ax.add_patch(plt.Rectangle((-396, -126), 792, 126, fc="#d5dbe1", ec="#5b6673"))
    ax.plot([-383, 383], [0, 0], color="#0b5cad", lw=4)
    ax.plot([-396, -396], [0, d], color="#17202b", lw=3)
    for a0 in v.blades:
        ax.plot([a0 * 1000, a0 * 1000 + d * tb], [0, d], color="#17202b", lw=2.5)
    if v.cheek_len:
        cl = v.cheek_len * 1000
        ax.plot([-396, -396 + cl, -396 + cl], [d, d * v.cheek_ratio, 0], color="#5b6673", lw=1.5,
                ls="--")
    # B3a zum Vergleich
    ax.plot([-410, -410], [0, 450], color="#7a4fb0", lw=1.5, ls=":")
    ax.text(-420, 450, "B3a\n450 mm", fontsize=8, color="#7a4fb0", ha="right", va="bottom")
    ax.annotate("", xy=(-450, 0), xytext=(-450, d), arrowprops=dict(arrowstyle="<->"))
    ax.text(-460, d / 2, f"{d:.1f} mm", ha="right", va="center", fontsize=10, weight="bold")
    ax.text(0, -63, "Leuchtengehäuse", ha="center", va="center", fontsize=9)
    ax.set_xlim(-650, 450)
    ax.set_ylim(500, -180)
    ax.set_aspect("equal")
    ax.set_xlabel("mm (← hinten, C180 | vorn, C0 →)")
    ax.set_title(f"B3k: {v.n} Lamelle{'n' if v.n != 1 else ''}, Neigung {best['beta']}° nach vorn")
    ax.grid(alpha=0.2)
    fig.suptitle("Kompakte außenliegende Blende B3k – berechnet, nicht gemessen", fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(DATA_DIR, "visor_mini.png"), bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
