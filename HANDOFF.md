# Agent Bridge — Handoff

**Date:** 2026-07-08
**Repo:** `/Users/joebowers/Projects/agent-bridge` (standalone git repo, branch `master`)
**Status:** Code complete (Tasks 1–7.5), all 30 automated tests passing. **Only Task 8 (live two-Blender end-to-end) remains** — it needs your machine and a fresh Claude Code session.

---

## 1. What Agent Bridge is

Replaces the single, fought-over Blender MCP port with a broker that routes an agent's Blender calls to the **live Blender instance named by its `.blend` filename**. Sticky per session, switchable mid-conversation via a `use_instance` tool. Any number of agents ↔ any number of Blenders; no hogging port 9876, no manual disconnect, no stale-port breakage on restart.

**One-liner:** `use_instance("resin")` points this agent session at the Blender editing `resin.blend`; every Blender call goes there until you switch.

## 2. How it works (architecture)

Agent Bridge **is `blmcp` (the official Blender MCP server) with a smarter address book** — NOT a fork.

- **Agent side** (`agent-bridge` console script → `agent_bridge/bridge_server.py:main`): builds its own `FastMCP("agent-bridge")`, runs blmcp's tool auto-discovery (inherits all ~20 tool modules / 28 tools), monkeypatches **one** function — `blmcp.tools_helpers.connection.get_connection_params` — to resolve the sticky target's live `(host, port)` from the registry, and adds two tools: `use_instance(target, pid=None)` and `list_instances()`.
- **Blender side** (`agent_bridge/__init__.py` operators + panel, `serve_helpers.py`): auto-serve starts the official MCP server on a free port and registers this instance (pid, port, `.blend` stem) into `~/.blender-pairs/<pid>.json`; the panel also provides manual stop/restart controls.
- **Registry** (`agent_bridge/registry.py`): shared on-disk format at `~/.blender-pairs/<pid>.json`. `gc_dead()` drops entries for dead PIDs so stale instances never resolve.
- **Resolver** (`agent_bridge/resolver.py`): filename→live port; sticky active target; refuses ambiguity (same `.blend` open twice → lists PIDs); default = the-only-one-live, else refuse.

### Why the monkeypatch lands (critical, don't "fix" it)
`blmcp`'s `send_code()` (called by all 17 name-binding tools) calls `get_connection_params()` **unqualified within its own module**, resolved at call time. So reassigning `connection.get_connection_params` is observed by every tool. Patching `send_code` instead would NOT work (tools `from ... import send_code` bind it at import). The coupling smoke test (`tests/test_coupling_smoke.py`) guards this seam.

## 3. Key decisions (context for anyone picking this up)

