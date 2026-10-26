"""
Blendungsbewertung für die sitzende Person hinter der Leuchte (ohne Blender ausführbar).

    python blendung.py [ordner]

Bewertet für die Montagehöhen 5 m und 8 m und vergleicht die Blende wie geliefert
(Lochung 3,4 %) mit der Variante 50 % Lochung (LVK aus perforation.py, abgeschätzt):
  * Geometrie Auge -> Leuchte (Abstand, Erhebungswinkel, Ausstrahlungswinkel gamma in C180)
  * Lichtstärke I in Richtung Auge (aus der IES-Datei, Blende in der LVK enthalten)
  * mittlere Leuchtdichte der Leuchte, wie die Person sie sieht
  * Beleuchtungsstärke am Auge E_Auge (senkrecht zur Blickrichtung) und E_v (vertikal, Richtung
    Leuchte)
  * Schleierleuchtdichte L_vl = 10 * E_Auge / theta^2 (theta in Grad, CIE 112)
  * Glare Rating GR = 27 + 24 * log10(L_vl / L_ve^0.9) nach CIE 112 / EN 12464-2 mit
    L_ve = 0.035 * rho * E_h,mittel / pi (Umgebungsschleierleuchtdichte)
  * Vergleich mit den Störlicht-Richtwerten nach EN 12464-2 / CIE 150 (I und E_v an der
    Position des Betrachters, Umweltzonen E1 bis E4)

Annahmen (unten als Parameter):
  * Blickrichtung horizontal nach vorn (+Y, also in Leuchtenrichtung), 2° nach unten geneigt
    wie in CIE 112 / EN 12464-2.
  * GR braucht die Umgebungsleuchtdichte. Bei 0 % Reflexion ist L_ve = 0 und GR nicht
    definiert (unendlich); deshalb wird GR mit einem angenommenen Reflexionsgrad des Bodens
    von 20 % (und zum Vergleich 10 % und 30 %) gerechnet. E_h,mittel ist die mittlere
    horizontale Direktbeleuchtungsstärke auf dem ganzen Boden des Raums.
"""

import csv
import math
import os
import sys

import numpy as np

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DATA_DIR)
from ldt2ies import read_ies  # noqa: E402
from perforation import D_OLD, d_for_open_area, hole_transmission  # noqa: E402

# (Kürzel, Beschreibung, IES-Datei, Lochdurchmesser der Blende [mm])
VARIANTS = [("", "Blende heute (Lochung 3,4 %)", "sirius1000.ies", D_OLD),
            ("perf50", "Lochung 50 %", "sirius1000_perf50.ies", d_for_open_area(0.5))]

MOUNT_HEIGHTS = [5.0, 8.0]
PERSON_DISTANCE = 8.0       # Person hinter der Leuchte [m]
EYE_HEIGHT = 1.2            # sitzend [m]
VIEW_DOWN_DEG = 2.0         # Blickrichtung 2° unter der Horizontalen (CIE 112)
ROOM_WIDTH, ROOM_FRONT, ROOM_BACK = 12.0, 8.0, -10.0
RHO_DEFAULT = 0.20
RHO_VARIANTS = [0.10, 0.20, 0.30]
# Lichtaustrittsfläche eines Moduls (LDT) und Blende: 200 mm tief an der hinteren Kante
LUM_LEN_C0 = 0.761          # Länge in C0-C180-Richtung (Achse mit Blende) [m]
LUM_WID_C90 = 0.300         # Breite quer [m]
VISOR_DEPTH = 0.200         # Blende ragt so weit unter das Glas [m]

# GR-Grenzwerte (Auswahl, EN 12464-2 / EN 12193)
GR_LIMITS = [("Sportanlage Wettkampf (EN 12193)", 50), ("Sportanlage Training", 55),
             ("Arbeitsstätte im Freien, feine Arbeiten", 45),
             ("Arbeitsstätte im Freien, grobe Arbeiten", 55)]
