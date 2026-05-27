# Agents Router Architect Design

## Source Scope

This stage implements `PROMPT_SPEC.md` Stage 6: `agents/base.py`, `agents/router.py`, `agents/mediator.py`, and one SubAgent named `architect`.

## Design

Stage 6 adds the first agent runtime layer without requiring live API keys. The Router can use a provider through `complete_json` when one is supplied, but it also has a deterministic local planner so `ivycode plan "<task>"` is runnable today.

The Router always emits a valid `ExecutionPlan`. The local planner emits a CodeGraph-first `graph_query`, then an `architect` subagent step, then an `aggregate` step. This preserves the invariant that coding work is grounded in CodeGraph before delegation.

The Mediator is the only dispatcher. It owns subagent registration, describes available subagents for Router prompts, validates step dependencies, dispatches graph queries into `CodeGraphService`, dispatches subagent steps to registered subagents, and aggregates `StepResult` objects.

The Architect subagent is provider-ready. If a provider is present, it calls `complete_json` and validates the JSON object against the directive schema. If no provider is present, it returns a deterministic architecture report built only from directive inputs and CodeGraph references.

## Non-Goals

- No parallel orchestration; that is Stage 7.
- No refactorer/tester/documenter subagents; those are Stage 9.
- No direct file reads from subagents.
- No raw source content in Router plans.

## Test Strategy

- Router emits CodeGraph-first plans and validates provider JSON with retry.
- Router prompt rendering leaves no unresolved placeholders.
- Mediator dispatches graph query and subagent steps in dependency order.
- Architect returns JSON matching the expected schema.
- CLI `ivycode plan "<task>"` returns a real `ExecutionPlan`.
