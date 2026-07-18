# Agent Bridge — middle-tier instructions

This is the **Agent Bridge** layer of a three-tier instruction hierarchy
(**Global → Agent Bridge → Project**). Rules here apply to any Blender
session where the Agent Bridge add-on is serving, and take precedence over
Global rules but yield to Project rules when they conflict.

Only put things in this file that are:

1. Specific to how Agent Bridge itself works, or
2. Cross-cutting knowledge about the user's Blender add-on ecosystem that
   every session should share (canonical repo locations, vendor
   relationships, etc.).

Anything project-specific belongs in the project's own `CLAUDE.md`; anything
truly universal belongs in the global doc.

---

## Domain expertise to bring by default

Every session under Agent Bridge should assume the user is working at the
intersection of:

- **CGI** — Blender-first, real-time and offline rendering, Eevee & Cycles,
  glTF/USD pipelines, Verge3D interop.
- **Applied Geometry** — geometry nodes, curve/surface math, parametric
  modeling, tolerance/fit reasoning for physical parts.
- **Design** — visual composition, typography, brand systems, layout;
  outputs should read as intentional, not defaults.
- **Class-A surface CAD** — G2/G3 curvature continuity, highlight/reflection
  quality, engineering-grade surface topology (industrial-design-native
  vocabulary is welcome).
- **Computational Design Theory** — rule-based / parametric / generative
  systems; treat "make it look right" as an optimization problem with
  constraints when appropriate.

Default to precise vocabulary from these fields rather than beginner
paraphrasing. If a term isn't in the user's context, name it and briefly
gloss it once.

---

## Canonical codebases (the drift map)

The rule for every entry below: **edit at the canonical path**, sync to
downstream copies via the documented tool, never edit the vendored/installed
copies directly.

### Agent Bridge (this add-on)

- **Canonical source**: `~/Projects/agent-bridge/agent_bridge/`
  - Git: local repo, branch `master`, no remote yet. Latest commit
    `f6d1b30 docs: handoff document` (as of 2026-07-08).
  - `HANDOFF.md` in the repo root has the current state + architecture +
    task list.
- **Installed copy** (Blender loads this): `~/Library/verge3d_blender/addons/agent_bridge/`
- **Sync policy**: currently these are separately-maintained copies.
  Preferred long-term fix: symlink installed → canonical
  (`ln -s ~/Projects/agent-bridge/agent_bridge ~/Library/verge3d_blender/addons/agent_bridge`).
  Until that's in place, mirror any edit made at the install path back to the
  source repo (and commit) before ending a session.

### No3d Dev — the active monorepo

- **Path**: `~/Projects/no3d-asset-developer/`
- **Git**: `github.com/node-dojo/no3d-dev.git` @ `main`
- **Read first**: `~/Projects/no3d-asset-developer/AGENTS.md` — that file is
  authoritative for anything inside this repo. Do not restate its rules
  here; this doc only points to it.
- **Also**: `README.md`, `HANDOFF.md` for state; `docs/` for architecture.
- **Tooling**:
  - `tools/ship.sh <extension_id> <version> [--notes ...] [--sync-vendor] [--dry-run]`
    — the ship pipeline (bump → build → prune → publish → git tag → vault
    ship-log append).
  - `tools/vendor_sync.sh <extension_id> | --all [--dry-run]` — pull the
    canonical upstream source of a vendored extension into
    `extensions/<name>/` before shipping.
  - `vendor.toml` — declares which sub-extensions are vendored and from
    where.

### Sub-extensions inside the monorepo

Path: `~/Projects/no3d-asset-developer/extensions/<name>/`

- **`no3d_asset_developer`** (v4.0.1) — **authored in place** in the
  monorepo. This is the backend / internal-facing developer suite: asset
  packaging, library management, personal WIP features that may migrate to
  the public product.
- **`no3d_camera_utilities`** (v1.0.0) — **vendored**, not authored in
  place. Canonical source is a separate repo (see next section). To pick up
  upstream changes:
  ```
  ~/Projects/no3d-asset-developer/tools/vendor_sync.sh no3d_camera_utilities
  ```
  Never edit inside `extensions/no3d_camera_utilities/` — the sync will
  clobber it.

### Canonical source repos for vendored extensions

- **no3d_camera_utilities**
  - Path: `~/Projects/No3d Camera Utilities/`
  - Git: `github.com/node-dojo/no3d-camera-utilities.git` @ `main`
  - **Edit here.** Bump version in `blender_manifest.toml`, commit, push,
    then run `vendor_sync.sh` inside the monorepo to pull it in.

### Publication target (public product)

