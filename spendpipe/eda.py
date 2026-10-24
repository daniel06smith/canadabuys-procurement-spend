"""Shared chart style for the EDA notebooks (matplotlib).

Colours follow a validated colour-blind-safe categorical order; each entity keeps
its colour in every chart (the old record system is always blue, the new one orange).
"""
from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SYSTEM_COLORS = {"old": SERIES[0], "new": SERIES[1]}
SOURCE_COLORS = {"contracts_legacy": SERIES[0], "contracts_current": SERIES[1],
                 "tenders_legacy": SERIES[0], "tenders_current": SERIES[1]}
INK, INK_2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"


def apply_style() -> None:
    plt.rcParams.update({
        "figure.figsize": (10, 4), "figure.dpi": 110, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK_2, "axes.titlecolor": INK, "axes.titlesize": 12,
        "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True,
        "grid.color": GRID, "grid.linewidth": 0.8, "xtick.color": MUTED, "ytick.color": MUTED,
        "legend.frameon": False, "lines.linewidth": 2, "axes.prop_cycle": plt.cycler(color=SERIES),
    })


def money(unit: str = "B"):
    """Axis formatter for dollars in billions ('B') or millions ('M')."""
    div = {"B": 1e9, "M": 1e6, "K": 1e3}[unit]
    return FuncFormatter(lambda v, _: f"${v / div:,.0f}{unit}")


def thousands():
    return FuncFormatter(lambda v, _: f"{v:,.0f}")
