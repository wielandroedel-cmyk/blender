"""
Blende V2 seitlich überarbeitet (V2s): Stirnblech bleibt wie geliefert, die Seitenwangen werden
so geändert, dass zur Seite weniger Licht verloren geht.

    python visor_v2s.py [ordner]

Die Wangen der V2 (237 mm lang, 211 mm tief am Stirnblech, 89 mm vorn, Lochung 3,4 %) liegen
quer zur Ausstrahlung und schneiden Licht in C60-C120 bzw. C240-C300 ab. Sie tragen aber kaum zur
Blendung der Person hinter der Leuchte bei (die sieht die Leuchte in C180). Untersucht werden
Tiefe, Länge, Form (vorn spitz auslaufend) und Lochung der Wangen. Das Strahlenmodell ist das
der V2 (perforation.visor_transmission) mit veränderlichen Wangen; die unveränderte Variante
gibt die gemessene LVK exakt wieder.

Bewertung: Lichtstrom, Lichtstrom zur Seite (C45-C135 und C225-C315), GR der Person (5 m / 8 m),
größtes GR der Zuschauer (Arena, 8 m), Arena-Reihe bei 8 m. Zulässig ist eine Variante, wenn die
Person höchstens 0,5 und die Zuschauer höchstens 1,0 GR mehr sehen als mit V2. Ganz ohne Wangen
fehlt die Versteifung des Stirnblechs; gewählt wird deshalb unter den Varianten mit Wangen die mit
dem meisten Licht zur Seite (bei Gleichstand die kleinere Lochung).

Ausgabe: sirius1000_v2s.ies, SIRIUS1000_Blende_V2s_berechnet.ldt, visor_v2s.npy, visor_v2s.txt,
visor_v2s_studie.csv, visor_v2s.png
"""

import os
import sys

import numpy as np

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DATA_DIR)
import arena  # noqa: E402
from blendung import LVK, PERSON_DISTANCE, evaluate, floor_eh_mean  # noqa: E402
from perforation import (CHEEK_FIELD_A, CHEEK_FIELD_H, D_OLD, END_PLATE, GLASS_A,  # noqa: E402
                         GLASS_B, d_for_open_area, free_lvk, hole_transmission, lumen,
                         lvk_directions, open_area)
from visor_design import SOURCE_IES, write_ies, write_ldt  # noqa: E402

CHEEK_B = 0.167
A_START = -0.394                      # Wangen beginnen am Stirnblech
V2_CHEEK = dict(depth=0.211, front=0.0885, length=0.237, d_hole=D_OLD)


def hole_tr(d, pitch, cos_inc, sheet=1.5):
    """Wie perforation.hole_transmission, aber mit wählbarer Teilung [mm]."""
    cos_inc = np.clip(np.abs(cos_inc), 1e-6, 1.0)
    s = sheet * np.sqrt(1.0 - cos_inc ** 2) / cos_inc
    r = d / 2.0
    x = np.clip(s / (2 * r), 0.0, 1.0)
    overlap = 2 * r * r * np.arccos(x) - (s / 2) * np.sqrt(np.maximum(4 * r * r - s * s, 0))
    overlap = np.where(s >= 2 * r, 0.0, overlap)
    return overlap / pitch ** 2


