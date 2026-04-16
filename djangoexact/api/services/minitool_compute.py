"""Extracted compute function for a single minitool module."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def compute_module_slice(
    module_type: str,
    chunk_size: int = 10000,
    max_rows: int = 10000,
    max_workers: int | None = None,
    save_results: bool = True,
) -> tuple[list[dict], list[dict]]:
    """Compute permutations for a single module type.

    Parameters
    ----------
    module_type:
        Key in MODULE_CONFIGS (e.g. "Grassland").
    chunk_size:
        Batch size for processing.
    max_rows:
        Maximum number of rows to process.
    max_workers:
        Maximum number of worker processes. None = auto.
    save_results:
        If True, saves results via DataManager (CSV to GCP/local).

    Returns
    -------
    tuple[list[dict], list[dict]]
        (data, errors) — data is list of successful computation dicts,
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

    # Initialize compute components
    data_builder_registry = ModuleDataBuilderRegistry()
    processor_registry = ProcessorRegistry(data_builder_registry)
    permutation_computer = PermutationComputer(processor_registry)

    logger.info("Computing permutations for %s (config: %s)", module_type, config_name)

    data, errors = permutation_computer.compute_permutations(
        module_config["fields"],
        model_class,
        chunk_size=chunk_size,
        stop_at=max_rows,
        max_workers=max_workers,
    )

    if save_results and (data or errors):
        data_manager = DataManager()
        data_manager.save_data(data, errors, module_type)

    logger.info(
        "Completed %s: %d successful, %d errors",
        module_type, len(data), len(errors),
    )

    return data, errors
