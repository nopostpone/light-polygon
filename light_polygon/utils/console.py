from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

theme = Theme(
    {
        "verdict.ac": "green",
        "verdict.wa": "red",
        "verdict.tle": "yellow",
        "verdict.mle": "yellow",
        "verdict.rte": "magenta",
        "verdict.ce": "bold red",
        "info": "dim",
        "heading": "bold cyan",
    }
)

console = Console(theme=theme)