# Störlicht EN 12464-2 / CIE 150: (Zone, I max vor/nach Sperrzeit [cd], Ev vor/nach [lx])
OBTRUSIVE = [("E1 (dunkel, z. B. Naturschutzgebiet)", 2500, 0, 2, 0),
             ("E2 (geringe Helligkeit, ländlich)", 7500, 500, 5, 1),
             ("E3 (mittlere Helligkeit, Vorort)", 10000, 1000, 10, 2),
             ("E4 (hohe Helligkeit, Innenstadt)", 25000, 2500, 25, 5)]


class LVK:
    def __init__(self, path):
        c, g, table, flux, name = read_ies(path)
        self.c, self.g, self.t = np.array(c), np.array(g), np.array(table)
        self.flux, self.name = flux, name

    def intensity(self, cang, gamma):
        """Lichtstärke [cd] bei C (Grad) und gamma (Grad, 0 = Nadir), bilinear."""
        cang = np.asarray(cang, dtype=float) % 360.0
        gamma = np.asarray(gamma, dtype=float)
        ci = np.clip(np.searchsorted(self.c, cang, side='right') - 1, 0, len(self.c) - 2)
        gi = np.clip(np.searchsorted(self.g, gamma, side='right') - 1, 0, len(self.g) - 2)
        fc = (cang - self.c[ci]) / (self.c[ci + 1] - self.c[ci])
        fg = (gamma - self.g[gi]) / (self.g[gi + 1] - self.g[gi])
        t = self.t
        return (t[ci, gi] * (1 - fc) * (1 - fg) + t[ci + 1, gi] * fc * (1 - fg) +
                t[ci, gi + 1] * (1 - fc) * fg + t[ci + 1, gi + 1] * fc * fg)

    def toward(self, light, point):
        """Lichtstärke von der Leuchte (Glas nach unten, C0 = +Y, C90 = +X) zum Punkt."""
        v = np.asarray(point, dtype=float) - light
        d = np.linalg.norm(v, axis=-1)
        gamma = np.degrees(np.arccos(np.clip(-v[..., 2] / d, -1, 1)))
        cang = np.degrees(np.arctan2(v[..., 0], v[..., 1]))
        return self.intensity(cang, gamma), d, gamma, cang % 360


def floor_eh_mean(lvk, h, step=0.1):
    xs = np.arange(-ROOM_WIDTH / 2 + step / 2, ROOM_WIDTH / 2, step)
    ys = np.arange(ROOM_BACK + step / 2, ROOM_FRONT, step)
    gx, gy = np.meshgrid(xs, ys)
    pts = np.stack([gx, gy, np.zeros_like(gx)], axis=-1)
    light = np.array([0.0, 0.0, h])
    intensity, d, gamma, _ = lvk.toward(light, pts)
    eh = intensity * (h / d) / d ** 2
    return float(eh.mean()), float(eh.max())


