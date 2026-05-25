from __future__ import annotations

from dataclasses import dataclass

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.pretty import Pretty
from rich.text import Text

from ivycode.ui.theme import PALETTE


@dataclass(frozen=True)
class ErrorPanel:
    skill_name: str
    exception: BaseException
    arguments: dict[str, object]

    def render(self) -> RenderableType:
        body = Group(
            Text(type(self.exception).__name__, style=f"bold {PALETTE.error}"),
            Text(str(self.exception), style=PALETTE.text_primary),
            Text("arguments", style=PALETTE.text_dim),
            Pretty(self.arguments),
            Text("Use --json for machine-readable failures.", style=PALETTE.text_dim),
        )
        return Panel(
            body,
            title=f"✗ {self.skill_name} failed",
            title_align="left",
            border_style=PALETTE.error,
            box=box.ROUNDED,
            padding=(0, 1),
        )
