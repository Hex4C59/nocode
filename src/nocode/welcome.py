"""
Welcome panel for the nocode TUI: branding, animated mascot, cwd, and tips.

A single centered splash screen displaying the mascot and shortcuts in a clean
bordered box.
"""

from __future__ import annotations

import pathlib
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from rich.cells import cell_len
from rich.text import Text
from textual.app import ComposeResult, RenderResult
from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Static

# ---------------------------------------------------------------------------
# Dog mascot pose data
# ---------------------------------------------------------------------------
# Each pose is a list of Rich Text lines. The dog is ~11 cols wide, 5 rows.
# Uses Unicode block-drawing characters (U+2580..U+259F) for sub-cell detail.
# Two colours: BODY (golden/amber) and FACE (darker brown for contrast).

BODY = "rgb(218,165,32)"
FACE = "rgb(139,90,43)"
TONGUE = "rgb(220,80,80)"

type PoseName = str


def _dog_default(tail: str = "╲") -> list[Text]:
    """Sitting dog, ears up. *tail* lets callers vary just the tail glyph."""
    lines: list[Text] = []

    # row 0: ears
    r0 = Text()
    r0.append("  ▄ ", style=BODY)
    r0.append("   ", style="default")
    r0.append("▄  ", style=BODY)
    lines.append(r0)

    # row 1: head (eyes on face background)
    r1 = Text()
    r1.append(" ▐", style=BODY)
    r1.append("◆   ◆", style=f"{FACE} on {BODY}")
    r1.append("▌ ", style=BODY)
    lines.append(r1)

    # row 2: snout + tongue
    r2 = Text()
    r2.append("  ▐", style=BODY)
    r2.append(" ▾ ", style=f"{FACE} on {BODY}")
    r2.append("▌  ", style=BODY)
    lines.append(r2)

    # row 3: body
    r3 = Text()
    r3.append(" ▗█████▖ ", style=BODY)
    lines.append(r3)

    # row 4: legs + tail
    r4 = Text()
    r4.append("  ▜▘ ▝▛", style=BODY)
    r4.append(f" {tail}", style=BODY)
    lines.append(r4)

    return lines


def _dog_wag_left() -> list[Text]:
    lines = _dog_default(tail="╱")
    return lines


def _dog_wag_right() -> list[Text]:
    lines = _dog_default(tail="╲")
    return lines


def _dog_bark() -> list[Text]:
    """Mouth open — bark!"""
    lines: list[Text] = []

    r0 = Text()
    r0.append("  ▄ ", style=BODY)
    r0.append("   ", style="default")
    r0.append("▄  ", style=BODY)
    lines.append(r0)

    r1 = Text()
    r1.append(" ▐", style=BODY)
    r1.append("◆   ◆", style=f"{FACE} on {BODY}")
    r1.append("▌ ", style=BODY)
    lines.append(r1)

    # mouth open wider
    r2 = Text()
    r2.append("  ▐", style=BODY)
    r2.append("▿▿▿", style=f"{TONGUE} on {BODY}")
    r2.append("▌  ", style=BODY)
    lines.append(r2)

    r3 = Text()
    r3.append(" ▗█████▖ ", style=BODY)
    lines.append(r3)

    r4 = Text()
    r4.append("  ▜▘ ▝▛ ╲", style=BODY)
    lines.append(r4)

    return lines


DOG_POSES: dict[PoseName, list[Text]] = {
    "default": _dog_default(),
    "wag-left": _dog_wag_left(),
    "wag-right": _dog_wag_right(),
    "bark": _dog_bark(),
}

IDLE_CYCLE: list[PoseName] = [
    "default",
    "wag-left",
    "default",
    "wag-right",
    "default",
    "wag-left",
    "default",
    "wag-right",
    "bark",
]


# ---------------------------------------------------------------------------
# DogMascot widget
# ---------------------------------------------------------------------------


class DogMascot(Widget):
    """Animated dog mascot that cycles idle poses via a timer."""

    DEFAULT_CSS = """
    DogMascot {
        height: auto;
        min-height: 5;
        width: 1fr;
        content-align: center middle;
    }
    """

    pose: reactive[PoseName] = reactive("default")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._cycle_idx = 0
        self._timer: Timer | None = None

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.6, self._next_pose)

    def _next_pose(self) -> None:
        self._cycle_idx = (self._cycle_idx + 1) % len(IDLE_CYCLE)
        self.pose = IDLE_CYCLE[self._cycle_idx]

    def watch_pose(self) -> None:
        self.refresh()

    def render(self) -> RenderResult:
        lines = DOG_POSES.get(self.pose, DOG_POSES["default"])
        max_w = max(cell_len(line.plain) for line in lines)
        padded: list[Text] = []
        for line in lines:
            gap = max_w - cell_len(line.plain)
            if gap > 0:
                padded_line = line.copy()
                padded_line.append(" " * gap)
                padded.append(padded_line)
            else:
                padded.append(line)
        return Text("\n").join(padded)


# ---------------------------------------------------------------------------
# Helper: version string
# ---------------------------------------------------------------------------


def _get_version() -> str:
    try:
        return version("nocode")
    except PackageNotFoundError:
        return "0.0.0"


# ---------------------------------------------------------------------------
# WelcomePanel widget
# ---------------------------------------------------------------------------

class WelcomePanel(Widget):
    """Centered startup panel mimicking Claude Code's LogoV2 compact layout.

    Structure: round border with embedded title, all children center-aligned.
    """

    DEFAULT_CSS = """
    WelcomePanel {
        height: auto;
        width: 1fr;
        margin-bottom: 1;
        layout: vertical;
        border: round $primary;
        padding: 1 1;
        border-title-align: left;
        border-title-color: $primary;
        border-title-style: bold;
        align: center middle;
    }

    WelcomePanel .wp-line {
        width: 1fr;
        height: auto;
        content-align: center middle;
    }

    WelcomePanel #wp-mascot-wrap {
        width: 1fr;
        height: auto;
        content-align: center middle;
        margin: 1 0;
    }

    WelcomePanel #wp-shortcuts {
        width: 1fr;
        height: auto;
        content-align: center middle;
        color: $text-muted;
    }
    """

    def on_mount(self) -> None:
        self.border_title = f"Nocode v{_get_version()}"

    def compose(self) -> ComposeResult:
        cwd = self._format_cwd()

        yield Static(
            "[bold]Welcome to Nocode[/bold]",
            classes="wp-line",
            markup=True,
        )
        yield DogMascot(id="wp-mascot-wrap")
        yield Static(f"[dim]{cwd}[/dim]", classes="wp-line", markup=True)
        yield Static(
            "[dim]› [bold]Enter[/bold] 发送  ·  › [bold]Alt+V[/bold] 贴图  ·  › [bold]/exit[/bold] 退出[/dim]",
            id="wp-shortcuts",
            markup=True,
        )

    @staticmethod
    def _format_cwd() -> str:
        cwd = pathlib.Path.cwd()
        home = pathlib.Path.home()
        try:
            return f"~/{cwd.relative_to(home)}"
        except ValueError:
            return str(cwd)
