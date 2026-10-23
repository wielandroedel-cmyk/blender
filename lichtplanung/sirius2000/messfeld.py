"""
Messfeld vor der Stirnwand (8 m vor der Leuchte): vertikale Beleuchtungsstärke in Lux,
als Falschfarbenbild in der Szene plus Luxwerte im 1-m-Raster und Messbericht (PNG/CSV).

Ausführen (nach build_scene.py):
    blender --background sirius2000_raum.blend --python messfeld.py -- <ordner_mit_dateien>

Verfahren:
  1. Cycles backt auf eine Messfläche 2 cm vor der Wand die direkte und die gesamte
     (direkt + Interreflexion) diffuse Beleuchtung.
  2. Die direkte Beleuchtungsstärke wird zusätzlich exakt aus der LDT berechnet
     (E = I(C, gamma) * cos(eps) / d^2). Daraus folgt der Umrechnungsfaktor Cycles -> Lux,
     der dann auf das Gesamtergebnis angewendet wird.
"""

import csv
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
DATA_DIR = argv[0] if argv else os.path.dirname(bpy.data.filepath)
sys.path.insert(0, DATA_DIR)
from ldt2ies import read_ldt  # noqa: E402

LDT_PATH = os.path.join(DATA_DIR, "sirius2000.ldt")

ROOM_FRONT = 8.0
ROOM_WIDTH = 12.0
ROOM_HEIGHT = 7.0
FIELD_OFFSET = 0.02       # Abstand Messfläche - Wand [m]
TEXEL = 0.05              # Auflösung der Messfläche [m]
GRID = 1.0                # Raster der angezeigten Luxwerte [m]
BAKE_SAMPLES = 1024

# Klassengrenzen der Falschfarbendarstellung [lx]
LEVELS = [0, 5, 10, 25, 50, 75, 100, 150, 200, 300, 400, 500, 600]
# Farbverlauf (blau -> cyan -> grün -> gelb -> rot -> magenta), wird auf die Klassen verteilt.
STOPS = [(0.00, (0.10, 0.00, 0.35)), (0.15, (0.00, 0.20, 0.90)), (0.35, (0.00, 0.80, 0.90)),
         (0.50, (0.10, 0.80, 0.20)), (0.65, (0.95, 0.95, 0.10)), (0.82, (1.00, 0.45, 0.00)),
         (0.94, (0.90, 0.00, 0.00)), (1.00, (0.85, 0.00, 0.85))]


def ramp(t):
    for (t0, c0), (t1, c1) in zip(STOPS, STOPS[1:]):
        if t <= t1:
            f = (t - t0) / (t1 - t0)
            return tuple(a + (b - a) * f for a, b in zip(c0, c1))
    return STOPS[-1][1]


CLASS_COLORS = [ramp(i / (len(LEVELS) - 1)) for i in range(len(LEVELS))]


def classify(e):
    idx = np.searchsorted(np.array(LEVELS[1:]), e, side='right')
    return np.clip(idx, 0, len(LEVELS) - 1)


def srgb_to_linear(c):
    c = np.asarray(c)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# ---------------------------------------------------------------------------
# Direkte Beleuchtungsstärke aus der LDT
# ---------------------------------------------------------------------------

def ldt_intensity_table():
    d = read_ldt(LDT_PATH)
    flux = sum(s["flux"] * s["n"] for s in d["sets"])
    table = np.array([d["full"][ci] for ci in range(d["mc"])] + [d["full"][0]])
    table *= flux / 1000.0 * d["cfac"]  # cd
    c = np.array(d["c"] + [360.0])
    g = np.array(d["gamma"])
    return c, g, table


def direct_illuminance(points, normal, light_pos, c_axis, c90_axis, nadir):
    """points: (N,3), normal: Flächennormale (zur Leuchte hin). C0 = c_axis, C90 = c90_axis,
    gamma 0 = nadir (alle als Welt-Einheitsvektoren)."""
    c_vals, g_vals, table = ldt_intensity_table()
    v = points - light_pos
    dist = np.linalg.norm(v, axis=1)
    u = v / dist[:, None]
    gamma = np.degrees(np.arccos(np.clip(u @ nadir, -1, 1)))
    cang = np.degrees(np.arctan2(u @ c90_axis, u @ c_axis)) % 360.0
    # bilineare Interpolation in (C, gamma)
    ci = np.clip(np.searchsorted(c_vals, cang, side='right') - 1, 0, len(c_vals) - 2)
    gi = np.clip(np.searchsorted(g_vals, gamma, side='right') - 1, 0, len(g_vals) - 2)
    fc = (cang - c_vals[ci]) / (c_vals[ci + 1] - c_vals[ci])
    fg = (gamma - g_vals[gi]) / (g_vals[gi + 1] - g_vals[gi])
    i00, i01 = table[ci, gi], table[ci, gi + 1]
    i10, i11 = table[ci + 1, gi], table[ci + 1, gi + 1]
    intensity = (i00 * (1 - fc) * (1 - fg) + i10 * fc * (1 - fg) + i01 * (1 - fc) * fg +
                 i11 * fc * fg)
    cos_eps = np.clip(-(u @ normal), 0, None)
    return intensity * cos_eps / dist ** 2


