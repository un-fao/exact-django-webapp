import logging as log
from django.apps import apps
from django.db.models import F
from api import models, results_cache


def cycle_all_modules_and_invalidate_cached_results():
    """
    Cycle all modules and invalidate cached results
    """
    for module_type in models.ModuleType.objects.all():
        log.debug(f"{'-' * 50}")
        log.debug(f"Invalidating cached results for {module_type.class_name}")
        try:
            ModuleClass: models.Module = apps.get_model("api", module_type.class_name)
            if issubclass(ModuleClass, models.CachedResultMixin):
                modules = ModuleClass.objects.all()
                if issubclass(ModuleClass, models.Submodule):
                    modules = ModuleClass.objects.filter(parent__activity__project__is_finalized=False)
                    log.debug(f"Skipping {ModuleClass.objects.filter(parent__activity__project__is_finalized=True).count():,} finalized modules")
                else:
                    modules = ModuleClass.objects.filter(activity__project__is_finalized=False)
                    log.debug(f"Skipping {ModuleClass.objects.filter(activity__project__is_finalized=True).count():,} finalized modules")

                modules.update(
                    updated_at=None,
                    last_cached_at=None,
                    cached_results_total=None,
                    cached_results_by_activity=None,
                    cached_results_by_gas=None,
                    cached_results_by_activity_by_gas=None,
                    last_modified=None,
                )

            log.debug(f"Invalidated {modules.count():,} modules")
        except LookupError:
            log.error(f"Could not find module class for {module_type}")

        log.debug(f"{'-' * 50}\n\n")


def invalidate_project_result_caches():
    """Clear the project-level results cache (ProjectResultCache) and bump the stamp
    for every non-finalized project, mirroring the finalized carve-out already used by
    cycle_all_modules_and_invalidate_cached_results above.

    This is the D3a manual invalidation lever: it does not know why a project's numbers
    might be stale (a reference-data reload, a bug fix, an ops decision), only that the
    project-level cache and the module-level cache should be treated the same way here.
    """
    dirty_projects = models.Project.objects.filter(is_finalized=False)
    count = dirty_projects.count()

    results_cache.clear_for_projects(dirty_projects)
    dirty_projects.update(results_stamp=F("results_stamp") + 1)

    log.debug(f"Cleared project result caches and bumped results_stamp for {count:,} projects")


def run():
    cycle_all_modules_and_invalidate_cached_results()
    invalidate_project_result_caches()
