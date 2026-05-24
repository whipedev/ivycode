from __future__ import annotations

from typer.testing import CliRunner

from ivycode import __version__
from ivycode.cli.app import app


def test_package_version_is_provider_foundation() -> None:
    assert __version__ == "0.3.0"


def test_doctor_reports_foundation_status() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "ivycode doctor" in result.output
    assert "version 0.3.0" in result.output
    assert "foundation ready" in result.output


def test_future_commands_report_stage_boundary() -> None:
    runner = CliRunner()

    for command in ("chat", "plan", "index"):
        result = runner.invoke(app, [command])
        assert result.exit_code == 2
        assert "not implemented in v0.3.0-provider-foundation" in result.output
