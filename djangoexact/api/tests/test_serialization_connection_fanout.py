"""Regression tests for the DB-connection fan-out in the request-path endpoints.

Django database connections are thread-local and CONN_MAX_AGE is 0, so every
thread-pool worker that touches the ORM opens its own Postgres connection, and
a wide per-request pool can burst past the App Engine instance-local Cloud SQL
socket's per-instance connection ceiling ("Connection refused" for whichever
request connects next). api/concurrency.py bounds that fan-out; these tests
guard it:

- ThreadPoolBoundsStaticTests fails if any request-path module constructs a
  ThreadPoolExecutor directly instead of going through api/concurrency.py, so
  a pool added to an endpoint these tests never exercise is still caught.
- BoundedThreadMapTests pins the helper's contract: input ordering, the worker
  ceiling, one connection released per worker, and which exception surfaces.
- DefaultLanguageTests and the Accept-Language test pin the response bytes:
  worker threads never inherit the active language, so fanned-out responses
  have always rendered modeltranslation fields in settings.LANGUAGE_CODE, and
  moving work onto the request thread must not start honouring Accept-Language.
- SerializationWorkerBudgetTests pins the configured width against the
  documented App Engine Standard ceiling of 100 concurrent Cloud SQL
  connections per instance.

The classes that need no database are plain unittest.TestCase so they can be run
in a sandbox without Postgres; Django's test runner still collects them.
"""

import ast
import pathlib
import threading
import time
import unittest
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Permission
from django.utils import translation
from rest_framework.test import APITestCase

from api import concurrency
from api import serializers as api_serializers
from api import views
from api.models import Climate, Country, Group, ProjectMembership
from api.tests.factories import ProjectFactory, UserFactory

CONCURRENCY_PATH = pathlib.Path(concurrency.__file__).with_suffix(".py")

# Every module that builds a response on a request thread. A ThreadPoolExecutor
# here costs Postgres connections on the serving instance.
REQUEST_PATH_MODULES = [
    pathlib.Path(views.__file__).with_suffix(".py"),
    pathlib.Path(views.__file__).parent.parent / "public" / "views.py",
]

# app.yaml runs `gunicorn -w 4`, and deploy/Dockerfile.web_service defaults to
# the same via ${GUNICORN_WORKERS:-4}.
#
# This models App Engine, where a gunicorn worker serves one request at a time.
# deploy/cloudrun-service.yaml templates containerConcurrency, and on Cloud Run
# with concurrency greater than 1 a single worker serves several requests at
# once, so the figure below understates the peak there.
GUNICORN_WORKERS_PER_INSTANCE = 4

# Documented App Engine Standard ceiling on concurrent Cloud SQL connections
# from a single instance.
APP_ENGINE_CONNECTION_CAP = 100


def worst_case_connections_per_instance(max_workers):
    """One connection for the request plus one per worker, on every gunicorn worker."""
    return GUNICORN_WORKERS_PER_INSTANCE * (1 + max_workers)


class SerializationWorkerBudgetTests(unittest.TestCase):
    """The pool width is a per-instance connection cost, not just a concurrency knob."""

    def test_configured_width_stays_under_the_app_engine_cap(self):
        self.assertLess(
            worst_case_connections_per_instance(concurrency.SERIALIZATION_MAX_WORKERS),
            APP_ENGINE_CONNECTION_CAP,
        )

    def test_budget_formula_rejects_a_bare_executor_default(self):
        """A bare ThreadPoolExecutor() resolves to min(32, os.cpu_count() + 4);
        at the 32-worker end that is 4 * 33 = 132 connections per instance, past
        the cap on one endpoint alone. If this ever passes, the budget formula
        has been weakened and the guard above is meaningless.
        """
        self.assertGreater(worst_case_connections_per_instance(32), APP_ENGINE_CONNECTION_CAP)

    def test_boundary_between_the_widest_legal_and_first_illegal_width(self):
        """Off-by-one neighbours around the cap: 23 fits (96), 24 does not (100)."""
        self.assertLess(worst_case_connections_per_instance(23), APP_ENGINE_CONNECTION_CAP)
        self.assertGreaterEqual(worst_case_connections_per_instance(24), APP_ENGINE_CONNECTION_CAP)


