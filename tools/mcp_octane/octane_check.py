# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Check whether OctaneRender is available in the running Blender and switch the
scene to it. Run it in Blender's Text Editor, with
``blender --python tools/mcp_octane/octane_check.py``, or paste it into the
MCP tool ``execute_blender_code``.
"""

import bpy
import addon_utils

OCTANE_ENGINE = 'octane'


def octane_available():
    engines = {
        engine.bl_idname
        for engine in bpy.types.RenderEngine.__subclasses__()
        if getattr(engine, "bl_idname", None)
    }
    return OCTANE_ENGINE in engines


def main():
    # The Octane add-on module name differs between releases, so try to enable
    # any installed add-on whose name mentions Octane.
    if not octane_available():
        for mod in addon_utils.modules():
            if "octane" in mod.__name__.lower():
                addon_utils.enable(mod.__name__, default_set=True, persistent=True)

    if not octane_available():
        print("OctaneRender NOT found. Install the Octane for Blender build/add-on first.")
        return False

    bpy.context.scene.render.engine = OCTANE_ENGINE
    print("OctaneRender active: scene.render.engine =", bpy.context.scene.render.engine)
    return True


if __name__ == "__main__":
    main()
