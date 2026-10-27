"""
V2s mit seitlichen Flügeln (V2f): kleine Flügel an den Seitenkanten des Stirnblechs, schräg nach
vorn-außen gebogen (nicht 90° wie die Wangen der V2). Sie sollen das Licht schräg nach hinten
(C110-C160 / C200-C250) abschirmen, das die V2-Wangen abgehalten haben, ohne viel Licht zu kosten.

    python visor_v2f.py [ordner]

Flügel (je Seite, im Leuchtensystem a nach vorn, b quer, h nach unten):
  - Biegekante = senkrechte Seitenkante des Stirnblechs (a = -0.396 m, b = +-0.164 m)
  - Biegewinkel beta gegen die Ebene des Stirnblechs: 90° = Wange nach vorn (wie V2), kleinere
    Winkel = Flügel spreizt nach außen; Richtung (sin beta, +-cos beta) in der a-b-Ebene
  - Länge L entlang des Flügels, Tiefe D an der Biegekante, vorn r * D (r = 1 Rechteck,
    r = 0 Dreieck), Oberkante 14 mm unter dem Glas (unter dem Gehäuserahmen)
  - Lochung wie das Stirnblech (Ø 2,5 mm, Teilung 12 mm), Innenseite matt angenommen
  - Eckwinkel 60 x 80 mm und Lochung des Stirnblechs wie V2s; die Flügel ersetzen die seitlichen
    Kantungen nach hinten (die Unterkante bleibt nach hinten gekantet)

Bewertet: Lichtstrom gegenüber V2s, Licht schräg nach hinten (Zone C110-C160 und C200-C250,
gamma 40-85°), GR der Person, größtes GR der Zuschauer, Rückwand, Arena-Reihe.
Gewählt: kleinstes Licht schräg nach hinten bei höchstens 1,5 % weniger Lichtstrom als V2s;
bei fast gleichem Ergebnis (2 %) der kleinere Flügel.

Ausgabe: sirius1000_v2f.ies, SIRIUS1000_Blende_V2f_berechnet.ldt, visor_v2f.npy, visor_v2f.txt,
visor_v2f_studie.csv, visor_v2f.png
"""

import math
import os
import sys

import numpy as np

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DATA_DIR)
from perforation import D_OLD, free_lvk, lumen, lvk_directions  # noqa: E402
from visor_design import SOURCE_IES, write_ies, write_ldt  # noqa: E402
from visor_v2s import V2Sides, assess, hole_tr  # noqa: E402

EDGE_A, EDGE_B = -0.396, 0.164
WING_TOP = 0.014
V2S_CHEEK = (0.06, 0.0, 0.08, 0.034)
LOSS_MAX = 0.015


class V2Wings(V2Sides):
    def __init__(self, beta_deg, length, depth, ratio, perforated=True):
        super().__init__(*V2S_CHEEK)
        self.beta = math.radians(beta_deg)
        self.L, self.D, self.r = length, depth, ratio
        self.w_d = D_OLD if perforated else 0.0

    def wing_depth(self, l):
        return self.D * (1 - (1 - self.r) * np.clip(l / self.L, 0, 1))

    def _shade(self, pa, pb, da, db, dh):
        t = super()._shade(pa, pb, da, db, dh)
        if self.L <= 0:
            return t
        sb, cb = math.sin(self.beta), math.cos(self.beta)
        for s in (-1.0, 1.0):
            u = np.array([sb, s * cb])            # Richtung des Flügels (a, b)
            n = np.array([-s * cb, sb])           # Normale in der a-b-Ebene
            den = da * n[0] + db * n[1]
            if abs(den) < 1e-9:
                continue
            tt = ((EDGE_A - pa) * n[0] + (s * EDGE_B - pb) * n[1]) / den
            qa, qb, hh = pa + tt * da, pb + tt * db, tt * dh
            ell = (qa - EDGE_A) * u[0] + (qb - s * EDGE_B) * u[1]
            dep = self.wing_depth(ell)
            hit = (tt > 0) & (ell >= 0) & (ell <= self.L) & (hh >= WING_TOP) & (hh <= dep)
            field = (ell >= 0.012) & (ell <= self.L - 0.012) & (hh >= 0.035) & (hh <= dep - 0.006)
            tau = hole_tr(self.w_d, 12.0, abs(den)) if self.w_d > 0 else 0.0
            t = t * np.where(hit, np.where(field, tau, 0.0), 1.0)
        return t


def zone_lumen(c, g, table):
    cc, gg = np.meshgrid(np.asarray(c), np.asarray(g), indexing="ij")
    mask = ((((cc >= 110) & (cc <= 160)) | ((cc >= 200) & (cc <= 250))) & (gg >= 40) & (gg <= 85))
    return lumen(c, g, np.where(mask, table, 0.0))


