"""
Blender-Szene: Siteco SIRIUS 1000 (ein Modul; LVK aus 5XA7100W40A13DA-Z SIRIUS 2000,
außenliegende Blende V2, Lichtstrom und Leistung halbiert)
frei im Raum in 5 m Höhe, sitzende Person 8 m hinter der Leuchte, Raum 8 m nach vorn.

Ausführen (Blender 4.2+ / 5.x):
    blender --background --python build_scene.py -- <ordner_mit_dateien> [montagehoehe_m] [variante]
    (Montagehöhe Standard 5 m; Raumhöhe = Montagehöhe + 2 m. Variante "perf50" = Blende mit
     50 % Lochung, nutzt sirius1000_perf50.glb/.ies aus perforation.py. Ergebnis:
     sirius1000[_perf50]_raum_<hoehe>m.blend)
oder im Blender-Text-Editor öffnen und "Run Script" (dann DATA_DIR unten anpassen).

Benötigte Dateien im Ordner:
    sirius1000.glb   (aus der STEP-Datei konvertiert, siehe step2glb.py)
    sirius1000.ies   (aus der LDT-Datei konvertiert, ein Modul:
                      python ldt2ies.py sirius2000.ldt sirius1000.ies 0.5 SIRIUS_1000)

Danach optional das Messfeld an der Stirnwand berechnen (Falschfarben + Luxwerte):
    blender --background sirius1000_raum_5m.blend --python messfeld.py -- <ordner_mit_dateien>

Rendern nur mit Cycles (EEVEE unterstützt keine IES-Lichtverteilungen).

Koordinaten (Meter, Z oben):
    Leuchte (Mitte Lichtaustrittsfläche/Glas): (0, 0, Montagehöhe)
    Person (Sitzposition):                     (0, -8, 0), Blick nach +Y
    Lichtrichtung: nach vorn = +Y, also von der Person weg.
"""

import math
import os
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

# ---------------------------------------------------------------------------
# Parameter
# ---------------------------------------------------------------------------

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
DATA_DIR = argv[0] if argv else os.path.dirname(os.path.abspath(__file__))
VARIANT = argv[2] if len(argv) > 2 else ""   # "" = Blende wie geliefert, "perf50" = 50 % Lochung
_base = "sirius1000" + (f"_{VARIANT}" if VARIANT else "")
GLB_PATH = os.path.join(DATA_DIR, _base + ".glb")
IES_PATH = os.path.join(DATA_DIR, _base + ".ies")

MOUNT_HEIGHT = float(argv[1]) if len(argv) > 1 else 5.0  # Höhe Glasmitte über Boden [m]
PERSON_DISTANCE = 8.0     # Person sitzt so weit hinter der Leuchte [m]
ROOM_FRONT = 8.0          # Raumtiefe vor der Leuchte [m]
ROOM_BEHIND_PERSON = 2.0  # Raum hinter der Person [m]
ROOM_WIDTH = 12.0         # [m]
ROOM_HEIGHT = MOUNT_HEIGHT + 2.0  # [m], 2 m Luft über der Leuchte
TILT_DEG = 0.0            # Neigung der Leuchte nach vorn (0 = Glas horizontal, wie gemessen)
EYE_HEIGHT_SEATED = 1.2   # Augenhöhe der sitzenden Person [m]
REFLECTANCE = 0.0         # Reflexionsgrad Boden, Wände, Decke (0 = nur Direktlicht)



# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'METERS'
    return scene


def new_collection(name, parent=None):
    col = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(col)
    return col


def diffuse_material(name, color, roughness=0.8, specular=0.5):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    # 0 = rein diffus, der Reflexionsgrad entspricht dann genau der Grundfarbe.
    bsdf.inputs["Specular IOR Level"].default_value = specular
    mat.diffuse_color = (*color, 1.0)
    return mat


def add_box(name, size, location, material, collection, rotation=(0, 0, 0)):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.rotation_euler = rotation
    mesh.materials.append(material)
    collection.objects.link(obj)
    return obj


def add_cylinder(name, radius, depth, location, material, collection, rotation=(0, 0, 0),
                 segments=24):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius,
                          radius2=radius, depth=depth)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.rotation_euler = rotation
    mesh.materials.append(material)
    collection.objects.link(obj)
    return obj


def add_sphere(name, radius, location, material, collection, scale=(1, 1, 1)):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=radius)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.scale = scale
    mesh.materials.append(material)
    collection.objects.link(obj)
    return obj


