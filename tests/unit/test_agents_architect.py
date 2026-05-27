from __future__ import annotations

import asyncio
from pathlib import Path

from ivycode.agents.base import AgentContext
from ivycode.agents.subagents.architect import (
    ARCHITECT_REPORT_SCHEMA,
    ArchitectSubAgent,
)
from ivycode.core.envelope import AgentName, SubAgentDirective
from ivycode.skills.registry import SkillRegistry


def test_architect_subagent_returns_schema_valid_report(tmp_path: Path) -> None:
    agent = ArchitectSubAgent()
    directive = SubAgentDirective(
        agent=AgentName.ARCHITECT,
        instructions=(
            "Analyze the requested architecture change. Return ONLY a JSON object "
            "matching the provided schema. Any deviation will be rejected."
        ),
        inputs={
            "user_task": "Refactor auth flow",
            "graph_snapshot": {
                "relevant_symbols": [
                    {
                        "qualified_name": "auth.login",
                        "file_path": "app/auth.py",
                        "line_start": 10,
                        "line_end": 40,
                    }
                ]
            },
        },
        allowed_skills=["graph.search_symbols", "fs.read_file"],
        token_budget=4000,
        expected_output_schema=ARCHITECT_REPORT_SCHEMA,
    )
    context = AgentContext(
        project_root=tmp_path,
        skills=SkillRegistry(),
        previous_results={},
    )

    result = asyncio.run(
        agent.execute(
            step_id="step_02",
            directive=directive,
            context=context,
        )
    )

    assert result.step_id == "step_02"
    assert result.success is True
    assert isinstance(result.output, dict)
    assert result.output["files"] == ["app/auth.py:10-40"]
    assert "decisions" in result.output
    assert result.duration_ms >= 1
