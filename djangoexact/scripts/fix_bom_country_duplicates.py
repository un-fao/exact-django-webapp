"""
Fix Country rows whose name is prepended with a UTF-8 BOM (U+FEFF).

A CSV import left some Country rows with a byte-order-mark character at the
start of their `name`. These rows shadow the clean counterpart: stripping the
BOM directly hits the unique-name constraint because the clean row already
exists. This script resolves the collision by repointing every FK pointing at
the BOM row to the clean row, then deleting the BOM row. If no clean
counterpart exists, it strips the BOM in place.

Usage:
    python manage.py runscript fix_bom_country_duplicates
    python manage.py runscript fix_bom_country_duplicates --script-args=--apply
"""

from django.db import transaction
from django.db.models import ManyToOneRel

from api.models import Country


BOM = "\ufeff"


class _DryRun(Exception):
    """Sentinel raised to roll back the atomic block on dry-run."""


def _repoint_and_delete(dirty: Country, clean: Country) -> int:
    """Move every FK from `dirty` to `clean`, then delete `dirty`. Returns total rows touched."""
    total = 0
    for rel in Country._meta.get_fields():
        if not isinstance(rel, ManyToOneRel):
            continue
        related_model = rel.related_model
        fk_name = rel.field.name
        is_unique = rel.field.unique

        if is_unique:
            # unique FK: can't blindly update; delete dirty's row if clean already has one,
            # otherwise repoint.
            deleted = 0
            if related_model.objects.filter(**{fk_name: clean}).exists():
                deleted, _ = related_model.objects.filter(**{fk_name: dirty}).delete()
                reassigned = 0
            else:
                reassigned = related_model.objects.filter(**{fk_name: dirty}).update(**{fk_name: clean})
            if reassigned or deleted:
                msg = f"    {related_model.__name__}.{fk_name}: {reassigned} reassigned"
                if deleted:
                    msg += f", {deleted} deleted"
                print(msg)
            total += reassigned
        else:
            reassigned = related_model.objects.filter(**{fk_name: dirty}).update(**{fk_name: clean})
            if reassigned:
                print(f"    {related_model.__name__}.{fk_name}: {reassigned} reassigned")
            total += reassigned

    dirty.delete()
    return total


def run(*args):
    apply = "--apply" in args

    dirty_rows = list(Country.objects.filter(name__startswith=BOM).order_by("pk"))
    if not dirty_rows:
        print("No Country rows with BOM prefix found. Nothing to do.")
        return

    print(f"Found {len(dirty_rows)} Country row(s) with BOM prefix:")
    for c in dirty_rows:
        print(f"  pk={c.pk} name={c.name!r}")

    try:
        with transaction.atomic():
            for dirty in dirty_rows:
                clean_name = dirty.name.lstrip(BOM)
                clean = Country.objects.filter(name=clean_name).exclude(pk=dirty.pk).first()

                if clean is None:
                    print(f"\npk={dirty.pk}: no clean counterpart; stripping BOM in place")
                    dirty.name = clean_name
                    dirty.save()
                else:
                    print(f"\npk={dirty.pk} -> merging into pk={clean.pk} (name={clean_name!r})")
                    touched = _repoint_and_delete(dirty, clean)
                    print(f"  total FK rows reassigned: {touched}")

            if not apply:
                raise _DryRun()
    except _DryRun:
        print("\nDRY RUN — no changes committed. Re-run with --script-args=--apply to persist.")
    else:
        print("\nApplied.")
