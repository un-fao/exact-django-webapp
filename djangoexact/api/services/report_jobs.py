"""Worker handler for async report generation.

Reproduces ProjectViewSet.template()/report() off-request: compute the
ProjectResult, render (PDF via WeasyPrint or Excel), and upload the bytes to GCS.
The result dict points the download endpoint at the stored object.
"""
import io

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import activate

from api.models import AsyncJob, Project
from api.reports import catalog, compute_project_result, generate_excel_report
from api.reports.narrative import clean_content
from api.reports.html_context import build_template_context
from api.reports.pdf import render_pdf


def run(job: AsyncJob) -> dict:
    params = job.params
    project = Project.objects.get(pk=params["project_id"])

    activity_ids = params.get("activity_ids")
    activities = None
    if activity_ids:
        activities = list(project.activities.filter(pk__in=activity_ids))

    fmt = params.get("format", "pdf")
    lang = params.get("lang", "en")
    activate(lang)

    if fmt == "pdf":
        template_name = params["template"]
        content = _render_pdf(
            project, activities, template_name, lang, job.created_by,
            content=params.get("content"), additional_sources=params.get("additional_sources"),
        )
        content_type = "application/pdf"
        ext = "pdf"
        filename = catalog.report_filename(project.name, template_name)
    else:
        buffer = generate_excel_report(project, activities)
        content = buffer.getvalue() if isinstance(buffer, io.BytesIO) else buffer
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
        filename = catalog.report_filename(project.name, None)

    gcs_path = _upload(project, job, content, ext)
    return {
        "gcs_path": gcs_path,
        "filename": filename,
        "content_type": content_type,
    }


def _render_pdf(project, activities, template_name, lang, user, content=None, additional_sources=None):
    # Resolved here as well as at enqueue, because jobs persisted before the
    # catalog existed can still be replayed; first, so an unrenderable report
    # fails before a carbon balance is computed for it.
    template_path = catalog.resolve_template(template_name, lang)
    # Sanitized again although the view already did: params are stored JSON,
    # and a row edited or replayed after enqueue must not reach the page as
    # trusted markup.
    if content:
        content = clean_content(content)
    if additional_sources:
        additional_sources = clean_content(additional_sources, "additional_sources")
    result = compute_project_result(project, activities)
    context = build_template_context(
        result, None, lang, content=content, additional_sources=additional_sources,
    )
    context["user"] = user
    html = render_to_string(template_path, context)
    return render_pdf(html)


def _upload(project, job, content, ext):
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(settings.STORAGE_BUCKET)
    blob_path = f"reports/{project.pk}/{job.pk}.{ext}"
    blob = bucket.blob(blob_path)
    blob.upload_from_string(content, content_type="application/octet-stream")
    return blob_path
