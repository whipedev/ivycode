from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ivycode import __version__
from ivycode.cli.app import app


def test_package_version_is_skills_ui_polish() -> None:
    assert __version__ == "0.6.0"


def test_doctor_reports_foundation_status() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "ivycode doctor" in result.output
    assert "version 0.6.0" in result.output
    assert "foundation ready" in result.output


def test_future_commands_report_stage_boundary() -> None:
    runner = CliRunner()

    for command in ("chat", "plan"):
        result = runner.invoke(app, [command])
        assert result.exit_code == 2
        assert "not implemented in v0.6.0-skills-ui-polish" in result.output


def test_index_command_indexes_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    (tmp_path / "app.py").write_text(
        "def hello() -> str:\n    return 'hello'\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["index", "--force"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "ivycode index" in result.output
    assert "files indexed 1" in result.output
    assert "symbols 1" in result.output
