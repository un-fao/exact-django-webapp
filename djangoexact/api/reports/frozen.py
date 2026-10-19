"""Report data of finalized projects: capture, (de)serialization and lookup.

A finalized project's report must show the parameters (defaults, emission factors, reference
names, tier 2 overrides, shadow prices, indicators) it showed when it was finalized. The report
intermediate model is therefore captured per language at finalization and stored in
``FinalizedReportData``; for a finalized project the report pipeline reads it instead of
computing it. Renderers stay live, so layout and translation fixes still apply.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from decimal import Decimal

import numpy as np
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils import translation
from django.utils.functional import Promise

from .data_types import InventoryItem, MetadataWrite, ModuleResult, ResultRow, T2Override

log = logging.getLogger("console")

SCHEMA_VERSION = 1
LANGUAGES = [code for code, _name in settings.LANGUAGES]
FALLBACK_LANGUAGE = "en"


class _Encoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Promise):
            return str(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, Decimal):
            return float(o)  # Excel cells must stay numeric
        # Anything else would render differently once decoded, so refuse it at freeze time.
        return super().default(o)


def _plain(value):
    return json.loads(json.dumps(value, cls=_Encoder))


def current_language() -> str:
    return (translation.get_language() or settings.LANGUAGE_CODE).split("-")[0].lower()


def module_result_to_json(result: ModuleResult) -> dict:
    return _plain({
        "title": result.title,
        "metadata_section_title": result.metadata_section_title,
        "result_rows": [asdict(row) for row in result.result_rows],
        "metadata_writes": [asdict(write) for write in result.metadata_writes],
        "additional_indicator_rows_w": [[label, list(values)] for label, values in result.additional_indicator_rows_w],
        "additional_indicator_rows_wo": [[label, list(values)] for label, values in result.additional_indicator_rows_wo],
        "total_emissions": list(result.total_emissions),
        "units_breakdown_w": list(result.units_breakdown_w),
        "units_breakdown_wo": list(result.units_breakdown_wo),
        "units_heads_w": list(result.units_heads_w),
        "units_catch_w": list(result.units_catch_w),
        "is_with": result.is_with,
        "is_without": result.is_without,
        "inventory_items": [asdict(item) for item in result._inventory_items],
    })


def module_result_from_json(data: dict) -> ModuleResult:
    return ModuleResult(
        title=data["title"],
        metadata_section_title=data["metadata_section_title"],
        result_rows=[ResultRow(**row) for row in data["result_rows"]],
        metadata_writes=[MetadataWrite(**write) for write in data["metadata_writes"]],
        additional_indicator_rows_w=[(label, values) for label, values in data["additional_indicator_rows_w"]],
        additional_indicator_rows_wo=[(label, values) for label, values in data["additional_indicator_rows_wo"]],
        total_emissions=data["total_emissions"],
        units_breakdown_w=data["units_breakdown_w"],
        units_breakdown_wo=data["units_breakdown_wo"],
        units_heads_w=data["units_heads_w"],
        units_catch_w=data["units_catch_w"],
        is_with=data["is_with"],
        is_without=data["is_without"],
        _inventory_items=[InventoryItem(**item) for item in data["inventory_items"]],
    )


@dataclass
class CapturedReportData:
    modules: dict  # (model class, pk) -> {lang: module result json}
    activities: dict  # activity pk -> {lang: {"t2_overrides": [...]}}
    project: dict  # {"shadow_prices": [[year, min, max], ...], "indicators": {lang: {...}}}


def capture_report_data(project) -> CapturedReportData:
    """Compute the report intermediate model of a project in every language.

    Runs the live report path (with emissions already read from the frozen results), so it must
    be called after the results snapshot exists. Raises NotReadyError like a report would.
    """
    import ipcc.models as ipcc_models

    from .base import BaseActivityReport, BaseProjectReport
    from .html_context import _compute_indicator_aggregates

    modules, activities, indicators_by_lang = {}, {}, {}
    for lang in LANGUAGES:
        with translation.override(lang):
            project_report = BaseProjectReport(project, use_frozen=False)
            activities_by_name = {}
            for activity in project_report.activities:
                activity.cache_modules()
                activities_by_name[activity.name] = activity
                result = BaseActivityReport(project_report, activity).compute()
                for module_report, module_result in zip(result._module_reports, result.module_results):
                    key = (module_report.module.__class__, module_report.module.pk)
                    modules.setdefault(key, {})[lang] = module_result_to_json(module_result)
                activities.setdefault(activity.pk, {})[lang] = _plain({"t2_overrides": [asdict(o) for o in result.t2_overrides]})

            indicators = _compute_indicator_aggregates(activities_by_name, project)
            soc = indicators.pop("soc")
            indicators["soc"] = soc.value if soc is not None else None
            indicators_by_lang[lang] = _plain(indicators)

    shadow_prices = [[sp.year, sp.min_value, sp.max_value] for sp in ipcc_models.ShadowPriceOfCarbon.objects.order_by("pk")]
    return CapturedReportData(
        modules=modules,
        activities=activities,
        project=_plain({"shadow_prices": shadow_prices, "indicators": indicators_by_lang}),
    )


def report_data_rows(project, captured: CapturedReportData, *, source: str, app_version: str | None) -> list:
    from api.models import Activity, FinalizedReportData, Project

    def row(model, pk, payload):
        return FinalizedReportData(
            project=project,
            finalized_at=project.finalized_at,
            content_type=ContentType.objects.get_for_model(model),
            object_id=pk,
            data={"schema": SCHEMA_VERSION, **payload},
            app_version=app_version,
            source=source,
        )

    rows = [row(model, pk, {"langs": langs}) for (model, pk), langs in captured.modules.items()]
    rows += [row(Activity, pk, {"langs": langs}) for pk, langs in captured.activities.items()]
    rows.append(row(Project, project.pk, captured.project))
    return rows


class FrozenReport:
    """Read side: the frozen report data of a finalized project, in the active language."""

    def __init__(self, project):
        from api.models import Activity, FinalizedReportData, Project

        self._project_pk = project.pk
        self._project_ct = ContentType.objects.get_for_model(Project).pk
        self._activity_ct = ContentType.objects.get_for_model(Activity).pk
        self._rows = {}
        for content_type_id, object_id, data in FinalizedReportData.objects.filter(
            project=project, finalized_at=project.finalized_at
        ).values_list("content_type_id", "object_id", "data"):
            if data.get("schema") != SCHEMA_VERSION:
                raise ValueError(f"Frozen report data schema {data.get('schema')} is not supported by this version")
            self._rows[(content_type_id, object_id)] = data

    def _get(self, content_type_id, object_id, what):
        from .base import NotReadyError

        data = self._rows.get((content_type_id, object_id))
        if data is None:
            log.error(f"Finalized project {self._project_pk} has no frozen report data for {what}")
            raise NotReadyError(
                f"The frozen report data of {what} is missing. It will not be recalculated because the project is "
                "finalized; please contact support."
            )
        return data

    @staticmethod
    def _in_language(langs: dict):
        lang = current_language()
        if lang not in langs:
            # A language added after this project was finalized: show the frozen values, in English.
            log.warning(f"No frozen report data in '{lang}', falling back to '{FALLBACK_LANGUAGE}'")
            lang = FALLBACK_LANGUAGE
        return langs[lang]

    def module_result(self, module) -> ModuleResult:
        content_type_id = ContentType.objects.get_for_model(module.__class__).pk
        data = self._get(content_type_id, module.pk, f"{module.module_type.name} in activity {module.activity.name}")
        return module_result_from_json(self._in_language(data["langs"]))

    def t2_overrides(self, activity) -> list[T2Override]:
        data = self._get(self._activity_ct, activity.pk, f"activity {activity.name}")
        return [T2Override(**o) for o in self._in_language(data["langs"])["t2_overrides"]]

    def shadow_prices(self) -> list:
        import ipcc.models as ipcc_models

        # Unsaved instances: the shadow price table and the renderers read year/min_value/max_value.
        data = self._get(self._project_ct, self._project_pk, "the project")
        return [
            ipcc_models.ShadowPriceOfCarbon(year=year, min_value=min_value, max_value=max_value)
            for year, min_value, max_value in data["shadow_prices"]
        ]

    def indicators(self) -> dict:
        return self._in_language(self._get(self._project_ct, self._project_pk, "the project")["indicators"])
