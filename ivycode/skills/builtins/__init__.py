from __future__ import annotations

from ivycode.skills.builtins.fs import register_fs_skills
from ivycode.skills.builtins.graph import register_graph_skills
from ivycode.skills.registry import SkillRegistry


def register_builtin_skills(registry: SkillRegistry) -> None:
    register_graph_skills(registry)
    register_fs_skills(registry)


__all__ = ["register_builtin_skills", "register_fs_skills", "register_graph_skills"]