def limb(name, a, b, radius, material, collection):
    """Zylinder von Punkt a nach Punkt b."""
    a, b = Vector(a), Vector(b)
    d = b - a
    obj = add_cylinder(name, radius, d.length, (a + b) / 2, material, collection)
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    return obj


# ---------------------------------------------------------------------------
# Raum
# ---------------------------------------------------------------------------

def build_room(collection):
    y_back = -PERSON_DISTANCE - ROOM_BEHIND_PERSON
    y_front = ROOM_FRONT
    depth = y_front - y_back
    y_mid = (y_front + y_back) / 2
    t = 0.2  # Wandstärke

    # Reflexionsgrad aller Raumflächen (Base Color ist in Blender linear = Reflexionsgrad).
    floor_mat = diffuse_material("Boden", (REFLECTANCE,) * 3, 1.0, 0.0)
    wall_mat = diffuse_material("Wand", (REFLECTANCE,) * 3, 1.0, 0.0)
    ceiling_mat = diffuse_material("Decke", (REFLECTANCE,) * 3, 1.0, 0.0)

    add_box("Boden", (ROOM_WIDTH + 2 * t, depth + 2 * t, t), (0, y_mid, -t / 2),
            floor_mat, collection)
    add_box("Decke", (ROOM_WIDTH + 2 * t, depth + 2 * t, t), (0, y_mid, ROOM_HEIGHT + t / 2),
            ceiling_mat, collection)
    add_box("Wand_vorn", (ROOM_WIDTH + 2 * t, t, ROOM_HEIGHT), (0, y_front + t / 2,
            ROOM_HEIGHT / 2), wall_mat, collection)
    add_box("Wand_hinten", (ROOM_WIDTH + 2 * t, t, ROOM_HEIGHT), (0, y_back - t / 2,
            ROOM_HEIGHT / 2), wall_mat, collection)
    add_box("Wand_links", (t, depth, ROOM_HEIGHT), (-ROOM_WIDTH / 2 - t / 2, y_mid,
            ROOM_HEIGHT / 2), wall_mat, collection)
    add_box("Wand_rechts", (t, depth, ROOM_HEIGHT), (ROOM_WIDTH / 2 + t / 2, y_mid,
            ROOM_HEIGHT / 2), wall_mat, collection)

    # 1-m-Raster auf dem Boden zur Orientierung (dünne Linien, leicht heller).
    # Raster mit gleichem Reflexionsgrad wie der Boden (bei 0 % unsichtbar, reflektiert nichts).
    grid_mat = diffuse_material("Bodenraster", (min(1.0, REFLECTANCE * 1.5),) * 3, 1.0, 0.0)
    for i in range(int(y_back) + 1, int(y_front)):
        add_box(f"Raster_y{i:+d}", (ROOM_WIDTH, 0.01, 0.002), (0, i, 0.001), grid_mat,
                collection)
    for i in range(-int(ROOM_WIDTH / 2) + 1, int(ROOM_WIDTH / 2)):
        add_box(f"Raster_x{i:+d}", (0.01, depth, 0.002), (i, y_mid, 0.001), grid_mat,
                collection)


# ---------------------------------------------------------------------------
# Person (sitzend, einfache Figur) mit Stuhl
# ---------------------------------------------------------------------------

