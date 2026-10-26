"""
Kiemenblende (KB): ein einziges Blech unter dem Glas über die ganze Leuchtenfläche, die Lamellen
sind aus dem Blech ausgeklinkt und nach unten gedrückt ("Kiemen"). Lackiert in RAL 9010.

    python visor_kiemen.py [ordner]

Geometrie (Leuchtensystem: a nach vorn/C0, b quer, h nach unten; Blech bei h = 0):
  - Reihen von Schlitzen quer zur Ausstrahlung (parallel zu C90), Teilung P = L + s in a-Richtung
    (L = Lamellenlänge = Schlitzlänge, s = Steg zwischen zwei Schlitzen)
  - In b-Richtung sind die Schlitze alle W mm von Stegen der Breite w unterbrochen (Steifigkeit,
    der Lamellenstreifen bleibt so am Blech)
  - Jede Lamelle bleibt an der hinteren Schlitzkante (Richtung C180) angebunden und ist um den
    Winkel theta nach unten gedrückt. Sie hängt damit schräg nach vorn unter ihrem Schlitz und fängt
    Licht ab, das nach hinten geht; der Hauptstrahl der Optik (C0, gamma ~35°) läuft parallel zu
    den Lamellen, wenn theta ~55° ist.

Licht und Reflexion (Monte-Carlo-Strahlverfolgung):
  - Strahlen aus der Lichtverteilung der Optik ohne außenliegende Blende (perforation.free_lvk),
    Startpunkt gleichverteilt über eine Zelle des (unendlich angenommenen) Schlitzmusters
  - RAL 9010 (Reinweiß, Pulverlack seidenglänzend): Reflexionsgrad 0,85, davon 0,80 diffus
    (Lambert) und 0,05 gerichtet; der Rest wird absorbiert
  - Licht, das auf die Oberseite der Stege trifft oder durch einen Schlitz nach oben zurückgeht,
    fällt in die Optik zurück. Grundwert: verloren (konservativ). Zusätzlich wird ausgewiesen, wie
    viel mehr herauskommt, wenn die Optik einen Anteil R davon wieder nach unten abgibt (gleiche
    Verteilung, geometrische Reihe: eta_R = eta / (1 - R * u), u = zurückgeworfener Anteil)
  - Licht oberhalb der Horizontalen (gamma >= 90°) geht unverändert vorbei

Bewertet werden Betriebswirkungsgrad der Blende (Lichtstrom mit / ohne Blende), Veränderung der
Lichtverteilung nach vorn, GR der Person 8 m hinter der Leuchte, Zuschauer und Arena-Reihe.
Gewählt wird die Variante mit dem höchsten Wirkungsgrad, bei der die Person (5 m und 8 m) nicht
stärker geblendet wird als mit der heutigen Blende V2.

Ausgabe: sirius1000_kiemen.ies, SIRIUS1000_Kiemenblende_berechnet.ldt, visor_kiemen.npy,
visor_kiemen.txt, visor_kiemen_studie.csv, visor_kiemen.png
"""

import math
import os
import sys

import numpy as np

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DATA_DIR)
import arena  # noqa: E402
from blendung import LVK, PERSON_DISTANCE, evaluate, floor_eh_mean  # noqa: E402
from perforation import free_lvk, lumen  # noqa: E402
from visor_design import SOURCE_IES, write_ies, write_ldt  # noqa: E402

RHO_DIFFUSE, RHO_SPECULAR = 0.80, 0.05      # RAL 9010, seidenglänzend
WEB = 2.0                                    # Steg zwischen den Schlitzen [mm] (>= 2 x Blech)
SLOT_W, BRIDGE_W = 98.0, 4.0                 # Schlitzbreite und Quersteg in b-Richtung [mm]
SHEET = 1.0                                  # Blechdicke [mm] (nur für CAD)
MAX_BOUNCES = 12
R_OPTIC = 0.5                                # Rückgewinnung in der Optik (Empfindlichkeit)
K_CELLS = 14


