from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import Project
from api.services.finalization import FinalizationError, restore_frozen_results


class Command(BaseCommand):
    help = (
        "Freeze the results of projects finalized before frozen results existed, as they stood at "
        "finalized_at: live cache written before finalization, else module history, else a "
        "calculation now (marked frozen_retroactively). Re-runnable: modules already frozen for "
        "the current finalization are skipped. Dry run by default."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the snapshots. Without it, only report what would happen.")
        parser.add_argument("--project", type=int, action="append", help="Limit to this project id (repeatable).")

    def handle(self, *args, **options):
        dry_run = not options["apply"]
        projects = Project.objects.filter(is_finalized=True).order_by("pk")
        if options["project"]:
            projects = projects.filter(pk__in=options["project"])

        undated = list(projects.filter(finalized_at__isnull=True).values_list("pk", flat=True))
        if undated:
            # Without a finalization date there is no "as it stood" to restore; these need a
            # human decision (set finalized_at by hand, then re-run).
            self.stderr.write(f"Skipping {len(undated)} finalized project(s) with no finalized_at in history: {undated}")

        totals = Counter()
        failed = []
        for project in projects.filter(finalized_at__isnull=False):
            try:
                with transaction.atomic():
                    counts = restore_frozen_results(project, dry_run=dry_run)
            except FinalizationError as e:
                failed.append(project.pk)
                self.stderr.write(f"Project {project.pk}: {e}")
                continue
            totals.update(counts)
            if counts:
                summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
                self.stdout.write(f"Project {project.pk} (finalized {project.finalized_at:%Y-%m-%d %H:%M}): {summary}")

        mode = "DRY RUN, nothing written" if dry_run else "applied"
        self.stdout.write(f"Totals ({mode}): " + (", ".join(f"{k}={v}" for k, v in sorted(totals.items())) or "nothing to do"))
        if failed:
            raise CommandError(f"{len(failed)} project(s) could not be frozen: {failed}")
