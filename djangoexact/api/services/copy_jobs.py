"""Worker handler for async project copy: populate a pre-created shell project."""
from django.db import transaction

from api import utilities as utils
from api.models import AsyncJob, Project


def run(job: AsyncJob) -> dict:
    params = job.params
    source = Project.objects.get(pk=params["source_project_id"])
    target = Project.objects.get(pk=params["target_project_id"])
    with transaction.atomic():
        utils.copy_activities_into(source, target, job.created_by)
    return {"new_project_id": target.pk}
