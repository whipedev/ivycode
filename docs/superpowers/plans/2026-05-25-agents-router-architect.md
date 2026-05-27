# Agents Router Architect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `PROMPT_SPEC.md` Stage 6 with a RouterAgent, AgentMediator, and first Architect subagent.

**Architecture:** Add `ivycode/agents` as the first execution-planning layer. Router builds strict `ExecutionPlan` objects, Mediator dispatches graph/subagent/aggregate steps, and Architect returns a schema-validated architecture report without direct disk access.

**Tech Stack:** Python 3.11, Pydantic v2, Typer, Rich, pytest, ruff, mypy strict.

---

### Task 1: Agent Contracts

**Files:**
- Create: `ivycode/agents/__init__.py`
- Create: `ivycode/agents/base.py`
- Test: `tests/unit/test_agents_architect.py`

- [x] Define `AgentContext`, `SubAgent`, `ArchitectReport`, and minimal JSON Schema validation helpers.
- [x] Ensure SubAgents return `StepResult`, not raw provider output.

### Task 2: Router Planner

**Files:**
- Create: `ivycode/agents/router.py`
- Create: `ivycode/agents/prompts/router.md`
- Test: `tests/unit/test_agents_router.py`

- [x] Render the Router prompt with no unresolved placeholders.
- [x] Support provider-backed `complete_json` with strict `ExecutionPlan` validation and two retries.
- [x] Support deterministic local planning when no provider is configured.
- [x] Always emit CodeGraph-first plan before architect delegation.

### Task 3: Mediator Dispatch

**Files:**
- Create: `ivycode/agents/mediator.py`
- Test: `tests/unit/test_agents_mediator.py`

- [x] Register subagents by `AgentName`.
- [x] Describe subagents as JSON for Router prompt rendering.
- [x] Validate dependencies and dispatch graph/subagent/aggregate steps in order.
- [x] Return `StepResult` objects for every dispatched step.

### Task 4: Architect SubAgent

**Files:**
- Create: `ivycode/agents/subagents/__init__.py`
- Create: `ivycode/agents/subagents/architect.py`
- Create: `ivycode/agents/prompts/architect.md`
- Test: `tests/unit/test_agents_architect.py`

- [x] Implement provider-ready Architect execution.
- [x] Provide deterministic fallback output for local CLI use.
- [x] Validate provider JSON against the directive schema.

### Task 5: CLI Plan Entry Point And Version

**Files:**
- Modify: `ivycode/cli/app.py`
- Modify: `ivycode/__init__.py`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Test: `tests/unit/test_cli.py`
- Test: `tests/unit/test_cli_plan.py`

- [x] Replace the `ivycode plan` stage boundary with a real Router plan command.
- [x] Keep `chat` as a stage boundary.
- [x] Bump version to `0.7.0`.
- [x] Document the Stage 6 runnable command.

### Task 6: Verification

**Files:**
- Modify tests as needed under `tests/unit/`.

- [x] Run `pytest`, `ruff`, `ruff format --check`, `mypy`, `doctor`, `index`, and `plan` smoke checks.
- [ ] Commit with `What changed`, `Why`, and `Validation`.