def gaussian_blur(img, sigma):
    radius = int(3 * sigma)
    x = np.arange(-radius, radius + 1)
    k = np.exp(-x ** 2 / (2 * sigma ** 2))
    k /= k.sum()
    out = np.pad(img, radius, mode='edge')
    out = np.apply_along_axis(lambda r: np.convolve(r, k, mode='valid'), 1, out)
    out = np.apply_along_axis(lambda c: np.convolve(c, k, mode='valid'), 0, out)
    return out


# ---------------------------------------------------------------------------
# Szene
# ---------------------------------------------------------------------------

def remove_old():
    col = bpy.data.collections.get("Messfeld")
    if col:
        for o in list(col.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(col)
    for name in ("Messfeld_Falschfarben", "Messfeld_Legende", "Messfeld_Bake"):
        if name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[name])


def make_plane(name, width, height, location, rotation, collection):
    mesh = bpy.data.meshes.new(name)
    hw, hh = width / 2, height / 2
    mesh.from_pydata([(-hw, -hh, 0), (hw, -hh, 0), (hw, hh, 0), (-hw, hh, 0)], [],
                     [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name="UVMap")
    for loop, co in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop.uv = co
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.rotation_euler = rotation
    collection.objects.link(obj)
    return obj


def camera_only_material(name, image=None, color=(0, 0, 0), strength=1.0):
    """Nur für die Kamera sichtbar (Emission), für alle anderen Strahlen transparent:
    beeinflusst die Lichtberechnung nicht."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    path = nt.nodes.new("ShaderNodeLightPath")
    transp = nt.nodes.new("ShaderNodeBsdfTransparent")
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = strength
    if image is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.interpolation = 'Closest'
        nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
    else:
        emit.inputs["Color"].default_value = (*color, 1)
    nt.links.new(path.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(transp.outputs[0], mix.inputs[1])
    nt.links.new(emit.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def add_text(body, location, rotation, size, mat, collection, align='CENTER'):
    curve = bpy.data.curves.new("Lux_" + body, 'FONT')
    curve.body = body
    curve.size = size
    curve.align_x = align
    curve.align_y = 'CENTER'
    obj = bpy.data.objects.new("Lux_" + body, curve)
    obj.location = location
    obj.rotation_euler = rotation
    obj.data.materials.append(mat)
    obj.visible_shadow = False
    collection.objects.link(obj)
    return obj


def bake(obj, image, pass_filter):
    scene = bpy.context.scene
    mat = obj.data.materials[0]
    node = mat.node_tree.nodes["BakeTarget"]
    mat.node_tree.nodes.active = node
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    scene.render.bake.use_pass_color = False
    scene.render.bake.margin = 0
    bpy.ops.object.bake(type='DIFFUSE', pass_filter=pass_filter, margin=0,
                        use_clear=True)
    w, h = image.size
    px = np.empty(w * h * 4, dtype=np.float32)
    image.pixels.foreach_get(px)
    return px.reshape(h, w, 4)[:, :, 0].astype(np.float64)


def main():
    scene = bpy.context.scene
    remove_old()
    col = bpy.data.collections.new("Messfeld")
    scene.collection.children.link(col)

    nx, nz = int(round(ROOM_WIDTH / TEXEL)), int(round(ROOM_HEIGHT / TEXEL))
    y_field = ROOM_FRONT - FIELD_OFFSET
    # Normale der Messfläche zeigt zur Leuchte (-Y). Rx(90°): lokal +Z -> -Y, lokal +Y -> +Z.
    field = make_plane("Messfeld_Stirnwand", ROOM_WIDTH, ROOM_HEIGHT,
                       (0, y_field, ROOM_HEIGHT / 2), (math.radians(90), 0, 0), col)
    field.visible_shadow = False

    # --- Backen ---------------------------------------------------------------
    bake_img = bpy.data.images.new("Messfeld_Bake", nx, nz, float_buffer=True)
    bake_mat = bpy.data.materials.new("Messfeld_Bake")
    bake_mat.use_nodes = True
    tex = bake_mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.name = "BakeTarget"
    tex.image = bake_img
    bsdf = bake_mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (1, 1, 1, 1)
    field.data.materials.append(bake_mat)

    scene.render.engine = 'CYCLES'
    samples_before = scene.cycles.samples
    scene.cycles.samples = BAKE_SAMPLES
    direct_raw = bake(field, bake_img, {'DIRECT'})
    total_raw = bake(field, bake_img, {'DIRECT', 'INDIRECT'})
    scene.cycles.samples = samples_before

    # --- Direkte Beleuchtungsstärke aus der LDT --------------------------------
    light = bpy.data.objects["LVK_SIRIUS_2000"]
    mw = light.matrix_world
    rot = mw.to_3x3().normalized()
    light_pos = np.array(mw.translation)
    nadir = np.array(rot @ Vector((0, 0, -1)))
    c_axis = np.array(rot @ Vector((0, -1, 0)))    # Cycles-IES: C0 = lokal -Y
    c90_axis = np.array(rot @ Vector((-1, 0, 0)))  # C90 = lokal -X
    xs = -ROOM_WIDTH / 2 + (np.arange(nx) + 0.5) * TEXEL
    zs = (np.arange(nz) + 0.5) * TEXEL
    gx, gz = np.meshgrid(xs, zs)
    pts = np.stack([gx.ravel(), np.full(gx.size, y_field), gz.ravel()], axis=1)
    normal = np.array((0.0, -1.0, 0.0))  # Flächennormale der Messfläche, zur Leuchte hin
    e_direct = direct_illuminance(pts, normal, light_pos, c_axis, c90_axis, nadir)
    e_direct = e_direct.reshape(nz, nx)

    # Umrechnungsfaktor Cycles -> Lux aus Bereichen mit deutlichem Direktlicht.
    mask = (e_direct > 0.3 * e_direct.max()) & (direct_raw > 0)
    factor = float(np.median(e_direct[mask] / direct_raw[mask]))
    e_cycles_direct = direct_raw * factor
    dev = np.abs(e_cycles_direct[mask] - e_direct[mask]) / e_direct[mask]
    print(f"Faktor Cycles->lx: {factor:.2f}, "
          f"Abweichung direkt Cycles/LDT: median {np.median(dev) * 100:.1f} %")
    # Gesamt = exakter Direktanteil aus der LDT + geglätteter Indirektanteil aus Cycles
    # (Interreflexion ist von Natur aus weich, das Glätten entfernt nur das Sampling-Rauschen).
    e_indirect = gaussian_blur(np.clip(total_raw - direct_raw, 0, None) * factor, 4.0)
    e_total = e_direct + e_indirect
    print(f"Direkt: max {e_direct.max():.1f} lx, mittel {e_direct.mean():.1f} lx; "
          f"Indirekt: min {e_indirect.min():.1f}, max {e_indirect.max():.1f}, "
          f"mittel {e_indirect.mean():.1f} lx")

    # --- Falschfarbenbild in der Szene ----------------------------------------
    cls = classify(e_total)
    rgb = np.array(CLASS_COLORS)[cls]
    # Klassengrenzen als feine dunkle Isolinien
    edge = np.zeros_like(cls, dtype=bool)
    edge[:, 1:] |= cls[:, 1:] != cls[:, :-1]
    edge[1:, :] |= cls[1:, :] != cls[:-1, :]
    rgb[edge] *= 0.35
    fc_img = bpy.data.images.new("Messfeld_Falschfarben", nx, nz, alpha=True)
    rgba = np.concatenate([srgb_to_linear(rgb), np.ones((nz, nx, 1))], axis=2)
    fc_img.pixels.foreach_set(rgba.astype(np.float32).ravel())
    fc_img.pack()
    # Emission so stark, dass die Farben bei der Szenenbelichtung etwa 1:1 erscheinen.
    strength = 2.0 ** (-scene.view_settings.exposure)
    field.data.materials.clear()
    field.data.materials.append(camera_only_material("Messfeld_Falschfarben", fc_img,
                                                     strength=strength))
    bpy.data.images.remove(bake_img)
    bpy.data.materials.remove(bake_mat)

    # --- Luxwerte im Raster ---------------------------------------------------
    text_mat = camera_only_material("Messfeld_Text", color=(0, 0, 0))
    text_mat_light = camera_only_material("Messfeld_Text_hell_Feld", color=(1, 1, 1),
                                          strength=2.0 ** (-scene.view_settings.exposure))
    gxn, gzn = int(ROOM_WIDTH / GRID), int(ROOM_HEIGHT / GRID)
    per = int(round(GRID / TEXEL))
    grid_vals = np.zeros((gzn, gxn))
    for j in range(gzn):
        for i in range(gxn):
            # Wert im Rasterpunkt (Mittel der 2x2 Texel um den Zellmittelpunkt)
            cj, ci = j * per + per // 2, i * per + per // 2
            grid_vals[j, i] = e_total[cj - 1:cj + 1, ci - 1:ci + 1].mean()
            x = -ROOM_WIDTH / 2 + (i + 0.5) * GRID
            z = (j + 0.5) * GRID
            # helle Schrift auf den dunklen Klassen, sonst schwarz
            tm = text_mat_light if classify(grid_vals[j, i]) <= 3 else text_mat
            add_text(f"{grid_vals[j, i]:.0f}", (x, y_field - 0.01, z),
                     (math.radians(90), 0, 0), 0.22, tm, col)
            add_text("+", (x, y_field - 0.01, z - 0.17), (math.radians(90), 0, 0), 0.1,
                     tm, col)

    # Achsbeschriftung des Messfelds: Höhe links, Position x oben
    for z in range(1, int(ROOM_HEIGHT)):
        tm = text_mat_light if e_total[int(z / TEXEL), 0] < LEVELS[4] else text_mat
        add_text(f"— {z} m", (-ROOM_WIDTH / 2 + 0.05, y_field - 0.01, z),
                 (math.radians(90), 0, 0), 0.16, tm, col, align='LEFT')
    for x in range(-int(ROOM_WIDTH / 2) + 1, int(ROOM_WIDTH / 2)):
        tm = text_mat_light if e_total[-1, int((x + ROOM_WIDTH / 2) / TEXEL)] < LEVELS[4] \
            else text_mat
        add_text(f"{x:+d} m" if x else "0 m", (x, y_field - 0.01, ROOM_HEIGHT - 0.15),
                 (math.radians(90), 0, 0), 0.16, tm, col)

    # --- Legende an der rechten Seitenwand, nahe der Stirnwand -------------------
    leg_h = 4.8
    leg_n = len(LEVELS)
    leg_img = bpy.data.images.new("Messfeld_Legende", 1, leg_n, alpha=True)
    leg_px = np.concatenate([srgb_to_linear(np.array(CLASS_COLORS)),
                             np.ones((leg_n, 1))], axis=1)
    leg_img.pixels.foreach_set(leg_px.astype(np.float32).ravel())
    leg_img.pack()
    xw = ROOM_WIDTH / 2 - 0.02
    leg = make_plane("Messfeld_Legende", 0.35, leg_h, (xw, ROOM_FRONT - 1.0, 1.0 + leg_h / 2),
                     (math.radians(90), 0, math.radians(90)), col)
    leg.data.materials.append(camera_only_material("Messfeld_Legende", leg_img,
                                                   strength=strength))
    leg.visible_shadow = False
    white = camera_only_material("Messfeld_Text_hell", color=(1, 1, 1), strength=strength)
    for k, lv in enumerate(LEVELS):
        z = 1.0 + (k + 0.5) * leg_h / leg_n
        label = f"≥ {lv} lx" if k else f"< {LEVELS[1]} lx"
        add_text(label, (xw - 0.01, ROOM_FRONT - 1.25, z), (math.radians(90), 0,
                 math.radians(90)), 0.16, white, col, align='RIGHT')
    add_text("Ev Stirnwand [lx]", (xw - 0.01, ROOM_FRONT - 1.0, 1.0 + leg_h + 0.3),
             (math.radians(90), 0, math.radians(90)), 0.2, white, col)

    # Kamera frontal auf das Messfeld
    cam = bpy.data.objects.get("Messfeld_Kamera")
    if cam is None:
        cam = bpy.data.objects.new("Messfeld_Kamera", bpy.data.cameras.new("Messfeld_Kamera"))
        col.objects.link(cam)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = ROOM_WIDTH + 0.4
    cam.location = (0, 0.5, ROOM_HEIGHT / 2)
    cam.rotation_euler = (math.radians(90), 0, 0)

    # --- Messbericht ----------------------------------------------------------
    stats = dict(Emin=e_total.min(), Emax=e_total.max(), Emittel=e_total.mean(),
                 Edirekt_mittel=e_direct.mean(), Eindirekt_mittel=e_indirect.mean())
    stats["U0"] = stats["Emin"] / stats["Emittel"] if stats["Emittel"] > 0 else 0
    print("Messfeld Stirnwand: " + ", ".join(f"{k} {v:.2f}" for k, v in stats.items()))
    with open(os.path.join(DATA_DIR, "messfeld_stirnwand.csv"), "w", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Hoehe z [m] / Position x [m]"] +
                   [f"{-ROOM_WIDTH / 2 + (i + 0.5) * GRID:.1f}" for i in range(gxn)])
        for j in reversed(range(gzn)):
            w.writerow([f"{(j + 0.5) * GRID:.1f}"] + [f"{v:.1f}" for v in grid_vals[j]])
    try:
        write_report(e_total, grid_vals, stats)
    except ImportError:
        print("matplotlib nicht verfügbar, kein PNG-Bericht")

    bpy.ops.wm.save_mainfile(compress=True)
    print("Gespeichert:", bpy.data.filepath)


def room_reflectance():
    mat = bpy.data.materials.get("Wand")
    if mat is None or not mat.node_tree:
        return float('nan')
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    return bsdf.inputs["Base Color"].default_value[0]


def write_report(e_total, grid_vals, stats):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap

    cmap = ListedColormap(CLASS_COLORS)
    bounds = LEVELS + [LEVELS[-1] * 2]
    norm = BoundaryNorm(bounds, cmap.N)
    fig, ax = plt.subplots(figsize=(13, 8.2), dpi=130)
    ext = (-ROOM_WIDTH / 2, ROOM_WIDTH / 2, 0, ROOM_HEIGHT)
    im = ax.imshow(e_total, origin="lower", extent=ext, cmap=cmap, norm=norm,
                   interpolation="nearest")
    xs = -ROOM_WIDTH / 2 + (np.arange(e_total.shape[1]) + 0.5) * TEXEL
    zs = (np.arange(e_total.shape[0]) + 0.5) * TEXEL
    ax.contour(xs, zs, e_total, levels=LEVELS[1:], colors="k", linewidths=0.4)
    gzn, gxn = grid_vals.shape
    for j in range(gzn):
        for i in range(gxn):
            x, z = -ROOM_WIDTH / 2 + (i + 0.5) * GRID, (j + 0.5) * GRID
            ax.plot(x, z, "k+", ms=5, mew=0.8)
            ax.text(x, z + 0.18, f"{grid_vals[j, i]:.0f}", ha="center", va="bottom",
                    fontsize=9, weight="bold")
    ax.axhline(5.0, color="w", ls="--", lw=0.8)
    ax.text(ROOM_WIDTH / 2 - 0.1, 5.05, "Montagehöhe Leuchte 5 m", color="w", ha="right",
            va="bottom", fontsize=8)
    ax.set_xlabel("Position x an der Stirnwand [m] (0 = Achse der Leuchte)")
    ax.set_ylabel("Höhe z [m]")
    ax.set_title("Vertikale Beleuchtungsstärke Ev auf der Stirnwand (8 m vor der Leuchte)\n"
                 "Siteco SIRIUS 2000, 5XA7100W40A13DA-Z mit außenliegender Blende V2, "
                 f"222.492 lm, Montagehöhe 5 m, Reflexionsgrad Raum {room_reflectance():.0%}",
                 fontsize=11)
    cb = fig.colorbar(im, ax=ax, ticks=LEVELS, fraction=0.03, pad=0.02)
    cb.set_label("Ev [lx]")
    txt = (f"Emin = {stats['Emin']:.1f} lx   Emittel = {stats['Emittel']:.1f} lx   "
           f"Emax = {stats['Emax']:.1f} lx   U0 = Emin/Emittel = {stats['U0']:.2f}\n"
           f"davon direkt (aus LDT) im Mittel {stats['Edirekt_mittel']:.1f} lx, "
           f"indirekt (Interreflexion, Cycles) im Mittel {stats['Eindirekt_mittel']:.1f} lx. "
           f"Werte im 1-m-Raster, Messfläche 2 cm vor der Wand")
    fig.text(0.07, 0.015, txt, fontsize=9)
    fig.subplots_adjust(bottom=0.14)
    fig.savefig(os.path.join(DATA_DIR, "messfeld_stirnwand.png"))
    plt.close(fig)


if __name__ == "__main__":
    main()
