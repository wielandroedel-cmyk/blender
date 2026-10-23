"""Convert an EULUMDAT (.ldt) file to IESNA LM-63-2002 (.ies) for Cycles.

    python ldt2ies.py eingabe.ldt ausgabe.ies [modulfaktor] [name]

Der optionale Modulfaktor skaliert Lichtstrom, Leistung und Länge der Lichtaustrittsfläche,
z. B. 0.5 für ein Modul (SIRIUS 1000) aus der LDT einer Leuchte mit zwei Modulen
(SIRIUS 2000). Die relative Lichtverteilung (cd/klm) bleibt dabei unverändert.
"""
import sys


def read_ldt(path):
    lines = [l.strip() for l in open(path, encoding="latin-1").read().splitlines()]
    g = lambda i: lines[i - 1]  # 1-based line numbers as in the EULUMDAT spec
    d = dict(
        company=g(1), ityp=int(g(2)), isym=int(g(3)), mc=int(g(4)), dc=float(g(5)),
        ng=int(g(6)), dg=float(g(7)), name=g(9), number=g(10),
        length=float(g(13)), width=float(g(14)), height=float(g(15)),
        lum_len=float(g(16)), lum_wid=float(g(17)),
        dff=float(g(22)), lorl=float(g(23)), cfac=float(g(24)), nsets=int(g(26)),
    )
    i = 27
    sets = []
    for _ in range(d["nsets"]):
        sets.append(dict(n=int(g(i)), type=g(i + 1), flux=float(g(i + 2)), cct=g(i + 3),
                         cri=g(i + 4), watt=float(g(i + 5))))
        i += 6
    d["sets"] = sets
    i += 10  # direct ratios
    d["c"] = [float(g(i + k)) for k in range(d["mc"])]
    i += d["mc"]
    d["gamma"] = [float(g(i + k)) for k in range(d["ng"])]
    i += d["ng"]
    isym, mc = d["isym"], d["mc"]
    if isym == 0:
        c_stored = list(range(mc))
    elif isym == 1:
        c_stored = [0]
    elif isym == 2:  # symmetry about C0-C180
        c_stored = list(range(mc // 2 + 1))
    elif isym == 3:  # symmetry about C90-C270
        c_stored = list(range(3 * mc // 4, mc)) + list(range(0, mc // 4 + 1))
    else:  # isym == 4
        c_stored = list(range(mc // 4 + 1))
    data = {}
    for ci in c_stored:
        data[ci] = [float(g(i + k)) for k in range(d["ng"])]
        i += d["ng"]
    # Expand to full 0..360 by symmetry.
    full = {}
    for ci in range(mc):
        c = d["c"][ci]
        if isym == 1:
            src = 0
        elif isym == 2:
            src = ci if c <= 180 else mc - ci
        elif isym == 3:
            mirror = (180 - c) % 360
            src = ci if ci in data else int(round(mirror / d["dc"])) % mc
        elif isym == 4:
            cc = c % 180
            cc = cc if cc <= 90 else 180 - cc
            src = int(round(cc / d["dc"]))
        else:
            src = ci
        full[ci] = data[src]
    d["full"] = full
    return d


def scale_modules(d, factor, name=None):
    """Lichtstrom, Leistung und leuchtende Länge auf einen Teil der Module skalieren."""
    for s in d["sets"]:
        s["flux"] *= factor
        s["watt"] *= factor
    d["lum_len"] *= factor
    d["length"] *= factor
    d["module_factor"] = factor
    if name:
        d["name"] = name
    return d


def write_ies(d, path):
    flux = sum(s["flux"] * s["n"] for s in d["sets"])
    scale = flux / 1000.0 * d["cfac"]  # cd/klm -> cd
    c_vals = d["c"] + [360.0]
    rows = [d["full"][ci] for ci in range(d["mc"])] + [d["full"][0]]
    out = [
        "IESNA:LM-63-2002",
        f"[MANUFAC] {d['company']}",
        f"[LUMCAT] {d['number']}",
        f"[LUMINAIRE] {d['name']}",
        f"[LAMP] {d['sets'][0]['type']} {d['sets'][0]['cct']} {d['sets'][0]['cri']}",
        "[OTHER] Converted from EULUMDAT"
        + (f", module factor {d['module_factor']:g} applied to flux, power and length"
           if d.get("module_factor", 1) != 1 else ""),
        "TILT=NONE",
        # lamps, lumens/lamp, multiplier, n vert, n horiz, photometric type C,
        # units meters, width, length, height (luminous opening)
        f"1 {flux:.0f} 1 {len(d['gamma'])} {len(c_vals)} 1 2 "
        f"{d['lum_wid'] / 1000:.3f} {d['lum_len'] / 1000:.3f} 0",
        f"1 1 {d['sets'][0]['watt']:.1f}",
        " ".join(f"{g:g}" for g in d["gamma"]),
        " ".join(f"{c:g}" for c in c_vals),
    ]
    for r in rows:
        out.append(" ".join(f"{v * scale:.2f}" for v in r))
    open(path, "w").write("\n".join(out) + "\n")


def read_ies(path):
    """Liest eine mit write_ies erzeugte IES-Datei (Typ C): C-Winkel, gamma-Winkel,
    Lichtstärken in cd als Tabelle [C, gamma], Lichtstrom und Leuchtenname."""
    lines = open(path, encoding="latin-1").read().splitlines()
    name = next((l[12:].strip() for l in lines if l.startswith("[LUMINAIRE]")), "")
    tilt = next(i for i, l in enumerate(lines) if l.startswith("TILT="))
    tok = " ".join(lines[tilt + 1:]).split()
    lamps, lumens, mult, nv, nh = (float(t) for t in tok[:5])
    nv, nh = int(nv), int(nh)
    i = 10 + 3  # 10 Werte Kopfzeile + Ballast, Ballast-Photometrie, Leistung
    gamma = [float(t) for t in tok[i:i + nv]]
    i += nv
    c = [float(t) for t in tok[i:i + nh]]
    i += nh
    table = [[float(t) * mult for t in tok[i + k * nv:i + (k + 1) * nv]] for k in range(nh)]
    return c, gamma, table, lamps * lumens, name


if __name__ == "__main__":
    d = read_ldt(sys.argv[1])
    if len(sys.argv) > 3:
        scale_modules(d, float(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else None)
    write_ies(d, sys.argv[2])
    peak = max((max(r), d["c"][ci], d["gamma"][r.index(max(r))]) for ci, r in d["full"].items())
    flux = sum(s["flux"] * s["n"] for s in d["sets"])
    print(f"{d['name']}: {flux:.0f} lm, peak {peak[0]:.1f} cd/klm = {peak[0]*flux/1000:.0f} cd "
          f"at C{peak[1]:g} gamma{peak[2]:g}; Isym={d['isym']}")