def build_person(collection):
    px, py = 0.0, -PERSON_DISTANCE
    skin = diffuse_material("Haut", (0.80, 0.62, 0.50), 0.6)
    cloth = diffuse_material("Kleidung", (0.10, 0.15, 0.30), 0.9)
    pants = diffuse_material("Hose", (0.15, 0.15, 0.15), 0.9)
    chair_mat = diffuse_material("Stuhl", (0.30, 0.20, 0.12), 0.6)

    seat_h = 0.45
    # Stuhl (Blick nach +Y, Lehne hinten bei -Y)
    add_box("Stuhl_Sitz", (0.45, 0.45, 0.04), (px, py, seat_h - 0.02), chair_mat, collection)
    add_box("Stuhl_Lehne", (0.45, 0.04, 0.45), (px, py - 0.21, seat_h + 0.25), chair_mat,
            collection)
    for sx in (-0.2, 0.2):
        for sy in (-0.2, 0.2):
            add_box("Stuhl_Bein", (0.03, 0.03, seat_h - 0.04), (px + sx, py + sy,
                    (seat_h - 0.04) / 2), chair_mat, collection)

    # Körper
    hip_z = seat_h + 0.08
    shoulder_z = seat_h + 0.62
    add_box("Person_Becken", (0.36, 0.25, 0.16), (px, py - 0.05, hip_z), pants, collection)
    torso = add_cylinder("Person_Oberkoerper", 0.17, shoulder_z - hip_z, (px, py - 0.08,
                         (hip_z + shoulder_z) / 2), cloth, collection)
    torso.scale = (1.15, 0.7, 1.0)
    add_cylinder("Person_Hals", 0.05, 0.1, (px, py - 0.08, shoulder_z + 0.05), skin, collection)
    head_z = EYE_HEIGHT_SEATED + 0.02
    add_sphere("Person_Kopf", 0.11, (px, py - 0.06, head_z), skin, collection,
               scale=(0.85, 1.0, 1.15))
    for side, sx in (("L", -1), ("R", 1)):
        x = px + sx * 0.11
        knee = (x, py + 0.38, seat_h + 0.06)
        limb(f"Person_Oberschenkel_{side}", (x, py - 0.02, hip_z), knee, 0.07, pants,
             collection)
        ankle = (x, py + 0.42, 0.08)
        limb(f"Person_Unterschenkel_{side}", knee, ankle, 0.055, pants, collection)
        add_box(f"Person_Fuss_{side}", (0.1, 0.24, 0.07), (x, py + 0.48, 0.035), pants,
                collection)
        sh = (px + sx * 0.22, py - 0.08, shoulder_z - 0.04)
        elbow = (px + sx * 0.25, py + 0.02, shoulder_z - 0.32)
        hand = (px + sx * 0.17, py + 0.30, hip_z + 0.15)
        limb(f"Person_Oberarm_{side}", sh, elbow, 0.045, cloth, collection)
        limb(f"Person_Unterarm_{side}", elbow, hand, 0.04, skin, collection)

    return Vector((px, py + 0.04, EYE_HEIGHT_SEATED))  # Augenposition


# ---------------------------------------------------------------------------
# Leuchte: Import + Ausrichtung
# ---------------------------------------------------------------------------

# Aus der STEP-Analyse (Modellkoordinaten nach glTF-Import, Meter, Blender-Achsen):
# - Lichtkopf 330 x 125 x 792 mm, Dicke entlang +Y_modell, Lichtaustritt auf der +Y-Seite.
# - Die Öffnung im Frontrahmen (y = 0.048) ist 304 x 766 mm groß, Mitte bei x = 0.184, z = 0.
#   Im STEP ist dort kein Glas modelliert, deshalb wird eine Scheibe eingesetzt.
# - Die außenliegende Blende sitzt am Ende z = -0.396 und ragt 200 mm über das Glas hinaus.
#   Laut LVK wird das Licht auf der C180-Seite hart abgeschnitten, die Blende liegt also
#   hinten (C180, zur Person hin), der Hauptstrahl (C0, gamma 35°) geht zur Seite +Z_modell.
GLASS_CENTER_MODEL = Vector((0.184, 0.046, 0.0))
GLASS_SIZE = (0.304, 0.766, 0.004)  # quer (X), längs C0-C180, Dicke
# Leuchtende Fläche eines Moduls (LDT SIRIUS 2000: 600 x 761 mm für zwei Module) für die
# Leuchtdichte des Glases.
LDT_LUMINOUS_AREA = 0.300 * 0.761


def import_luminaire(collection):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=GLB_PATH)
    imported = [o for o in bpy.data.objects if o not in before]
    for o in imported:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        collection.objects.link(o)
    # Gehäuse-Netz sinnvoll benennen (im glTF heißt es nur "=>[0:1:1:5]").
    for o in imported:
        if o.type == 'MESH' and o.name.startswith("=>") and o.parent is not None:
            o.name = o.parent.name + "_Netz"
    bpy.context.view_layer.update()
    return imported


