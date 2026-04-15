"""
Rename EX-ACT country names to FAO official names (Q1).

Usage:
    python manage.py runscript rename_countries
    python manage.py runscript rename_countries --script-args=--apply
    python manage.py runscript rename_countries --script-args=--q3 --script-args=--apply
"""

from django.db import transaction
from django.db.models import ManyToOneRel

from api.models import Country


Q1_RENAMES: list[tuple[str, str]] = [
    ("Bolivia", "Bolivia (Plurinational State of)"),
    ("Channel Islands (U.K)", "Channel Islands"),
    ("China, Hong Kong Special Administrative Region", "China, Hong Kong SAR"),
    ("China, Macao Special Administrative Region", "China, Macao SAR"),
    ("Iran", "Iran (Islamic Republic of)"),
    ("Madeira (Portugal)", "Madeira Islands"),
    ("Netherlands", "Netherlands (Kingdom of the)"),
    ("Turkey", "Türkiye"),
    ("Venezuela", "Venezuela (Bolivarian Republic of)"),
    ("State Of Palestine", "Palestine"),
]


Q3_MERGES: list[tuple[str, str]] = [
    ("Aland Islands", "Åland Islands"),
    ("Cote D'ivoire", "Côte d'Ivoire"),
    ("Taiwan (Chinese Taipei)", "Taiwan"),
]


class _DryRun(Exception):
    """Sentinel raised to roll back the atomic block on dry-run."""


class CountryAction:
    def describe(self) -> str:
        raise NotImplementedError

    def execute(self) -> int:
        raise NotImplementedError


# Future: AggregateAction(sources, target) for Q2, DeleteAction(name) for Q3.


class RenameAction(CountryAction):
    def __init__(self, old: str, new: str):
        self.old = old
        self.new = new

    def describe(self) -> str:
        return f"Rename '{self.old}' -> '{self.new}'"

    def execute(self) -> int:
        src_qs = Country.objects.filter(name=self.old)
        if not src_qs.exists():
            print(f"    skip: source '{self.old}' not found")
            return 0

        target = Country.objects.filter(name=self.new).first()
        if target is not None and not src_qs.filter(pk=target.pk).exists():
            print(f"    skip: target '{self.new}' already exists (id={target.pk})")
            return 0

        return src_qs.update(name=self.new)


class MergeAction(CountryAction):
    def __init__(self, duplicate_name: str, keep_name: str):
        self.duplicate_name = duplicate_name
        self.keep_name = keep_name

    def describe(self) -> str:
        return f"Merge '{self.duplicate_name}' -> '{self.keep_name}'"

    def execute(self) -> int:
        duplicate = Country.objects.filter(name=self.duplicate_name).first()
        if duplicate is None:
            print(f"    skip: duplicate '{self.duplicate_name}' not found")
            return 0

        keep = Country.objects.filter(name=self.keep_name).first()
        if keep is None:
            print(f"    skip: keep '{self.keep_name}' not found")
            return 0

        total_reassigned = 0
        for rel in Country._meta.get_fields():
            if not isinstance(rel, ManyToOneRel):
                continue
            related_model = rel.related_model
            fk_name = rel.field.name
            is_unique = rel.field.unique

            if is_unique:
                deleted = 0
                if related_model.objects.filter(**{fk_name: keep}).exists():
                    deleted, _ = related_model.objects.filter(**{fk_name: duplicate}).delete()
                    reassigned = 0
                else:
                    reassigned = related_model.objects.filter(**{fk_name: duplicate}).update(**{fk_name: keep})
                if reassigned or deleted:
                    msg = f"    {related_model.__name__}.{fk_name}: {reassigned} reassigned"
                    if deleted > 0:
                        msg += f", {deleted} deleted"
                    print(msg)
                total_reassigned += reassigned
            else:
                reassigned = related_model.objects.filter(**{fk_name: duplicate}).update(**{fk_name: keep})
                if reassigned:
                    print(f"    {related_model.__name__}.{fk_name}: {reassigned} reassigned")
                total_reassigned += reassigned

        duplicate.delete()
        return total_reassigned


def run(*args):
    apply = "--apply" in args
    only_q1 = "--q1" in args
    only_q3 = "--q3" in args
    run_q1 = only_q1 or not only_q3
    run_q3 = only_q3 or not only_q1

    try:
        with transaction.atomic():
            if run_q1:
                print("Q1: renames")
                for action in [RenameAction(o, n) for o, n in Q1_RENAMES]:
                    n = action.execute()
                    print(f"  {action.describe()}: {n} row(s)")
            if run_q3:
                print("Q3: merges")
                for action in [MergeAction(o, n) for o, n in Q3_MERGES]:
                    n = action.execute()
                    print(f"  {action.describe()}: {n} row(s)")
            if not apply:
                raise _DryRun()
    except _DryRun:
        print("\nDRY RUN — no changes committed. Re-run with --apply to persist.")
    else:
        print("\nApplied.")
