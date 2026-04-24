"""Extracted compute function for a single minitool module."""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)


def _find_instance_by_name(queryset, name: str) -> Any:
    """Find a model instance in a queryset by its string representation or name attribute.

    Raises ValueError if no match is found.
    """
    for item in queryset:
        if str(item) == name or getattr(item, "name", None) == name:
            return item
    raise ValueError(
        f"Could not find '{name}' in {[str(x) for x in queryset]}"
    )


def _constrain_fields_for_change(
    fields: dict,
    attribute: str,
    from_value: str,
    to_value: str,
) -> tuple[dict, list[tuple[str, str]]]:
    """Constrain a fields dict for a specific attribute change.

    For a change like ``organic_input_type: "Low C input" -> "Medium C input"``:

    * The **changed** pair is fixed: ``_start`` = from-instance, ``_w`` = to-instance.
    * All **other** ``_start``/``_w`` pairs vary together (``_start == _w``).
      Both keys keep the *same* list object so the pairing logic in
      ``compute_permutations`` can zip them into a single axis.

    The returned ``constrained_fields`` dict preserves the *original* key
    ordering of ``fields`` exactly. This is critical because module processors
    unpack the resulting combination tuples positionally -- reordering the
    keys would make every combination decode into the wrong variables.

    Returns
    -------
    constrained_fields : dict
        A *new* dict with the same keys, in the same order, but constrained values.
    paired_keys : list[tuple[str, str]]
        ``(start_key, w_key)`` pairs that must vary together (not crossed).
    """
    constrained: dict = {}
    paired_keys: list[tuple[str, str]] = []

    # _w / _wo / _end keys that have already been placed into `constrained`
    # by their matching _start pair-handler. When we reach these keys in the
    # main iteration we skip them (they are already in the correct position).
    skip_w_keys: set[str] = set()

    for key in fields:
        if key in constrained:
            # Already inserted by a preceding _start pair-handler.
            continue

        if key in skip_w_keys:
            # Defensive: counterpart appears before its _start. The _start
            # will insert both keys when reached.
            continue

        if key.endswith("_start"):
            base_name = key.rsplit("_start", 1)[0]

            # Find the counterpart key (_w, _wo, _end) in `fields`.
            w_key: str | None = None
            for suffix in ("_w", "_wo", "_end"):
                candidate = f"{base_name}{suffix}"
                if candidate in fields:
                    w_key = candidate
                    break

            if w_key is None:
                # Unpaired _start field -- keep as-is.
                constrained[key] = fields[key]
                continue

            skip_w_keys.add(w_key)

            if base_name == attribute:
                # Changed field pair: fix to the specific from/to instances.
                from_instance = _find_instance_by_name(fields[key], from_value)
                to_instance = _find_instance_by_name(fields[w_key], to_value)
                constrained[key] = [from_instance]
                constrained[w_key] = [to_instance]
            else:
                # Other paired field: _start == _w, vary together as one axis.
                start_values = (
                    list(fields[key])
                    if not isinstance(fields[key], list)
                    else fields[key]
                )
                constrained[key] = start_values
                # Same reference -- values will be zipped by compute_permutations.
                constrained[w_key] = start_values
                paired_keys.append((key, w_key))
        else:
            # Non-paired field (e.g. livestock_category_types, fishery_type,
            # land_use_type, waterbody_type, etc.): keep as-is, preserving
            # its original position.
            constrained[key] = fields[key]

    return constrained, paired_keys