def build_luminaire(collection):
    imported = import_luminaire(collection)

    root = bpy.data.objects.new("Leuchte_SIRIUS_1000", None)
    root.empty_display_type = 'ARROWS'
    root.empty_display_size = 0.5
    collection.objects.link(root)
    for o in imported:
        if o.parent is None:
            o.parent = root

    # Modell -> Welt: Glasnormale (+Y_modell) nach unten (-Z), C0 (+Z_modell) nach vorn (+Y).
    # Das ist eine Drehung um X um -90°. Drehpunkt ist die Glasmitte, die auf 5 m Höhe liegt.
    tilt = Matrix.Rotation(math.radians(TILT_DEG), 4, 'X')
    rot = Matrix.Rotation(math.radians(-90.0), 4, 'X')
    glass_world = Vector((0, 0, MOUNT_HEIGHT))
    root.matrix_world = (Matrix.Translation(glass_world) @ tilt @ rot @
                         Matrix.Translation(-GLASS_CENTER_MODEL))
    bpy.context.view_layer.update()

    meshes = [o for o in imported if o.type == 'MESH']
    for o in meshes:
        # Die LVK wurde MIT Blende gemessen, Abschattung und Reflexion an Gehäuse und Blende
        # stecken also schon in der LDT. Damit sie nicht doppelt wirken, werfen die
        # Leuchtenteile keine Schatten und reflektieren kein Licht in den Raum; sie sind nur
        # für die Kamera sichtbar.
        o.visible_shadow = False
        o.visible_diffuse = False
        o.visible_glossy = False
        o.visible_transmission = False
        o.visible_volume_scatter = False

    # Abhängung zur Decke (Leuchte hängt frei im Raum).
    steel = diffuse_material("Abhaengung", (0.6, 0.6, 0.62), 0.4)
    top = max((o.matrix_world @ Vector(b)).z for o in meshes for b in o.bound_box)
    add_cylinder("Abhaengung", 0.015, ROOM_HEIGHT - top, (0, 0, (ROOM_HEIGHT + top) / 2),
                 steel, collection)
    return root, tilt


# ---------------------------------------------------------------------------
# LVK: IES-Licht und leuchtendes Glas
# ---------------------------------------------------------------------------

def lvk_frame(tilt, offset_z):
    """Weltmatrix für IES-Licht/Glas. Cycles-IES: gamma 0 = lokal -Z, C0 = lokal -Y.
    Gewünscht: gamma 0 nach unten, C0 nach vorn (+Y), also Drehung um 180° um Z."""
    return (Matrix.Translation(Vector((0, 0, MOUNT_HEIGHT))) @ tilt @
            Matrix.Translation(Vector((0, 0, offset_z))) @ Matrix.Rotation(math.pi, 4, 'Z'))


def ies_text():
    name = os.path.basename(IES_PATH)
    return bpy.data.texts.get(name) or bpy.data.texts.load(IES_PATH)


def build_light(collection, root, tilt):
    light_data = bpy.data.lights.new("LVK_SIRIUS_1000", type='POINT')
    # Photometrisch korrekt: Leistung 1 W und Stärke 1 -> Werte der IES-Datei in cd
    # (ein Modul: 111.246 lm, 985,5 W, max. 97.986 cd).
    light_data.energy = 1.0
    light_data.shadow_soft_size = 0.2
    light_data.use_nodes = True
    nt = light_data.node_tree
    emission = nt.nodes["Emission"]
    ies = nt.nodes.new("ShaderNodeTexIES")
    ies.mode = 'INTERNAL'  # IES-Daten in der .blend eingebettet
    ies.ies = ies_text()
    ies.inputs["Strength"].default_value = 1.0
    ies.location = (-300, 300)
    nt.links.new(ies.outputs["Fac"], emission.inputs["Strength"])
    bb = nt.nodes.new("ShaderNodeBlackbody")  # 5000 K laut LDT
    bb.inputs["Temperature"].default_value = 5000.0
    bb.location = (-300, 0)
    nt.links.new(bb.outputs["Color"], emission.inputs["Color"])

    light = bpy.data.objects.new("LVK_SIRIUS_1000", light_data)
    collection.objects.link(light)
    # 1 cm unter der Glasfläche.
    light.matrix_world = lvk_frame(tilt, -0.01)
    mw = light.matrix_world.copy()
    light.parent = root
    light.matrix_world = mw
    return light


