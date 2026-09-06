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
for keymap_name in (
    "3D View", "Outliner", "Node Editor", "Sequencer", "Property Editor", "Window"
):
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
    assert len(agent_bridge._addon_keymaps) == 6
    for keymap, item in agent_bridge._addon_keymaps:
        assert keymap.name in {
            "3D View", "Outliner", "Node Editor", "Sequencer", "Property Editor", "Window"
        }
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
    assert 'Referenced Node Group: "Nested Geometry"' in node_address
    assert f'Node: "{group_node.name}"' in node_address
    assert agent_bridge._handoff_specificity(
        fake_context("NODE_EDITOR", space_data=SimpleNamespace(edit_tree=group))
    ) == "Pid -> Node"

    frame = group.nodes.new("NodeFrame")
    frame.name = "Burn Interior Frame"
    frame.label = "Burn until the nearest surface switches across the interior"
    group.nodes.active = frame
    frame_address = agent_bridge._build_context_address(
        fake_context("NODE_EDITOR", space_data=SimpleNamespace(edit_tree=group))
    )
    assert 'Frame: "Burn Interior Frame"' in frame_address
    assert (
        'Frame Label: "Burn until the nearest surface switches across the interior"'
        in frame_address
    )
    assert agent_bridge._handoff_specificity(
        fake_context("NODE_EDITOR", space_data=SimpleNamespace(edit_tree=group))
    ) == "Pid -> Frame"

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

    vse_scene = bpy.data.scenes.new("Transcript Edit")
    sequence_editor = vse_scene.sequence_editor_create()
    subtitle = sequence_editor.strips.new_effect(
        name="Transcript 001",
        type="TEXT",
        channel=3,
        frame_start=10,
        length=30,
    )
    sequence_editor.active_strip = subtitle
    timeline_space = SimpleNamespace(view_type="SEQUENCER")
    timeline_region = SimpleNamespace(
        view2d=SimpleNamespace(region_to_view=lambda x, y: (x, y))
    )
    subtitle_event = SimpleNamespace(mouse_region_x=20, mouse_region_y=3.5)
    vse_context = fake_context(
        "SEQUENCE_EDITOR",
        scene=vse_scene,
        active_strip=subtitle,
        space_data=timeline_space,
        region=timeline_region,
    )
    strip_address = agent_bridge._build_context_address(
        vse_context,
        event=subtitle_event,
    )
    assert 'Scene: "Transcript Edit"' in strip_address
    assert 'Text Strip: "Transcript 001"' in strip_address
    assert agent_bridge._handoff_specificity(
        vse_context,
        event=subtitle_event,
    ) == "Pid -> Strip"

    transcript_meta = sequence_editor.strips.new_meta(
        name="Transcript Pass",
        channel=5,
        frame_start=50,
    )
    nested_subtitle = transcript_meta.strips.new_effect(
        name="Transcript 002",
        type="TEXT",
        channel=2,
        frame_start=50,
        length=30,
    )
    sequence_editor.display_stack(transcript_meta)
    sequence_editor.active_strip = nested_subtitle
    nested_event = SimpleNamespace(mouse_region_x=60, mouse_region_y=2.5)
    nested_context = fake_context(
        "SEQUENCE_EDITOR",
        scene=vse_scene,
        active_strip=nested_subtitle,
        space_data=timeline_space,
        region=timeline_region,
    )
    nested_address = agent_bridge._build_context_address(
        nested_context,
        event=nested_event,
    )
    assert 'Meta Strip: "Transcript Pass"' in nested_address
    assert 'Text Strip: "Transcript 002"' in nested_address

    # The gap between VSE channels deliberately resolves to the active strip
    # fallback rather than pretending the pointer intersects a strip body.
    gap_event = SimpleNamespace(mouse_region_x=20, mouse_region_y=3.99)
    assert agent_bridge._strip_under_mouse(
        vse_context,
        gap_event,
        sequence_editor,
    ) is None

    empty_vse_scene = bpy.data.scenes.new("Empty Edit")
    empty_vse_address = agent_bridge._build_context_address(
        fake_context(
            "SEQUENCE_EDITOR",
            scene=empty_vse_scene,
            space_data=SimpleNamespace(view_type="PREVIEW"),
        )
    )
    assert empty_vse_address.endswith('Scene: "Empty Edit"')
    assert agent_bridge._handoff_specificity(
        fake_context(
            "SEQUENCE_EDITOR",
            scene=empty_vse_scene,
            space_data=SimpleNamespace(view_type="PREVIEW"),
        )
    ) == "Pid -> Scene"

    compositor_scene = bpy.data.scenes.new("Caption Composite")
    compositor_tree = bpy.data.node_groups.new(
        "Caption Composite Nodes",
        "CompositorNodeTree",
    )
    compositor_scene.compositing_node_group = compositor_tree
    compositor_context = fake_context(
        "NODE_EDITOR",
        scene=compositor_scene,
        space_data=SimpleNamespace(
            tree_type="CompositorNodeTree",
            id=compositor_scene,
            edit_tree=compositor_tree,
            node_tree=compositor_tree,
        ),
    )
    compositor_address = agent_bridge._build_context_address(compositor_context)
    assert 'Scene: "Caption Composite"' in compositor_address
    assert 'Compositor Nodes: "Caption Composite Nodes"' in compositor_address
    assert agent_bridge._handoff_specificity(compositor_context) == "Pid -> Node Group"

    assert agent_bridge._handoff_specificity(
        fake_context("EMPTY"), instance_only=True
    ) == "Pid"

    class BrokenContext:
        @property
        def area(self):
            raise RuntimeError("context unavailable")

    fallback_address = agent_bridge._build_context_address(BrokenContext())
    assert fallback_address.startswith("Blender target: ")
    assert " → " not in fallback_address
    assert agent_bridge._handoff_specificity(BrokenContext()) == "Pid"
finally:
    agent_bridge.unregister()

assert not agent_bridge._addon_keymaps
print("AGENT_BRIDGE_CONTEXT_ADDRESS_OK")
