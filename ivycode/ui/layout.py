from __future__ import annotations

from rich.layout import Layout


def build_root_layout() -> Layout:
    layout = Layout(name="root")
    layout.split_column(
        Layout(name="header", size=1),
        Layout(name="body"),
        Layout(name="input", size=1),
        Layout(name="footer", size=1),
    )
    layout["body"].split_row(
        Layout(name="feed", ratio=3),
        Layout(name="side", ratio=1),
    )
    layout["side"].split_column(
        Layout(name="activity", ratio=1),
        Layout(name="tools", ratio=1),
    )
    return layout