class V2Sides:
    """V2 mit wählbaren Wangen; depth = 0 heißt ohne Wangen. plate_d/plate_pitch: Lochung des
    Stirnblechs (Standard wie V2: Ø 2,5 mm, Teilung 12 mm; plate_d = 0: geschlossen)."""

    def __init__(self, depth, front, length, open_ratio, plate_d=D_OLD, plate_pitch=12.0):
        self.depth, self.front, self.length = depth, front, length
        self.p = open_ratio
        self.d_hole = d_for_open_area(open_ratio) if open_ratio > 0 else None
        self.plate_d, self.plate_pitch = plate_d, plate_pitch

    def cheek_depth(self, a):
        rel = np.clip((a - A_START) / self.length, 0, 1) if self.length > 0 else 0
        return self.depth - (self.depth - self.front) * rel

    def transmission(self, dirs, n_pts=24):
        ga = np.linspace(-GLASS_A, GLASS_A, n_pts)
        gb = np.linspace(-GLASS_B, GLASS_B, max(6, n_pts // 2))
        pa, pb = np.meshgrid(ga, gb)
        pa, pb = pa.ravel(), pb.ravel()
        out = np.zeros(len(dirs))
        a_end = A_START + self.length
        for k, (da, db, dh) in enumerate(dirs):
            if dh <= 1e-6:
                out[k] = 1.0
                continue
            t = np.ones_like(pa)
            # Stirnblech wie V2
            if da < -1e-9:
                s = (END_PLATE["a"] - pa) / da
                hb, hh = pb + s * db, s * dh
                hit = ((s > 0) & (hb >= END_PLATE["b"][0]) & (hb <= END_PLATE["b"][1]) &
                       (hh >= END_PLATE["h"][0]) & (hh <= END_PLATE["h"][1]))
                field = ((hb >= END_PLATE["field_b"][0]) & (hb <= END_PLATE["field_b"][1]) &
                         (hh >= END_PLATE["field_h"][0]) & (hh <= END_PLATE["field_h"][1]))
                tau_p = hole_tr(self.plate_d, self.plate_pitch, da) if self.plate_d > 0 else 0.0
                t = t * np.where(hit, np.where(field, tau_p, 0.0), 1.0)
            # Wangen
            if self.depth > 0 and abs(db) > 1e-9:
                tau = 0.0 if self.d_hole is None else hole_transmission(self.d_hole, db)
                for b0 in (-CHEEK_B, CHEEK_B):
                    s = (b0 - pb) / db
                    ha, hh = pa + s * da, s * dh
                    dep = self.cheek_depth(ha)
                    hit = (s > 0) & (ha >= A_START) & (ha <= a_end) & (hh >= 0.0) & (hh <= dep)
                    field = ((ha >= CHEEK_FIELD_A[0]) & (ha <= a_end - 0.0225) &
                             (hh >= CHEEK_FIELD_H[0]) & (hh <= CHEEK_FIELD_H[1]) &
                             (hh <= dep - 0.006))
                    t = t * np.where(hit, np.where(field, tau, 0.0), 1.0)
            out[k] = t.mean()
        return out


def lvk_obj(c, g, table):
    lvk = LVK.__new__(LVK)
    lvk.c, lvk.g, lvk.t = np.array(c), np.array(g), np.array(table)
    lvk.flux, lvk.name = lumen(c, g, table), "variante"
    return lvk


def side_lumen(c, g, table):
    """Lichtstrom in C45-C135 und C225-C315 (Raumwinkel-Summe wie lumen())."""
    cc = np.asarray(c)
    mask = ((cc >= 45) & (cc <= 135)) | ((cc >= 225) & (cc <= 315))
    t = np.where(mask[:, None], table, 0.0)
    return lumen(c, g, t)


def assess(v, base):
    c, g, table, t_old, i_free = base
    flat = lvk_directions(c, g).reshape(-1, 3)
    t_new = v.transmission(flat).reshape(table.shape)
    i_new = np.maximum(table + i_free * (t_new - t_old), 0.0)
    lvk = lvk_obj(c, g, i_new)
    res = dict(i=i_new, flux=lvk.flux, side=side_lumen(c, g, i_new))
    for h in (5.0, 8.0):
        res[f"gr{h:.0f}"] = evaluate(lvk, h, PERSON_DISTANCE, eh_mean=floor_eh_mean(lvk, h)[0],
                                     d_hole=v)["GR"]
    step = 0.25
    fx = np.arange(arena.FIELD_X[0] + step / 2, arena.FIELD_X[1], step)
    fy = np.arange(arena.FIELD_Y[0] + step / 2, arena.FIELD_Y[1], step)
    em_field = float(arena.eh_grid(lvk, 8.0, fx, fy).mean())
    sx = np.arange(arena.SPECT_X[0], arena.SPECT_X[1] + 1e-9, 0.5)
    sy = np.arange(arena.SPECT_Y[0], arena.SPECT_Y[1] + 1e-9, 0.5)
    res["gr_sp"] = float(arena.gr_grid(lvk, 8.0, sx, sy, em_field)[0].max())
    em, _, u0 = arena.continuous_row(lvk, 8.0)
    res.update(em=em, u0=u0, cls=arena.classify(em, u0))
    return res


def main():
    c, g, table, t_old, i_free, _ = free_lvk(os.path.join(DATA_DIR, SOURCE_IES))
    base = (c, g, table, t_old, i_free)
    p_v2 = open_area(D_OLD)
    ref_v = V2Sides(0.211, 0.0885, 0.237, p_v2)
    ref = assess(ref_v, base)
    dev = float(np.abs(ref["i"] - table).max())
    print(f"Kontrolle: unveränderte V2 gegen Messung, größte Abweichung {dev:.1f} cd")

    variants = [(0.0, 0.0, 0.0, 0.0)]
    for depth in (0.211, 0.15, 0.10, 0.06):
        for front_ratio in (0.42, 0.0):
            for length in (0.237, 0.15, 0.08):
                for p in (p_v2, 0.20, 0.40, 0.50):
                    variants.append((depth, round(depth * front_ratio, 4), length, p))
    rows = []
    head = ("Tiefe  vorn  Länge  Loch | Lichtstrom  zur Seite | GR 5 m  GR 8 m  GR Zusch. | "
            "Reihe 8 m: E  U0")
    lines = [head, f"V2 (Messung): {lumen(c, g, table):.0f} lm, zur Seite "
             f"{side_lumen(c, g, table):.0f} lm, GR {ref['gr5']:.1f} / {ref['gr8']:.1f}, "
             f"Zuschauer {ref['gr_sp']:.1f}, Reihe {ref['em']:.0f} lx U0 {ref['u0']:.3f}"]
    print("\n".join(lines))
    for depth, front, length, p in variants:
        v = V2Sides(depth, front, length, p)
        r = assess(v, base)
        r.update(depth=depth, front=front, length=length, p=p,
                 d_flux=r["flux"] / ref["flux"] - 1, d_side=r["side"] / ref["side"] - 1)
        r["ok"] = (r["gr5"] <= ref["gr5"] + 0.5 and r["gr8"] <= ref["gr8"] + 0.5 and
                   r["gr_sp"] <= ref["gr_sp"] + 1.0)
        rows.append(r)
        line = (f"{depth * 1000:4.0f}  {front * 1000:4.0f}  {length * 1000:4.0f}  {p * 100:4.1f} % | "
                f"{r['d_flux'] * 100:+6.1f} %   {r['d_side'] * 100:+6.1f} %  | {r['gr5']:5.1f}  "
                f"{r['gr8']:5.1f}  {r['gr_sp']:7.1f}   | {r['em']:6.0f} {r['u0']:.3f}"
                f"{'  <- zulässig' if r['ok'] else ''}")
        lines.append(line)
        print(line, flush=True)

    good = [r for r in rows if r["ok"] and r["depth"] > 0]
    best = max(good, key=lambda r: (round(r["side"], -2), -r["p"]))
    none = next(r for r in rows if r["depth"] == 0)
    lines.append(f"Ohne Wangen: Lichtstrom {none['d_flux'] * 100:+.1f} %, zur Seite "
                 f"{none['d_side'] * 100:+.1f} %; gewählte Variante erreicht "
                 f"{best['d_flux'] / none['d_flux'] * 100:.0f} % davon")
    summary = (f"Gewählt: Wangen {best['depth'] * 1000:.0f} mm tief am Stirnblech, vorn "
               f"{best['front'] * 1000:.0f} mm, {best['length'] * 1000:.0f} mm lang, Lochung "
               f"{best['p'] * 100:.0f} % | Lichtstrom {best['flux']:.0f} lm ({best['d_flux'] * 100:+.1f} %), "
               f"zur Seite {best['d_side'] * 100:+.1f} %, GR {best['gr5']:.1f} / {best['gr8']:.1f}, "
               f"Zuschauer {best['gr_sp']:.1f}, Reihe {best['em']:.0f} lx U0 {best['u0']:.3f} "
               f"{best['cls']}")
    print(summary)
    lines += ["", summary]
    open(os.path.join(DATA_DIR, "visor_v2s.txt"), "w").write("\n".join(lines) + "\n")
    with open(os.path.join(DATA_DIR, "visor_v2s_studie.csv"), "w") as f:
        f.write("tiefe_mm;vorn_mm;laenge_mm;lochung;lichtstrom;seite;gr5;gr8;gr_zuschauer;"
                "reihe_e;reihe_u0;zulaessig\n")
        for r in rows:
            f.write(f"{r['depth'] * 1000:.0f};{r['front'] * 1000:.0f};{r['length'] * 1000:.0f};"
                    f"{r['p']:.3f};{r['flux']:.0f};{r['side']:.0f};{r['gr5']:.2f};{r['gr8']:.2f};"
                    f"{r['gr_sp']:.2f};{r['em']:.0f};{r['u0']:.4f};{int(r['ok'])}\n")

    name = "SIRIUS_1000_Blende_V2s"
    note = (f"Berechnet: Stirnblech wie V2, Wangen {best['depth'] * 1000:.0f}/"
            f"{best['front'] * 1000:.0f} mm, {best['length'] * 1000:.0f} mm lang, Lochung "
            f"{best['p'] * 100:.0f} %")
    write_ies(os.path.join(DATA_DIR, "sirius1000_v2s.ies"), os.path.join(DATA_DIR, SOURCE_IES),
              c, g, best["i"], best["flux"], name, note)
    write_ldt(os.path.join(DATA_DIR, "SIRIUS1000_Blende_V2s_berechnet.ldt"), c, g, best["i"],
              best["flux"], name, note)
    np.save(os.path.join(DATA_DIR, "visor_v2s.npy"),
            np.array([best["depth"], best["front"], best["length"], best["p"], best["flux"]]))
    plot(c, g, table, best, ref)


def plot(c, g, table, best, ref):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(17, 5.2), dpi=130)
    for ax, cv in ((axes[0], 90.0), (axes[1], 120.0)):
        ci = int(np.argmin(np.abs(np.asarray(c) - cv)))
        ax.plot(g, table[ci], color="#17202b", lw=2, label="V2 heute (gemessen)")
        ax.plot(g, best["i"][ci], color="#0b5cad", lw=2.4, ls="--", label="V2s (berechnet)")
        ax.set_xlim(0, 100)
        ax.set_title(f"C{cv:.0f} – {'zur Seite' if cv == 90 else 'schräg hinten'}")
        ax.set_xlabel("γ [°]")
        ax.set_ylabel("Lichtstärke [cd]")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    ax = axes[2]
    for v, col, lab in ((V2Sides(0.211, 0.0885, 0.237, 0.034), "#17202b", "V2"),
                        (V2Sides(best["depth"], best["front"], best["length"], best["p"]),
                         "#0b5cad", "V2s")):
        if v.depth > 0:
            a = np.linspace(A_START, A_START + v.length, 20)
            ax.plot(np.r_[a, a[-1]] * 1000, np.r_[v.cheek_depth(a), 0] * 1000, color=col, lw=2,
                    label=f"Wange {lab}")
    ax.plot([-383, 383], [0, 0], color="#0b5cad", lw=4, alpha=0.4)
    ax.plot([-396, -396], [0, 211], color="#5b6673", lw=3, label="Stirnblech (unverändert)")
    ax.set_xlim(-450, 400)
    ax.set_ylim(260, -40)
    ax.set_aspect("equal")
    ax.set_xlabel("mm (← hinten | vorn →)")
    ax.set_title("Seitenansicht der Wangen")
    ax.grid(alpha=0.2)
    ax.legend(fontsize=8, loc="lower right")
    fig.suptitle(f"Blende V2s – Lichtstrom {best['d_flux'] * 100:+.1f} %, zur Seite "
                 f"{best['d_side'] * 100:+.1f} %; GR Person {ref['gr5']:.1f} → {best['gr5']:.1f} (5 m) "
                 f"· berechnet, nicht gemessen", fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(DATA_DIR, "visor_v2s.png"), bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
