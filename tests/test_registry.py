from agent_bridge import registry as reg

def test_stem_of_prefers_explicit_field():
    assert reg.stem_of({"blendfile_stem": "resin", "blendfile": "/x/other.blend"}) == "resin"

def test_stem_of_derives_from_blendfile_when_no_stem():
    assert reg.stem_of({"blendfile": "/a/b/no3d asset dev.blend"}) == "no3d asset dev"

def test_stem_of_empty_when_nothing():
    assert reg.stem_of({}) == ""

def test_write_read_remove_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "REGISTRY_DIR", tmp_path)
    reg.write(4242, {"port": 9877, "blendfile": "/x/resin.blend"})
    got = reg.read(4242)
    assert got["port"] == 9877 and got["blender_pid"] == 4242
    assert reg.remove(4242) is True
    assert reg.read(4242) is None

def test_list_all_reads_multiple(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "REGISTRY_DIR", tmp_path)
    reg.write(1, {"port": 9877})
    reg.write(2, {"port": 9878})
    ports = sorted(e["port"] for e in reg.list_all())
    assert ports == [9877, 9878]

def test_gc_dead_removes_dead_pids(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "REGISTRY_DIR", tmp_path)
    # A PID that cannot exist (very large) is treated as dead.
    reg.write(999999999, {"port": 9877})
    cleaned = reg.gc_dead()
    assert 999999999 in cleaned
    assert reg.read(999999999) is None