def compute_module_slice(
    module_type: str,
    attribute: str | None = None,
    from_value: str | None = None,
    to_value: str | None = None,
    chunk_size: int = 10000,
    max_rows: int = 10000,
    max_workers: int | None = None,
    save_results: bool = True,
    progress_callback=None,
) -> tuple[list[dict], list[dict]]:
    """Compute permutations for a single module type.

    Parameters
    ----------
    module_type:
        Key in MODULE_CONFIGS (e.g. ``"Grassland"``).
    attribute:
        The field base name being changed (e.g. ``"organic_input_type"``).
        When provided together with *from_value* and *to_value*, permutations
        are constrained so that only the changed pair varies independently
        while all other ``_start``/``_w`` pairs are locked together.
    from_value:
        Human-readable name of the starting value for the changed field.
    to_value:
        Human-readable name of the target value for the changed field.
    chunk_size:
        Batch size for processing.
    max_rows:
        Maximum number of rows to process.
    max_workers:
        Maximum number of worker processes.  ``None`` = auto.
    save_results:
        If ``True``, saves results via ``DataManager`` (CSV to GCP/local).

    Returns
    -------
    tuple[list[dict], list[dict]]
        ``(data, errors)`` -- data is list of successful computation dicts,
        errors is list of error dicts.
    """
    from api.minitool import (
        MODULE_CONFIGS,
        ModuleDataBuilderRegistry,
        ProcessorRegistry,
        DataManager,
        PermutationComputer,
    )
    import api.models as models

    if module_type not in MODULE_CONFIGS:
        raise ValueError(
            f"Unknown module_type '{module_type}'. "
            f"Valid: {sorted(MODULE_CONFIGS.keys())}"
        )

    module_config = MODULE_CONFIGS[module_type]
    config_name = module_config.get("config_name", "")

    # Get the Django model class matching the MODULE_CONFIGS key
    model_class = getattr(models, module_type, None)
    if model_class is None:
        raise ValueError(
            f"No model class found for '{module_type}' in api.models"
        )

    # Shallow-copy fields so we never mutate the module-level config
    fields = dict(module_config["fields"])
    paired_keys: list[tuple[str, str]] = []

    if attribute and from_value and to_value:
        fields, paired_keys = _constrain_fields_for_change(
            fields, attribute, from_value, to_value,
        )
        logger.info(
            "Constrained permutations for change: %s (%s -> %s), "
            "%d paired field groups",
            attribute, from_value, to_value, len(paired_keys),
        )

    # Initialize compute components
    data_builder_registry = ModuleDataBuilderRegistry()
    processor_registry = ProcessorRegistry(data_builder_registry)
    permutation_computer = PermutationComputer(processor_registry)

    logger.info("Computing permutations for %s (config: %s)", module_type, config_name)

    data, errors = permutation_computer.compute_permutations(
        fields,
        model_class,
        chunk_size=chunk_size,
        stop_at=max_rows,
        max_workers=max_workers,
        progress_callback=progress_callback,
        paired_keys=paired_keys,
    )

    if save_results and (data or errors):
        data_manager = DataManager()
        data_manager.save_data(data, errors, module_type)

    # Populate ChangeRecord directly from the in-memory permutation
    # results so the scenario UI / Excel export show non-zero counts
    # without a follow-up `import_changes` invocation. Gated behind the
    # same `save_results` flag as the CSV upload so unit tests with
    # save_results=False keep their old behaviour. Crucially this runs
    # *outside* the GCS save_data block above -- a GCS auth failure
    # there falls back to local CSV but must not block the DB import.
    if save_results and data:
        from api.services.minitool_changes_import import import_changes_from_data
        try:
            import_stats = import_changes_from_data(data, module_type)
            logger.info(
                "Imported ChangeRecord rows for %s: %s",
                module_type, import_stats,
            )
        except Exception:
            # Re-raise after logging: the CSV upload already happened so
            # the data isn't lost, but silently swallowing this would
            # reproduce the original bug (empty DB, count=0 / sum=0 in UI).
            logger.exception(
                "Failed to import ChangeRecord rows for %s", module_type,
            )
            raise

    logger.info(
        "Completed %s: %d successful, %d errors",
        module_type, len(data), len(errors),
    )

    if errors:
        # Workers run with logging suppressed at CRITICAL level, so per-error
        # warnings never surface. Summarize the top distinct errors here so
        # users get actionable diagnostics without 48k log lines.
        error_counter: Counter = Counter(
            (err.get("error_type", ""), err.get("error_message", ""))
            for err in errors
        )
        top_errors = error_counter.most_common(3)
        sample_lines = [f"Sample errors for {module_type}:"]
        for (error_type, error_message), count in top_errors:
            sample_lines.append(
                f"  [{count}x] {error_type}: {error_message}"
            )
        logger.warning("\n".join(sample_lines))

    return data, errors
