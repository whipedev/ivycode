from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.text import Text

from ivycode.core.envelope import CallerMeta, UsageMetrics
from ivycode.ui.theme import PALETTE, theme_for_provider


@dataclass(frozen=True)
class ModelPanel:
    meta: CallerMeta
    body: str
    usage: UsageMetrics | None = None

    def render(self) -> RenderableType:
        theme = theme_for_provider(self.meta.model.provider)
        lines: list[Text] = [
            Text.assemble(
                ("▏ ", theme.border),
                (f"{theme.glyph}  ", theme.accent),
                (self.meta.model.display_name, "bold"),
                (" / ", PALETTE.text_dim),
                (self.meta.agent.value, PALETTE.text_dim),
            ),
            Text("▏", style=theme.border),
        ]

        for body_line in self.body.splitlines() or [""]:
            lines.append(
                Text.assemble(
                    ("▏  ", theme.border),
                    (body_line, PALETTE.text_primary),
                )
            )

        if self.usage is not None:
            lines.append(Text("▏", style=theme.border))
            lines.append(
                Text.assemble(
                    ("▏  ", theme.border),
                    (
                        f"in {self.usage.input_tokens} · "
                        f"out {self.usage.output_tokens} · "
                        f"TTFB {self.usage.latency_ms}ms · "
                        f"${self.usage.cost_usd:.4f}",
                        PALETTE.text_dim,
                    ),
                )
            )

        return Group(*lines)
