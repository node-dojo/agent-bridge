"""Run with Blender 5.2 --background --factory-startup --python."""

import sys
from pathlib import Path
from types import SimpleNamespace

import bpy


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_bridge  # noqa: E402


def fake_context(area_type, **values):
    return SimpleNamespace(
        area=SimpleNamespace(type=area_type),
        space_data=values.pop("space_data", None),
        active_object=values.pop("active_object", None),
        selected_ids=values.pop("selected_ids", ()),
        id=values.pop("id", None),
        **values,
    )


# Cmd+Shift+C has no Blender-default collision in the intended editors.
default_config = bpy.context.window_manager.keyconfigs.default
for keymap_name in ("3D View", "Outliner", "Node Editor", "Property Editor"):
    keymap = default_config.keymaps.get(keymap_name)
    collisions = [] if keymap is None else [
        item
        for item in keymap.keymap_items
        if item.type == "C" and item.shift and item.oskey and item.active
    ]
    assert not collisions, (keymap_name, [(item.idname, item.type) for item in collisions])

agent_bridge.register()
try:
    assert agent_bridge.AGENT_BRIDGE_OT_copy_context_address.is_registered
    assert agent_bridge.AGENT_BRIDGE_Preferences.is_registered
    assert len(agent_bridge._addon_keymaps) == 4
    for keymap, item in agent_bridge._addon_keymaps:
        assert keymap.name in {"3D View", "Outliner", "Node Editor", "Property Editor"}
        assert item.idname == "agent_bridge.copy_context_address"
        assert item.type == "C" and item.shift and item.oskey

    mesh = bpy.data.meshes.new("Address Mesh")
    obj = bpy.data.objects.new("Address Object", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    group = bpy.data.node_groups.new("Address Geometry", "GeometryNodeTree")
    modifier = obj.modifiers.new("GeometryNodes", "NODES")
    modifier.node_group = group

    object_address = agent_bridge._build_context_address(
        fake_context("VIEW_3D", active_object=obj)
    )
    assert 'Object: "Address Object"' in object_address
    assert 'Geometry Nodes: "Address Geometry"' in object_address
    assert agent_bridge._handoff_specificity(
        fake_context("VIEW_3D", active_object=obj)
    ) == "Pid -> Node Group"

    nested = bpy.data.node_groups.new("Nested Geometry", "GeometryNodeTree")
    group_node = group.nodes.new("GeometryNodeGroup")
    group_node.node_tree = nested
    group_node.select = True
    group.nodes.active = group_node
    node_address = agent_bridge._build_context_address(
        fake_context("NODE_EDITOR", space_data=SimpleNamespace(edit_tree=group))
    )
    assert 'Geometry Nodes: "Address Geometry"' in node_address
    assert 'Selected Group: "Nested Geometry"' in node_address
    assert agent_bridge._handoff_specificity(
        fake_context("NODE_EDITOR", space_data=SimpleNamespace(edit_tree=group))
    ) == "Pid -> Node Group"

    outliner_address = agent_bridge._build_context_address(
        fake_context("OUTLINER", active_object=obj)
    )
    assert 'Object: "Address Object"' in outliner_address

    properties_address = agent_bridge._build_context_address(
        fake_context("PROPERTIES", active_object=obj)
    )
    assert 'Object: "Address Object"' in properties_address
    assert 'Geometry Nodes: "Address Geometry"' in properties_address
    assert agent_bridge._handoff_specificity(
        fake_context("PROPERTIES", active_object=obj)
    ) == "Pid -> Node Group"
    assert agent_bridge._handoff_specificity(
        fake_context("EMPTY"), instance_only=True
    ) == "Pid"
finally:
    agent_bridge.unregister()

assert not agent_bridge._addon_keymaps
print("AGENT_BRIDGE_CONTEXT_ADDRESS_OK")
