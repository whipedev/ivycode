from __future__ import annotations

from rich.console import Console

_CONSOLE: Console | None = None


def get_console() -> Console:
    global _CONSOLE
    if _CONSOLE is None:
        _CONSOLE = Console(force_terminal=True, color_system="truecolor")
    return _CONSOLE
