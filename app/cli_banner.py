from __future__ import annotations

from collections.abc import Sequence
import os
import sys

from rich.console import Console
from rich.text import Text


BANNER_TITLE = "Skill-Seeking Agent"
BANNER_SUBTITLE = "governed capability acquisition"
BANNER_BOUNDARY = "local CLI | evidence first | no hidden authority"
BANNER_WIDTH = 74
BANNER_ART = (
    " #####  #   #  #####  #       #             ##     #####  #####  #   #  #######",
    "#       #  #     #    #       #            #  #   #       #      ##  #     #   ",
    "#       # #      #    #       #           #    #  #       #      # # #     #   ",
    " ####   ##       #    #       #           ######  #  ###  #####  #  ##     #   ",
    "     #  # #      #    #       #           #    #  #    #  #      #   #     #   ",
    "     #  #  #     #    #       #           #    #  #    #  #      #   #     #   ",
    "#####   #   #  #####  ######  ######      #    #   ####   #####  #   #     #   ",
)
BANNER_COLORS = (
    (249, 115, 22),
    (244, 114, 182),
    (96, 165, 250),
)


def emit_cli_banner(*, color: bool = True, force_color: bool = False) -> None:
    """Emit a compact human-facing CLI banner."""

    color = color and (force_color or "NO_COLOR" not in os.environ)
    force_terminal = None
    no_color = None
    if not color:
        force_terminal = False
        no_color = True
    elif force_color:
        force_terminal = True
        no_color = False

    console = Console(
        file=sys.stdout,
        color_system="truecolor" if color else None,
        force_terminal=force_terminal,
        highlight=False,
        no_color=no_color,
        soft_wrap=True,
        width=80,
    )
    console.print(_chrome_text(f"+-- Welcome to the {BANNER_TITLE} v1.0 local CLI --+", color=color))
    console.print("")
    for line in BANNER_ART:
        console.print(_gradient_text(line, colors=BANNER_COLORS))
    console.print(_gradient_text("-" * BANNER_WIDTH, colors=BANNER_COLORS))
    console.print(Text(f"mode: {BANNER_SUBTITLE}", style="bold white" if color else ""))
    console.print(Text(f"scope: {BANNER_BOUNDARY}", style="#94a3b8" if color else ""))
    console.print(Text("start: skill-agent run \"Cluster arguments from these sources.\"", style="#fbbf24" if color else ""))


def _chrome_text(text: str, *, color: bool) -> Text:
    return Text(text, style="#f97316" if color else "")


def _gradient_text(text: str, *, colors: Sequence[tuple[int, int, int]]) -> Text:
    if not text:
        return Text()
    if len(colors) < 2:
        raise ValueError("gradient requires at least two colors")

    styled = Text()
    last_index = max(1, len(text) - 1)
    segment_count = len(colors) - 1
    for index, character in enumerate(text):
        if character == " ":
            styled.append(character)
            continue
        scaled = (index / last_index) * segment_count
        left_index = min(int(scaled), segment_count - 1)
        right_index = left_index + 1
        local_ratio = scaled - left_index
        rgb = _interpolate_rgb(colors[left_index], colors[right_index], local_ratio)
        styled.append(character, style=f"bold #{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}")
    return styled


def _interpolate_rgb(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    ratio: float,
) -> tuple[int, int, int]:
    return tuple(
        round(start_value + (end_value - start_value) * ratio)
        for start_value, end_value in zip(start, end, strict=True)
    )
