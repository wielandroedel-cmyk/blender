"""
Messfeld vor einer Wand: vertikale Beleuchtungsstärke in Lux, als Falschfarbenbild in der
Szene plus Luxwerte im 1-m-Raster und Messbericht (PNG/CSV).

Standard ist die Rückwand hinter der Person (2 m hinter ihr, 10 m hinter der Leuchte), also
die Seite, die die außenliegende Blende abschirmt. Mit "stirnwand" als zweitem Argument
wird stattdessen die Wand 8 m vor der Leuchte ausgewertet.

Ausführen (nach build_scene.py):
    blender --background sirius1000_raum_5m.blend --python messfeld.py -- <ordner> [rueckwand|stirnwand]

Raumgeometrie und Montagehöhe werden aus der Szene gelesen (von build_scene.py abgelegt),
Ergebnisdateien: messfeld_<wand>_<hoehe>m.png / .csv

Verfahren:
  1. Cycles backt auf eine Messfläche 2 cm vor der Wand die direkte und die gesamte
     (direkt + Interreflexion) diffuse Beleuchtung.
  2. Die direkte Beleuchtungsstärke wird zusätzlich exakt aus der LDT berechnet
     (E = I(C, gamma) * cos(eps) / d^2). Daraus folgt der Umrechnungsfaktor Cycles -> Lux,
     der dann auf das Gesamtergebnis angewendet wird.
"""

import csv
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
DATA_DIR = argv[0] if argv else os.path.dirname(bpy.data.filepath)
sys.path.insert(0, DATA_DIR)
from ldt2ies import read_ies  # noqa: E402

_scene = bpy.context.scene
# Dieselbe IES-Datei wie das Licht in der Szene (absolute Werte in cd).
IES_PATH = os.path.join(DATA_DIR, _scene.get("ies_file", "sirius1000.ies"))
VARIANT = _scene.get("variant", "")
VARIANT_TEXT = {"": "Blende V2 wie geliefert (Lochung 3,4 %)",
                "perf50": "Blende V2 mit 50 % Lochung (LVK abgeschätzt)"}.get(VARIANT, VARIANT)
MOUNT_HEIGHT = float(_scene.get("mount_height", 5.0))
ROOM_FRONT = float(_scene.get("room_front", 8.0))
ROOM_BACK = float(_scene.get("room_back", -10.0))  # y der Rückwand
PERSON_DISTANCE = float(_scene.get("person_distance", 8.0))
ROOM_WIDTH = float(_scene.get("room_width", 12.0))
ROOM_HEIGHT = float(_scene.get("room_height", 7.0))

WALL = argv[1] if len(argv) > 1 else "rueckwand"
if WALL == "stirnwand":
    WALL_Y = ROOM_FRONT
    WALL_NORMAL = Vector((0, -1, 0))  # zeigt in den Raum, zur Leuchte
    WALL_TITLE = f"Stirnwand ({ROOM_FRONT:g} m vor der Leuchte)"
    WALL_NAME = "Stirnwand"
else:
    WALL = "rueckwand"
    WALL_Y = ROOM_BACK
    WALL_NORMAL = Vector((0, 1, 0))
    WALL_TITLE = (f"Rückwand hinter der Person ({-ROOM_BACK:g} m hinter der Leuchte, "
                  f"{-ROOM_BACK - PERSON_DISTANCE:g} m hinter der Person)")
    WALL_NAME = "Rückwand"
UP = Vector((0, 0, 1))
# "rechts" für einen Betrachter, der auf die Wand blickt
WALL_RIGHT = (-WALL_NORMAL).cross(UP)
SUFFIX = f"_{WALL}_{MOUNT_HEIGHT:g}m" + (f"_{VARIANT}" if VARIANT else "")
FIELD_OFFSET = 0.02       # Abstand Messfläche - Wand [m]
TEXEL = 0.05              # Auflösung der Messfläche [m]
GRID = 1.0                # Raster der angezeigten Luxwerte [m]
BAKE_SAMPLES = 1024

# Klassengrenzen der Falschfarbendarstellung [lx]; werden nach der Rechnung an Emax angepasst.
LEVELS = [0, 5, 10, 25, 50, 75, 100, 150, 200, 300, 400, 500, 600]
NICE_LEVELS = [0.1, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5, 7.5, 10, 15, 20, 30, 50, 75, 100,
               150, 200, 300, 400, 500, 600, 800, 1000, 1500, 2000]
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