class Kiemen:
    def __init__(self, length, theta_deg, web=WEB):
        self.L, self.theta, self.s = length, math.radians(theta_deg), web
        self.P = length + web
        self.Pb = SLOT_W + BRIDGE_W
        self.zb = length * math.sin(self.theta)          # Bautiefe unter dem Blech
        self.ex, self.ez = math.cos(self.theta), math.sin(self.theta)

    @property
    def open_ratio(self):
        return self.L / self.P * SLOT_W / self.Pb

    def in_slot(self, x, y):
        return (np.mod(x, self.P) < self.L) & (np.mod(y, self.Pb) < SLOT_W)

    def trace(self, d0, rng):
        """d0: (N,3) Startrichtungen nach unten. Rückgabe: Austrittsrichtungen (M,3)."""
        n = len(d0)
        x = rng.uniform(0, self.P, n)
        y = rng.uniform(0, self.Pb, n)
        z = np.zeros(n)
        d = d0.copy()
        alive = self.in_slot(x, y)          # auf der Stegoberseite: zurück in die Optik
        self.returned = float((~alive).sum()) * (RHO_DIFFUSE + RHO_SPECULAR)
        out = []
        tongue_n = np.array([self.ez, 0.0, -self.ex])   # Normale der Lamelle (Oberseite, nach oben-vorn)
        for _ in range(MAX_BOUNCES):
            idx = np.nonzero(alive)[0]
            if len(idx) == 0:
                break
            px, py, pz = x[idx], y[idx], z[idx]
            dx, dy, dz = d[idx, 0], d[idx, 1], d[idx, 2]
            inf = np.full(len(idx), np.inf)
            with np.errstate(divide="ignore", invalid="ignore"):
                t_exit = np.where(dz > 1e-12, (self.zb - pz) / dz, inf)
                t_plane = np.where(dz < -1e-12, -pz / dz, inf)
            t_plane = np.where(t_plane > 1e-9, t_plane, inf)
            t_tng = inf.copy()
            # Lamellen der Nachbarzellen: Strecke von (kP, 0) nach (kP + L ex, L ez)
            c0 = np.floor(px / self.P)
            den = dx * self.ez - dz * self.ex
            ok_den = np.abs(den) > 1e-12
            for k in range(-K_CELLS, K_CELLS + 1):
                ax = (c0 + k) * self.P
                # px + t dx = ax + u L ex ; pz + t dz = u L ez
                with np.errstate(divide="ignore", invalid="ignore"):
                    t = ((ax - px) * self.ez + pz * self.ex) / den
                    u = (pz + t * dz) / (self.L * self.ez)
                hy = py + t * dy
                hit = (ok_den & (t > 1e-7) & (u >= 0) & (u <= 1) &
                       (np.mod(hy, self.Pb) < SLOT_W))
                t_tng = np.where(hit & (t < t_tng), t, t_tng)
            t_min = np.minimum(np.minimum(t_exit, t_plane), t_tng)
            px, py, pz = px + t_min * dx, py + t_min * dy, pz + t_min * dz
            x[idx], y[idx], z[idx] = px, py, pz
            # 1. Austritt nach unten
            ex_m = (t_exit <= t_min) & np.isfinite(t_exit)
            out.append(d[idx[ex_m]])
            alive[idx[ex_m]] = False
            # 2. Blechebene von unten: Schlitz -> zurück in die Optik (verloren), Steg -> Reflexion
            pl_m = (t_plane <= t_min) & ~ex_m & np.isfinite(t_plane)
            slot = self.in_slot(px, py)
            alive[idx[pl_m & slot]] = False
            self.returned += float((pl_m & slot).sum())
            web_m = pl_m & ~slot
            # 3. Lamelle
            tg_m = (t_tng <= t_min) & ~ex_m & ~pl_m & np.isfinite(t_tng)
            refl = web_m | tg_m
            ridx = idx[refl]
            if len(ridx) == 0:
                continue
            nrm = np.zeros((len(ridx), 3))
            nrm[web_m[refl]] = (0.0, 0.0, 1.0)
            tsel = tg_m[refl]
            nt = np.tile(tongue_n, (int(tsel.sum()), 1))
            din = d[ridx[tsel]]
            flip = (din @ tongue_n) > 0          # von unten getroffen: Normale nach unten
            nt[flip] *= -1
            nrm[tsel] = nt
            dir_in = d[ridx]
            r = rng.random(len(ridx))
            spec = r < RHO_SPECULAR
            diff = (r >= RHO_SPECULAR) & (r < RHO_SPECULAR + RHO_DIFFUSE)
            absorbed = ~(spec | diff)
            new = dir_in - 2 * np.sum(dir_in * nrm, 1)[:, None] * nrm
            nd = int(diff.sum())
            if nd:
                new[diff] = cosine_hemisphere(nrm[diff], rng)
            d[ridx] = new
            # etwas von der Fläche weg, damit der nächste Schnitt nicht dieselbe Fläche ist
            x[ridx] += 1e-6 * nrm[:, 0]
            y[ridx] += 1e-6 * nrm[:, 1]
            z[ridx] += 1e-6 * nrm[:, 2]
            alive[ridx[absorbed]] = False
        return np.concatenate(out) if out else np.zeros((0, 3))


