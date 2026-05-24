from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ivycode.cli.app import app


def test_skills_dashboard_renders_command_center(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["skills"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "ivycode skills" in result.output
    assert "local command center" in result.output
    assert "graph.search_symbols" in result.output
    assert "fs.read_file" in result.output
    assert "Plugin Shelf" in result.output


def test_skills_save_creates_local_plugin_shell(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", tmp_path.as_posix())
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "skills",
            "save",
            "auth-helper",
            "--skill",
            "graph.search_symbols",
            "--description",
            "Auth helper",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "saved auth-helper" in result.output
    assert (tmp_path / ".ivycode" / "plugins" / "auth-helper" / "plugin.json").exists()