def quick(v, base):
    c, g, table, t_old, i_free = base
    flat = lvk_directions(c, g).reshape(-1, 3)
    t_new = v.transmission(flat).reshape(table.shape)
    i_new = np.maximum(table + i_free * (t_new - t_old), 0.0)
    return i_new, lumen(c, g, i_new), zone_lumen(c, g, i_new)


def main():
    c, g, table, t_old, i_free, _ = free_lvk(os.path.join(DATA_DIR, SOURCE_IES))
    base = (c, g, table, t_old, i_free)
    flux_free = lumen(c, g, i_free)
    refs = {}
    for key, v in (("V2", V2Sides(0.211, 0.0885, 0.237, 0.034)), ("V2s", V2Sides(*V2S_CHEEK))):
        r = assess(v, base)
        r["zone"] = zone_lumen(c, g, r["i"])
        refs[key] = r
    lines = [f"{k}: Lichtstrom {r['flux']:.0f} lm (Wirkungsgrad {r['flux'] / flux_free * 100:.1f} %), schräg "
             f"hinten {r['zone']:.0f} lm, GR {r['gr5']:.1f} / {r['gr8']:.1f}, Zuschauer {r['gr_sp']:.1f}, "
             f"Reihe {r['em']:.0f} lx U0 {r['u0']:.3f}" for k, r in refs.items()]
    print("\n".join(lines), flush=True)
    v2s = refs["V2s"]

    rows = []
    for beta in (20, 35, 50, 65, 90):
        for length in (0.04, 0.07, 0.10, 0.14):
            for depth in (0.10, 0.15, 0.211):
                for ratio in (1.0, 0.5, 0.0):
                    v = V2Wings(beta, length, depth, ratio)
                    i_new, flux, zone = quick(v, base)
                    area = length * depth * (1 + ratio) / 2
                    rows.append(dict(beta=beta, L=length, D=depth, r=ratio, i=i_new, flux=flux,
                                     zone=zone, area=area, loss=1 - flux / v2s["flux"]))
    ok = [r for r in rows if r["loss"] <= LOSS_MAX]
    best_zone = min(r["zone"] for r in ok)
    near = [r for r in ok if r["zone"] <= best_zone * 1.02]
    best = min(near, key=lambda r: (r["area"], r["loss"]))
    lines += ["", "beta  L [mm]  D [mm]  vorn | Lichtstrom ggü. V2s | schräg hinten"]
    for r in sorted(rows, key=lambda r: (r["beta"], r["L"], r["D"], -r["r"])):
        lines.append(f"{r['beta']:3d}°  {r['L'] * 1000:5.0f}  {r['D'] * 1000:5.0f}  {r['r']:.1f} | "
                     f"{-r['loss'] * 100:+6.2f} % | {r['zone']:6.0f} lm"
                     f"{'  <- zulässig' if r['loss'] <= LOSS_MAX else ''}")
    # Detailbewertung der gewählten Variante und einiger Nachbarn
    v = V2Wings(best["beta"], best["L"], best["D"], best["r"])
    fin = assess(v, base)
    fin["zone"] = zone_lumen(c, g, fin["i"])
    summary = (f"Gewählt: Flügel {best['beta']}° gebogen, {best['L'] * 1000:.0f} mm lang, "
               f"{best['D'] * 1000:.0f} mm tief, vorn {best['r'] * best['D'] * 1000:.0f} mm | Lichtstrom "
               f"{fin['flux']:.0f} lm ({(fin['flux'] / v2s['flux'] - 1) * 100:+.1f} % ggü. V2s, "
               f"{(fin['flux'] / refs['V2']['flux'] - 1) * 100:+.1f} % ggü. V2), schräg hinten "
               f"{fin['zone']:.0f} lm (V2s {v2s['zone']:.0f}, V2 {refs['V2']['zone']:.0f}), GR "
               f"{fin['gr5']:.1f} / {fin['gr8']:.1f}, Zuschauer {fin['gr_sp']:.1f}, Reihe {fin['em']:.0f} lx "
               f"U0 {fin['u0']:.3f} {fin['cls']}")
    print(summary)
    lines += ["", summary]
    open(os.path.join(DATA_DIR, "visor_v2f.txt"), "w").write("\n".join(lines) + "\n")
    with open(os.path.join(DATA_DIR, "visor_v2f_studie.csv"), "w") as f:
        f.write("beta;laenge_mm;tiefe_mm;vorn_anteil;lichtstrom;verlust_ggue_v2s;schraeg_hinten\n")
        for r in rows:
            f.write(f"{r['beta']};{r['L'] * 1000:.0f};{r['D'] * 1000:.0f};{r['r']:.1f};{r['flux']:.0f};"
                    f"{r['loss']:.4f};{r['zone']:.0f}\n")
    name = "SIRIUS_1000_Blende_V2f"
    note = (f"Berechnet: V2s mit Flügeln {best['beta']} Grad, {best['L'] * 1000:.0f} x "
            f"{best['D'] * 1000:.0f} mm, Lochung 3,4 %")
    write_ies(os.path.join(DATA_DIR, "sirius1000_v2f.ies"), os.path.join(DATA_DIR, SOURCE_IES),
              c, g, fin["i"], fin["flux"], name, note)
    write_ldt(os.path.join(DATA_DIR, "SIRIUS1000_Blende_V2f_berechnet.ldt"), c, g, fin["i"],
              fin["flux"], name, note)
    np.save(os.path.join(DATA_DIR, "visor_v2f.npy"),
            np.array([best["beta"], best["L"], best["D"], best["r"], fin["flux"]]))
    plot(c, g, refs, fin, best, rows)