def cosine_hemisphere(nrm, rng):
    n = len(nrm)
    u1, u2 = rng.random(n), rng.random(n)
    r, phi = np.sqrt(u1), 2 * np.pi * u2
    local = np.stack([r * np.cos(phi), r * np.sin(phi), np.sqrt(1 - u1)], 1)
    helper = np.where(np.abs(nrm[:, [0]]) < 0.9, [[1.0, 0, 0]], [[0, 1.0, 0]])
    t1 = np.cross(nrm, helper)
    t1 /= np.linalg.norm(t1, axis=1)[:, None]
    t2 = np.cross(nrm, t1)
    return local[:, [0]] * t1 + local[:, [1]] * t2 + local[:, [2]] * nrm


def sample_directions(c, g, table, n, rng):
    """Richtungen gemäß Lichtstärkeverteilung (nur gamma < 90°), Rückgabe (n,3) und Anteil."""
    cr, gr = np.radians(c), np.radians(g)
    dc = np.gradient(cr)
    # Zellgrenzen in gamma
    gb = np.concatenate([[0], (gr[1:] + gr[:-1]) / 2, [np.pi]])
    dom = (np.cos(gb[:-1]) - np.cos(gb[1:]))[None, :] * dc[:, None]
    w = table * dom
    if c[-1] == 360:
        w[-1] = 0
    down = gr < np.pi / 2 - 1e-9
    w_down = w[:, down]
    frac = w_down.sum() / w.sum()
    p = (w_down / w_down.sum()).ravel()
    pick = rng.choice(p.size, n, p=p)
    ci, gi = np.unravel_index(pick, w_down.shape)
    cc = cr[ci] + (rng.random(n) - 0.5) * dc[ci]
    lo, hi = np.cos(gb[gi]), np.cos(np.minimum(gb[gi + 1], np.pi / 2))
    cg = lo + rng.random(n) * (hi - lo)
    sg = np.sqrt(1 - cg ** 2)
    return np.stack([sg * np.cos(cc), sg * np.sin(cc), cg], 1), frac


def bin_lvk(dirs, c, g, flux):
    """Austrittsrichtungen -> Lichtstärke [cd] auf dem Raster c, g (Fluss je Strahl = flux/N)."""
    cdeg = np.degrees(np.arctan2(dirs[:, 1], dirs[:, 0])) % 360
    gdeg = np.degrees(np.arccos(np.clip(dirs[:, 2], -1, 1)))
    # Spiegelsymmetrie zur Ebene C0-C180: beide Hälften zusammenlegen
    cdeg = np.concatenate([cdeg, (360 - cdeg) % 360])
    gdeg = np.concatenate([gdeg, gdeg])
    w = flux / len(cdeg)
    step_c, step_g = c[1] - c[0], g[1] - g[0]
    ci = np.round(cdeg / step_c).astype(int) % int(round(360 / step_c))
    gi = np.clip(np.round(gdeg / step_g).astype(int), 0, len(g) - 1)
    nc = int(round(360 / step_c))
    hist = np.zeros((nc, len(g)))
    np.add.at(hist, (ci, gi), w)
    gr = np.radians(g)
    gb = np.concatenate([[0], np.radians(g[:-1] + step_g / 2), [np.pi]])
    dom = (np.cos(gb[:-1]) - np.cos(gb[1:])) * np.radians(step_c)
    inten = hist / dom[None, :]
    # gamma = 0 ist eine Richtung: Mittelwert über alle C-Ebenen
    inten[:, 0] = inten[:, 0].mean()
    # leichte Glättung in C (zyklisch) und gamma gegen Rauschen
    k = np.array([0.25, 0.5, 0.25])
    inten = sum(kk * np.roll(inten, s, 0) for kk, s in zip(k, (-1, 0, 1)))
    sm = inten.copy()
    sm[:, 1:-1] = 0.25 * inten[:, :-2] + 0.5 * inten[:, 1:-1] + 0.25 * inten[:, 2:]
    if len(c) == nc + 1:
        sm = np.vstack([sm, sm[:1]])
    del gr
    return sm


