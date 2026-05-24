from __future__ import annotations

import json
from pathlib import Path

import pytest

from ivycode.skills.store import PluginStore


def test_plugin_store_saves_manifest(tmp_path: Path) -> None:
    store = PluginStore(plugin_root=tmp_path / "plugins")

    manifest = store.save_plugin(
        slug="auth-helper",
        description="Auth workflow helper",
        skills=["graph.search_symbols", "fs.read_file"],
    )

    manifest_path = tmp_path / "plugins" / "auth-helper" / "plugin.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest.slug == "auth-helper"
    assert payload["description"] == "Auth workflow helper"
    assert payload["skills"] == ["graph.search_symbols", "fs.read_file"]


def test_plugin_store_rejects_invalid_slug(tmp_path: Path) -> None:
    store = PluginStore(plugin_root=tmp_path / "plugins")

    with pytest.raises(ValueError, match="invalid plugin slug"):
        store.save_plugin(slug="Bad Slug", description="x", skills=["fs.read_file"])