- **no3d-tools-addon** — `~/Projects/no3d-tools-addon/`
  - The user-facing flagship at **no3dtools.com**.
  - No git remote at the moment; publication mechanism lives elsewhere in
    the workflow. Verify with `git -C ~/Projects/no3d-tools-addon remote -v`
    before assuming anything.
  - Features migrate here from No3d Dev when production-ready. **Do not
    author new features directly here** — start in the monorepo, promote.

### Archived / inactive

- `~/Projects/_archive/no3d-tools-wip/` — WIP that was parked in June 2026,
  git-initialized on archive for preservation. Not active; do not use as a
  reference for new work. If any of its ideas (`align.py`, `make_spin.py`,
  `toolbox.py`) become relevant again, resurrect them as a branch inside
  the monorepo, not as a floating folder.

### Drift-check ritual

Before making non-trivial edits to any add-on:

```
git -C <canonical_path> status
git -C <canonical_path> log --oneline -5
```

If there's uncommitted or unpushed work, ask the user before overwriting.
If in doubt about "which copy is canonical," this file's map is authoritative
— consult it first.

---

## How Agent Bridge itself works

**Purpose**: let external Claude agents target a specific Blender instance
by its `.blend` filename, even when many Blender processes are open.

**Registry**: JSON files at `~/.blender-pairs/<pid>.json`. Each running
Blender that has clicked "Serve to Agents" in the N-panel writes its own
entry. Schema (see `registry.py` and `build_register_payload` in
`__init__.py`):

```json
{
  "blender_pid": 12345,
  "port": 9877,
  "host": "localhost",
  "blendfile": "/absolute/path/to/scene.blend",
  "blendfile_stem": "scene",
  "started_at": 1721340000.0
}
```

- **Serve**: click *Serve to Agents* → starts the official Blender MCP
  server on a free port in `9876–9999` → writes the registry entry.
- **Stop**: click *Stop Serving* → stops the MCP server → removes the
  registry file.
- **GC**: `registry.live_instances()` prunes entries whose pid is no longer
  alive before returning the list.
- **Targeting**: the standalone `agent-bridge` MCP process (outside Blender)
  reads the registry and routes agent bpy calls to the matching entry by
  `.blend` stem.

**Key files** (both source repo and installed copy have the same layout):

- `__init__.py` — Blender-side operators + N-panel (this doc's discovery
  helper `discover_instruction_files` lives here).
- `registry.py` — bpy-free registry read/write/GC. Runs both in Blender and
  in the standalone MCP subprocess.
- `serve_helpers.py` — port allocation + official MCP add-on start/stop
  glue.
- `bridge_server.py`, `bridge_tools.py`, `resolver.py` — standalone MCP
  server side (bpy-free; not exercised inside Blender).

---

## Editing / reloading this add-on

**Golden rule**: edit at the canonical source
(`~/Projects/agent-bridge/agent_bridge/`), sync to install, hot-reload in
Blender. If you edit at the install path directly, mirror back to the source
repo and commit before ending the session — otherwise the next `ship` or the
next dev session sees stale code.

**Sync from source to install** (manual, until a symlink is in place):

```
rsync -a --delete \
  ~/Projects/agent-bridge/agent_bridge/ \
  ~/Library/verge3d_blender/addons/agent_bridge/
```

**Hot-reload inside a running Blender** (works from the Agent Bridge MCP or
Blender's Python console):

```python
import bpy, sys
addon_id = "bl_ext.addons.agent_bridge"
bpy.ops.preferences.addon_disable(module=addon_id)
for name in list(sys.modules):
    if name == addon_id or name.startswith(addon_id + "."):
        del sys.modules[name]
bpy.ops.preferences.addon_enable(module=addon_id)
```

**Manifest changes** (`blender_manifest.toml` — version, permissions,
dependencies): a hot-reload will not pick these up. Do a full extension
re-install through Blender's Preferences → Extensions.

**Testing without Blender**: the top-level module and `registry.py` are
`bpy`-guarded / bpy-free respectively — you can import them from plain
Python for unit tests. `serve_helpers.py` imports `bpy` lazily inside its
functions for the same reason.

---

## Ship log & the Vault

`tools/ship.sh` (inside the No3d Dev monorepo) appends an entry to
`$VAULT_001/PROJECTS/no3d tools/ship-log.md` on every successful ship.
Treat that log as the audit trail for "what shipped when." When the user
asks about release history, consult it first, not git tags in isolation —
the log has the human-written notes.

`$VAULT_001` is expected at `~/Vault_001/`.

---

## When in doubt

Prefer reading the canonical repo's `AGENTS.md` / `HANDOFF.md` / `README.md`
over inferring from folder contents. Prefer running a `git status` +
`git log --oneline -5` on any add-on before you claim to know its state.
Prefer asking the user over overwriting uncommitted work.
