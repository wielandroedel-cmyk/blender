"""
Ansicht der Leuchte mit Blende V2 und mit der neuen Blende (Cycles-Renderings für die
Präsentation).

    python render_visor.py [v2|b3a|b3k|v2s|kb|v2f ...] [--alle] [ordner]
"""

import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

DATA_DIR = sys.argv[-1] if len(sys.argv) > 1 and os.path.isdir(sys.argv[-1]) else \
    os.path.dirname(os.path.abspath(__file__))
GLASS_CENTER_MODEL = Vector((0.184, 0.046, 0.0))
VIEWS = {"hinten": ((1.9, -2.9, -1.6), (0.0, -0.2, -0.2)),
         "seite": ((2.9, -0.25, -0.4), (0.0, -0.05, -0.18))}
# zusätzliche Ansichten nur auf Wunsch: python render_visor.py v2s --alle
EXTRA_VIEWS = {"vorn": ((1.4, 2.7, -1.5), (0.0, -0.05, -0.12)),
               "unten": ((0.25, -0.9, -2.6), (0.0, -0.1, -0.05)),
               "detail": ((0.8, 0.25, -0.5), (0.15, -0.37, -0.12), 85)}
if "--detail" in sys.argv:
    VIEWS = {"detail": EXTRA_VIEWS["detail"]}
elif "--alle" in sys.argv:
    VIEWS.update(EXTRA_VIEWS)


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.93, 0.95, 0.97, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    sc.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN'))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(140), math.radians(20), math.radians(-30))
    sc.collection.objects.link(sun)
    sc.render.resolution_x, sc.render.resolution_y = 2400, 1720
    sc.view_settings.view_transform = 'Standard'
    return sc


def load(glb):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(DATA_DIR, glb))
    imported = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new("root", None)
    bpy.context.scene.collection.objects.link(root)
    for o in imported:
        if o.parent is None:
            o.parent = root
    root.matrix_world = Matrix.Rotation(math.radians(-90.0), 4, 'X') @ \
        Matrix.Translation(-GLASS_CENTER_MODEL)
    return imported


def render(glb, tag):
    sc = setup()
    load(glb)
    for name, view in VIEWS.items():
        pos, target = view[:2]
        cam_data = bpy.data.cameras.new(name)
        cam_data.lens = view[2] if len(view) > 2 else 50
        cam = bpy.data.objects.new(name, cam_data)
        sc.collection.objects.link(cam)
        cam.location = pos
        cam.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
        sc.camera = cam
        sc.render.filepath = os.path.join(DATA_DIR, f"ansicht_{tag}_{name}.png")
        bpy.ops.render.render(write_still=True)


MODELS = {"v2": "sirius1000.glb", "b3a": "sirius1000_visor_b3.glb", "b3k": "sirius1000_visor_b3k.glb",
          "v2s": "sirius1000_v2s.glb", "kb": "sirius1000_kiemen.glb",
          "v2f": "sirius1000_v2f.glb"}
for tag in [a for a in sys.argv[1:] if a in MODELS] or list(MODELS):
    render(MODELS[tag], tag)
