from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from pydantic import Field

from ivycode.core.envelope import IvyBaseModel

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class PluginManifest(IvyBaseModel):
    slug: str
    description: str
    skills: list[str] = Field(min_length=1)
    created_by: str = "ivycode"
    manifest_version: int = 1


class PluginStore:
    def __init__(self, *, plugin_root: Path) -> None:
        self.plugin_root = plugin_root.expanduser().resolve()

    def save_plugin(
        self,
        *,
        slug: str,
        description: str,
        skills: list[str],
    ) -> PluginManifest:
        _validate_slug(slug)
        manifest = PluginManifest(
            slug=slug,
            description=description,
            skills=skills,
        )
        target = self.plugin_root / slug
        temp = self.plugin_root / f".{slug}.tmp"
        if target.exists():
            raise FileExistsError(f"plugin already exists: {slug}")
        if temp.exists():
            shutil.rmtree(temp)

        try:
            temp.mkdir(parents=True, exist_ok=False)
            (temp / "plugin.json").write_text(
                json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n",
                encoding="utf-8",
            )
            temp.rename(target)
        except Exception:
            if temp.exists():
                shutil.rmtree(temp)
            raise

        return manifest

    def list_plugins(self) -> list[PluginManifest]:
        if not self.plugin_root.exists():
            return []
        manifests: list[PluginManifest] = []
        for path in sorted(self.plugin_root.iterdir()):
            manifest_path = path / "plugin.json"
            if not manifest_path.is_file():
                continue
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifests.append(PluginManifest.model_validate(payload))
        return manifests


def _validate_slug(slug: str) -> None:
    if _SLUG_PATTERN.fullmatch(slug) is None:
        raise ValueError(f"invalid plugin slug: {slug}")