def evaluate(lvk, h, behind, eye_height=EYE_HEIGHT, rho=RHO_DEFAULT, eh_mean=None,
             d_hole=D_OLD):
    light = np.array([0.0, 0.0, h])
    eye = np.array([0.0, -behind, eye_height])
    intensity, d, gamma, cang = lvk.toward(light, eye)
    intensity, d, gamma = float(intensity), float(d), float(gamma)
    to_lum = (light - eye) / d
    view = np.array([0.0, math.cos(math.radians(VIEW_DOWN_DEG)),
                     -math.sin(math.radians(VIEW_DOWN_DEG))])
    theta = math.degrees(math.acos(np.clip(to_lum @ view, -1, 1)))
    elevation = math.degrees(math.asin(to_lum[2]))
    e_eye = intensity * math.cos(math.radians(theta)) / d ** 2   # Ebene senkrecht zur Blickr.
    e_v = intensity * math.cos(math.radians(elevation)) / d ** 2  # vertikal, zur Leuchte
    e_normal = intensity / d ** 2                                 # senkrecht zum Lichteinfall
    l_vl = 10.0 * e_eye / theta ** 2
    if eh_mean is None:
        eh_mean = floor_eh_mean(lvk, h)[0]
    l_ve = 0.035 * rho * eh_mean / math.pi
    gr = 27 + 24 * math.log10(l_vl / l_ve ** 0.9) if l_ve > 0 and l_vl > 0 else float('inf')
    # Leuchtdichte: projizierte Fläche; Anteil, den die Blende (hinten) verdeckt. Durch die
    # Lochung des Stirnblechs ist zusätzlich ein Teil des verdeckten Glases zu sehen.
    a = LUM_LEN_C0 * LUM_WID_C90
    cos_g = math.cos(math.radians(gamma))
    if d_hole is None:  # ohne außenliegende Blende: ganze Lichtaustrittsfläche sichtbar
        eff_len = LUM_LEN_C0
    elif hasattr(d_hole, "transmission"):  # eigene Blendengeometrie (visor_design.Visor)
        g = math.radians(gamma)
        eff_len = LUM_LEN_C0 * float(d_hole.transmission([(-math.sin(g), 0.0, math.cos(g))])[0])
    else:
        visible_len = max(0.0, LUM_LEN_C0 - VISOR_DEPTH * math.tan(math.radians(gamma)))
        tau = float(hole_transmission(d_hole, math.sin(math.radians(gamma))))
        eff_len = visible_len + (LUM_LEN_C0 - visible_len) * tau
    l_mean = intensity / (a * cos_g)
    l_visible = intensity / (eff_len * LUM_WID_C90 * cos_g) if eff_len > 0 else 0.0
    omega = eff_len * LUM_WID_C90 * cos_g / d ** 2
    return dict(h=h, behind=behind, d=d, elevation=elevation, gamma=gamma, theta=theta,
                I=intensity, E_eye=e_eye, E_v=e_v, E_n=e_normal, L_vl=l_vl, Eh_mean=eh_mean,
                L_ve=l_ve, rho=rho, GR=gr, L_mean=l_mean, L_visible=l_visible,
                visible_frac=eff_len / LUM_LEN_C0, omega=omega)