- **Sticky + agent-switchable**, not per-call targeting. One active target at a time; switch with `use_instance`. Rejected per-call because: larger wrong-target blast radius, no confirmable "current" instance, and — since each call is an independent socket that closes after — per-call's "one agent spans two Blenders in one step" benefit is thin anyway.
- **STANDALONE. Does NOT import `claude_pair`.** Claude Pair was only a code-guidance reference. Agent Bridge owns its own bpy-free `registry.py` and `serve_helpers.py`. Interop with other writers is by registry *format* only.
- **Extracted to its own repo.** Originally built nested inside `no3d-asset-developer`, but that repo's root is itself a Blender add-on package (`__init__.py` → `import bpy`), which broke headless pytest collection every way tried. Moving to a standalone repo eliminated the whole class of problem. **Lesson:** don't nest a testable package under a bpy-importing add-on root. (See the vault card's note about the future `no3d-blender-extensions` monorepo "bucket" — Agent Bridge is intended to fold in there later.)
- **blmcp is pinned to a git SHA** (`98b0e49d98321d321c7e631389200f513f765d59`) in `pyproject.toml`. Not a moving target. Bump deliberately; see Maintenance.

## 4. Repo layout

```
agent-bridge/
├── agent_bridge/
│   ├── __init__.py          # Blender side: build_register_payload (headless-safe) +
│   │                         #   bpy-guarded serve/stop operators + panel + register()
│   ├── blender_manifest.toml # Blender extension manifest (THIS dir is the extension root)
│   ├── registry.py          # standalone ~/.blender-pairs/<pid>.json access + stem_of/live_instances
│   ├── resolver.py           # Resolver: sticky filename→(host,port), ambiguity/default rules, TargetError
│   ├── serve_helpers.py      # own port-finding + official-MCP-addon control (bpy imported lazily)
│   ├── bridge_server.py      # RESOLVER, install_patch(), patched_get_connection_params(),
│   │                         #   build_server() (assembly), main() (=build_server + mcp.run stdio)
│   └── bridge_tools.py        # use_instance + list_instances (register onto the FastMCP)
├── tests/                    # 30 tests: registry, resolver, bridge_tools, register_payload, coupling_smoke
├── docs/superpowers/
│   ├── specs/2026-07-08-agent-bridge-design.md
│   └── plans/2026-07-08-agent-bridge.md
├── dist/agent_bridge-0.2.0.zip   # built Blender extension (gitignored)
├── pyproject.toml            # `agent-bridge` console script; pinned blmcp git dep; hatchling
├── pytest.ini                # testpaths=tests (clean; no conftest hacks needed in this repo)
├── README.md
└── LICENSE                    # GPL-3.0-or-later
```

## 5. Current state

- **Branch:** `master`. 10 commits, `62dbdb0` (Task 1) → `073eea0` (Task 7.5).
- **Tests:** `.venv/bin/python -m pytest` → **30 passed**.
- **Package:** editable-installed in `.venv`; wheel builds clean; `agent-bridge` console script launches as a stdio MCP server.
- **Blender extension:** `dist/agent_bridge-0.2.0.zip` validates (`extension validate` exit 0) and builds.
- **Task ledger:** `.superpowers/sdd/progress.md` (per-task commit ranges, review status, deferred findings).

### Per-task status
| Task | Status |
|---|---|
| 1. Registry module | ✅ 6 tests |
| 2. Sticky resolver (+ KeyError→TargetError hardening) | ✅ reviewed, 17 tests |
| 3. Monkeypatch seam + entry point | ✅ patch-lands verified |
| 4. Bridge tools + FastMCP wiring | ✅ reviewed; 28 tools assemble incl use_instance/list_instances |
| 5. Blender-side serve+register + serve_helpers | ✅ reviewed; bpy guard airtight, headless imports OK |
| 6. Coupling smoke test (8 guards) + build_server refactor | ✅ reviewed |
| 7. Packaging + README | ✅ wheel builds |
| 7.5. Blender extension manifest + LICENSE | ✅ validates, zip builds |
| **8. Live two-Blender e2e** | ⏳ **pending — needs you** |

## 6. Environment already set up (done in the build session)

- `~/.claude.json` **already swapped**: the top-level `blender` MCP server `command` now points at
  `/Users/joebowers/Projects/agent-bridge/.venv/bin/agent-bridge` (was `/Users/joebowers/.local/bin/blender-mcp`).
  **Backup:** `~/.claude.json.bak-agentbridge`. Revert anytime: `cp ~/.claude.json.bak-agentbridge ~/.claude.json`.
- Stale registry entries cleared (a live PID 12858 entry was correctly kept).

## 7. Task 8 — how to finish (the only remaining work)

Needs a **fresh Claude Code session** (the MCP command swap loads at session launch).

**Setup**
1. Install the extension in Blender: **Edit > Preferences > Get Extensions > ▾ > Install from Disk…** → `/Users/joebowers/Projects/agent-bridge/dist/agent_bridge-0.2.0.zip`. Enable it → an **Agent Bridge** panel appears in the 3D viewport N-panel under the **Claude** tab and auto-serves after startup.

**Test (new session)**
2. Open **two** Blenders and save each to a distinct file (e.g. `resin.blend`, `assetdev.blend`). Confirm both appear in **Claude > Agent Bridge > Live instances**.
3. Confirm registration: `ls ~/.blender-pairs/` and cat the JSONs → two entries, distinct ports, `blendfile_stem` = `resin` / `assetdev`.
4. In the new agent chat: `list_instances` (shows both) → `use_instance("resin")` → create empty `AB_MARKER_RESIN` → `use_instance("assetdev")` → create `AB_MARKER_ASSETDEV`.
5. Verify partition: each marker exists ONLY in its own file → routing works.
6. Restart-resilience: close resin's Blender → `use_instance("resin")` should error cleanly (not hang) → reopen + Serve → `use_instance("resin")` succeeds on the new port.

### ⚠️ Watch these first (review-flagged risks that only surface live)
These `serve_helpers.py` assumptions are copied from the design doc and NOT yet verified against a real Blender + official MCP add-on:
- **Official add-on operator idnames**: `bpy.ops.blmcp.server_start` / `server_stop`. If wrong for your Blender's official MCP add-on, **Serve to Agents will error** — this is the #1 thing to check.
- **Package keys**: `bl_ext.lab_blender_org.mcp` (and fallbacks) in `serve_helpers.official_mcp_prefs()`.
- **`mcp_to_blender_server.is_running()`** interface.
- When the official add-on is absent, confirm the Serve error surfaces **legibly in the Blender UI**, not just console.
- Port-reuse branch: if the official server was started independently by you, confirm `prefs.port` reflects the actually-bound port.

## 8. Maintenance

- **Bumping blmcp:** change the pinned SHA in `pyproject.toml`, reinstall, then run
  `.venv/bin/python -m pytest tests/test_coupling_smoke.py`. It **fails loudly** if the upstream seam moved
  (tool-module count `EXPECTED_TOOL_MODULE_COUNT`, skip filters, `prompts.yml`, `register()` shape, patch landing).
  A pin bump is the trigger to re-run that suite.
- **Run all tests:** `.venv/bin/python -m pytest` from repo root.
- **Rebuild the extension zip:** `"/Applications/Blender 5.2 Beta.app/Contents/MacOS/Blender" --background --factory-startup --command extension build --source-dir ./agent_bridge --output-dir ./dist`

## 9. Deferred / future

- **Deferred minors** (see ledger): resolver's pid-filtered no-match message wording; `_norm(None)` guard. Both low-risk, non-blocking — candidates for the final whole-branch review.
- **Final whole-branch review** not yet run (SDD's last step). Recommended before merge/first real use.
- **Phase 2 (design §7):** mirror each agent's active target to `~/.blender-pairs/agents/<agent-port>.json` so the Blender panel can show "agent on :NNNN → targeting X". Deferred out of v1.
- **The "bucket" monorepo:** intended home is a future `no3d-blender-extensions` monorepo grouping all no3d add-ons (each a top-level package, shared tooling, no add-on as the repo root). Fold `agent_bridge/` in as the seed member via `git mv`. See the vault project card.

## 10. Reference docs

- **Design spec:** `docs/superpowers/specs/2026-07-08-agent-bridge-design.md`
- **Implementation plan:** `docs/superpowers/plans/2026-07-08-agent-bridge.md`
- **Task ledger + per-task briefs/reports:** `.superpowers/sdd/`
- **Vault project card:** `$VAULT_001/PROJECTS/Agent Bridge/Agent Bridge.md`
