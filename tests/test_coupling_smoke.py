# SPDX-License-Identifier: GPL-3.0-or-later
"""Coupling smoke test: guards the upstream blmcp seam Agent Bridge depends on.

Agent Bridge does not vendor or fork blmcp — it runs blmcp's own tool
auto-discovery and monkeypatches one module attribute
(blmcp.tools_helpers.connection.get_connection_params) to reroute connection
resolution through Agent Bridge's own Resolver. That only works as long as:

  - get_connection_params keeps its 0-arg, (host, port)-returning shape,
  - send_code keeps resolving get_connection_params unqualified at call time
    (so patching the module attribute is actually observed),
  - blmcp.tools keeps being a pkgutil-discoverable package of modules exposing
    a register(mcp) callable, using the same *_toolcode / _template_* skip
    filters main()/build_server() apply,
  - blmcp/data/prompts.yml keeps existing with an 'initial_instructions' key,
  - build_server() keeps assembling a FastMCP that carries both blmcp's tools
    and Agent Bridge's own use_instance/list_instances.

This suite is the regression gate for any blmcp pin (SHA) bump in
pyproject.toml. Re-run it (`.venv/bin/python -m pytest tests/test_coupling_smoke.py -v`)
immediately after bumping the pin, before touching anything else. A failure
here means the monkeypatch or tool-discovery wiring broke silently upstream —
fix the seam before shipping.
"""
import asyncio
import importlib
import inspect
import pkgutil

import pytest


# --- base tests (from the Task 6 brief) -------------------------------------


def test_get_connection_params_exists_zero_arg():
    from blmcp.tools_helpers import connection
    assert hasattr(connection, "get_connection_params")
    sig = inspect.signature(connection.get_connection_params)
    assert len(sig.parameters) == 0


def test_send_code_exists():
    from blmcp.tools_helpers import connection
    assert hasattr(connection, "send_code")


def test_patch_lands_through_send_code():
    """send_code must resolve get_connection_params at call time (unqualified),
    so patching the module attribute is observed."""
    from blmcp.tools_helpers import connection

    called = {}

    def fake():
        called["hit"] = True
        return ("localhost", 65500)  # nothing listening -> ConnectionError expected

    orig = connection.get_connection_params
    connection.get_connection_params = fake
    try:
        with pytest.raises(ConnectionError):
            connection.send_code("x", strict_json=False)
        assert called.get("hit"), "send_code did not call the patched get_connection_params"
    finally:
        connection.get_connection_params = orig


# --- enhanced tests (from the wiring review) --------------------------------


def _skip_module(modname: str) -> bool:
    """Same skip filters build_server()/main() apply during auto-discovery."""
    return modname.endswith("_toolcode") or modname.startswith("_template_")


def _discovered_register_modules():
    import blmcp.tools as tools_pkg

    mods = []
    for _importer, modname, _ispkg in pkgutil.iter_modules(tools_pkg.__path__):
        if _skip_module(modname):
            continue
        mod = importlib.import_module(f"blmcp.tools.{modname}")
        if hasattr(mod, "register"):
            mods.append(mod)
    return mods


# Recorded expected count of register()-bearing blmcp.tools modules, pinned to
# blmcp @ 98b0e49 (see pyproject.toml). If a blmcp pin bump changes this
# number, that's expected — update EXPECTED_TOOL_MODULE_COUNT deliberately,
# don't just silence the assertion.
EXPECTED_TOOL_MODULE_COUNT = 20


def test_tool_auto_discovery_count():
    mods = _discovered_register_modules()
    assert len(mods) > 0
    assert len(mods) == EXPECTED_TOOL_MODULE_COUNT, (
        f"Discovered {len(mods)} register()-bearing blmcp.tools modules, "
        f"expected {EXPECTED_TOOL_MODULE_COUNT}. If blmcp's pin was bumped "
        "and this is intentional, update EXPECTED_TOOL_MODULE_COUNT."
    )


def test_every_discovered_module_register_is_callable():
    mods = _discovered_register_modules()
    assert mods, "no register()-bearing modules discovered"
    for mod in mods:
        assert hasattr(mod, "register"), f"{mod.__name__} lost its register attribute"
        assert callable(mod.register), f"{mod.__name__}.register is not callable"


def test_every_discovered_module_register_accepts_a_mcp_instance():
    """Cheap enough to actually call: build one FastMCP and register every
    discovered module onto it, proving register(mcp) really has that shape
    (rather than just being *a* callable) — no server is run."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("coupling-smoke-probe")
    for mod in _discovered_register_modules():
        mod.register(mcp)


def test_prompts_yml_has_initial_instructions():
    import os
    import yaml
    import blmcp

    data_dir = os.path.join(os.path.dirname(os.path.abspath(blmcp.__file__)), "data")
    prompts_path = os.path.join(data_dir, "prompts.yml")
    assert os.path.exists(prompts_path), f"missing {prompts_path}"

    with open(prompts_path, encoding="utf-8") as fh:
        prompts = yaml.safe_load(fh)

    assert "initial_instructions" in prompts


def test_build_server_assembles_expected_tool_set():
    """build_server() (main()'s assembly logic, minus mcp.run) must yield a
    FastMCP named 'agent-bridge' whose tool set includes both a blmcp tool
    and Agent Bridge's own bridge tools."""
    from blmcp.tools_helpers import connection
    import agent_bridge.bridge_server as bridge_server

    # Capture globals before the patch is installed (via build_server()).
    orig_get_connection_params = connection.get_connection_params
    orig_active_target = bridge_server.RESOLVER.active_target
    orig_active_pid = bridge_server.RESOLVER.active_pid

    try:
        mcp = bridge_server.build_server()
        assert mcp.name == "agent-bridge"

        tools = asyncio.run(mcp.list_tools())
        tool_names = {t.name for t in tools}

        assert "use_instance" in tool_names
        assert "list_instances" in tool_names
        assert "execute_blender_code" in tool_names
    finally:
        # Restore the patched globals to prevent test isolation hazard.
        connection.get_connection_params = orig_get_connection_params
        bridge_server.RESOLVER.active_target = orig_active_target
        bridge_server.RESOLVER.active_pid = orig_active_pid