def fmt(v, nd=1):
    return f"{v:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    results, sweep, lines = [], {}, []
    behind = np.arange(1.0, 10.01, 0.25)
    for key, label, ies, d_hole in VARIANTS:
        path = os.path.join(DATA_DIR, ies)
        if not os.path.exists(path):
            print(f"{ies} fehlt, Variante '{label}' übersprungen")
            continue
        lvk = LVK(path)
        lines += [f"=== {label}: {lvk.name}, {fmt(lvk.flux, 0)} lm, Person sitzend "
                  f"{PERSON_DISTANCE:g} m hinter der Leuchte, Augenhöhe {EYE_HEIGHT:g} m, "
                  f"Blick nach vorn {VIEW_DOWN_DEG:g}° nach unten", ""]
        for h in MOUNT_HEIGHTS:
            eh_mean, eh_max = floor_eh_mean(lvk, h)
            r = evaluate(lvk, h, PERSON_DISTANCE, eh_mean=eh_mean, d_hole=d_hole)
            r.update(Eh_max=eh_max, variant=key, label=label, lvk=lvk)
            r["GR_rho"] = {rho: evaluate(lvk, h, PERSON_DISTANCE, rho=rho, eh_mean=eh_mean,
                                         d_hole=d_hole)["GR"] for rho in RHO_VARIANTS}
            results.append(r)
            sweep[(key, h)] = [evaluate(lvk, h, b, eh_mean=eh_mean, d_hole=d_hole)
                               for b in behind]
            lines += [
                f"Montagehöhe {h:g} m:",
                f"  Abstand Auge-Leuchte {fmt(r['d'], 2)} m, Leuchte {fmt(r['elevation'])}° über "
                f"der Horizontalen, Winkel zur Blickrichtung theta = {fmt(r['theta'])}°",
                f"  Ausstrahlungswinkel zur Person: C180, gamma = {fmt(r['gamma'])}°",
                f"  Lichtstärke zur Person I = {fmt(r['I'], 0)} cd",
                f"  sichtbarer Glasanteil (direkt + durch die Lochung) "
                f"{r['visible_frac'] * 100:.0f} %, Raumwinkel {r['omega']:.5f} sr",
                f"  Leuchtdichte sichtbares Glas {fmt(r['L_visible'] / 1000, 0)} kcd/m² "
                f"(gemittelt über die ganze Lichtaustrittsfläche {fmt(r['L_mean'] / 1000, 0)} "
                f"kcd/m²)",
                f"  E am Auge (senkrecht zur Blickrichtung) {fmt(r['E_eye'], 2)} lx, "
                f"E_v (vertikal) {fmt(r['E_v'], 2)} lx",
                f"  Schleierleuchtdichte L_vl = {fmt(r['L_vl'], 3)} cd/m²",
                f"  E_h Boden: Mittel {fmt(eh_mean, 0)} lx, Max {fmt(eh_max, 0)} lx; "
                f"L_ve (rho {RHO_DEFAULT:.0%}) = {fmt(r['L_ve'], 2)} cd/m²",
                "  GR = " + ", ".join(f"{fmt(g, 1)} (rho {rho:.0%})"
                                      for rho, g in r["GR_rho"].items()) +
                ", bei rho 0 %: nicht definiert (keine Umgebungsleuchtdichte)",
                "",
            ]

    for line in lines:
        print(line)
    with open(os.path.join(DATA_DIR, "blendung.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(DATA_DIR, "blendung_verlauf.csv"), "w", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Variante", "Montagehoehe [m]", "Abstand hinter Leuchte [m]",
                    "gamma [Grad]", "theta [Grad]", "I [cd]", "E_Auge [lx]", "E_v [lx]",
                    "L_vl [cd/m2]", f"GR (rho {RHO_DEFAULT:.0%})"])
        for (key, h), rows in sweep.items():
            for r in rows:
                w.writerow([key or "heute", f"{h:g}", f"{r['behind']:.2f}", f"{r['gamma']:.1f}",
                            f"{r['theta']:.1f}", f"{r['I']:.0f}", f"{r['E_eye']:.3f}",
                            f"{r['E_v']:.3f}", f"{r['L_vl']:.4f}", f"{r['GR']:.1f}"])
    try:
        write_report(results, behind, sweep)
    except ImportError:
        print("matplotlib nicht verfügbar, kein PNG-Bericht")