def set_levels(e_max):
    """Bis zu 13 Klassen von 0 bis knapp über Emax aus einer 1-2-3-5-Reihe."""
    global LEVELS, CLASS_COLORS
    upper = [v for v in NICE_LEVELS if v <= e_max * 1.05]
    LEVELS = [0] + upper[-12:]
    CLASS_COLORS = [ramp(i / (len(LEVELS) - 1)) for i in range(len(LEVELS))]


def fmt_lx(v):
    return f"{v:.1f}" if v < 10 else f"{v:.0f}"


def wall_matrix():
    """Rotation: lokal X -> rechts, lokal Y -> oben, lokal Z -> Wandnormale (in den Raum)."""
    from mathutils import Matrix
    return Matrix((WALL_RIGHT, UP, WALL_NORMAL)).transposed()


def wall_point(u, z, offset):
    """Punkt auf der Messfläche: u nach rechts (Blick auf die Wand), z Höhe über Boden."""
    return (Vector((0, WALL_Y, 0)) + WALL_RIGHT * u + UP * z + WALL_NORMAL * offset)


def classify(e):
    idx = np.searchsorted(np.array(LEVELS[1:]), e, side='right')
    return np.clip(idx, 0, len(LEVELS) - 1)


def srgb_to_linear(c):
    c = np.asarray(c)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# ---------------------------------------------------------------------------
# Direkte Beleuchtungsstärke aus der LVK (IES)
# ---------------------------------------------------------------------------

def ldt_intensity_table():
    c, g, table, _flux, _name = read_ies(IES_PATH)
    return np.array(c), np.array(g), np.array(table)  # table in cd, [C, gamma]


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