class ThreadPoolBoundsStaticTests(unittest.TestCase):
    """No request-path module may build its own ThreadPoolExecutor.

    Static rather than behavioural so it also covers endpoints these tests do
    not exercise, including all of public/views.py.
    """

    @staticmethod
    def executor_calls(path):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name == "ThreadPoolExecutor":
                yield node

    def test_the_modules_under_guard_exist(self):
        """Keeps the assertions below from passing vacuously on a bad path."""
        for path in REQUEST_PATH_MODULES + [CONCURRENCY_PATH]:
            self.assertTrue(path.is_file(), f"{path} is missing, so this guard is not checking anything")

    def test_request_path_modules_do_not_build_their_own_pools(self):
        offenders = []
        for path in REQUEST_PATH_MODULES:
            offenders.extend(f"{path.name}:{node.lineno}" for node in self.executor_calls(path))
        self.assertEqual(
            offenders,
            [],
            f"ThreadPoolExecutor constructed directly at {offenders}. Every worker opens its own "
            "Postgres connection; route the fan-out through api.concurrency.map_in_bounded_threads "
            "so the per-instance budget stays in one place.",
        )

    def test_the_helpers_own_pool_declares_a_bound(self):
        pools = list(self.executor_calls(CONCURRENCY_PATH))
        self.assertEqual(len(pools), 1, "api/concurrency.py should own exactly one pool")
        self.assertTrue(
            any(keyword.arg == "max_workers" for keyword in pools[0].keywords),
            "api/concurrency.py built a ThreadPoolExecutor without max_workers, which defaults to "
            "min(32, os.cpu_count() + 4). That is the original defect.",
        )


class BoundedThreadMapTests(unittest.TestCase):
    """The contract map_in_bounded_threads has to honour for the call sites."""

    def test_results_come_back_in_input_order_not_completion_order(self):
        """The slowest item is first, so completion order is the reverse of input order."""

        def slow_for_early_items(item):
            time.sleep(0.02 * (5 - item))
            return item

        self.assertEqual(
            concurrency.map_in_bounded_threads(slow_for_early_items, range(5)),
            [0, 1, 2, 3, 4],
        )

    def test_empty_input_does_not_start_a_pool(self):
        with mock.patch.object(concurrency, "ThreadPoolExecutor") as pool:
            self.assertEqual(concurrency.map_in_bounded_threads(lambda item: item, []), [])
        pool.assert_not_called()

    def test_never_uses_more_threads_than_the_configured_bound(self):
        seen = set()
        barrier_lock = threading.Lock()

        def record(item):
            with barrier_lock:
                seen.add(threading.get_ident())
            time.sleep(0.01)
            return item

        concurrency.map_in_bounded_threads(record, range(40))
        self.assertLessEqual(len(seen), concurrency.SERIALIZATION_MAX_WORKERS)

    def test_worker_count_never_exceeds_the_item_count(self):
        with mock.patch.object(concurrency, "ThreadPoolExecutor", wraps=concurrency.ThreadPoolExecutor) as pool:
            concurrency.map_in_bounded_threads(lambda item: item, [1, 2])
        pool.assert_called_once_with(max_workers=2)

    def test_each_worker_releases_its_connection(self):
        """Without this the connection stays open until the pool joins its threads."""
        with mock.patch.object(concurrency, "connection") as fake_connection:
            concurrency.map_in_bounded_threads(lambda item: item, range(20))
        self.assertEqual(fake_connection.close.call_count, concurrency.SERIALIZATION_MAX_WORKERS)

    def test_without_on_error_the_earliest_failure_in_input_order_is_raised(self):
        """ThreadPoolExecutor.map surfaces item 0's exception first; so must this."""

        def fail_on_two_and_four(item):
            if item in (2, 4):
                raise ValueError(f"boom-{item}")
            return item

        with self.assertRaises(ValueError) as raised:
            concurrency.map_in_bounded_threads(fail_on_two_and_four, range(6))
        self.assertEqual(str(raised.exception), "boom-2")

    def test_with_on_error_the_failed_items_are_dropped_and_the_rest_survive(self):
        reported = []

        def fail_on_two(item):
            if item == 2:
                raise ValueError("boom")
            return item * 10

        result = concurrency.map_in_bounded_threads(
            fail_on_two,
            range(5),
            on_error=lambda item, exc: reported.append((item, str(exc))),
        )
        self.assertEqual(result, [0, 10, 30, 40])
        self.assertEqual(reported, [(2, "boom")])


class DefaultLanguageTests(unittest.TestCase):
    """Serialization must render in settings.LANGUAGE_CODE regardless of the thread.

    The old ThreadPoolExecutor workers never inherited the request's active
    language, so every fanned-out response rendered modeltranslation fields in
    settings.LANGUAGE_CODE. Anything that moves work onto the request thread has
    to reproduce that, or the response bytes change for non-English clients.
    """

    def test_override_reproduces_the_language_a_worker_thread_would_see(self):
        with translation.override("fr"):
            self.assertEqual(translation.get_language(), "fr")
            with concurrency.default_language():
                self.assertEqual(translation.get_language(), settings.LANGUAGE_CODE)
            self.assertEqual(translation.get_language(), "fr", "the request language must be restored")

    def test_helper_workers_ignore_the_callers_active_language(self):
        """Characterization of the premise the call sites rest on.

        This holds because a worker thread inherits no active language, so
        get_language() falls back to settings.LANGUAGE_CODE. It is not a guard
        on any single line of the helper; the guard is the invariant below.
        """
        with translation.override("fr"):
            observed = concurrency.map_in_bounded_threads(lambda item: translation.get_language(), range(4))
        self.assertEqual(observed, [settings.LANGUAGE_CODE] * 4)

    def test_work_never_runs_on_the_calling_thread(self):
        """The invariant that keeps the test above true, including for one item.

        Running work inline is a tempting optimization for a single-item page:
        it saves a thread and a Postgres connection. It would also make that page
        honour Accept-Language while a two-item page did not, so response bytes
        would depend on page size. If this ever needs to change, wrap the inline
        body in concurrency.default_language() first.
        """
        caller = threading.get_ident()
        for size in (1, 2, 10):
            observed = concurrency.map_in_bounded_threads(lambda item: threading.get_ident(), range(size))
            self.assertNotIn(caller, observed, f"work ran on the request thread for a {size}-item input")


