from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ivycode.cli.app import app
from ivycode.core.envelope import ExecutionPlan, StepKind


def test_plan_command_renders_execution_plan_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "app.py").write_text(
        "def login_user() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["plan", "Refactor login_user"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    plan = ExecutionPlan.model_validate(payload)
    assert plan.steps[0].kind is StepKind.GRAPH_QUERY
    assert plan.steps[1].subagent is not None
    assert plan.steps[1].subagent.agent == "architect"
