from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel

from ivycode.codegraph import CodeGraphService
from ivycode.core.envelope import AgentName, StepResult, SubAgentDirective
from ivycode.skills.registry import SkillRegistry

JsonObject = dict[str, Any]
JsonSchema = dict[str, Any]


@dataclass
class AgentContext:
    project_root: Path
    skills: SkillRegistry
    previous_results: dict[str, StepResult]
    codegraph: CodeGraphService | None = None


class SubAgent(ABC):
    name: ClassVar[AgentName]
    description: ClassVar[str]

    def describe(self) -> JsonObject:
        return {
            "name": self.name.value,
            "description": self.description,
        }

    @abstractmethod
    async def execute(
        self,
        *,
        step_id: str,
        directive: SubAgentDirective,
        context: AgentContext,
    ) -> StepResult:
        raise NotImplementedError


def jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    return value


def validate_json_object_schema(payload: object, schema: JsonSchema) -> JsonObject:
    if schema.get("type") == "object" and not isinstance(payload, dict):
        raise ValueError("schema expected an object")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")

    required = schema.get("required", [])
    if isinstance(required, list):
        missing = [
            key for key in required if isinstance(key, str) and key not in payload
        ]
        if missing:
            raise ValueError(f"missing required schema keys: {', '.join(missing)}")

    properties = schema.get("properties", {})
    if isinstance(properties, dict):
        for key, value in payload.items():
            property_schema = properties.get(key)
            if isinstance(property_schema, dict) and not _matches_schema_type(
                value,
                property_schema,
            ):
                expected = _schema_type_label(property_schema)
                raise ValueError(f"schema key {key!r} must be {expected}")
    return payload


def _matches_schema_type(value: object, schema: JsonSchema) -> bool:
    schema_types = _schema_types(schema)
    if value is None:
        return "null" in schema_types
    return any(_matches_type(value, schema_type) for schema_type in schema_types)


def _matches_type(value: object, schema_type: str) -> bool:
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


def _schema_type_label(schema: JsonSchema) -> str:
    return " | ".join(_schema_types(schema))


def _schema_types(schema: JsonSchema) -> list[str]:
    schema_type = schema.get("type")
    if isinstance(schema_type, str):
        return [schema_type]
    any_of = schema.get("anyOf")
    if isinstance(any_of, list):
        parsed: list[str] = []
        for item in any_of:
            if isinstance(item, dict) and isinstance(item.get("type"), str):
                parsed.append(item["type"])
        if parsed:
            return parsed
    return ["object"]