def plot(c, g, refs, fin, best, rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(17, 5.2), dpi=130)
    ax = axes[0]
    cols = {20: "#a35a00", 35: "#2f9a46", 50: "#0b5cad", 65: "#7a4fb0", 90: "#17202b"}
    for beta, col in cols.items():
        rs = [r for r in rows if r["beta"] == beta]
        ax.scatter([-r["loss"] * 100 for r in rs], [r["zone"] for r in rs], s=14, color=col,
                   label=f"{beta}°", alpha=0.8)
    v2, v2s = refs["V2"], refs["V2s"]
    ax.scatter([(v2["flux"] / v2s["flux"] - 1) * 100], [v2["zone"]], marker="s", s=60, color="k",
               label="V2 heute")
    ax.scatter([0], [v2s["zone"]], marker="D", s=50, color="#5b6673", label="V2s")
    ax.scatter([-best["loss"] * 100], [best["zone"]], marker="*", s=220, color="#e0a800",
               edgecolor="k", zorder=5, label="gewählt")
    ax.axvline(-LOSS_MAX * 100, color="0.5", ls="--", lw=1)
    ax.set_xlabel("Lichtstrom gegenüber V2s [%]")
    ax.set_ylabel("Licht schräg nach hinten [lm]")
    ax.set_title("Flügelvarianten (Farbe = Biegewinkel)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, ncol=2)

    ax = axes[1]
    cc = np.asarray(c)
    for cv, ls in ((135, "-"), (150, "--")):
        ci = int(np.argmin(np.abs(cc - cv)))
        ax.plot(g, v2["i"][ci], color="#17202b", ls=ls, lw=1.6, label=f"V2 C{cv}")
        ax.plot(g, v2s["i"][ci], color="#5b6673", ls=ls, lw=1.6, label=f"V2s C{cv}")
        ax.plot(g, fin["i"][ci], color="#e0a800", ls=ls, lw=2.2, label=f"V2f C{cv}")
    ax.set_xlim(0, 100)
    ax.set_xlabel("γ [°]")
    ax.set_ylabel("Lichtstärke [cd]")
    ax.set_title("Schräg nach hinten (C135, C150)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7)

    ax = axes[2]   # Draufsicht von unten auf die Blendenecke
    beta = math.radians(best["beta"])
    ax.add_patch(plt.Rectangle((-383, -152), 766, 304, fc="#e3eef9", ec="#0b5cad"))
    ax.plot([-396, -396], [-164, 164], color="#17202b", lw=3)
    for s in (-1, 1):
        ax.plot([-396, -396 + 80], [s * 167, s * 167], color="#5b6673", lw=1.5, ls=":")
        ax.plot([-396, -396 + best["L"] * 1000 * math.sin(beta)],
                [s * 164, s * (164 + best["L"] * 1000 * math.cos(beta))], color="#e0a800", lw=3)
        ax.plot([-396, -396 + 237], [s * 167, s * 167], color="#17202b", lw=1, ls="--", alpha=0.5)
    ax.text(-380, 0, "Stirnblech", rotation=90, va="center", fontsize=8)
    ax.text(-250, 0, "Glas", color="#0b5cad", fontsize=9, va="center")
    ax.text(-160, 175, "gestrichelt: Wange V2", fontsize=7, color="#17202b")
    ax.set_xlim(-430, -100)
    ax.set_ylim(-260, 260)
    ax.set_aspect("equal")
    ax.set_xlabel("a [mm] (vorn →)")
    ax.set_ylabel("b [mm]")
    ax.set_title(f"Draufsicht: Flügel {best['beta']}°, {best['L'] * 1000:.0f} mm lang, "
                 f"{best['D'] * 1000:.0f} mm tief", fontsize=10)
    ax.grid(alpha=0.2)
    fig.suptitle(f"V2s mit Flügeln (V2f) – Lichtstrom {(fin['flux'] / v2s['flux'] - 1) * 100:+.1f} % ggü. "
                 f"V2s, schräg nach hinten {fin['zone'] / v2s['zone'] * 100 - 100:+.0f} % · berechnet",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(DATA_DIR, "visor_v2f.png"), bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
