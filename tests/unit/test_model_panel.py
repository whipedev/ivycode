from __future__ import annotations

from rich.console import Console

from ivycode.core.envelope import (
    AgentName,
    CallerMeta,
    ModelRef,
    ProviderName,
    UsageMetrics,
)
from ivycode.ui.panels.model_panel import ModelPanel


def test_model_panel_renders_identity_and_body() -> None:
    console = Console(record=True, width=100, color_system=None)
    model = ModelRef(
        provider=ProviderName.ANTHROPIC,
        model_id="claude-opus-4-7",
        display_name="Claude Opus 4.7",
    )
    meta = CallerMeta(agent=AgentName.ARCHITECT, model=model)
    panel = ModelPanel(meta=meta, body="Plan the first refactor.")

    console.print(panel.render())
    output = console.export_text()

    assert "◆  Claude Opus 4.7" in output
    assert "architect" in output
    assert "Plan the first refactor." in output


def test_model_panel_renders_usage_when_available() -> None:
    console = Console(record=True, width=100, color_system=None)
    model = ModelRef(
        provider=ProviderName.OPENAI,
        model_id="gpt-5.5-xhigh",
        display_name="GPT-5.5 xhigh",
    )
    meta = CallerMeta(agent=AgentName.TESTER, model=model)
    usage = UsageMetrics(
        input_tokens=100,
        output_tokens=25,
        cost_usd=0.0042,
        latency_ms=412,
    )
    panel = ModelPanel(meta=meta, body="Tests are ready.", usage=usage)

    console.print(panel.render())
    output = console.export_text()

    assert "▲  GPT-5.5 xhigh" in output
    assert "in 100" in output
    assert "out 25" in output
    assert "$0.0042" in output