def kiemen_lvk(v, base, n_rays, seed=1):
    c, g, table, t_old, i_free = base
    rng = np.random.default_rng(seed)
    dirs, frac_down = sample_directions(c, g, i_free, n_rays, rng)
    out = v.trace(dirs, rng)
    flux_free = lumen(c, g, i_free)
    flux_down = flux_free * frac_down
    i_down = bin_lvk(out, c, g, flux_down * len(out) / n_rays) if len(out) else 0
    up = np.asarray(g) >= 90 - 1e-9
    i_new = np.where(up[None, :], i_free, i_down)
    v.u_return = v.returned / n_rays * frac_down
    return i_new, len(out) / n_rays


def lvk_obj(c, g, table):
    lvk = LVK.__new__(LVK)
    lvk.c, lvk.g, lvk.t = np.array(c), np.array(g), np.array(table)
    lvk.flux, lvk.name = lumen(c, g, table), "variante"
    return lvk


def shape_change(i_new, i_ref, c, g):
    """Formänderung der Verteilung nach vorn und zur Seite (C -90…90, gamma 0…80), normiert auf
    gleichen Lichtstrom: mittlere logarithmische Abweichung, raumwinkelgewichtet."""
    cc, gg = np.meshgrid(np.asarray(c), np.asarray(g), indexing="ij")
    mask = ((cc <= 90) | (cc >= 270)) & (gg <= 80)
    a = i_new / lumen(c, g, i_new)
    b = i_ref / lumen(c, g, i_ref)
    w = np.sin(np.radians(gg))[mask]
    e = np.log((a[mask] + 1e-6) / (b[mask] + 1e-6))
    return float(np.sqrt(np.sum(w * e * e) / np.sum(w)))


