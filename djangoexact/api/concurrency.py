"""Bounded, connection-aware fan-out for per-request serialization work.

Django database connections are thread-local and ``CONN_MAX_AGE`` is 0, so an
ORM call made inside a worker thread cannot borrow the request thread's
connection: it opens a brand-new Postgres connection of its own, held for the
life of the pool. One fanned-out request therefore costs ``1 + max_workers``
simultaneous connections. App Engine Standard reaches Cloud SQL through an
instance-local unix socket with a per-instance ceiling on concurrent
connections; a burst past that ceiling is refused outright (psycopg2
``OperationalError: ... Connection refused``), and the refusal lands on
whichever request is connecting at that instant, including endpoints that never
fan out at all.

Every ORM-touching fan-out in the request path (``api/views.py``,
``public/views.py``) goes through :func:`map_in_bounded_threads` so the width of
that fan-out lives in exactly one place.
"""

import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from django.conf import settings
from django.db import connection
from django.utils import translation


# Upper bound on worker threads for any ORM-touching fan-out in the request path.
#
# The width of such a pool is a per-instance connection cost, not just a
# concurrency knob. Worst case per App Engine instance:
#
#     gunicorn workers x (1 request connection + SERIALIZATION_MAX_WORKERS)
#     4 x (1 + 4) = 20
#
# comfortably under the documented ceiling of 100 concurrent Cloud SQL
# connections per App Engine Standard instance. The leading "4" is gunicorn's
# ``-w 4`` (``djangoexact/app.yaml``; ``deploy/Dockerfile.web_service`` defaults
# the same via ``${GUNICORN_WORKERS:-4}``). On Cloud Run,
# ``deploy/cloudrun-service.yaml`` templates ``containerConcurrency``; with
# concurrency greater than 1 a single gunicorn worker serves several requests at
# once, so the formula understates the real peak there. Re-derive the budget
# before raising either knob.
SERIALIZATION_MAX_WORKERS = 4


@contextmanager
def default_language():
    """Pin the active language to ``settings.LANGUAGE_CODE`` for the enclosed block.

    ``django.utils.translation``'s active language is thread-local and worker
    threads inherit nothing from the request thread, so serialization that runs
    in a thread pool renders modeltranslation fields in ``settings.LANGUAGE_CODE``
    no matter what the client sent in ``Accept-Language``. Serializing on the
    request thread under this context manager preserves that behaviour, so the
    response bytes do not change for non-English clients (``ReadProjectSerializer``
    embeds ``climate``, ``moisture`` and ``soil_type``, all translated).

    Localizing these list and results responses is a deliberate API change to
    make for all endpoints at once, with the WebApp frontend in the loop.
    """
    with translation.override(settings.LANGUAGE_CODE):
        yield


def map_in_bounded_threads(func, items, max_workers=SERIALIZATION_MAX_WORKERS, on_error=None):
    """Apply ``func`` to ``items`` across at most ``max_workers`` threads.

    Returns a list in the order of ``items``, never in completion order.

    Each worker drains a shared queue rather than owning a fixed slice, so one
    slow item does not leave the other workers idle, and each worker closes its
    own Django connection as soon as the queue runs dry: the run costs
    ``min(max_workers, len(items))`` connections, released when the work
    finishes instead of being pinned until the pool joins its threads.

    ``func`` always runs on a worker thread, never on the caller's thread, even
    for a single item. Callers depend on that: a worker inherits no active
    language, so it renders modeltranslation fields in ``settings.LANGUAGE_CODE``
    rather than honouring ``Accept-Language``. An inline fast path for small
    inputs would change response bytes for non-English clients unless the body
    is wrapped in :func:`default_language`; a test pins the invariant.

    Error handling mirrors ``ThreadPoolExecutor.map``:

    ``on_error is None``
        the failure earliest in input order is re-raised once the workers have
        stopped.
    ``on_error`` callable
        called as ``on_error(item, exc)``; that item is dropped from the returned
        list and the remaining items still run.
    """
    items = list(items)
    if not items:
        return []

    worker_count = min(max_workers, len(items))
    pending = deque(enumerate(items))
    produced = []
    failures = []
    lock = threading.Lock()

    def drain(_worker_index):
        try:
            while True:
                try:
                    # deque.popleft is atomic, so no lock is needed here.
                    position, item = pending.popleft()
                except IndexError:
                    return

                try:
                    value = func(item)
                except Exception as exc:
                    if on_error is None:
                        with lock:
                            failures.append((position, exc))
                        return
                    on_error(item, exc)
                else:
                    with lock:
                        produced.append((position, value))
        finally:
            # Release this worker's connection now. Without this it stays open
            # until the pool joins its threads at the end of the block.
            connection.close()

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        list(executor.map(drain, range(worker_count)))

    if failures:
        raise min(failures, key=lambda failure: failure[0])[1]

    produced.sort(key=lambda entry: entry[0])
    return [value for _position, value in produced]
