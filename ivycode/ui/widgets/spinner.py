from __future__ import annotations

from typing import Any, cast

import rich.spinner

CUSTOM_SPINNERS: dict[str, dict[str, object]] = {
    "ivy-pulse": {
        "interval": 90,
        "frames": ["▰▱▱▱", "▱▰▱▱", "▱▱▰▱", "▱▱▱▰", "▱▱▰▱", "▱▰▱▱"],
    },
    "ivy-orbit": {
        "interval": 110,
        "frames": ["◜", "◠", "◝", "◞", "◡", "◟"],
    },
    "ivy-stream": {
        "interval": 60,
        "frames": ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "▊", "▋", "▌", "▍", "▎"],
    },
}


def register_custom_spinners() -> None:
    spinners = cast(dict[str, Any], rich.spinner.SPINNERS)  # type: ignore[attr-defined]
    spinners.update(CUSTOM_SPINNERS)
