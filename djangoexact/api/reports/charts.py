"""Charts embedded in the FAO PDF report, rendered as base64 SVG.

Labels go through gettext and numbers through Django's locale formatting, so the
caller must ``activate(lang)`` first (``build_template_context`` does). Text is
written into the SVG as paths, so the PDF never depends on WeasyPrint finding the
chart font.
"""
from __future__ import annotations

import base64
import io
from collections.abc import Sequence

from django.template.defaultfilters import floatformat
from django.utils.translation import gettext as _
from matplotlib import font_manager, rc_context
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MaxNLocator

# 17 cm: A4 width minus the 2 cm @page margins, so the chart prints at 1:1 and
# its 9 pt text matches the body copy instead of being scaled down.
CONTENT_WIDTH_IN = 6.7

INK = "#1f1f1e"
INK_MUTED = "#52514e"
GRID = "#e4e3df"
NEUTRAL = "#a8a7a1"
ACCENT = "#2a78d6"
UNIT = "tCO$_2$e"

# Fixed slot per gas (validated all-pairs for CVD), so a gas keeps its color
# whichever subset of gases a project has. A None label is translated at render time.
GAS_SERIES = (
    ("CO$_2$", ("CO2",), "#2a78d6"),
    ("CH$_4$", ("CH4",), "#eb6834"),
    ("N$_2$O", ("N2O",), "#1baf7a"),
    (None, ("CO", "DOC", "OTHER"), NEUTRAL),
)

_PREFERRED_FONTS = ("Liberation Sans", "Arial", "Helvetica")
_installed = {f.name for f in font_manager.fontManager.ttflist}
# Only installed families are listed: matplotlib logs a warning for every missing
# one on every render. DejaVu ships with matplotlib and covers Cyrillic.
_FONTS = [f for f in _PREFERRED_FONTS if f in _installed] + ["DejaVu Sans"]

_STYLE = {
    "font.family": "sans-serif",
    "font.sans-serif": _FONTS,
    "font.size": 9,
    "text.color": INK,
    "axes.labelcolor": INK_MUTED,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "axes.spines.bottom": False,
    "axes.axisbelow": True,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
    "xtick.major.size": 0,
    "ytick.major.size": 0,
    "legend.frameon": False,
    "svg.fonttype": "path",
    # Arial and Liberation have no subscript-digit glyphs (CO₂ prints as tofu),
    # so subscripts are mathtext drawn in the same font as the rest of the chart.
    "mathtext.fontset": "custom",
    "mathtext.rm": _FONTS[0],
    "mathtext.default": "regular",
}


def _fmt(value: float, decimals: int = 2) -> str:
    """Locale-formatted number, identical to the ``floatformat:"2g"`` figures in the report text.

    Same filter on purpose: number_format rounds the binary float, so 218483.75
    (stored as 218483.7499...) printed .74 in the chart and .75 in the text.
    """
    return str(floatformat(value, f"{decimals}g"))


def _axis_formatter() -> FuncFormatter:
    return FuncFormatter(lambda v, _pos: _fmt(v, 0))


def _to_svg_b64(fig: Figure) -> str:
    buf = io.BytesIO()
    # Tight bbox keeps outside-axes text (legend, value labels) inside the canvas.
    fig.savefig(buf, format="svg", bbox_inches="tight", pad_inches=0.05)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _padded_limits(values: Sequence[float], pad: float) -> tuple[float, float]:
    """Axis limits that always include 0 and leave room past each bar end for its label."""
    lo, hi = min(0.0, *values), max(0.0, *values)
    span = (hi - lo) or 1.0
    return (lo - span * pad if lo < 0 else lo, hi + span * pad if hi > 0 else hi)


def diverging_bottoms(rows: Sequence[Sequence[float]]) -> list[list[float]]:
    """Bottom of each stacked segment, stacking positives up and negatives down from 0.

    ``rows[i][j]`` is series i in column j. A plain running sum would draw a
    negative segment over the positive ones beneath it.
    """
    n_cols = len(rows[0]) if rows else 0
    pos, neg = [0.0] * n_cols, [0.0] * n_cols
    bottoms = []
    for row in rows:
        bottom = []
        for j, v in enumerate(row):
            if v >= 0:
                bottom.append(pos[j])
                pos[j] += v
            else:
                bottom.append(neg[j])
                neg[j] += v
        bottoms.append(bottom)
    return bottoms


