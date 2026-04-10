"""Welcome panel widgets for the `nocode` Textual application."""

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

BODY = "rgb(218,165,32)"
FACE = "rgb(139,90,43)"
TONGUE = "rgb(220,80,80)"

type PoseName = str


def _dog_default(tail: str = "╲") -> list[Text]:
    lines: list[Text] = []

    row0 = Text()
    row0.append("  ▄ ", style=BODY)
    row0.append("   ", style="default")
    row0.append("▄  ", style=BODY)
    lines.append(row0)

    row1 = Text()
    row1.append(" ▐", style=BODY)
    row1.append("◆   ◆", style=f"{FACE} on {BODY}")
    row1.append("▌ ", style=BODY)
    lines.append(row1)

    row2 = Text()
    row2.append("  ▐", style=BODY)
    row2.append(" ▾ ", style=f"{FACE} on {BODY}")
    row2.append("▌  ", style=BODY)
    lines.append(row2)

    row3 = Text()
    row3.append(" ▗█████▖ ", style=BODY)
    lines.append(row3)

    row4 = Text()
    row4.append("  ▜▘ ▝▛", style=BODY)
    row4.append(f" {tail}", style=BODY)
    lines.append(row4)

    return lines


def _dog_wag_left() -> list[Text]:
    return _dog_default(tail="╱")


def _dog_wag_right() -> list[Text]:
    return _dog_default(tail="╲")


def _dog_bark() -> list[Text]:
    lines: list[Text] = []

    row0 = Text()
    row0.append("  ▄ ", style=BODY)
    row0.append("   ", style="default")
    row0.append("▄  ", style=BODY)
    lines.append(row0)

    row1 = Text()
    row1.append(" ▐", style=BODY)
    row1.append("◆   ◆", style=f"{FACE} on {BODY}")
    row1.append("▌ ", style=BODY)
    lines.append(row1)

    row2 = Text()
    row2.append("  ▐", style=BODY)
    row2.append("▿▿▿", style=f"{TONGUE} on {BODY}")
    row2.append("▌  ", style=BODY)
    lines.append(row2)

    row3 = Text()
    row3.append(" ▗█████▖ ", style=BODY)
    lines.append(row3)

    row4 = Text()
    row4.append("  ▜▘ ▝▛ ╲", style=BODY)
    lines.append(row4)

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


class DogMascot(Widget):
    """Animated dog mascot that cycles through idle poses."""

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
        self._cycle_index = 0
        self._timer: Timer | None = None

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.6, self._next_pose)

    def _next_pose(self) -> None:
        self._cycle_index = (self._cycle_index + 1) % len(IDLE_CYCLE)
        self.pose = IDLE_CYCLE[self._cycle_index]

    def watch_pose(self) -> None:
        self.refresh()

    def render(self) -> RenderResult:
        lines = DOG_POSES.get(self.pose, DOG_POSES["default"])
        max_width = max(cell_len(line.plain) for line in lines)
        padded: list[Text] = []
        for line in lines:
            gap = max_width - cell_len(line.plain)
            if gap > 0:
                padded_line = line.copy()
                padded_line.append(" " * gap)
                padded.append(padded_line)
                continue
            padded.append(line)
        return Text("\n").join(padded)


def _get_version() -> str:
    try:
        return version("nocode")
    except PackageNotFoundError:
        return "0.0.0"


class WelcomePanel(Widget):
    """Centered startup panel showing branding, mascot, cwd, and shortcuts."""

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
