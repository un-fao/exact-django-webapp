from django.test import TestCase

from api.models import AsyncJob


class AsyncJobModelTestCase(TestCase):
    def test_defaults(self):
        job = AsyncJob.objects.create(kind=AsyncJob.Kind.REPORT, params={"project_id": 1})
        self.assertEqual(job.status, AsyncJob.Status.PENDING)
        self.assertEqual(job.progress, 0)
        self.assertEqual(job.result, {})
        self.assertEqual(job.error_message, "")
        self.assertIsNone(job.started_at)
        self.assertIsNotNone(job.created_at)

    def test_kind_choices(self):
        self.assertEqual(AsyncJob.Kind.PROJECT_COPY.value, "project_copy")
        self.assertEqual(AsyncJob.Kind.REPORT.value, "report")
