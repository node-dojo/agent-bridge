# Agent Bridge

Agent Bridge is a standalone MCP server that routes an agent's Blender tool
calls to whichever live Blender instance has a given `.blend` file open. It
wraps the upstream [blmcp](https://projects.blender.org/lab/blender_mcp)
(`blender-mcp`) tool set unmodified — every one of its ~30 tools is inherited
as-is — and adds a registry-backed resolver so a target is picked by filename
stem (e.g. `"resin"` for `resin.blend`) instead of always hitting whichever
Blender the socket happens to connect to first. The chosen target is sticky
per session and can be changed at any time with `use_instance(...)`.

This solves a real multi-instance problem: when several Blenders are running
at once, plain `blender-mcp` has no way to distinguish them. Agent Bridge adds
that layer without forking or patching blmcp itself.

## Install

Agent Bridge is a standalone repo (not a subdirectory of another project).
From the repo root:

```bash
uv tool install --from . agent-bridge
```

or, into a local virtualenv:

```bash
pip install -e .
```

Either way, upstream `blender-mcp` is pulled in automatically — it's pinned
to a specific git commit in `pyproject.toml` (see Maintenance below), not a
released version, so no separate blmcp install step is needed.

Installing produces an `agent-bridge` console script (entry point
`agent_bridge.bridge_server:main`). Confirm it resolved:

```bash
which agent-bridge          # uv tool install
# or, for a local venv:
ls .venv/bin/agent-bridge
```

## Use

1. **In each Blender instance:** open the N-panel, go to **Claude > Agent
   Bridge**, and click **Serve to Agents**. This starts the official Blender
   MCP add-on's socket server in that instance and registers its PID, port,
   and `.blend` filename stem into a shared registry at
   `~/.blender-pairs/<pid>.json`. Click **Stop Serving** to unregister.

2. **Point Claude Code's `blender` MCP server at Agent Bridge instead of
   blender-mcp.** In `~/.claude.json`, find the `blender` MCP server entry
   and change its `command` to the `agent-bridge` executable path (the one
   printed by `which agent-bridge`, or your venv's `.venv/bin/agent-bridge`):

   ```jsonc
   {
     "mcpServers": {
       "blender": {
         "command": "/path/to/agent-bridge",
         "args": []
       }
     }
   }
   ```

   Restart Claude Code (or reconnect the MCP server) after editing.

3. **In chat:**
   - `list_instances` — list the live Blenders currently registered (stem,
     pid, port, blend path).
   - `use_instance("resin")` — target the Blender editing `resin.blend`.
     All subsequent Blender tool calls in this session go there until you
     switch again. Pass `pid=...` to disambiguate if the same filename is
     open in more than one instance.

## How it works

Agent Bridge doesn't fork blmcp — it depends on it as a library and
monkeypatches one seam: `blmcp.tools_helpers.connection.get_connection_params`
is replaced with a function that resolves the current sticky target from the
registry (`~/.blender-pairs/<pid>.json`) instead of blmcp's normal fixed
host/port lookup. Because blmcp's tools call `get_connection_params()`
unqualified at call time, patching the module attribute once, at startup,
is enough to redirect every one of blmcp's ~30 auto-discovered tools —
nothing else about them changes.

On top of that, Agent Bridge registers two of its own tools:
`use_instance` (pick/switch the sticky target) and `list_instances` (list
what's currently registered and reachable). The Blender-side panel/operator
in `agent_bridge/__init__.py` is what writes an instance into the registry
in the first place.

## Maintenance

`blender-mcp` is pinned to a specific git commit SHA in `pyproject.toml`
(not a tag or branch), because Agent Bridge depends on an internal seam
(`get_connection_params`) that upstream could relocate or rename without
warning:

```
blender-mcp @ git+https://projects.blender.org/lab/blender_mcp.git@<SHA>#subdirectory=mcp
```

Bump this pin deliberately, not automatically. After bumping, run the
coupling smoke test — it fails loudly if the upstream seam moved or its
tool-discovery shape changed:

```bash
.venv/bin/python -m pytest tests/test_coupling_smoke.py
```

Run the full suite the same way:

```bash
.venv/bin/python -m pytest
```