def build_glass(collection, root, tilt):
    """Glasscheibe in der Lichtaustrittsöffnung. Ihre Leuchtdichte folgt der LVK:
    L(gamma, C) = I(gamma, C) / (A * cos gamma), sichtbar nur für Kamerastrahlen, damit das
    Licht nicht doppelt in den Raum kommt (die Beleuchtung macht das IES-Licht)."""
    mat = bpy.data.materials.new("Glas_LVK")
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (900, 0)
    glass = nodes.new("ShaderNodeBsdfPrincipled")
    glass.location = (300, 300)
    glass.inputs["Roughness"].default_value = 0.0
    glass.inputs["IOR"].default_value = 1.5
    glass.inputs["Transmission Weight"].default_value = 1.0
    add = nodes.new("ShaderNodeAddShader")
    add.location = (700, 0)
    emission = nodes.new("ShaderNodeEmission")
    emission.location = (500, -200)

    geo = nodes.new("ShaderNodeNewGeometry")
    geo.location = (-900, -200)
    # Richtung zum Betrachter im lokalen System des Glases (= System des IES-Lichts).
    to_local = nodes.new("ShaderNodeVectorTransform")
    to_local.vector_type = 'VECTOR'
    to_local.convert_from = 'WORLD'
    to_local.convert_to = 'OBJECT'
    to_local.location = (-700, -200)
    links.new(geo.outputs["Incoming"], to_local.inputs["Vector"])

    ies = nodes.new("ShaderNodeTexIES")
    ies.mode = 'INTERNAL'
    ies.ies = ies_text()
    ies.location = (-400, -100)
    links.new(to_local.outputs["Vector"], ies.inputs["Vector"])

    # cos(gamma) = -z der normierten lokalen Richtung, nach unten auf 0.05 begrenzt.
    norm = nodes.new("ShaderNodeVectorMath")
    norm.operation = 'NORMALIZE'
    norm.location = (-500, -400)
    links.new(to_local.outputs["Vector"], norm.inputs[0])
    sep = nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-320, -400)
    links.new(norm.outputs["Vector"], sep.inputs["Vector"])
    cos_g = nodes.new("ShaderNodeMath")
    cos_g.operation = 'MULTIPLY'
    cos_g.inputs[1].default_value = -1.0
    cos_g.location = (-150, -400)
    links.new(sep.outputs["Z"], cos_g.inputs[0])
    cos_c = nodes.new("ShaderNodeMath")
    cos_c.operation = 'MAXIMUM'
    cos_c.inputs[1].default_value = 0.05
    cos_c.location = (0, -400)
    links.new(cos_g.outputs[0], cos_c.inputs[0])

    # IES-Fac = I_cd * 4*pi / 177.83  ->  Strahldichte = Fac / (4*pi * A * cos gamma).
    denom = nodes.new("ShaderNodeMath")
    denom.operation = 'MULTIPLY'
    denom.inputs[1].default_value = 4.0 * math.pi * LDT_LUMINOUS_AREA
    denom.location = (150, -400)
    links.new(cos_c.outputs[0], denom.inputs[0])
    radiance = nodes.new("ShaderNodeMath")
    radiance.operation = 'DIVIDE'
    radiance.location = (150, -150)
    links.new(ies.outputs["Fac"], radiance.inputs[0])
    links.new(denom.outputs[0], radiance.inputs[1])

    path = nodes.new("ShaderNodeLightPath")
    path.location = (0, 100)
    cam_only = nodes.new("ShaderNodeMath")
    cam_only.operation = 'MULTIPLY'
    cam_only.location = (330, -150)
    links.new(radiance.outputs[0], cam_only.inputs[0])
    links.new(path.outputs["Is Camera Ray"], cam_only.inputs[1])

    bb = nodes.new("ShaderNodeBlackbody")
    bb.inputs["Temperature"].default_value = 5000.0
    bb.location = (330, -350)
    links.new(bb.outputs["Color"], emission.inputs["Color"])
    links.new(cam_only.outputs[0], emission.inputs["Strength"])
    links.new(glass.outputs["BSDF"], add.inputs[0])
    links.new(emission.outputs["Emission"], add.inputs[1])
    links.new(add.outputs["Shader"], out.inputs["Surface"])

    obj = add_box("Leuchte_Glas", GLASS_SIZE, (0, 0, 0), mat, collection)
    # Lokales System wie beim IES-Licht; Außenseite bündig mit dem Frontrahmen.
    obj.matrix_world = lvk_frame(tilt, 0.0)
    mw = obj.matrix_world.copy()
    obj.parent = root
    obj.matrix_world = mw
    obj.visible_shadow = False
    return obj


# ---------------------------------------------------------------------------
# Maßstäbe und Maßketten (nur für die Kamera sichtbar, beeinflussen das Licht nicht)
# ---------------------------------------------------------------------------

