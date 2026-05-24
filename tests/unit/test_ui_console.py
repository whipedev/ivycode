from __future__ import annotations

from rich.console import Console

from ivycode.ui.console import get_console


def test_get_console_returns_singleton() -> None:
    first = get_console()
    second = get_console()

    assert first is second
    assert isinstance(first, Console)


def test_console_uses_truecolor_terminal() -> None:
    console = get_console()

    assert console.color_system == "truecolor"
    assert console.is_terminal is True
