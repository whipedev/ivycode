from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from ivycode import __version__
from ivycode.codegraph import CodeGraphService, CodeGraphStats
from ivycode.core.settings import Settings
from ivycode.skills.builtins import register_builtin_skills
from ivycode.skills.registry import SkillDefinition, SkillRegistry
from ivycode.skills.runtime import SkillRuntime
from ivycode.skills.store import PluginStore

app = typer.Typer(rich_markup_mode="rich", no_args_is_help=True)
skills_app = typer.Typer(
    rich_markup_mode="rich",
    no_args_is_help=False,
    invoke_without_command=True,
)
console = Console()


def _stage_boundary(command: str) -> None:
    console.print(
        f"ivycode {command}: not implemented in v0.5.0-skills-foundation",
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
    stats = asyncio.run(_run_index(force=force))
    console.print("ivycode index", style="bold")
    console.print(f"files indexed {stats.indexed_files_count}")
    console.print(f"symbols {stats.symbols_count}")
    console.print(f"routes {stats.routes_count}")


async def _run_index(*, force: bool) -> CodeGraphStats:
    service = CodeGraphService()
    await service.boot(Path.cwd())
    try:
        return await service.index(force=force)
    finally:
        await service.shutdown()


@skills_app.callback(invoke_without_command=True)
def skills(ctx: typer.Context) -> None:
    """Inspect and manage local ivycode skills."""
    if ctx.invoked_subcommand is None:
        asyncio.run(_render_skills_dashboard())


@skills_app.command("list")
def skills_list() -> None:
    """List registered builtin skills."""
    registry = _create_registry()
    _render_skill_table(registry.list())


@skills_app.command("inspect")
def skills_inspect(name: Annotated[str, typer.Argument()]) -> None:
    """Inspect a skill contract."""
    registry = _create_registry()
    definition = registry.get(name)
    console.print(f"ivycode skill {definition.name}", style="bold")
    console.print(definition.description)
    console.print(f"permissions {_human_permissions(definition.permissions)}")
    console.print_json(json.dumps(definition.parameters_schema))


@skills_app.command("run")
def skills_run(
    name: Annotated[str, typer.Argument()],
    arg: Annotated[list[str] | None, typer.Option("--arg")] = None,
) -> None:
    """Run a skill with --arg key=value pairs."""
    arguments = _parse_arg_pairs(arg or [])
    result = asyncio.run(_invoke_skill(name=name, arguments=arguments))
    console.print_json(json.dumps(_jsonable(result)))


@skills_app.command("save")
def skills_save(
    slug: Annotated[str, typer.Argument()],
    skill_names: Annotated[list[str] | None, typer.Option("--skill")] = None,
    description: Annotated[str, typer.Option("--description")] = "Local ivycode plugin",
) -> None:
    """Save selected skills as a local plugin shell."""
    registry = _create_registry()
    selected = skill_names or []
    if not selected:
        raise typer.BadParameter("at least one --skill is required")
    for skill_name in selected:
        registry.get(skill_name)

    manifest = _plugin_store().save_plugin(
        slug=slug,
        description=description,
        skills=selected,
    )
    console.print(f"saved {manifest.slug}", style="bold green")
    console.print(f"skills {', '.join(manifest.skills)}")
    console.print(f"path {_plugin_store().plugin_root / manifest.slug}")


@skills_app.command("plugins")
def skills_plugins() -> None:
    """List locally saved plugin shells."""
    _render_plugin_shelf(_plugin_store())


app.add_typer(skills_app, name="skills")


async def _render_skills_dashboard() -> None:
    registry = _create_registry()
    store = _plugin_store()
    codegraph = CodeGraphService()
    await codegraph.boot(Path.cwd())
    try:
        stats = await codegraph.stats()
        console.print("ivycode skills", style="bold")
        console.print("local command center", style="#A78BFA")
        console.print(
            f"graph {stats.indexed_files_count} files · "
            f"{stats.symbols_count} symbols · {stats.routes_count} routes",
            style="dim",
        )
        _render_skill_table(registry.list())
        _render_plugin_shelf(store)
        console.print(
            "suggested next action: ivycode skills save <slug> --skill <name>",
            style="dim",
        )
    finally:
        await codegraph.shutdown()


async def _invoke_skill(*, name: str, arguments: dict[str, object]) -> object:
    registry = _create_registry()
    codegraph = CodeGraphService()
    await codegraph.boot(Path.cwd())
    try:
        runtime = SkillRuntime(project_root=Path.cwd(), codegraph=codegraph)
        return await registry.invoke(name, runtime=runtime, arguments=arguments)
    finally:
        await codegraph.shutdown()


def _create_registry() -> SkillRegistry:
    registry = SkillRegistry()
    register_builtin_skills(registry)
    return registry


def _plugin_store() -> PluginStore:
    return PluginStore(plugin_root=Path.home() / ".ivycode" / "plugins")


def _render_skill_table(definitions: list[SkillDefinition]) -> None:
    table = Table(title="Builtin Skills", show_lines=False)
    table.add_column("Skill", style="bold")
    table.add_column("Permissions")
    table.add_column("Status")
    for definition in definitions:
        table.add_row(
            definition.name,
            _human_permissions(definition.permissions),
            _status_for(definition),
        )
    console.print(table)


def _render_plugin_shelf(store: PluginStore) -> None:
    console.print("Plugin Shelf", style="bold")
    plugins = store.list_plugins()
    if not plugins:
        console.print("no local plugins saved yet", style="dim")
        return
    table = Table(show_header=True)
    table.add_column("Plugin", style="bold")
    table.add_column("Skills")
    for manifest in plugins:
        table.add_row(manifest.slug, ", ".join(manifest.skills))
    console.print(table)


def _human_permissions(permissions: list[str]) -> str:
    labels = {
        "graph:read": "can search the local code graph",
        "fs:read": "can read files inside this project",
        "fs:write": "can write files inside this project",
        "plugin:write": "can save a local plugin shell",
    }
    return ", ".join(labels.get(permission, permission) for permission in permissions)


def _status_for(definition: SkillDefinition) -> str:
    if definition.name.startswith("graph."):
        return "ready"
    if definition.name == "fs.read_file":
        return "project-gated"
    if definition.name == "fs.write_file":
        return "guarded"
    return "ready"


def _parse_arg_pairs(pairs: list[str]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for pair in pairs:
        if "=" not in pair:
            raise typer.BadParameter(f"--arg must use key=value syntax: {pair}")
        key, value = pair.split("=", 1)
        parsed[key] = _parse_arg_value(value)
    return parsed


def _parse_arg_value(value: str) -> object:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.isdigit():
        return int(value)
    return value


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def main() -> None:
    app()
