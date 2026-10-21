# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Simple render test with OctaneRender: builds a small scene (floor, sphere,
light, camera), switches to Octane and renders one image.

Run it from a terminal:
``blender --background --factory-startup --python tools/mcp_octane/octane_render_test.py``
(drop ``--factory-startup`` if the Octane add-on is only enabled in your
preferences), or paste it into the MCP tool ``execute_blender_code``.
The image is written to ``~/octane_render_test.png``.
"""

import os

import bpy
import addon_utils  # Import after `bpy` so it also works with the `bpy` module.

OCTANE_ENGINE = 'octane'
OUTPUT_PATH = os.path.join(os.path.expanduser("~"), "octane_render_test.png")


def enable_octane(scene):
    # The Octane add-on module name differs between releases.
    for mod in addon_utils.modules():
        if "octane" in mod.__name__.lower():
            addon_utils.enable(mod.__name__, default_set=True)
    try:
        scene.render.engine = OCTANE_ENGINE
    except TypeError as ex:
        # The message lists the engines that are actually available.
        print("OctaneRender NOT available:", ex)
        return False
    return True


def build_scene(scene):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    bpy.ops.mesh.primitive_plane_add(size=10.0)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0.0, 0.0, 1.0))
    bpy.ops.object.shade_smooth()

    bpy.ops.object.light_add(type='AREA', location=(3.0, -3.0, 5.0))
    light = bpy.context.object
    light.data.energy = 1000.0
    light.data.size = 3.0
    light.rotation_euler = (0.6, 0.0, 0.8)

    bpy.ops.object.camera_add(location=(6.0, -6.0, 4.0), rotation=(1.1, 0.0, 0.785))
    scene.camera = bpy.context.object


def main():
    scene = bpy.context.scene
    build_scene(scene)
    if not enable_octane(scene):
        return False

    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = OUTPUT_PATH

    bpy.ops.render.render(write_still=True)
    print("Render finished with", scene.render.engine, "->", OUTPUT_PATH)
    return True


if __name__ == "__main__":
    main()
