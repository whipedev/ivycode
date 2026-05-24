from __future__ import annotations

from ivycode.ui.layout import build_root_layout


def test_build_root_layout_exposes_expected_regions() -> None:
    layout = build_root_layout()

    assert layout.name == "root"
    assert layout["header"].name == "header"
    assert layout["body"].name == "body"
    assert layout["feed"].name == "feed"
    assert layout["side"].name == "side"
    assert layout["activity"].name == "activity"
    assert layout["tools"].name == "tools"
    assert layout["input"].name == "input"
    assert layout["footer"].name == "footer"


def test_build_root_layout_uses_spec_ratios_and_fixed_rows() -> None:
    layout = build_root_layout()

    assert layout["header"].size == 1
    assert layout["input"].size == 1
    assert layout["footer"].size == 1
    assert layout["feed"].ratio == 3
    assert layout["side"].ratio == 1
