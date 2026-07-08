# SPDX-License-Identifier: GPL-3.0-or-later
from agent_bridge import build_register_payload


def test_payload_has_stem_and_core_fields():
    p = build_register_payload(25591, 9877, "localhost",
                               "/x/no3d asset dev.blend")
    assert p["blender_pid"] == 25591
    assert p["port"] == 9877
    assert p["host"] == "localhost"
    assert p["blendfile"] == "/x/no3d asset dev.blend"
    assert p["blendfile_stem"] == "no3d asset dev"


def test_payload_stem_empty_for_unsaved():
    p = build_register_payload(1, 9877, "localhost", "")
    assert p["blendfile_stem"] == ""