def write_report(results, behind, sweep):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(14, 15), dpi=120)
    gs = fig.add_gridspec(3, 2, height_ratios=[1.0, 1.0, 1.25], hspace=0.38, wspace=0.22)
    colors = {5.0: "#1f6fd1", 8.0: "#d1491f"}
    styles = {"": "-", "perf50": "--"}
    names = {key: label for key, label, _, _ in VARIANTS}
    lines_for = [(key, h) for key, _, _, _ in VARIANTS for h in MOUNT_HEIGHTS
                 if (key, h) in sweep]
    fig.suptitle("Blendungsbewertung – Siteco SIRIUS 1000 (1 Modul) mit außenliegender Blende V2:"
                 " heute vs. 50 % Lochung\n"
                 f"Person sitzend, Augenhöhe {EYE_HEIGHT:g} m, Blick horizontal nach vorn (2° nach"
                 " unten), Leuchte frei im Raum, Glas nach unten", fontsize=13)

    ax = fig.add_subplot(gs[0, 0])
    for key, h in lines_for:
        ax.plot(behind, [r["GR"] for r in sweep[(key, h)]], color=colors[h], ls=styles[key],
                lw=2, label=f"{h:g} m, {names[key]}")
    for name, lim in GR_LIMITS[:2]:
        ax.axhline(lim, color="k", ls="--", lw=0.8)
        ax.text(behind[0] + 0.05, lim + 0.4, f"GR {lim}: {name}", fontsize=8)
    ax.axvline(PERSON_DISTANCE, color="gray", lw=0.8)
    ax.text(PERSON_DISTANCE + 0.05, ax.get_ylim()[0] + 1, "Person", fontsize=8, color="gray")
    ax.set_xlabel("Abstand hinter der Leuchte [m]")
    ax.set_ylabel(f"GR (Boden-Reflexionsgrad {RHO_DEFAULT:.0%})")
    ax.set_title("Glare Rating GR (CIE 112 / EN 12464-2)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=9)

    ax = fig.add_subplot(gs[0, 1])
    for key, h in lines_for:
        ax.semilogy(behind, [r["I"] for r in sweep[(key, h)]], color=colors[h], ls=styles[key],
                    lw=2, label=f"{h:g} m, {names[key]}")
    for zone, pre, post, _, _ in OBTRUSIVE[1:]:
        ax.axhline(pre, color="k", ls=":", lw=0.7)
        ax.text(behind[-1] - 0.05, pre * 1.08, f"{zone.split()[0]} {fmt(pre, 0)} cd", fontsize=7,
                ha="right")
    ax.axvline(PERSON_DISTANCE, color="gray", lw=0.8)
    ax.set_xlabel("Abstand hinter der Leuchte [m]")
    ax.set_ylabel("Lichtstärke [cd]")
    ax.set_title("Lichtstärke in Richtung Auge (Störlicht-Richtwerte vor Sperrzeit)")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=9)

    ax = fig.add_subplot(gs[1, 0])
    for key, h in lines_for:
        ax.plot(behind, [r["E_v"] for r in sweep[(key, h)]], color=colors[h], ls=styles[key],
                lw=2, label=f"{h:g} m, {names[key]}")
    for zone, _, _, pre, post in OBTRUSIVE[1:]:
        ax.axhline(pre, color="k", ls=":", lw=0.7)
        ax.text(behind[0] + 0.05, pre + 0.3, f"{zone.split()[0]} {pre} lx", fontsize=7)
    ax.axvline(PERSON_DISTANCE, color="gray", lw=0.8)
    ax.set_xlabel("Abstand hinter der Leuchte [m]")
    ax.set_ylabel("E_v [lx]")
    ax.set_title("Vertikale Beleuchtungsstärke am Auge (Richtung Leuchte)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=9)

    ax = fig.add_subplot(gs[1, 1])
    g = np.linspace(0, 120, 241)
    first = results[0]["lvk"]
    ax.semilogy(g, np.maximum(first.intensity(np.zeros_like(g), g), 1), color="0.6", lw=1.5,
                label="C0 (nach vorn)")
    seen = set()
    for r in results:
        if r["variant"] not in seen:
            seen.add(r["variant"])
            ax.semilogy(g, np.maximum(r["lvk"].intensity(np.full_like(g, 180.0), g), 1),
                        color="k", ls=styles[r["variant"]], lw=2,
                        label=f"C180 (nach hinten), {names[r['variant']]}")
    for r in results:
        ax.plot(r["gamma"], r["I"], "o" if not r["variant"] else "s", color=colors[r["h"]],
                ms=7, label=f"Person {r['h']:g} m, {names[r['variant']]}: {fmt(r['I'], 0)} cd")
    ax.set_xlabel("Ausstrahlungswinkel γ [°] (0 = senkrecht nach unten)")
    ax.set_ylabel("Lichtstärke [cd]")
    ax.set_title("LVK in der Ebene Leuchte – Person")
    ax.set_xlim(0, 120)
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=7.5, loc="lower left")

    ax = fig.add_subplot(gs[2, :])
    ax.axis("off")
    results = sorted(results, key=lambda r: (r["h"], r["variant"]))
    short = {"": "heute (3,4 %)", "perf50": "Lochung 50 %"}
    rows = [["", *[f"{r['h']:g} m – {short.get(r['variant'], r['variant'])}" for r in results]]]
    spec = [("Abstand Auge – Leuchte", lambda r: f"{fmt(r['d'], 2)} m"),
            ("Leuchte über Horizontale / Winkel zum Blick θ",
             lambda r: f"{fmt(r['elevation'])}° / {fmt(r['theta'])}°"),
            ("Ausstrahlungswinkel zur Person", lambda r: f"C180, γ = {fmt(r['gamma'])}°"),
            ("Lichtstärke zur Person I", lambda r: f"{fmt(r['I'], 0)} cd"),
            ("Sichtbarer Glasanteil (direkt + durch die Lochung)",
             lambda r: f"{r['visible_frac'] * 100:.0f} %"),
            ("Leuchtdichte sichtbares Glas (Mittel ganze Fläche)",
             lambda r: f"{fmt(r['L_visible'] / 1000, 0)} kcd/m² ({fmt(r['L_mean'] / 1000, 0)})"),
            ("E am Auge senkr. zum Blick / E_v vertikal",
             lambda r: f"{fmt(r['E_eye'], 2)} lx / {fmt(r['E_v'], 2)} lx"),
            ("Schleierleuchtdichte L_vl = 10·E_Auge/θ²", lambda r: f"{fmt(r['L_vl'], 3)} cd/m²"),
            ("E_h Boden Mittel (Direktlicht)", lambda r: f"{fmt(r['Eh_mean'], 0)} lx"),
            (f"L_ve = 0,035·ρ·E_h/π (ρ = {RHO_DEFAULT:.0%})",
             lambda r: f"{fmt(r['L_ve'], 2)} cd/m²"),
            ("GR bei ρ = 10 % / 20 % / 30 %",
             lambda r: " / ".join(fmt(r["GR_rho"][x], 1) for x in RHO_VARIANTS)),
            ("Störlicht I ≤ Richtwert vor Sperrzeit", lambda r: zones_ok(r["I"], 1)),
            ("Störlicht E_v ≤ Richtwert vor Sperrzeit", lambda r: zones_ok(r["E_v"], 3))]
    for name, f in spec:
        rows.append([name, *[f(r) for r in results]])
    n = len(results)
    table = ax.table(cellText=rows, loc="upper center", cellLoc="left",
                     colWidths=[0.32] + [0.68 / n] * n)
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    table.scale(1, 1.55)
    for (i, j), cell in table.get_celld().items():
        if i == 0:
            cell.set_text_props(weight="bold")
            cell.set_facecolor("#e8e8e8")
    ax.text(0.0, -0.14,
            "GR-Grenzwerte (Auswahl): Sport Wettkampf ≤ 50, Training ≤ 55 (EN 12193); Arbeitsstätten im "
            "Freien 45–55 (EN 12464-2). Bei 0 % Reflexion ist L_ve = 0 und GR nicht definiert.\n"
            "Störlicht-Richtwerte (EN 12464-2 / CIE 150) gelten für Fenster von Anwohnern und dienen "
            "hier nur zur Einordnung. UGR (EN 12464-1) ist für diese Anordnung nicht anwendbar "
            "(einzelne Flutlichtleuchte, kein Innenraum-Hintergrund bei 0 % Reflexion).",
            fontsize=8.5, transform=ax.transAxes, va="top")
    fig.savefig(os.path.join(DATA_DIR, "blendung.png"), bbox_inches="tight")
    plt.close(fig)


def zones_ok(value, idx):
    ok = [z[0].split()[0] for z in OBTRUSIVE if value <= z[idx]]
    return ("ja: " + ", ".join(ok)) if ok else "in keiner Zone"


if __name__ == "__main__":
    main()