def scenario_labels() -> list[str]:
    return [_("With project"), _("Without project"), _("Balance")]


def chart_project_balance(total_w: float, total_wo: float, total_balance: float) -> str:
    """Horizontal bars for With / Without / Balance in tCO2e. Returns base64 SVG."""
    values = [total_w, total_wo, total_balance]
    y = [2, 1, 0]  # With on top, Balance last, the order the report text reads them
    with rc_context(_STYLE):
        fig = Figure(figsize=(CONTENT_WIDTH_IN, 2.4))
        ax = fig.add_subplot()
        ax.barh(y, values, height=0.56, color=[NEUTRAL, NEUTRAL, ACCENT])
        ax.set_yticks(y, scenario_labels())
        ax.get_yticklabels()[2].set_fontweight("bold")
        ax.tick_params(axis="y", labelcolor=INK)
        ax.grid(False, axis="y")
        ax.axvline(0, color=INK_MUTED, linewidth=0.9)
        ax.set_xlim(*_padded_limits(values, pad=0.24))
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
        ax.xaxis.set_major_formatter(_axis_formatter())
        ax.set_xlabel(UNIT)
        for yi, v in zip(y, values):
            ax.annotate(
                _fmt(v), (v, yi), xytext=(4 if v >= 0 else -4, 0), textcoords="offset points",
                ha="left" if v >= 0 else "right", va="center", color=INK,
                fontweight="bold" if yi == 0 else "normal",
            )
        return _to_svg_b64(fig)


def gas_rows(data_w: dict, data_wo: dict) -> list[tuple[str, list[float], str]]:
    """(label, [with, without, balance], color) per gas series, dropping all-zero series."""
    rows = []
    for label, keys, color in GAS_SERIES:
        w = sum(data_w[k] for k in keys)
        wo = sum(data_wo[k] for k in keys)
        values = [w, wo, w - wo]
        if any(values):
            rows.append((label or _("Other"), values, color))
    return rows


def chart_gases_w_wo(data_w: dict, data_wo: dict) -> str:
    """Stacked bars per gas for With / Without / Balance in tCO2e. Returns base64 SVG."""
    rows = gas_rows(data_w, data_wo)
    series = [values for _label, values, _color in rows]
    x = [0, 1, 2]
    col_top = [sum(max(s[j], 0.0) for s in series) for j in x]
    col_bot = [sum(min(s[j], 0.0) for s in series) for j in x]
    totals = [t + b for t, b in zip(col_top, col_bot)]

    with rc_context(_STYLE):
        fig = Figure(figsize=(CONTENT_WIDTH_IN, 3.4))
        ax = fig.add_subplot()
        for (label, values, color), bottom in zip(rows, diverging_bottoms(series)):
            # The white edge is the surface gap between stacked segments.
            ax.bar(x, values, width=0.42, bottom=bottom, color=color, label=label,
                   edgecolor="white", linewidth=1.2)
        for xi, total in zip(x, totals):
            # With mixed signs the net total sits inside the stack, not at its end,
            # so it gets its own marker, named in the legend and in its label:
            # unlabelled, readers took it for a misplaced bar end.
            ax.plot([xi - 0.27, xi + 0.27], [total, total], color=INK, linewidth=1.6, solid_capstyle="butt",
                    label=_("Net total") if xi == 0 else "_nolegend_")
            ax.annotate(_("Net: %(value)s") % {"value": _fmt(total)}, (xi + 0.27, total), xytext=(4, 0),
                        textcoords="offset points", ha="left", va="center", color=INK, fontweight="bold")

        ax.set_ylim(*_padded_limits(col_top + col_bot, pad=0.06))
        ax.set_xticks(x, scenario_labels())
        ax.tick_params(axis="x", labelcolor=INK, pad=6)
        ax.grid(False, axis="x")
        ax.axhline(0, color=INK_MUTED, linewidth=0.9)
        ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
        ax.yaxis.set_major_formatter(_axis_formatter())
        ax.set_ylabel(UNIT)
        if rows:
            ax.legend(loc="lower left", bbox_to_anchor=(0, 1.02), ncols=len(rows) + 1,
                      handlelength=1.0, handleheight=1.0, columnspacing=1.6, borderaxespad=0)
        return _to_svg_b64(fig)
