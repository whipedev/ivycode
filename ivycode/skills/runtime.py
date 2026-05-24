from __future__ import annotations

from pathlib import Path

from ivycode.codegraph import CodeGraphService


class SkillRuntime:
    def __init__(
        self,
        *,
        project_root: Path,
        codegraph: CodeGraphService | None = None,
        plugin_root: Path | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.codegraph = codegraph
        self.plugin_root = plugin_root or Path.home() / ".ivycode" / "plugins"

    def resolve_project_path(self, file_path: str) -> Path:
        raw_path = Path(file_path)
        path = raw_path if raw_path.is_absolute() else self.project_root / raw_path
        resolved = path.resolve()
        if not resolved.is_relative_to(self.project_root):
            raise ValueError(f"path is outside project root: {file_path}")
        return resolved
