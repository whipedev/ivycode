# Ivycode UI Foundation Design

## Scope

This stage implements `PROMPT_SPEC.md` section 15, step 2:

- `ivycode/ui/theme.py`
- `ivycode/ui/console.py`
- `ivycode/ui/layout.py`
- basic `ModelPanel`

The goal is to establish stable Rich renderables and design tokens that later
streaming, activity, tool-call, and status components can reuse.

## Non-Scope

This stage does not implement live streaming, scroll state, keyboard input,
fold/expand behavior, tool cards, custom spinners, or status metrics. Those
require the EventBus and orchestration layers that are scheduled later in
`PROMPT_SPEC.md` section 15.

## Architecture

`ui.theme` owns immutable design tokens:

- core palette from `PROMPT_SPEC.md` section 17.1
- model themes from sections 4.7 and 17.1
- router theme

`ui.console` owns the shared Rich `Console` instance and keeps stdout/stderr
behind Rich output.

`ui.layout` owns static layout assembly for the first UI contract:

- header
- body split into feed and side
- activity panel
- tools panel
- input
- footer

`ui.panels.model_panel` owns one renderable message block. It uses the left-bar
marker style from `PROMPT_SPEC.md` section 17.5 instead of a nested decorative
card. It can render a title line, body, and optional usage line.

## Testing

Tests verify:

- palette and model-theme values match the spec
- provider fallback theme is deterministic
- console factory returns a singleton
- layout has the expected named regions
- `ModelPanel` renders model identity and message body through Rich

## Verification

Before commit:

- `python -m pytest -q`
- `python -m ruff check .`
- `python -m mypy ivycode`
- `python -m ivycode doctor`
