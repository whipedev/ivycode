from __future__ import annotations

import asyncio
import json
from pathlib import Path
from time import perf_counter
from typing import Annotated

import typer
from pydantic import BaseModel
from rich import box
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.pretty import Pretty
from rich.table import Table
from rich.text import Text

from ivycode import __version__
from ivycode.codegraph import CodeGraphService, CodeGraphStats
from ivycode.core.settings import Settings
from ivycode.skills.builtins import register_builtin_skills
from ivycode.skills.registry import SkillDefinition, SkillRegistry
from ivycode.skills.runtime import SkillRuntime
from ivycode.skills.store import PluginStore
from ivycode.ui.panels.error_panel import ErrorPanel
from ivycode.ui.theme import PALETTE, theme_for_skill
from ivycode.ui.widgets.spinner import register_custom_spinners

app = typer.Typer(rich_markup_mode="rich", no_args_is_help=True)
skills_app = typer.Typer(
    rich_markup_mode="rich",
    no_args_is_help=False,
    invoke_without_command=True,
)
console = Console()
register_custom_spinners()


def _stage_boundary(command: str) -> None:
    console.print(
        Panel(
            (
                f"ivycode {command} is not implemented in "
                "v0.6.0-skills-ui-polish.\n"
                "This command is reserved for the next agent orchestration stage."
            ),
            title="stage boundary",
            border_style=PALETTE.warn,
            box=box.ROUNDED,
        )
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
def skills_inspect(
    name: Annotated[str, typer.Argument()],
    show_schema: Annotated[bool, typer.Option("--schema")] = False,
) -> None:
    """Inspect a skill contract."""
    registry = _create_registry()
    definition = registry.get(name)
    if show_schema:
        console.print_json(json.dumps(definition.parameters_schema))
        return
    _render_skill_inspect(definition)


@skills_app.command("run")
def skills_run(
    name: Annotated[str, typer.Argument()],
    arg: Annotated[list[str] | None, typer.Option("--arg")] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Run a skill with --arg key=value pairs."""
    registry = _create_registry()
    definition = registry.get(name)
    arguments = _parse_arg_pairs(arg or [])
    _validate_arguments(definition, arguments)

    started = perf_counter()
    try:
        if json_output:
            result = asyncio.run(_invoke_skill(name=name, arguments=arguments))
        else:
            status_line = f"running {name} · {_format_arguments(arguments)}"
            with console.status(status_line, spinner="ivy-orbit"):
                result = asyncio.run(_invoke_skill(name=name, arguments=arguments))
    except Exception as exc:
        if json_output:
            console.print_json(
                json.dumps(
                    {
                        "success": False,
                        "skill": name,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            )
        else:
            console.print(
                ErrorPanel(
                    skill_name=name,
                    exception=exc,
                    arguments=arguments,
                ).render()
            )
        raise typer.Exit(code=1) from exc

    if json_output:
        console.print_json(json.dumps(_jsonable(result)))
        return

    duration_ms = max(1, int((perf_counter() - started) * 1000))
    _render_skill_result(definition, result, duration_ms)


def _render_skill_inspect(definition: SkillDefinition) -> None:
    theme = theme_for_skill(definition.name)
    console.print(f"ivycode skill · {definition.name}", style="bold")
    console.print(f"{theme.glyph} {definition.description}", style=theme.accent)
    console.print()
    console.print("permissions", style="bold")
    for permission in definition.permissions:
        console.print(
            Text.assemble(
                ("  ", ""),
                _permission_badge(permission),
                (" ", ""),
                (_permission_label(permission), PALETTE.text_dim),
            )
        )
    console.print()
    console.print("parameters", style="bold")
    console.print(_parameters_table(definition))
    console.print("usage", style="bold")
    console.print(f"  {_usage_for(definition)}", style=PALETTE.text_dim)


def _render_skill_result(
    definition: SkillDefinition,
    result: object,
    duration_ms: int,
) -> None:
    console.print(
        Panel(
            _result_renderable(result),
            title=f"✓ {definition.name} · {duration_ms}ms",
            title_align="left",
            border_style=PALETTE.accent_mint,
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )


def _result_renderable(result: object) -> RenderableType:
    if isinstance(result, str):
        return Text(result.rstrip("\n") or " ", overflow="fold", no_wrap=False)
    return Pretty(_jsonable(result))


@skills_app.command("save")
def skills_save(
    slug: Annotated[str, typer.Argument()],
    skill_names: Annotated[list[str] | None, typer.Option("--skill")] = None,
    description: Annotated[str, typer.Option("--description")] = "Local ivycode plugin",
    yes: Annotated[bool, typer.Option("--yes")] = False,
) -> None:
    """Save selected skills as a local plugin shell."""
    registry = _create_registry()
    store = _plugin_store()
    selected = skill_names or []
    if not selected:
        raise typer.BadParameter("at least one --skill is required")
    try:
        if store.plugin_exists(slug):
            raise typer.BadParameter(f"plugin already exists: {slug}")
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    for skill_name in selected:
        registry.get(skill_name)

    target = store.plugin_path(slug)
    console.print(f"will save plugin '{slug}' with skills: {', '.join(selected)}")
    console.print(f"target: {target}", style="dim")
    if not yes and not typer.confirm("proceed?", default=False):
        raise typer.Abort()

    manifest = store.save_plugin(
        slug=slug,
        description=description,
        skills=selected,
    )
    console.print(f"saved {manifest.slug}", style="bold green")
    console.print(f"skills {', '.join(manifest.skills)}")
    console.print(f"path {target}")


@skills_app.command("plugins")
def skills_plugins() -> None:
    """List locally saved plugin shells."""
    _render_plugin_shelf(_plugin_store(), _create_registry())


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
        _render_plugin_shelf(store, registry)
        console.print(
            f"suggested next action: {_suggested_next_action(store, registry)}",
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
    table = Table(
        title=f"ivycode skills · {len(definitions)} builtins",
        show_lines=False,
        box=box.ROUNDED,
    )
    table.add_column("Glyph", style="bold", no_wrap=True)
    table.add_column("Skill", style="bold", no_wrap=True)
    table.add_column("Description")
    table.add_column("Permissions")
    table.add_column("Risk", no_wrap=True)
    for definition in definitions:
        theme = theme_for_skill(definition.name)
        table.add_row(
            Text(theme.glyph, style=theme.accent),
            definition.name,
            definition.description,
            _permission_badges(definition.permissions),
            _risk_badge(definition.risk),
        )
    console.print(table)


def _render_plugin_shelf(store: PluginStore, registry: SkillRegistry) -> None:
    console.print("Plugin Shelf", style="bold")
    plugins = store.list_plugins()
    if not plugins:
        console.print("no local plugins saved yet", style="dim")
        return
    table = Table(show_header=True, box=box.ROUNDED)
    table.add_column("Plugin", style="bold")
    table.add_column("Description")
    table.add_column("Skills")
    table.add_column("Created")
    table.add_column("Status")
    table.add_column("Path")
    for manifest in plugins:
        valid = all(registry.has(skill_name) for skill_name in manifest.skills)
        status = Text("valid", style=PALETTE.accent_mint) if valid else Text("broken")
        if not valid:
            status.stylize(PALETTE.error)
        table.add_row(
            manifest.slug,
            manifest.description,
            ", ".join(manifest.skills),
            manifest.created_at.astimezone().strftime("%Y-%m-%d"),
            status,
            store.plugin_path(manifest.slug).as_posix(),
        )
    console.print(table)


def _permission_label(permission: str) -> str:
    labels = {
        "graph:read": "can search the local code graph",
        "fs:read": "can read files inside this project",
        "fs:write": "can write files inside this project",
        "plugin:write": "can save a local plugin shell",
    }
    return labels.get(permission, permission)


def _permission_badges(permissions: list[str]) -> Text:
    text = Text()
    for index, permission in enumerate(permissions):
        if index:
            text.append(" ")
        text.append_text(_permission_badge(permission))
    return text


def _permission_badge(permission: str) -> Text:
    labels = {
        "graph:read": "GRAPH·R",
        "fs:read": "FS·R",
        "fs:write": "FS·W",
        "plugin:write": "PLUGIN·W",
    }
    label = labels.get(permission, permission.upper().replace(":", "·"))
    style = PALETTE.warn if permission.endswith(":write") else PALETTE.text_dim
    return Text(f"[{label}]", style=style)


def _risk_badge(risk: str) -> Text:
    styles = {
        "read": PALETTE.text_dim,
        "write": PALETTE.warn,
        "destructive": PALETTE.error,
    }
    return Text(risk, style=styles.get(risk, PALETTE.text_dim))


def _suggested_next_action(store: PluginStore, registry: SkillRegistry) -> str:
    plugins = store.list_plugins()
    if plugins:
        return "ivycode skills run fs.read_file --arg file_path=README.md"
    if registry.list():
        return "ivycode skills inspect fs.read_file"
    return "ivycode skills list"


def _parameters_table(definition: SkillDefinition) -> Table:
    schema = definition.parameters_schema
    required = set(schema.get("required", []))
    properties = schema.get("properties", {})
    table = Table(show_header=True, box=box.ROUNDED)
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Required")
    table.add_column("Default")
    table.add_column("Description")
    if not isinstance(properties, dict) or not properties:
        table.add_row("—", "—", "no", "—", "no parameters")
        return table

    for name, property_schema in properties.items():
        if not isinstance(property_schema, dict):
            continue
        table.add_row(
            name,
            _schema_type_label(property_schema),
            "yes" if name in required else "no",
            _schema_default_label(property_schema),
            str(property_schema.get("description", "—")),
        )
    return table


def _schema_default_label(property_schema: dict[str, object]) -> str:
    if "default" not in property_schema:
        return "—"
    value = property_schema["default"]
    if value is None:
        return "None"
    return str(value)


def _usage_for(definition: SkillDefinition) -> str:
    properties = definition.parameters_schema.get("properties", {})
    required = definition.parameters_schema.get("required", [])
    args: list[str] = []
    if isinstance(properties, dict) and isinstance(required, list):
        for name in required:
            property_schema = properties.get(name)
            if isinstance(name, str) and isinstance(property_schema, dict):
                args.append(f"--arg {name}={_placeholder_for(property_schema)}")
    suffix = f" {' '.join(args)}" if args else ""
    return f"ivycode skills run {definition.name}{suffix}"


def _placeholder_for(property_schema: dict[str, object]) -> str:
    type_label = _schema_type_label(property_schema)
    if type_label == "str":
        return "<text>"
    if type_label == "int":
        return "1"
    if type_label == "bool":
        return "true"
    if type_label == "list":
        return "[]"
    if type_label == "dict":
        return "{}"
    return "<value>"


def _format_arguments(arguments: dict[str, object]) -> str:
    if not arguments:
        return "no args"
    return ", ".join(f"{key}={value!r}" for key, value in sorted(arguments.items()))


def _validate_arguments(
    definition: SkillDefinition,
    arguments: dict[str, object],
) -> None:
    schema = definition.parameters_schema
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        return

    missing = [
        name for name in required if isinstance(name, str) and name not in arguments
    ]
    if missing:
        raise typer.BadParameter(f"missing required --arg: {', '.join(missing)}")

    extra = [name for name in arguments if name not in properties]
    if extra:
        raise typer.BadParameter(
            f"unknown --arg for {definition.name}: {', '.join(extra)}"
        )

    for name, value in arguments.items():
        property_schema = properties.get(name)
        if not isinstance(property_schema, dict):
            continue
        if not _schema_accepts_value(property_schema, value):
            expected = _schema_type_label(property_schema)
            actual = type(value).__name__
            raise typer.BadParameter(f"--arg {name} must be {expected}; got {actual}")


def _schema_accepts_value(
    property_schema: dict[str, object],
    value: object,
) -> bool:
    accepted = _schema_types(property_schema)
    if value is None:
        return "null" in accepted
    return any(
        _value_matches_schema_type(value, schema_type) for schema_type in accepted
    )


def _value_matches_schema_type(value: object, schema_type: str) -> bool:
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "integer":
        return type(value) is int
    if schema_type == "number":
        return type(value) in (int, float)
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type == "array":
        return isinstance(value, list)
    if schema_type == "object":
        return isinstance(value, dict)
    return schema_type == "null" and value is None


def _schema_type_label(property_schema: dict[str, object]) -> str:
    labels = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "list",
        "object": "dict",
        "null": "None",
    }
    return " | ".join(labels.get(item, item) for item in _schema_types(property_schema))


def _schema_types(property_schema: dict[str, object]) -> list[str]:
    schema_type = property_schema.get("type")
    if isinstance(schema_type, str):
        return [schema_type]
    any_of = property_schema.get("anyOf")
    if isinstance(any_of, list):
        parsed: list[str] = []
        for item in any_of:
            if isinstance(item, dict) and isinstance(item.get("type"), str):
                parsed.append(item["type"])
        if parsed:
            return parsed
    return ["object"]


def _parse_arg_pairs(pairs: list[str]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for pair in pairs:
        if "=" not in pair:
            raise typer.BadParameter(f"--arg must use key=value syntax: {pair}")
        key, value = pair.split("=", 1)
        parsed[key] = _parse_arg_value(value)
    return parsed


def _parse_arg_value(value: str) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass
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
