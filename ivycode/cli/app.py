from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from ivycode import __version__
from ivycode.core.settings import Settings

app = typer.Typer(rich_markup_mode="rich", no_args_is_help=True)
console = Console()


def _stage_boundary(command: str) -> None:
    console.print(
        f"ivycode {command}: not implemented in v0.2.0-ui-foundation",
        style="yellow",
    )
    raise typer.Exit(code=2)


@app.command()
def doctor() -> None:
    """Diagnose foundation configuration."""
    settings = Settings()
    configured = [
        name
        for name, value in (
            ("anthropic", settings.anthropic_api_key),
            ("openai", settings.openai_api_key),
            ("google", settings.google_api_key),
        )
        if value is not None
    ]
    provider_status = ", ".join(configured) if configured else "no api keys configured"

    console.print("ivycode doctor", style="bold")
    console.print(f"version {__version__}")
    console.print("foundation ready")
    console.print(f"router model {settings.default_router_model.model_id}")
    console.print(f"providers {provider_status}")


@app.command()
def chat(
    model: Annotated[list[str] | None, typer.Option("--model", "-m")] = None,
) -> None:
    """Open interactive multi-model chat session."""
    _ = model
    _stage_boundary("chat")


@app.command()
def plan(task: Annotated[str | None, typer.Argument()] = None) -> None:
    """Produce an ExecutionPlan for the given task without executing it."""
    _ = task
    _stage_boundary("plan")


@app.command()
def index(force: Annotated[bool, typer.Option("--force")] = False) -> None:
    """Re-index the current project into CodeGraph."""
    _ = force
    _stage_boundary("index")


def main() -> None:
    app()
