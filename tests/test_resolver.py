import pytest
from agent_bridge import resolver as R

def _inst(pid, port, stem, host="localhost"):
    return {"blender_pid": pid, "port": port, "host": host,
            "blendfile": f"/x/{stem}.blend", "blendfile_stem": stem}

def make(instances):
    return R.Resolver(instances_fn=lambda: list(instances))

def test_set_target_single_match():
    r = make([_inst(1, 9877, "resin"), _inst(2, 9878, "assetdev")])
    entry = r.set_target("resin")
    assert entry["port"] == 9877
    assert r.resolve() == ("localhost", 9877)

def test_target_match_is_case_insensitive_and_ext_optional():
    r = make([_inst(1, 9877, "Resin")])
    r.set_target("resin.blend")
    assert r.resolve() == ("localhost", 9877)

def test_no_match_raises_listing_live():
    r = make([_inst(1, 9877, "resin")])
    with pytest.raises(R.TargetError) as ex:
        r.set_target("nope")
    assert "resin" in str(ex.value)

def test_ambiguous_same_file_twice_refuses_and_lists_pids():
    r = make([_inst(1, 9877, "resin"), _inst(2, 9879, "resin")])
    with pytest.raises(R.TargetError) as ex:
        r.set_target("resin")
    assert "1" in str(ex.value) and "2" in str(ex.value)

def test_ambiguous_resolved_by_pid():
    r = make([_inst(1, 9877, "resin"), _inst(2, 9879, "resin")])
    entry = r.set_target("resin", pid=2)
    assert entry["port"] == 9879

def test_default_single_live_used_when_no_target():
    r = make([_inst(7, 9880, "only")])
    assert r.resolve() == ("localhost", 9880)

def test_default_zero_live_raises():
    r = make([])
    with pytest.raises(R.TargetError):
        r.resolve()

def test_default_multi_live_refuses():
    r = make([_inst(1, 9877, "a"), _inst(2, 9878, "b")])
    with pytest.raises(R.TargetError) as ex:
        r.resolve()
    assert "a" in str(ex.value) and "b" in str(ex.value)

def test_sticky_survives_between_calls():
    r = make([_inst(1, 9877, "resin"), _inst(2, 9878, "assetdev")])
    r.set_target("assetdev")
    assert r.resolve() == ("localhost", 9878)
    assert r.resolve() == ("localhost", 9878)
