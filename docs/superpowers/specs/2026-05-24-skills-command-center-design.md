# Skills Command Center Design

## Source

This design implements Stage 5 from `PROMPT_SPEC.md`: `skills/` with
`registry`, `builtins/graph.py`, and `builtins/fs.py`.

It also respects the system invariant from `PROMPT_SPEC.md` that SubAgents do
not access disk directly. They use `read_file`, `write_file`, and CodeGraph
tools through Skills.

## Product Direction

Stage 5 is `v0.5.0-skills-foundation`.

The approved UX direction is Guided Command Center with a stronger "wow"
presentation:

- `ivycode skills` opens a polished Rich dashboard.
- Graph and filesystem skills are visible, named, and permission-labelled.
- Users can save a reusable local plugin shell without hand-editing folders.
- Every guided action has a direct CLI command for power users.
- Scan, validate, save, and rollback use short terminal-native status motion.

The design target is simple for beginners and fast for experienced users.

## User Experience

### `ivycode skills`

Default command. It prints a compact command center:

- header: `ivycode skills · local command center`
- graph stats if `.ivycode/codegraph.sqlite` exists
- installed builtin skills grouped by capability
- permission labels in plain language
- local plugin shelf from `~/.ivycode/plugins`
- suggested next action, for example saving a workflow as a local plugin shell

Example rows:

```text
✓ search_symbols         graph:read      ready
✓ get_impact_radius     graph:read      ready
◆ read_file             fs:read         project-gated
◇ write_file            fs:write        guarded
```

### Direct Commands

The dashboard must not be required for automation. Stage 5 exposes:

- `ivycode skills list`
- `ivycode skills inspect <name>`
- `ivycode skills run <name> --arg key=value`
- `ivycode skills save <slug> --skill <name> --description <text>`
- `ivycode skills plugins`

`save` creates a local plugin shell under:

```text
~/.ivycode/plugins/<slug>/
```

The initial saved plugin shell contains metadata and selected skill references,
not arbitrary executable code. This keeps Stage 5 safe and testable while
creating the plugin-saving flow users can understand immediately.

## Architecture

### Files

- `ivycode/skills/registry.py`
  - `SkillDefinition`
  - `SkillRegistry`
  - `@skill` decorator
  - JSON Schema generation from Python signatures and annotations

- `ivycode/skills/runtime.py`
  - `SkillRuntime`
  - owns `project_root`
  - optionally owns `CodeGraphService`

- `ivycode/skills/builtins/graph.py`
  - `search_symbols`
  - `get_impact_radius`
  - `get_framework_routes`

- `ivycode/skills/builtins/fs.py`
  - `read_file`
  - `write_file`
  - path checks against `project_root`
  - optional line-range reads for SubAgent-safe context expansion

- `ivycode/skills/store.py`
  - local plugin shell creation
  - plugin manifest read/list
  - rollback if a save fails halfway

- `ivycode/cli/app.py`
  - add `skills` Typer subcommand group
  - keep `chat` and `plan` behind the current stage boundary

### Data Flow

1. CLI creates `SkillRuntime(project_root=Path.cwd())`.
2. Builtin skills register into `SkillRegistry`.
3. `ivycode skills` renders registry state and local plugin shelf.
4. `ivycode skills run graph.search_symbols --arg query=auth` invokes the
   registered callable through the registry.
5. `ivycode skills save auth-helper --skill graph.search_symbols` writes a
   local plugin shell after manifest validation.

## Safety

Filesystem skills are project-gated:

- `read_file` rejects paths outside `project_root`.
- `write_file` rejects paths outside `project_root`.
- `write_file` creates parent folders only inside `project_root`.
- Plugin shell writes are restricted to `~/.ivycode/plugins/<slug>`.
- Slugs must be lowercase letters, digits, and hyphens.

Permissions are both machine-readable and human-readable:

| Scope | Human Label |
|---|---|
| `graph:read` | can search the local code graph |
| `fs:read` | can read files inside this project |
| `fs:write` | can write files inside this project |
| `plugin:write` | can save a local plugin shell |

## Motion And Polish

Terminal motion is used only for state changes:

- scanning skills
- validating a manifest
- saving a plugin shell
- rolling back a failed save

No animation is used for repeated keyboard actions. Status motion should feel
fast: under 300 ms where practical, with immediate feedback.

The dashboard uses the existing ivycode palette:

- mint for ready/safe state
- cyan for filesystem read state
- warm accent for guarded write state
- violet for system/router/plugin state
- red only for blocked or failed actions

## Non-Scope

Stage 5 does not implement:

- external plugin marketplace
- arbitrary third-party Python code execution
- prompt_toolkit REPL command palette
- Router planning
- SubAgent execution
- full plugin lifecycle hooks

Those belong to later stages after Skills have a stable local contract.

## Testing

Required tests:

- registry registers async callables and exposes JSON Schema
- duplicate skill names are rejected
- builtin graph skills call `CodeGraphService`
- `read_file` returns exact line ranges
- `read_file` and `write_file` reject paths outside `project_root`
- plugin save creates a manifest and rolls back on validation/write failure
- `ivycode skills` renders builtin skills and plugin shelf
- direct CLI commands return stable output for tests

## Verification Before Commit

Run:

```bash
python -m pytest -q
python -m ruff check .
python -m mypy ivycode
python -m ivycode skills
```

Expected result: all commands exit with code 0.