def make_plane(name, width, height, location, rotation, collection, matrix=None):
    mesh = bpy.data.meshes.new(name)
    hw, hh = width / 2, height / 2
    mesh.from_pydata([(-hw, -hh, 0), (hw, -hh, 0), (hw, hh, 0), (-hw, hh, 0)], [],
                     [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name="UVMap")
    for loop, co in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop.uv = co
    obj = bpy.data.objects.new(name, mesh)
    if matrix is not None:
        obj.matrix_world = matrix
    else:
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


def add_text(body, location, rotation, size, mat, collection, align='CENTER', matrix=None):
    curve = bpy.data.curves.new("Lux_" + body, 'FONT')
    curve.body = body
    curve.size = size
    curve.align_x = align
    curve.align_y = 'CENTER'
    obj = bpy.data.objects.new("Lux_" + body, curve)
    if matrix is not None:
        obj.matrix_world = matrix
    obj.location = location
    if matrix is None:
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
    rot = wall_matrix().to_4x4()
    field_matrix = rot.copy()
    field_matrix.translation = wall_point(0, ROOM_HEIGHT / 2, FIELD_OFFSET)
    field = make_plane(f"Messfeld_{WALL_NAME}", ROOM_WIDTH, ROOM_HEIGHT, None, None, col,
                       matrix=field_matrix)
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
    light = bpy.data.objects["LVK_SIRIUS_1000"]
    mw = light.matrix_world
    lrot = mw.to_3x3().normalized()
    light_pos = np.array(mw.translation)
    nadir = np.array(lrot @ Vector((0, 0, -1)))
    c_axis = np.array(lrot @ Vector((0, -1, 0)))    # Cycles-IES: C0 = lokal -Y
    c90_axis = np.array(lrot @ Vector((-1, 0, 0)))  # C90 = lokal -X
    us = -ROOM_WIDTH / 2 + (np.arange(nx) + 0.5) * TEXEL
    zs = (np.arange(nz) + 0.5) * TEXEL
    gu, gz = np.meshgrid(us, zs)
    origin = np.array(wall_point(0, 0, FIELD_OFFSET))
    pts = (origin + gu.ravel()[:, None] * np.array(WALL_RIGHT) +
           gz.ravel()[:, None] * np.array(UP))
    normal = np.array(WALL_NORMAL)  # Flächennormale der Messfläche, in den Raum
    e_direct = direct_illuminance(pts, normal, light_pos, c_axis, c90_axis, nadir)
    e_direct = e_direct.reshape(nz, nx)

    # Umrechnungsfaktor Cycles -> Lux aus Bereichen mit deutlichem Direktlicht.
    # (Die Person wirft dabei in Cycles einen Schatten, die LDT-Rechnung nicht; der Median
    # über die hellen Bereiche ist dagegen robust.)
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
    set_levels(float(e_total.max()))
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
            u = -ROOM_WIDTH / 2 + (i + 0.5) * GRID
            z = (j + 0.5) * GRID
            # helle Schrift auf den dunklen Klassen, sonst schwarz
            tm = text_mat_light if classify(grid_vals[j, i]) <= 3 else text_mat
            add_text(fmt_lx(grid_vals[j, i]), wall_point(u, z, FIELD_OFFSET + 0.01), None, 0.22,
                     tm, col, matrix=rot)
            add_text("+", wall_point(u, z - 0.17, FIELD_OFFSET + 0.01), None, 0.1, tm, col,
                     matrix=rot)

    # Achsbeschriftung des Messfelds: Höhe links, Welt-x oben (0 = Achse der Leuchte)
    for z in range(1, int(ROOM_HEIGHT)):
        tm = text_mat_light if classify(e_total[int(z / TEXEL), 0]) <= 3 else text_mat
        add_text(f"— {z} m", wall_point(-ROOM_WIDTH / 2 + 0.05, z, FIELD_OFFSET + 0.01), None,
                 0.16, tm, col, align='LEFT', matrix=rot)
    for k in range(-int(ROOM_WIDTH / 2) + 1, int(ROOM_WIDTH / 2)):
        u = float(k)
        x_world = round(u * WALL_RIGHT.x)
        tm = text_mat_light if classify(e_total[-1, int((u + ROOM_WIDTH / 2) / TEXEL)]) <= 3 \
            else text_mat
        add_text(f"x {x_world:+d} m" if x_world else "x 0 m",
                 wall_point(u, ROOM_HEIGHT - 0.15, FIELD_OFFSET + 0.01), None, 0.16, tm, col,
                 matrix=rot)

    # --- Legende an der rechten Seitenwand (Blick auf die Messwand), 1 m vor ihr ---
    leg_h = 4.8
    leg_n = len(LEVELS)
    leg_img = bpy.data.images.new("Messfeld_Legende", 1, leg_n, alpha=True)
    leg_px = np.concatenate([srgb_to_linear(np.array(CLASS_COLORS)),
                             np.ones((leg_n, 1))], axis=1)
    leg_img.pixels.foreach_set(leg_px.astype(np.float32).ravel())
    leg_img.pack()
    from mathutils import Matrix
    # Seitenwand rechts: Normale -WALL_RIGHT; "rechts" für den Blick auf diese Seitenwand.
    side_n = -WALL_RIGHT
    side_r = (-side_n).cross(UP)
    side_rot = Matrix((side_r, UP, side_n)).transposed().to_4x4()
    base = (WALL_RIGHT * (ROOM_WIDTH / 2 - 0.02) + Vector((0, WALL_Y, 0)) +
            WALL_NORMAL * 1.0)
    leg_m = side_rot.copy()
    leg_m.translation = base + UP * (1.0 + leg_h / 2)
    leg = make_plane("Messfeld_Legende", 0.35, leg_h, None, None, col, matrix=leg_m)
    leg.data.materials.append(camera_only_material("Messfeld_Legende", leg_img,
                                                   strength=strength))
    leg.visible_shadow = False
    white = camera_only_material("Messfeld_Text_hell", color=(1, 1, 1), strength=strength)
    for k, lv in enumerate(LEVELS):
        z = 1.0 + (k + 0.5) * leg_h / leg_n
        label = f"≥ {lv:g} lx" if k else f"< {LEVELS[1]:g} lx"
        add_text(label, base + side_n * 0.01 - side_r * 0.25 + UP * z, None, 0.16, white, col,
                 align='RIGHT', matrix=side_rot)
    add_text(f"Ev {WALL_NAME} [lx]", base + side_n * 0.01 + UP * (1.0 + leg_h + 0.3), None,
             0.2, white, col, matrix=side_rot)

    # Kamera frontal auf das Messfeld
    cam = bpy.data.objects.get("Messfeld_Kamera")
    if cam is None:
        cam = bpy.data.objects.new("Messfeld_Kamera", bpy.data.cameras.new("Messfeld_Kamera"))
        col.objects.link(cam)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = max(ROOM_WIDTH, ROOM_HEIGHT * 16 / 9) + 0.4
    cam_m = rot.copy()  # Kamera blickt entlang -lokal Z, also auf die Wand
    cam_m.translation = wall_point(0, ROOM_HEIGHT / 2, 0.6)
    cam.matrix_world = cam_m

    # --- Messbericht ----------------------------------------------------------
    stats = dict(Emin=e_total.min(), Emax=e_total.max(), Emittel=e_total.mean(),
                 Edirekt_mittel=e_direct.mean(), Eindirekt_mittel=e_indirect.mean())
    stats["U0"] = stats["Emin"] / stats["Emittel"] if stats["Emittel"] > 0 else 0
    print(f"Messfeld {WALL_NAME}: " + ", ".join(f"{k} {v:.2f}" for k, v in stats.items()))
    with open(os.path.join(DATA_DIR, f"messfeld{SUFFIX}.csv"), "w", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([f"{WALL_NAME}: Hoehe z [m] / Position x [m] (Blick auf die Wand)"] +
                   [f"{(-ROOM_WIDTH / 2 + (i + 0.5) * GRID) * WALL_RIGHT.x:.1f}"
                    for i in range(gxn)])
        for j in reversed(range(gzn)):
            w.writerow([f"{(j + 0.5) * GRID:.1f}"] + [f"{v:.1f}" for v in grid_vals[j]])
    try:
        write_report(e_total, grid_vals, stats)
    except ImportError:
        print("matplotlib nicht verfügbar, kein PNG-Bericht")

    bpy.ops.wm.save_mainfile(compress=True)
    print("Gespeichert:", bpy.data.filepath)


def ies_flux():
    return read_ies(IES_PATH)[3]


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
    fig, ax = plt.subplots(figsize=(13, 3.2 + 0.72 * ROOM_HEIGHT), dpi=130)
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
            ax.text(x, z + 0.18, fmt_lx(grid_vals[j, i]), ha="center", va="bottom",
                    fontsize=9, weight="bold")
    ax.axhline(MOUNT_HEIGHT, color="w", ls="--", lw=0.8)
    ax.text(ROOM_WIDTH / 2 - 0.1, MOUNT_HEIGHT + 0.05, f"Montagehöhe Leuchte {MOUNT_HEIGHT:g} m",
            color="w", ha="right", va="bottom", fontsize=8)
    ticks = list(range(-int(ROOM_WIDTH / 2), int(ROOM_WIDTH / 2) + 1, 2))
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{round(t * WALL_RIGHT.x):g}" for t in ticks])
    ax.set_xlabel(f"Position x [m], Blick auf die {WALL_NAME} (0 = Achse der Leuchte)")
    ax.set_ylabel("Höhe z [m]")
    ax.set_title(f"Vertikale Beleuchtungsstärke Ev auf der {WALL_TITLE}\n"
                 f"Siteco SIRIUS 1000 (1 Modul), {VARIANT_TEXT}\n" +
                 f"{ies_flux():,.0f}".replace(",", ".") +
                 f" lm, Montagehöhe {MOUNT_HEIGHT:g} m, "
                 f"Reflexionsgrad Raum {room_reflectance():.0%}",
                 fontsize=11)
    cb = fig.colorbar(im, ax=ax, ticks=LEVELS, fraction=0.03, pad=0.02, format="%g")
    cb.set_label("Ev [lx]")
    txt = (f"Emin = {stats['Emin']:.2f} lx   Emittel = {stats['Emittel']:.2f} lx   "
           f"Emax = {stats['Emax']:.2f} lx   U0 = Emin/Emittel = {stats['U0']:.2f}\n"
           f"davon direkt (aus LDT) im Mittel {stats['Edirekt_mittel']:.2f} lx, "
           f"indirekt (Interreflexion, Cycles) im Mittel {stats['Eindirekt_mittel']:.2f} lx. "
           f"Werte im 1-m-Raster, Messfläche 2 cm vor der Wand; Person nicht als Hindernis "
           f"berücksichtigt")
    fig.text(0.07, 0.015, txt, fontsize=9)
    fig.subplots_adjust(bottom=0.14)
    fig.savefig(os.path.join(DATA_DIR, f"messfeld{SUFFIX}.png"))
    plt.close(fig)


if __name__ == "__main__":
    main()
