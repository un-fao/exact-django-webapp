"""Saved-fixtures permutation runner for LandUseChange.

Unlike per-module slices, LUC needs a saved ``Activity`` with attached
sibling land modules so ``LandUseChange.get_modules()`` resolves. This
module wraps that work in ``transaction.atomic`` + ``set_rollback(True)``
so each combination's fixtures are rolled back; only the data dicts
collected in memory escape the transaction.
"""
from __future__ import annotations

import logging
from typing import Any, Iterator

logger = logging.getLogger(__name__)


def iterate_concrete_combos(
    start_spec: tuple[str, int],
    w_spec: tuple[str, int],
) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    """Cross-product of expand_preset(start, START) x expand_preset(w, W).

    Yields ``(start_values, w_values)`` field dicts. ``w_values`` already
    has any ``_destination_overrides`` applied.
    """
    from admin_scripts.luc_permutations import Side, expand_preset

    start_combos = expand_preset(start_spec[0], start_spec[1], Side.START)
    w_combos = expand_preset(w_spec[0], w_spec[1], Side.W)
    for s in start_combos:
        for w in w_combos:
            yield s, w
