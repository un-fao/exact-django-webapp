from django.db import migrations, models
from django.db.models import Count


def collapse_duplicate_memberships(apps, schema_editor):
    """Keep one membership per (user, project): Admin if any, else the group with the most
    permissions, ties broken by the lowest id. Group names other than Admin live only in the
    database, so permission count stands in for "highest role"."""
    ProjectMembership = apps.get_model("api", "ProjectMembership")

    duplicated = (
        ProjectMembership.objects.values("user_id", "project_id").annotate(n=Count("id")).filter(n__gt=1)
    )
    for pair in duplicated:
        rows = (
            ProjectMembership.objects.filter(user_id=pair["user_id"], project_id=pair["project_id"])
            .annotate(perm_count=Count("group__permissions"))
            .select_related("group")
        )
        keep = min(rows, key=lambda m: (m.group.name != "Admin", -m.perm_count, m.id))
        ProjectMembership.objects.filter(user_id=pair["user_id"], project_id=pair["project_id"]).exclude(pk=keep.pk).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0295_project_guided_step"),
    ]

    operations = [
        migrations.RunPython(collapse_duplicate_memberships, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="projectmembership",
            constraint=models.UniqueConstraint(fields=("user", "project"), name="unique_project_membership"),
        ),
    ]
