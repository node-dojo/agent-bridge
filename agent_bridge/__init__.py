# SPDX-License-Identifier: GPL-3.0-or-later
"""Agent Bridge — Blender-side serve+register so agents can target this
instance by its .blend filename via the Agent Bridge MCP server."""

__all__ = ("register", "unregister", "build_register_payload")

import os
from pathlib import Path


def build_register_payload(pid: int, port: int, host: str, blendfile: str) -> dict:
    stem = Path(blendfile).stem if blendfile else ""
    return {
        "blender_pid": pid,
        "port": port,
        "host": host,
        "blendfile": blendfile,
        "blendfile_stem": stem,
    }


# --- Blender-only below (guarded so the module imports without bpy for tests) ---
try:
    import bpy
    from bpy.types import Operator, Panel
    _HAS_BPY = True
except ImportError:
    _HAS_BPY = False

if _HAS_BPY:
    from . import registry as reg
    from . import serve_helpers as sh

    _PID = os.getpid()

    class AGENT_BRIDGE_OT_serve(Operator):
        bl_idname = "agent_bridge.serve"
        bl_label = "Serve to Agents"
        bl_description = "Start this Blender's MCP server and register it so agents can target it by .blend name"
        bl_options = {"REGISTER"}

        def execute(self, context):
            del context
            prefs_host = "localhost"
            try:
                if not sh.is_official_mcp_running():
                    port = sh.find_free_port(host=prefs_host)
                    sh.start_official_mcp_on_port(port, host=prefs_host)
                else:
                    port = sh.official_mcp_prefs().port
            except Exception as ex:  # pylint: disable=broad-exception-caught
                self.report({"ERROR"}, f"Could not start MCP server: {ex}")
                return {"CANCELLED"}
            blendfile = bpy.data.filepath or ""
            reg.write(_PID, build_register_payload(_PID, port, prefs_host, blendfile))
            self.report({"INFO"}, f"Serving '{Path(blendfile).stem or '(unsaved)'}' on :{port}")
            return {"FINISHED"}

    class AGENT_BRIDGE_OT_stop(Operator):
        bl_idname = "agent_bridge.stop"
        bl_label = "Stop Serving"
        bl_description = "Stop this Blender's MCP server and remove it from the agent registry"
        bl_options = {"REGISTER"}

        def execute(self, context):
            del context
            try:
                sh.stop_official_mcp()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            reg.remove(_PID)
            self.report({"INFO"}, "Stopped serving.")
            return {"FINISHED"}

    class AGENT_BRIDGE_PT_panel(Panel):
        bl_idname = "AGENT_BRIDGE_PT_panel"
        bl_label = "Agent Bridge"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "Claude"

        def draw(self, context):
            del context
            layout = self.layout
            entry = reg.read(_PID)
            if entry:
                layout.label(text=f"Serving :{entry.get('port')}", icon="CHECKMARK")
                layout.label(text=f"As: {entry.get('blendfile_stem') or '(unsaved)'}")
                layout.operator("agent_bridge.stop", icon="UNLINKED")
            else:
                layout.operator("agent_bridge.serve", icon="LINKED")
            layout.separator()
            box = layout.box()
            box.label(text="Live instances (agents can target):", icon="OUTLINER")
            for i in reg.live_instances():
                box.label(text=f"{reg.stem_of(i)}  :{i.get('port')}  pid{i.get('blender_pid')}")

    _classes = (AGENT_BRIDGE_OT_serve, AGENT_BRIDGE_OT_stop, AGENT_BRIDGE_PT_panel)

    def register():
        for cls in _classes:
            bpy.utils.register_class(cls)

    def unregister():
        for cls in reversed(_classes):
            bpy.utils.unregister_class(cls)
else:
    def register():
        raise RuntimeError("agent_bridge Blender side requires bpy")

    def unregister():
        pass