class ProjectListSerializationTests(APITestCase):
    """GET /api/projects/ must not fan serialization out, and must not change bytes."""

    def setUp(self):
        group, _ = Group.objects.get_or_create(name="Admin")
        # has_project_permission walks membership.group.permissions, so the group
        # needs the permission explicitly. Do not rely on the seed fixture here.
        group.permissions.add(Permission.objects.get(codename="view_project", content_type__app_label="api"))
        self.group = group
        self.country = Country.objects.filter(region__isnull=False).order_by("?").first() or Country.objects.first()
        self.user = UserFactory(email="fanout-list@example.com")
        self.client.force_authenticate(self.user)

    def make_visible_projects(self, count, prefix, **project_kwargs):
        projects = []
        for index in range(count):
            project = ProjectFactory(owner=self.user, country=self.country, name=f"{prefix}-{index}", **project_kwargs)
            ProjectMembership.objects.create(project=project, user=self.user, group=self.group)
            projects.append(project)
        return projects

    def test_summary_list_uses_a_single_thread(self):
        """Recording the thread identity is what makes the no-fan-out claim falsifiable.

        Reintroducing a ThreadPoolExecutor grows the set of observed threads
        beyond the request thread, at any width.
        """
        self.make_visible_projects(5, "fanout-project")

        seen_threads = set()
        original_get_role = api_serializers.ProjectSummarySerializer.get_role

        def recording_get_role(serializer, obj):
            seen_threads.add(threading.get_ident())
            return original_get_role(serializer, obj)

        with mock.patch.object(api_serializers.ProjectSummarySerializer, "get_role", recording_get_role):
            response = self.client.get("/api/projects/?summary=true&page=1&page_size=15")

        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(seen_threads), 0, "get_role never ran, so the thread assertion would be vacuous")
        self.assertEqual(
            len(seen_threads),
            1,
            f"project list serialization ran on {len(seen_threads)} threads. Every extra thread opens its "
            "own Postgres connection and reintroduces the App Engine connection burst.",
        )

    def test_page_order_is_still_newest_updated_first(self):
        """executor.map preserved input order; the sequential path must too."""
        self.make_visible_projects(3, "fanout-order")

        response = self.client.get("/api/projects/?summary=true&page=1&page_size=15")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        rows = payload["results"] if isinstance(payload, dict) and "results" in payload else payload
        self.assertEqual(len(rows), 3)
        timestamps = [row["updated_at"] for row in rows]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_non_summary_list_still_answers_in_the_default_language(self):
        """The path that actually changed, on the client type that would notice.

        Without ?summary=true the endpoint uses ReadProjectSerializer, which
        embeds climate/moisture/soil_type with fields="__all__". All three are
        modeltranslation-registered with a translated name, so if serialization
        started honouring Accept-Language these bytes would change for every
        non-English client. ProjectSummarySerializer reaches no translated field,
        which is why the summary tests above cannot catch this.
        """
        climate = Climate.objects.create(name="Boreal test", name_en="Boreal test", name_fr="Boreal en francais")
        self.make_visible_projects(1, "fanout-lang", climate=climate)

        response = self.client.get("/api/projects/?page=1&page_size=15", HTTP_ACCEPT_LANGUAGE="fr")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        rows = payload["results"] if isinstance(payload, dict) and "results" in payload else payload
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["climate"]["name"],
            "Boreal test",
            "the project list started localizing embedded reference names. That is a deliberate API "
            "change and must not ride along with a connection fix.",
        )

    def test_retrieve_localizes_and_list_does_not(self):
        """Characterization of a pre-existing inconsistency, not an endorsement.

        ProjectViewSet.retrieve has always serialized on the request thread, so
        it has always honoured Accept-Language, while the fanned-out list has
        not. Removing the pool did not create this split; it is recorded here so
        that whoever unifies the behaviour has to update this test deliberately.
        """
        climate = Climate.objects.create(name="Tropical test", name_en="Tropical test", name_fr="Tropical en francais")
        project = self.make_visible_projects(1, "fanout-retrieve", climate=climate)[0]

        response = self.client.get(f"/api/projects/{project.pk}/", HTTP_ACCEPT_LANGUAGE="fr")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["climate"]["name"], "Tropical en francais")
