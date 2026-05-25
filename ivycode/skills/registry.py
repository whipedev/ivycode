from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, cast

from pydantic import create_model

SkillHandler = Callable[..., Awaitable[Any]]
SkillRisk = Literal["read", "write", "destructive"]


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    description: str
    permissions: list[str]
    risk: SkillRisk
    requires_confirmation: bool
    idempotent: bool
    parameters_schema: dict[str, Any]
    handler: SkillHandler


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    permissions: list[str]
    risk: SkillRisk
    requires_confirmation: bool
    idempotent: bool


def skill(
    *,
    name: str,
    description: str,
    permissions: list[str],
    risk: SkillRisk | None = None,
    requires_confirmation: bool | None = None,
    idempotent: bool | None = None,
) -> Callable[[SkillHandler], SkillHandler]:
    def decorator(handler: SkillHandler) -> SkillHandler:
        if not inspect.iscoroutinefunction(handler):
            raise TypeError("skills must be async callables")
        resolved_risk = risk or _risk_from_permissions(permissions)
        cast(Any, handler).__ivy_skill__ = SkillMetadata(
            name=name,
            description=description,
            permissions=list(permissions),
            risk=resolved_risk,
            requires_confirmation=(
                resolved_risk == "destructive"
                if requires_confirmation is None
                else requires_confirmation
            ),
            idempotent=resolved_risk == "read" if idempotent is None else idempotent,
        )
        return handler

    return decorator


class SkillRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, SkillDefinition] = {}

    def register(self, handler: SkillHandler) -> SkillDefinition:
        metadata = _metadata_for(handler)
        if metadata.name in self._definitions:
            raise ValueError(f"skill already registered: {metadata.name}")

        definition = SkillDefinition(
            name=metadata.name,
            description=metadata.description,
            permissions=metadata.permissions,
            risk=metadata.risk,
            requires_confirmation=metadata.requires_confirmation,
            idempotent=metadata.idempotent,
            parameters_schema=_parameters_schema(handler),
            handler=handler,
        )
        self._definitions[definition.name] = definition
        return definition

    def get(self, name: str) -> SkillDefinition:
        try:
            return self._definitions[name]
        except KeyError as exc:
            raise KeyError(f"skill not found: {name}") from exc

    def list(self) -> list[SkillDefinition]:
        return [self._definitions[name] for name in sorted(self._definitions)]

    def has(self, name: str) -> bool:
        return name in self._definitions

    async def invoke(
        self,
        name: str,
        *,
        runtime: object,
        arguments: dict[str, object],
    ) -> object:
        definition = self.get(name)
        return await definition.handler(runtime, **arguments)


def _metadata_for(handler: SkillHandler) -> SkillMetadata:
    metadata = getattr(handler, "__ivy_skill__", None)
    if not isinstance(metadata, SkillMetadata):
        raise TypeError("callable is missing @skill metadata")
    return metadata


def _risk_from_permissions(permissions: list[str]) -> SkillRisk:
    if any(permission.endswith(":destructive") for permission in permissions):
        return "destructive"
    if any(permission.endswith(":write") for permission in permissions):
        return "write"
    return "read"


def _parameters_schema(handler: SkillHandler) -> dict[str, Any]:
    signature = inspect.signature(handler)
    fields: dict[str, tuple[Any, Any]] = {}
    for index, parameter in enumerate(signature.parameters.values()):
        if index == 0 and parameter.name == "runtime":
            continue
        annotation = Any
        if parameter.annotation is not inspect.Signature.empty:
            annotation = parameter.annotation
        default = (
            ... if parameter.default is inspect.Signature.empty else parameter.default
        )
        fields[parameter.name] = (annotation, default)

    field_definitions: dict[str, Any] = fields
    model = create_model(f"{handler.__name__.title()}Params", **field_definitions)
    return model.model_json_schema()
