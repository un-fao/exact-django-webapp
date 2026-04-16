"""
Catalog module for admin scripts.

Provides dataclasses and utilities for loading, parsing, and validating
YAML-based catalog definitions against the minitool MODULE_CONFIGS registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml


class ValidationError(Exception):
    """Custom exception raised for catalog validation errors."""

    pass


@dataclass
class CatalogField:
    """Represents a single field within a catalog module definition."""

    field_name: str
    label: str
    value_source: dict

    @classmethod
    def from_dict(cls, data: dict) -> CatalogField:
        """Build a CatalogField from a raw dictionary.

        Parameters
        ----------
        data:
            Dictionary that must contain ``field_name`` and optionally
            ``label`` and ``value_source``.

        Raises
        ------
        KeyError
            If ``field_name`` is missing from *data*.
        """
        return cls(
            field_name=data["field_name"],
            label=data.get("label", ""),
            value_source=data.get("value_source", {}),
        )


@dataclass
class CatalogModule:
    """Represents a module entry inside a catalog YAML file."""

    module_type: str
    label: str
    config_name: str
    fields: list[CatalogField] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> CatalogModule:
        """Build a CatalogModule from a raw dictionary.

        Parameters
        ----------
        data:
            Dictionary that must contain ``module_type``, and optionally
            ``label``, ``config_name``, and ``fields`` (list of dicts).
        """
        raw_fields = data.get("fields", [])
        return cls(
            module_type=data.get("module_type", ""),
            label=data.get("label", ""),
            config_name=data.get("config_name", ""),
            fields=[CatalogField.from_dict(f) for f in raw_fields],
        )


def load_catalog(path: str) -> list[CatalogModule]:
    """Load a catalog definition from a YAML file.

    Parameters
    ----------
    path:
        Filesystem path to the YAML catalog file.

    Returns
    -------
    list[CatalogModule]
        Parsed catalog modules.

    Raises
    ------
    ValidationError
        If the file is empty / parses to a falsy value, or if the parsed
        document does not contain a ``modules`` key.
    """
    with open(path, "r") as fh:
        data = yaml.safe_load(fh)

    if not data:
        raise ValidationError(
            f"Catalog file is empty or could not be parsed: {path}"
        )

    if "modules" not in data:
        raise ValidationError(
            f"Catalog file is missing the 'modules' key: {path}"
        )

    return [CatalogModule.from_dict(m) for m in data["modules"]]


def validate_catalog(modules: list[CatalogModule]) -> list[str]:
    """Validate catalog modules against the minitool MODULE_CONFIGS registry.

    For every module the function checks:
    1. ``module_type`` exists as a top-level key in ``MODULE_CONFIGS``.
    2. Each field's ``field_name`` maps to an entry in the config's
       ``fields`` dict -- either as ``<field_name>_start`` **or** as the
       literal ``<field_name>`` (some fields like ``forest_type`` do not
       follow the ``_start`` / ``_w`` naming convention).

    The import of ``MODULE_CONFIGS`` is performed lazily inside this
    function to avoid circular-import issues at module load time.

    Parameters
    ----------
    modules:
        List of ``CatalogModule`` instances to validate.

    Returns
    -------
    list[str]
        A list of human-readable error strings.  An empty list means the
        catalog is valid.
    """
    # Lazy import to prevent circular dependencies at module level.
    from api.minitool import MODULE_CONFIGS

    errors: list[str] = []

    for module in modules:
        if module.module_type not in MODULE_CONFIGS:
            errors.append(
                f"Unknown module_type '{module.module_type}'. "
                f"Valid types: {sorted(MODULE_CONFIGS.keys())}"
            )
            continue

        config_fields = MODULE_CONFIGS[module.module_type]["fields"]

        for catalog_field in module.fields:
            name = catalog_field.field_name
            start_name = f"{name}_start"

            if start_name not in config_fields and name not in config_fields:
                errors.append(
                    f"Module '{module.module_type}': field '{name}' not found "
                    f"in MODULE_CONFIGS (checked '{start_name}' and '{name}'). "
                    f"Available fields: {sorted(config_fields.keys())}"
                )

    return errors


_catalog_cache = None


def get_catalog():
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache
    from pathlib import Path
    catalog_path = Path(__file__).resolve().parent / "scenario_catalog.yaml"
    _catalog_cache = load_catalog(str(catalog_path))
    return _catalog_cache
