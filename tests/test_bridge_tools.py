# SPDX-License-Identifier: GPL-3.0-or-later
from agent_bridge import bridge_tools
from agent_bridge.resolver import Resolver


def _inst(pid, port, stem):
    return {"blender_pid": pid, "port": port, "host": "localhost",
            "blendfile": f"/x/{stem}.blend", "blendfile_stem": stem}


def test_use_instance_sets_target_and_confirms():
    r = Resolver(instances_fn=lambda: [_inst(1, 9877, "resin")])
    msg = bridge_tools._use_instance_impl(r, "resin")
    assert "resin" in msg and "9877" in msg and "1" in msg
    assert r.resolve() == ("localhost", 9877)


def test_list_instances_shape():
    r = Resolver(instances_fn=lambda: [_inst(1, 9877, "resin"), _inst(2, 9878, "dev")])
    rows = bridge_tools._list_instances_impl(r)
    assert {row["stem"] for row in rows} == {"resin", "dev"}
    assert all({"stem", "pid", "port", "blendfile"} <= row.keys() for row in rows)


def test_use_instance_error_is_readable():
    r = Resolver(instances_fn=lambda: [_inst(1, 9877, "resin")])
    msg = bridge_tools._use_instance_impl(r, "nope")
    assert "No live Blender" in msg  # errors returned as text, not raised, for the agent
