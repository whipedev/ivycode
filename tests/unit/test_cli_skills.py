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
            "--yes",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "saved auth-helper" in result.output
    assert (tmp_path / ".ivycode" / "plugins" / "auth-helper" / "plugin.json").exists()


def test_skills_save_requires_confirmation(
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
        input="n\n",
    )

    assert result.exit_code != 0
    assert "proceed?" in result.output
    assert not (
        tmp_path / ".ivycode" / "plugins" / "auth-helper" / "plugin.json"
    ).exists()


def test_skills_list_renders_description_badges_and_risk() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["skills", "list"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "Description" in result.output
    assert "Risk" in result.output
    assert "Status" not in result.output
    assert "▤" in result.output
    assert "◈" in result.output
    assert "FS·R" in result.output
    assert "GRAPH·R" in result.output


def test_skills_inspect_renders_parameter_table_by_default() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["skills", "inspect", "fs.write_file"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "ivycode skill · fs.write_file" in result.output
    assert "parameters" in result.output
    assert "file_path" in result.output
    assert "content" in result.output
    assert "usage" in result.output
    assert '"properties"' not in result.output


def test_skills_inspect_schema_flag_renders_raw_schema() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["skills", "inspect", "fs.write_file", "--schema"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert '"properties"' in result.output
    assert '"file_path"' in result.output


def test_skills_run_renders_human_success_panel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["skills", "run", "fs.read_file", "--arg", "file_path=README.md"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "✓ fs.read_file" in result.output
    assert "# Demo" in result.output
    assert '"# Demo' not in result.output


def test_skills_run_json_keeps_machine_readable_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "skills",
            "run",
            "fs.read_file",
            "--arg",
            "file_path=README.md",
            "--json",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert result.output.strip().startswith('"# Demo')


def test_skills_run_errors_render_error_panel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "skills",
            "run",
            "fs.read_file",
            "--arg",
            "file_path=README.md",
            "--arg",
            "line_start=3",
            "--arg",
            "line_end=1",
        ],
    )

    assert result.exit_code != 0
    assert "✗ fs.read_file failed" in result.output
    assert "ValueError" in result.output
    assert "line_end must be >= line_start" in result.output