EXPOSURE = -2.0


def camera_only_material(name, color, strength=None):
    """Emission nur für Kamerastrahlen, sonst transparent: sichtbar auch bei 0 % Reflexion,
    ohne Einfluss auf Beleuchtung und Messwerte."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    path = nt.nodes.new("ShaderNodeLightPath")
    transp = nt.nodes.new("ShaderNodeBsdfTransparent")
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (*color, 1)
    emit.inputs["Strength"].default_value = strength or 2.0 ** (-EXPOSURE)
    # Nur die Vorderseite ist sichtbar, damit Beschriftungen nie spiegelverkehrt erscheinen
    # (jede Beschriftung gibt es zweimal, je eine pro Blickrichtung).
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    front = nt.nodes.new("ShaderNodeMath")
    front.operation = 'SUBTRACT'
    front.inputs[0].default_value = 1.0
    nt.links.new(geo.outputs["Backfacing"], front.inputs[1])
    visible = nt.nodes.new("ShaderNodeMath")
    visible.operation = 'MULTIPLY'
    nt.links.new(path.outputs["Is Camera Ray"], visible.inputs[0])
    nt.links.new(front.outputs[0], visible.inputs[1])
    nt.links.new(visible.outputs[0], mix.inputs[0])
    nt.links.new(transp.outputs[0], mix.inputs[1])
    nt.links.new(emit.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def no_light_influence(obj):
    obj.visible_shadow = False
    obj.visible_diffuse = False
    obj.visible_glossy = False
    obj.visible_transmission = False


def scale_line(name, a, b, width, mat, collection):
    """Flacher Balken von a nach b (Breite quer, liegt in der Ebene senkrecht zu 'up')."""
    a, b = Vector(a), Vector(b)
    obj = limb(name, a, b, width / 2, mat, collection)
    no_light_influence(obj)
    return obj


def label(body, location, mat, collection, size=0.22, rotation=(math.radians(90), 0, 0),
          align='CENTER'):
    """Beschriftung, von beiden Seiten lesbar: eine zweite, um 180° gedrehte Kopie zeigt in
    die Gegenrichtung (die Rückseiten sind im Material ausgeblendet)."""
    mirrored_align = {'LEFT': 'RIGHT', 'RIGHT': 'LEFT'}.get(align, align)
    turn = Matrix.Rotation(math.pi, 3, 'Z')
    rot = mathutils_euler_matrix(rotation)
    first = None
    for side, (al, m) in enumerate(((align, rot), (mirrored_align, turn @ rot))):
        curve = bpy.data.curves.new("Text_" + body, 'FONT')
        curve.body = body
        curve.size = size
        curve.align_x = al
        curve.align_y = 'CENTER'
        obj = bpy.data.objects.new("Text_" + body + ("_Rueckseite" if side else ""), curve)
        obj.matrix_world = m.to_4x4()
        obj.location = location
        obj.data.materials.append(mat)
        no_light_influence(obj)
        collection.objects.link(obj)
        first = first or obj
    return first


def mathutils_euler_matrix(rotation):
    from mathutils import Euler
    return Euler(rotation).to_matrix()


def arrow_head(name, tip, direction, mat, collection, length=0.18, radius=0.06):
    direction = Vector(direction).normalized()
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=radius, radius2=0.0,
                          depth=length)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = Vector(tip) - direction * length / 2
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(direction)
    mesh.materials.append(mat)
    no_light_influence(obj)
    collection.objects.link(obj)
    return obj


def dimension(name, a, b, text, mat, collection, text_offset=(0, 0, 0.25), size=0.3,
              align='CENTER'):
    """Maßkette mit Pfeilen an beiden Enden und Beschriftung in der Mitte."""
    a, b = Vector(a), Vector(b)
    d = (b - a).normalized()
    scale_line(name, a + d * 0.15, b - d * 0.15, 0.025, mat, collection)
    arrow_head(name + "_Pfeil_a", a, -d, mat, collection)
    arrow_head(name + "_Pfeil_b", b, d, mat, collection)
    return label(text, (a + b) / 2 + Vector(text_offset), mat, collection, size=size,
                 align=align)


def build_scales(collection, eye):
    yellow = camera_only_material("Massstab_gelb", (1.0, 0.8, 0.05))
    white = camera_only_material("Massstab_weiss", (1.0, 1.0, 1.0))
    cyan = camera_only_material("Massstab_cyan", (0.1, 0.8, 1.0))
    y_person = -PERSON_DISTANCE
    upright = (math.radians(90), 0, 0)  # Text steht senkrecht, lesbar von der Person aus

    # 1) Bodenmaßstab entlang der Raumachse (x = -2), 1-m-Teilung, 0 = Lotpunkt der Leuchte.
    xr = -2.0
    z0 = 0.01
    scale_line("Massstab_Boden", (xr, y_person, z0), (xr, ROOM_FRONT, z0), 0.03, white,
               collection)
    for i in range(int(y_person), int(ROOM_FRONT) + 1):
        major = 0.6 if i % 2 == 0 else 0.35
        scale_line(f"Massstab_Boden_Strich_{i:+d}", (xr - major / 2, i, z0),
                   (xr + major / 2, i, z0), 0.03, white, collection)
        if i == 0:
            text = "0 m  Leuchte"
        elif i == y_person:
            text = f"{abs(i)} m  Person"
        elif i == ROOM_FRONT:
            text = f"{i} m  Wand"
        else:
            text = f"{abs(i)} m"
        label(text, (xr - 0.45, i, 0.15), white, collection, size=0.2, align='RIGHT',
              rotation=upright)

    # Lotpunkt der Leuchte und Position der Person auf dem Boden
    for a, b in (((-0.4, 0, z0), (0.4, 0, z0)), ((0, -0.4, z0), (0, 0.4, z0))):
        scale_line("Lotpunkt_Leuchte", a, b, 0.03, yellow, collection)

    # 2) Maßketten auf dem Boden (x = +2): Person -> Leuchte, Leuchte -> Wand
    xd = 2.0
    dimension("Mass_Person_Leuchte", (xd, y_person, 0.05), (xd, 0, 0.05),
              f"{PERSON_DISTANCE:.2f} m".replace(".", ","), yellow, collection,
              text_offset=(0, 0, 0.3))
    dimension("Mass_Leuchte_Wand", (xd, 0, 0.05), (xd, ROOM_FRONT, 0.05),
              f"{ROOM_FRONT:.2f} m".replace(".", ","), yellow, collection,
              text_offset=(0, 0, 0.3))
    for y in (y_person, 0.0, ROOM_FRONT):
        scale_line(f"Mass_Hilfslinie_{y:+.0f}", (xd - 0.3, y, 0.02), (xd + 0.3, y, 0.02),
                   0.02, yellow, collection)

    # 3) Höhenmaßstab neben der Leuchte (x = +0.8), 0 bis 5 m, 0.5-m-Teilung
    xh = 0.8
    scale_line("Massstab_Hoehe", (xh, 0, 0), (xh, 0, MOUNT_HEIGHT), 0.03, cyan, collection)
    for k in range(0, int(MOUNT_HEIGHT * 2) + 1):
        z = k * 0.5
        w = 0.4 if k % 2 == 0 else 0.2
        scale_line(f"Massstab_Hoehe_Strich_{k}", (xh, -w / 2, z), (xh, w / 2, z), 0.025, cyan,
                   collection)
        if k % 2 == 0 and k > 0:
            label(f"{z:.0f} m", (xh + 0.15, 0, z), cyan, collection, size=0.2, align='LEFT',
                  rotation=upright)
    label(f"Montagehöhe {MOUNT_HEIGHT:.2f} m".replace(".", ","), (xh + 0.15, 0,
          MOUNT_HEIGHT + 0.35), cyan, collection, size=0.24, align='LEFT', rotation=upright)
    scale_line("Massstab_Hoehe_Bezug", (0.25, 0, MOUNT_HEIGHT), (xh, 0, MOUNT_HEIGHT), 0.02,
               cyan, collection)

    # 4) Augenhöhe der Person
    xe = eye.x + 0.6
    dimension("Mass_Augenhoehe", (xe, eye.y, 0.0), (xe, eye.y, eye.z),
              f"Augenhöhe {eye.z:.2f} m".replace(".", ","), cyan, collection,
              text_offset=(0.15, 0, 0), size=0.16, align='LEFT')

    # 5) Sichtlinie Person -> Leuchte mit Abstand und Blickwinkel
    lum = Vector((0, 0, MOUNT_HEIGHT))
    los = lum - eye
    elev = math.degrees(math.atan2(los.z, los.y))
    gamma = math.degrees(math.atan2(abs(los.y), los.z))  # Ausstrahlungswinkel ab Nadir
    scale_line("Sichtlinie", eye + los.normalized() * 0.3, lum - los.normalized() * 0.3,
               0.012, white, collection)
    label(f"Sichtlinie {los.length:.2f} m, {elev:.1f}° über der Horizontalen "
          f"(gamma {gamma:.1f}° in C180)".replace(".", ","),
          eye + los * 0.5 + Vector((0, 0, 0.3)), white, collection, size=0.16,
          rotation=upright)


# ---------------------------------------------------------------------------
# Kameras, Render-Einstellungen
# ---------------------------------------------------------------------------

def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()


def build_cameras(collection, eye):
    cam_data = bpy.data.cameras.new("Blick_Person")
    cam_data.lens = 18
    cam = bpy.data.objects.new("Blick_Person", cam_data)
    cam.location = eye
    collection.objects.link(cam)
    # Blick nach vorn (+Y), 10° angehoben, damit Leuchte und beleuchteter Boden im Bild sind.
    # Anheben so weit, dass auch eine hoch montierte Leuchte im Bild ist (halber vertikaler
    # Bildwinkel bei 18 mm und 16:9 etwa 29°).
    elevation = math.degrees(math.atan2(MOUNT_HEIGHT - eye.z, PERSON_DISTANCE))
    cam.rotation_euler = (math.radians(90 + max(10.0, elevation - 22.0)), 0, 0)

    over_data = bpy.data.cameras.new("Uebersicht")
    over_data.lens = 16 if MOUNT_HEIGHT <= 5 else 13
    over = bpy.data.objects.new("Uebersicht", over_data)
    over.location = (ROOM_WIDTH / 2 - 0.4, -PERSON_DISTANCE - ROOM_BEHIND_PERSON + 0.4,
                     ROOM_HEIGHT - 0.4)
    collection.objects.link(over)
    look_at(over, (0, 0.5, 0.3 * MOUNT_HEIGHT))

    # Übersicht von vorn auf Leuchte, Person und Rückwand (Messfeld hinter der Person)
    back_data = bpy.data.cameras.new("Uebersicht_Rueckwand")
    back_data.lens = 16 if MOUNT_HEIGHT <= 5 else 13
    back = bpy.data.objects.new("Uebersicht_Rueckwand", back_data)
    back.location = (-ROOM_WIDTH / 2 + 0.4, ROOM_FRONT - 0.4, ROOM_HEIGHT - 0.4)
    collection.objects.link(back)
    look_at(back, (0, -PERSON_DISTANCE + 1.0, 0.3 * MOUNT_HEIGHT))

    bpy.context.scene.camera = cam
    return cam, over


def setup_render(scene):
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 256
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    try:
        scene.view_settings.view_transform = 'AgX'
    except TypeError:
        scene.view_settings.view_transform = 'Filmic'
    scene.view_settings.exposure = EXPOSURE
    world = bpy.data.worlds.new("Welt")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    scene.world = world


# ---------------------------------------------------------------------------

def main():
    scene = reset_scene()
    room_col = new_collection("Raum")
    person_col = new_collection("Person")
    lum_col = new_collection("Leuchte")
    cam_col = new_collection("Kameras")
    scale_col = new_collection("Massstaebe")

    build_room(room_col)
    eye = build_person(person_col)
    root, tilt = build_luminaire(lum_col)
    build_light(lum_col, root, tilt)
    build_glass(lum_col, root, tilt)
    build_scales(scale_col, eye)
    build_cameras(cam_col, eye)
    setup_render(scene)

    # Geometrie für messfeld.py in der Szene ablegen
    scene["mount_height"] = MOUNT_HEIGHT
    scene["room_height"] = ROOM_HEIGHT
    scene["room_width"] = ROOM_WIDTH
    scene["room_front"] = ROOM_FRONT
    scene["room_back"] = -PERSON_DISTANCE - ROOM_BEHIND_PERSON
    scene["person_distance"] = PERSON_DISTANCE
    scene["variant"] = VARIANT
    scene["ies_file"] = os.path.basename(IES_PATH)
    out = os.path.join(DATA_DIR, f"{_base}_raum_{MOUNT_HEIGHT:g}m.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("Gespeichert:", out)


if __name__ == "__main__":
    main()