def assess(c, g, i_new, i_free):
    lvk = lvk_obj(c, g, i_new)
    res = dict(i=i_new, flux=lvk.flux, change=shape_change(i_new, i_free, c, g))
    for h in (5.0, 8.0):
        res[f"gr{h:.0f}"] = evaluate(lvk, h, PERSON_DISTANCE, eh_mean=floor_eh_mean(lvk, h)[0],
                                     d_hole=None)["GR"]
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
    flux_free = lumen(c, g, i_free)
    v2 = assess(c, g, table, i_free)
    v2["eta"] = v2["flux"] / flux_free
    lines = [f"Optik ohne Blende: {flux_free:.0f} lm. V2 heute: {v2['flux']:.0f} lm, Wirkungsgrad "
             f"{v2['eta'] * 100:.1f} %, Formänderung {v2['change']:.3f}, GR {v2['gr5']:.1f} / "
             f"{v2['gr8']:.1f}, Zuschauer {v2['gr_sp']:.1f}, Reihe {v2['em']:.0f} lx U0 {v2['u0']:.3f}",
             f"L [mm]  theta  Tiefe | offen  Wirkungsgrad (R={R_OPTIC:g})  Formänd. | GR 5 m  GR 8 m  Zusch. | "
             "Reihe 8 m"]
    print("\n".join(lines), flush=True)
    rows = []
    for length in (8.0, 12.0, 20.0, 30.0, 40.0):
        for theta in (40, 50, 55, 60, 70, 80, 90):
            v = Kiemen(length, theta)
            i_new, _ = kiemen_lvk(v, base, 300_000)
            r = assess(c, g, i_new, i_free)
            r.update(L=length, theta=theta, zb=v.zb, open=v.open_ratio, eta=r["flux"] / flux_free,
                     u=v.u_return)
            r["eta_r"] = r["eta"] / (1 - R_OPTIC * r["u"])
            r["ok"] = r["gr5"] <= v2["gr5"] and r["gr8"] <= v2["gr8"]
            rows.append(r)
            line = (f"{length:5.0f}  {theta:4d}°  {v.zb:5.1f} | {v.open_ratio * 100:4.0f} %  "
                    f"{r['eta'] * 100:6.1f} % ({r['eta_r'] * 100:4.1f} %)  {r['change']:.3f}  | {r['gr5']:5.1f}  "
                    f"{r['gr8']:5.1f}  {r['gr_sp']:5.1f} | {r['em']:5.0f} lx U0 {r['u0']:.3f}"
                    f"{'  <- Blendung <= V2' if r['ok'] else ''}")
            lines.append(line)
            print(line, flush=True)

    good = [r for r in rows if r["ok"]] or rows
    best = max(good, key=lambda r: (r["eta"], -r["change"]))
    # Endrechnung mit mehr Strahlen
    v = Kiemen(best["L"], best["theta"])
    i_new, _ = kiemen_lvk(v, base, 2_000_000, seed=7)
    fin = assess(c, g, i_new, i_free)
    fin.update(L=best["L"], theta=best["theta"], zb=v.zb, open=v.open_ratio,
               eta=fin["flux"] / flux_free, u=v.u_return)
    fin["eta_r"] = fin["eta"] / (1 - R_OPTIC * fin["u"])
    summary = (f"Gewählt: Lamellen {fin['L']:.0f} mm, {fin['theta']}° gedrückt, Steg {WEB:.0f} mm, "
               f"Bautiefe {fin['zb']:.1f} mm, offene Fläche {fin['open'] * 100:.0f} % | Lichtstrom "
               f"{fin['flux']:.0f} lm, Wirkungsgrad {fin['eta'] * 100:.1f} % (mit Rückgewinnung R={R_OPTIC:g}: "
               f"{fin['eta_r'] * 100:.1f} %; V2 {v2['eta'] * 100:.1f} %), "
               f"Formänderung {fin['change']:.3f} (V2 {v2['change']:.3f}), GR {fin['gr5']:.1f} / "
               f"{fin['gr8']:.1f}, Zuschauer {fin['gr_sp']:.1f}, Reihe {fin['em']:.0f} lx U0 "
               f"{fin['u0']:.3f} {fin['cls']}")
    print(summary)
    lines += ["", summary]
    open(os.path.join(DATA_DIR, "visor_kiemen.txt"), "w").write("\n".join(lines) + "\n")
    with open(os.path.join(DATA_DIR, "visor_kiemen_studie.csv"), "w") as f:
        f.write("lamelle_mm;theta;tiefe_mm;offen;wirkungsgrad;wirkungsgrad_r;formaenderung;gr5;gr8;"
                "gr_zuschauer;reihe_e;reihe_u0\n")
        for r in rows:
            f.write(f"{r['L']:.0f};{r['theta']};{r['zb']:.1f};{r['open']:.3f};{r['eta']:.4f};{r['eta_r']:.4f};"
                    f"{r['change']:.4f};{r['gr5']:.2f};{r['gr8']:.2f};{r['gr_sp']:.2f};"
                    f"{r['em']:.0f};{r['u0']:.4f}\n")
    name = "SIRIUS_1000_Kiemenblende"
    note = (f"Berechnet: Kiemenblech, Lamellen {fin['L']:.0f} mm {fin['theta']} Grad, RAL 9010 "
            f"rho 0,85, Monte-Carlo")
    write_ies(os.path.join(DATA_DIR, "sirius1000_kiemen.ies"), os.path.join(DATA_DIR, SOURCE_IES),
              c, g, fin["i"], fin["flux"], name, note)
    write_ldt(os.path.join(DATA_DIR, "SIRIUS1000_Kiemenblende_berechnet.ldt"), c, g, fin["i"],
              fin["flux"], name, note)
    np.save(os.path.join(DATA_DIR, "visor_kiemen.npy"),
            np.array([fin["L"], fin["theta"], WEB, SLOT_W, BRIDGE_W, fin["flux"], fin["eta"],
                      fin["eta_r"]]))
    plot(c, g, table, i_free, fin, v2, rows)


