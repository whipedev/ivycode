# Ivycode Foundation Design

## Scope

This stage implements `v0.1.0-foundation` from `PROMPT_SPEC.md` section 15,
step 1:

- `pyproject.toml`
- `ivycode/__init__.py`
- `ivycode/core/settings.py`
- `ivycode/core/envelope.py`

It also adds the smallest usable CLI entrypoint:

- `ivycode/__main__.py`
- `ivycode/cli/app.py`

The CLI is included so the package can be executed with `python -m ivycode`
and so the foundation can be checked by an end-to-end command.

## Non-Scope

This stage does not implement providers, CodeGraph indexing, agents, skills,
Rich live layout, persistence, or gateway behavior. Those are separate stages
defined later in `PROMPT_SPEC.md` section 15.

## Architecture

The first code boundary is `ivycode.core.envelope`. It owns immutable Pydantic
contracts for messages, stream events, caller metadata, execution plans, step
results, and session transcripts. These contracts are the shared language for
later providers, agents, skills, and UI components.

The second boundary is `ivycode.core.settings`. It owns the runtime settings
model and defaults. API keys are optional at this stage so `ivycode doctor` can
report missing configuration without crashing before onboarding exists.

The CLI boundary is intentionally thin. `ivycode.cli.app` defines a Typer app
with a `doctor` command and placeholder command groups for the future public
commands specified in `PROMPT_SPEC.md` section 10. Placeholder commands are not
implemented as fake behavior; they return explicit "not implemented in this
stage" diagnostics.

## Data Contracts

All Pydantic models use the shared strict config:

- `extra="forbid"`
- `frozen=True`
- `populate_by_name=True`

Enums use `StrEnum`. Timestamps are created as UTC-aware datetimes. Structured
router plans validate that every `PlanStep` has exactly one payload and that the
payload matches the step kind.

## Testing

The stage is test-first:

- envelope tests verify immutability, forbidden extra fields, UTC metadata,
  schema validation, and plan-step payload validation.
- settings tests verify default models and optional missing API keys.
- CLI tests verify that `doctor` exits cleanly and reports the foundation
  status through Typer's test runner.

## Verification

Before commit:

- `python -m pytest -q`
- `python -m ruff check .`
- `python -m mypy ivycode`
- `python -m ivycode doctor`

If dependencies are not installed, create a local virtual environment and
install the project with development extras before running the checks.
