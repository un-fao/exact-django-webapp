import math
import statistics as stats_module

from django.db.models import Avg, Count, Max, Min, Q, Sum


def _coerce_unit(value):
    """Convert a POSTed unit value to a safe float multiplier.

    Returns 1.0 for None, blank strings, non-numeric strings, non-finite values
    (NaN, +inf, -inf), and negative numbers.
    """
    if value is None:
        return 1.0
    try:
        f = float(value)
    except (TypeError, ValueError, OverflowError):
        return 1.0
    if not math.isfinite(f):
        return 1.0
    if f < 0:
        return 1.0
    return f


def stats_for(qs):
    """Compute descriptive statistics for a ChangeRecord queryset's 'total' field."""
    agg = qs.aggregate(
        n=Count("id"),
        s=Sum("total"),
        mean=Avg("total"),
        minv=Min("total"),
        maxv=Max("total"),
    )
    n, s = agg["n"] or 0, agg["s"] or 0.0
    mean = agg["mean"] if n else None

    if n > 0:
        total_values = list(qs.values_list("total", flat=True))
        ss = sum(x * x for x in total_values)

        if n > 1:
            var = max(0, (ss - (s * s) / n) / (n - 1))
            std = var**0.5
            se = std / (n**0.5)
            ci95 = 1.96 * se
            ci99 = 2.58 * se
        else:
            std = se = ci95 = ci99 = None

        sorted_values = sorted(total_values)

        if len(sorted_values) >= 4:
            q1 = stats_module.quantiles(sorted_values, n=4)[0]
            median = stats_module.median(sorted_values)
            q3 = stats_module.quantiles(sorted_values, n=4)[2]
        else:
            n_values = len(sorted_values)
            if n_values % 2 == 0:
                median = (sorted_values[n_values // 2 - 1] + sorted_values[n_values // 2]) / 2
            else:
                median = sorted_values[n_values // 2]

            q1_idx = (n_values - 1) * 0.25
            q3_idx = (n_values - 1) * 0.75

            if q1_idx.is_integer():
                q1 = sorted_values[int(q1_idx)]
            else:
                lower_idx = int(q1_idx)
                upper_idx = min(lower_idx + 1, n_values - 1)
                weight = q1_idx - lower_idx
                q1 = sorted_values[lower_idx] * (1 - weight) + sorted_values[upper_idx] * weight

            if q3_idx.is_integer():
                q3 = sorted_values[int(q3_idx)]
            else:
                lower_idx = int(q3_idx)
                upper_idx = min(lower_idx + 1, n_values - 1)
                weight = q3_idx - lower_idx
                q3 = sorted_values[lower_idx] * (1 - weight) + sorted_values[upper_idx] * weight
    else:
        std = se = ci95 = ci99 = None
        q1 = median = q3 = None

    iqr = (q3 - q1) if (q1 is not None and q3 is not None) else None

    return {
        "count": n,
        "sum_total": s,
        "mean": mean,
        "median": median,
        "min": agg["minv"],
        "max": agg["maxv"],
        "std": std,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "ci_95": ci95,
        "ci_99": ci99,
    }


def _create_flexible_value_query(field_name, value):
    """Handle numeric values that may be stored as int or float strings."""
    try:
        float_val = float(value)
        if float_val.is_integer():
            return Q(**{field_name: str(int(float_val))}) | Q(**{field_name: str(float_val)})
        else:
            return Q(**{field_name: str(float_val)})
    except (ValueError, TypeError):
        return Q(**{field_name: str(value)})


def _build_single_change_q(change, global_filters):
    """Build a Q object matching ChangeRecords for one change in a scenario.

    Returns ``Q(pk__in=[])`` (a sentinel that matches nothing — a bare
    ``Q()`` would match *everything*) when the change has no module_type,
    so the helper is safe to call standalone. Callers that OR results
    together should still skip such changes to avoid noise.
    """
    module_type = change.get("module_type")
    if not module_type:
        return Q(pk__in=[])

    change_filters = {**global_filters, **change.get("filters", {})}
    csv_row_filters = change.get("csv_row_filters", {})

    change_q = (
        Q(module_type=module_type, field=change["start"]["field"])
        & _create_flexible_value_query("from_value", change["start"]["value"])
        & _create_flexible_value_query("to_value", change["end"]["value"])
    )

    for col in ("region", "climate", "moisture", "soil_type"):
        if change_filters.get(col):
            values = change_filters[col] if isinstance(change_filters[col], list) else [change_filters[col]]
            col_q = Q()
            for val in values:
                col_q |= Q(**{col: val})
            change_q &= col_q

    for filter_key, filter_value in change_filters.items():
        if filter_key in ("region", "climate", "moisture", "soil_type"):
            continue
        filter_values = filter_value if isinstance(filter_value, list) else [filter_value]
        filter_q = Q()
        for val in filter_values:
            filter_q |= Q(**{f"csv_row_data__{filter_key}": val}) | Q(**{f"custom_filters__{filter_key}": val})
        change_q &= filter_q

    for filter_key, filter_value in csv_row_filters.items():
        if filter_key in ("module_start_type", "module_w_type"):
            continue
        filter_values = filter_value if isinstance(filter_value, list) else [filter_value]
        csv_filter_q = Q()
        for val in filter_values:
            csv_filter_q |= Q(**{f"csv_row_data__{filter_key}": val})
        change_q &= csv_filter_q

    return change_q


def build_scenario_query(changes, global_filters):
    """
    Build a combined Q object for filtering ChangeRecords based on scenario changes.

    Args:
        changes: List of change dicts, each with keys:
            - module_type (str)
            - start: {field, value}
            - end: {field, value}
            - filters (optional dict): region, climate, moisture, soil_type, or custom
            - csv_row_filters (optional dict): filters on csv_row_data JSONField
        global_filters: Dict of filters applied to ALL changes (same keys as change filters)

    Returns:
        Q object suitable for ChangeRecord.objects.filter()
    """
    q_objects = Q()
    for change in changes:
        if not change.get("module_type"):
            continue
        q_objects |= _build_single_change_q(change, global_filters)
    return q_objects


def _descriptive_stats_from_values(values):
    """Compute the same descriptive-statistics dict shape as ``stats_for(qs)``,
    but from an already-materialized list of floats.
    """
    n = len(values)
    if n == 0:
        return {
            "count": 0,
            "sum_total": 0.0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "std": None,
            "q1": None,
            "q3": None,
            "iqr": None,
            "ci_95": None,
            "ci_99": None,
        }

    s = sum(values)
    mean = s / n
    minv = min(values)
    maxv = max(values)
    ss = sum(x * x for x in values)

    if n > 1:
        var = max(0, (ss - (s * s) / n) / (n - 1))
        std = var**0.5
        se = std / (n**0.5)
        ci95 = 1.96 * se
        ci99 = 2.58 * se
    else:
        std = se = ci95 = ci99 = None

    sorted_values = sorted(values)

    if len(sorted_values) >= 4:
        q1 = stats_module.quantiles(sorted_values, n=4)[0]
        median = stats_module.median(sorted_values)
        q3 = stats_module.quantiles(sorted_values, n=4)[2]
    else:
        n_values = len(sorted_values)
        if n_values % 2 == 0:
            median = (sorted_values[n_values // 2 - 1] + sorted_values[n_values // 2]) / 2
        else:
            median = sorted_values[n_values // 2]

        q1_idx = (n_values - 1) * 0.25
        q3_idx = (n_values - 1) * 0.75

        if q1_idx.is_integer():
            q1 = sorted_values[int(q1_idx)]
        else:
            lower_idx = int(q1_idx)
            upper_idx = min(lower_idx + 1, n_values - 1)
            weight = q1_idx - lower_idx
            q1 = sorted_values[lower_idx] * (1 - weight) + sorted_values[upper_idx] * weight

        if q3_idx.is_integer():
            q3 = sorted_values[int(q3_idx)]
        else:
            lower_idx = int(q3_idx)
            upper_idx = min(lower_idx + 1, n_values - 1)
            weight = q3_idx - lower_idx
            q3 = sorted_values[lower_idx] * (1 - weight) + sorted_values[upper_idx] * weight

    iqr = q3 - q1

    return {
        "count": n,
        "sum_total": s,
        "mean": mean,
        "median": median,
        "min": minv,
        "max": maxv,
        "std": std,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "ci_95": ci95,
        "ci_99": ci99,
    }


def stats_for_scenario(changes, global_filters):
    """Compute descriptive statistics over ``record.total × change.unit`` for
    every ChangeRecord matched by each change in *changes*.

    A record matching multiple changes is counted once *per matching change*
    (so its scaled value appears once for each change's unit). The unit
    defaults to 1.0 for missing / blank / non-numeric / negative inputs,
    which makes a scenario with no explicit units behave equivalently to the
    legacy ``stats_for(build_scenario_query(...))`` pipeline.
    """
    # Lazy import to keep this module import-cycle-safe.
    from minitool.models import ChangeRecord

    scaled_values = []
    for change in changes:
        if not change.get("module_type"):
            continue
        unit = _coerce_unit(change.get("unit"))
        q = _build_single_change_q(change, global_filters)
        totals = ChangeRecord.objects.filter(q).values_list("total", flat=True)
        if unit == 1.0:
            scaled_values.extend(totals)
        else:
            scaled_values.extend(v * unit for v in totals)

    return _descriptive_stats_from_values(scaled_values)