def plot(c, g, table, i_free, fin, v2, rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(17, 5.2), dpi=130)
    ax = axes[0]
    for length, col in zip((8.0, 12.0, 20.0, 30.0, 40.0),
                           ("#17202b", "#0b5cad", "#2f9a46", "#a35a00", "#7a4fb0")):
        rs = [r for r in rows if r["L"] == length]
        ax.plot([r["gr5"] for r in rs], [r["eta"] * 100 for r in rs], "o-", color=col,
                label=f"Lamelle {length:.0f} mm")
        for r in rs:
            ax.annotate(f"{r['theta']}°", (r["gr5"], r["eta"] * 100), fontsize=6.5,
                        xytext=(3, 3), textcoords="offset points")
    ax.axvline(v2["gr5"], color="0.5", ls="--", lw=1)
    ax.axhline(v2["eta"] * 100, color="0.5", ls=":", lw=1)
    ax.text(v2["gr5"] + 0.2, ax.get_ylim()[0] + 1, "V2", fontsize=8, color="0.4")
    ax.set_xlabel("GR der Person, 5 m Montagehöhe")
    ax.set_ylabel("Wirkungsgrad der Blende [%]")
    ax.set_title("Wirkungsgrad gegen Blendung")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)

    ax = axes[1]
    for cv, ls in ((0.0, "-"), (180.0, "--")):
        ci = int(np.argmin(np.abs(np.asarray(c) - cv)))
        ax.plot(g, i_free[ci], color="#a35a00", lw=1.6, ls=ls, label=f"ohne Blende C{cv:.0f}")
        ax.plot(g, table[ci], color="#17202b", lw=1.6, ls=ls, label=f"V2 C{cv:.0f}")
        ax.plot(g, fin["i"][ci], color="#0b5cad", lw=2.2, ls=ls, label=f"Kiemenblende C{cv:.0f}")
    ax.set_xlim(0, 100)
    ax.set_xlabel("γ [°]")
    ax.set_ylabel("Lichtstärke [cd]")
    ax.set_title("C0 (vorn, durchgezogen) und C180 (hinten, gestrichelt)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7)

    ax = axes[2]
    v = Kiemen(fin["L"], fin["theta"])
    for k in range(4):
        x0 = k * v.P
        ax.plot([x0 - v.s, x0], [0, 0], color="#17202b", lw=3)
        ax.plot([x0, x0 + v.L * v.ex], [0, v.L * v.ez], color="#17202b", lw=3)
    ax.plot([-v.s, 4 * v.P - v.s], [-6, -6], color="#0b5cad", lw=4, alpha=0.4)
    ax.text(2 * v.P, -8, "Glas", color="#0b5cad", ha="center", fontsize=9)
    gr35 = math.radians(35)
    for k in range(3):
        x0 = k * v.P + v.L * 0.5
        ax.annotate("", xy=(x0 + 20 * math.sin(gr35), 20 * math.cos(gr35)), xytext=(x0, 0),
                    arrowprops=dict(arrowstyle="->", color="#a35a00"))
    ax.text(4 * v.P - v.s, v.zb + 4, "→ vorn (C0)", ha="right", fontsize=9, color="#a35a00")
    ax.set_aspect("equal")
    ax.set_ylim(v.zb + 10, -14)
    ax.set_xlabel("mm")
    ax.set_title(f"Schnitt: Lamelle {v.L:.0f} mm, {fin['theta']}°, Steg {v.s:.0f} mm, Tiefe "
                 f"{v.zb:.0f} mm", fontsize=10)
    ax.grid(alpha=0.2)
    fig.suptitle(f"Kiemenblende RAL 9010 – Wirkungsgrad {fin['eta'] * 100:.1f} % (V2 "
                 f"{v2['eta'] * 100:.1f} %), GR Person {fin['gr5']:.1f} / {fin['gr8']:.1f} · berechnet, "
                 f"nicht gemessen", fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(DATA_DIR, "visor_kiemen.png"), bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
