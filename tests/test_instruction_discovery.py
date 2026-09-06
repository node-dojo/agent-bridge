from pathlib import Path

import agent_bridge


def test_agent_bridge_prefers_its_agent_agnostic_instruction_file():
    records = agent_bridge.discover_instruction_files(Path("/nonexistent-project"))
    bridge_records = [item for item in records if item["scope"] == "agent_bridge"]

    assert len(bridge_records) == 1
    assert bridge_records[0]["label"] == "AGENT.md"
    assert Path(bridge_records[0]["path"]).name == "AGENT.md"
