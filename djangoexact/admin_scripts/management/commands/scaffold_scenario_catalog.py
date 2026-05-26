"""Management command to generate a starter scenario_catalog.yaml from MODULE_CONFIGS."""

from __future__ import annotations

import re

import yaml
from django.core.management.base import BaseCommand


def _humanize_label(module_type: str) -> str:
    """Insert spaces before uppercase letters to create a human-readable label.

    Example: ``"AnnualCropland"`` becomes ``"Annual Cropland"``.
    """
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", module_type)


def _determine_value_source(value: object) -> dict:
    """Inspect a field value from MODULE_CONFIGS and return its value_source dict.

    Handles three cases:
    - Python list  -> ``{"kind": "static", "values": <list>}``
    - QuerySet     -> ``{"kind": "queryset", "model": <model name>}``
    - Model instance -> ``{"kind": "queryset", "model": <model name>}``
    """
    if isinstance(value, list):
        return {"kind": "static", "values": value}

    # QuerySet: has a .model attribute
    if hasattr(value, "model"):
        return {"kind": "queryset", "model": value.model.__name__}

    # Model instance: Django models expose _meta on their class
    if hasattr(type(value), "_meta"):
        return {"kind": "queryset", "model": type(value).__name__}

    # Fallback for mock objects where type(value).__name__ gives a model name
    return {"kind": "queryset", "model": type(value).__name__}


class Command(BaseCommand):
    help = "Generate a starter scenario_catalog.yaml from MODULE_CONFIGS"

    def handle(self, *args, **options):
        from api.minitool import MODULE_CONFIGS

        seen_config_names: set[str] = set()
        modules: list[dict] = []

        for module_type, config in MODULE_CONFIGS.items():
            config_name = config.get("config_name", "")

            # Deduplicate by config_name (e.g. CoastalWetland2 shares
            # config_name "coastal_wetland" with CoastalWetland).
            if config_name in seen_config_names:
                continue
            seen_config_names.add(config_name)

            raw_fields = config.get("fields", {})

            # Group field keys by stripping _start / _w suffixes.
            # Maintain insertion order via dict.
            unique_fields: dict[str, object] = {}
            for key, value in raw_fields.items():
                if key.endswith("_start"):
                    base = key[: -len("_start")]
                    if base not in unique_fields:
                        unique_fields[base] = value
                elif key.endswith("_w"):
                    base = key[: -len("_w")]
                    if base not in unique_fields:
                        # Use _w value only when we haven't seen _start yet
                        unique_fields[base] = value
                else:
                    # Non-suffixed field
                    if key not in unique_fields:
                        unique_fields[key] = value

            fields: list[dict] = []
            for field_name, value in unique_fields.items():
                value_source = _determine_value_source(value)
                fields.append(
                    {
                        "field_name": field_name,
                        "label": field_name.replace("_", " ").title(),
                        "value_source": value_source,
                    }
                )

            modules.append(
                {
                    "module_type": module_type,
                    "label": _humanize_label(module_type),
                    "config_name": config_name,
                    "fields": fields,
                }
            )

        output = yaml.dump(
            {"modules": modules},
            default_flow_style=False,
            sort_keys=False,
        )
        self.stdout.write(output)
