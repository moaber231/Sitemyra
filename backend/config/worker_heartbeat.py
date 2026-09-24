"""Celery worker heartbeat registry in Redis.

``GET /api/health/`` used to run ``celery_app.control.inspect(timeout=2)``
on every probe — a live broker broadcast. Measured problems
(docs/RESOURCE-BUDGET.md section 6):

* **~2.1 s per probe**: the reply drain always waits out the full
  ``timeout``, even when workers answer in milliseconds.
* **Concurrency wedge**: every thread shares one ``app.control`` → one
  kombu pidbox producer pool. Under 20 concurrent probes, 17 blocked
  in ``pool.acquire()``'s ``queue.get()`` (no timeout) for >45 s while
  3 raced through — and each wedged request pinned its Django DB
  connection (7 → 24 ``pg_stat_activity`` rows), heading straight for
  Postgres ``max_connections`` exhaustion.

The fix is a registry instead of a round-trip: each worker process
writes one small key (``celery:worker-hb:<nodename>``) every
``TTL / 3`` seconds with a TTL, and the health endpoint merely ``SCAN``s
that prefix. No broker round-trip, no reply drain, no shared pool —
sub-millisecond and safe under unlimited concurrency.

Wire-up: ``config/celery.py`` calls :func:`install` at import time, so
both dev and prod workers (``celery -A config worker``) register on
``worker_ready`` and deregister on ``worker_shutdown``. The API process
never fires those signals, so it never registers. Beat never fires them
either — matching the old ``inspect()`` output, which listed workers
only. A worker that dies without a shutdown signal (SIGKILL, OOM) drops
out of the health response once its TTL lapses (default 15 s).

Endpoint response shape is unchanged: ``ok`` + ``workers``,
``degraded`` + ``detail``, or ``error`` + ``error``.
"""

import json
import logging
import os
import socket
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

KEY_PREFIX = "celery:worker-hb:"
DEFAULT_TTL_S = 15
MIN_TTL_S = 3
MAX_TTL_S = 3600
DEFAULT_NODE_PREFIX = "celery@"

# nodename -> (thread, stop_event); only ever touched while holding
# _HEARTBEATS_LOCK. Lives at module scope so the shutdown handler can
# find what the ready handler started.
_HEARTBEATS = {}
_HEARTBEATS_LOCK = threading.Lock()


def heartbeat_ttl_seconds(env=None):
    """WORKER_HEARTBEAT_TTL_S, clamped to [3, 3600]; default 15."""
    env = os.environ if env is None else env
    try:
        ttl = int(env.get("WORKER_HEARTBEAT_TTL_S", DEFAULT_TTL_S))
    except (TypeError, ValueError):
        ttl = DEFAULT_TTL_S
    return max(MIN_TTL_S, min(MAX_TTL_S, ttl))


def heartbeat_interval_seconds(ttl):
    """Re-register often enough to survive two lost beats."""
    return max(1, ttl // 3)


def heartbeat_key(nodename, prefix=KEY_PREFIX):
    return f"{prefix}{nodename}"


def beat(client, nodename, ttl, prefix=KEY_PREFIX):
    """One registry write: SET key <payload> EX ttl."""
    payload = json.dumps(
        {
            "nodename": nodename,
            "pid": os.getpid(),
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    client.set(heartbeat_key(nodename, prefix), payload, ex=ttl)


def remove(client, nodename, prefix=KEY_PREFIX):
    client.delete(heartbeat_key(nodename, prefix))


def live_workers(client, prefix=KEY_PREFIX):
    """Sorted nodenames with a non-expired heartbeat (SCAN, never KEYS).

    ``SCAN`` is incremental so it never blocks Redis the way ``KEYS``
    would on the shared db0; the ``GET`` guard drops keys that expired
    between the scan page and the read.
    """
    names = []
    for key in client.scan_iter(match=f"{prefix}*", count=100):
        if isinstance(key, bytes):
            key = key.decode("utf-8", "replace")
        if client.get(key) is None:
            continue
        names.append(key[len(prefix):])
    return sorted(names)


def run_heartbeat(
    stop_event, client, nodename, interval, ttl, prefix=KEY_PREFIX
):
    """Beat every *interval* until *stop_event*; deregister on exit.

    Redis failures are logged and retried on the next tick — a
    transient outage must never take the worker down.
    """
    while not stop_event.is_set():
        try:
            beat(client, nodename, ttl, prefix)
        except Exception as exc:
            logger.warning("worker heartbeat write failed: %s", exc)
        stop_event.wait(interval)
    try:
        remove(client, nodename, prefix)
    except Exception as exc:
        logger.warning("worker heartbeat cleanup failed: %s", exc)


def start_heartbeat(
    nodename,
    ttl=None,
    client=None,
    interval=None,
    prefix=KEY_PREFIX,
):
    """Start the daemon thread; returns ``(thread, stop_event)``."""
    ttl = heartbeat_ttl_seconds() if ttl is None else ttl
    if interval is None:
        interval = heartbeat_interval_seconds(ttl)
    if client is None:
        from django.conf import settings

        import redis

        client = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2)
    stop_event = threading.Event()
    thread = threading.Thread(
        target=run_heartbeat,
        args=(stop_event, client, nodename, interval, ttl, prefix),
        name=f"celery-heartbeat-{nodename}",
        daemon=True,  # never keep the worker process alive
    )
    thread.start()
    return thread, stop_event


def nodename_from(sender=None):
    """Resolve the Celery nodename (``celery@<host>``) from a signal sender.

    ``worker_ready`` fires with the *consumer* as sender and
    ``worker_shutdown`` with the *work controller*; both carry a
    ``hostname`` attribute that may be the bare host (consumer) or the
    full nodename (controller), so normalize: add the ``celery@`` prefix
    only when it is missing. Fallback matches Celery's default nodename
    (compose never passes ``-n``).
    """
    name = getattr(sender, "hostname", None)
    if isinstance(name, str) and name:
        return name if "@" in name else f"{DEFAULT_NODE_PREFIX}{name}"
    return f"{DEFAULT_NODE_PREFIX}{socket.gethostname()}"


def handle_worker_ready(sender=None, **kwargs):
    """worker_ready: start heartbeating for this worker process."""
    try:
        nodename = nodename_from(sender)
        thread, stop = start_heartbeat(nodename)
    except Exception as exc:
        # Never fail worker boot over a diagnostic.
        logger.warning("celery heartbeat could not start: %s", exc)
        return
    with _HEARTBEATS_LOCK:
        previous = _HEARTBEATS.get(nodename)
        _HEARTBEATS[nodename] = (thread, stop)
    if previous is not None:  # defensive; ready fires once per worker
        previous[1].set()
    logger.debug("celery heartbeat started for %s", nodename)


def handle_worker_shutdown(sender=None, **kwargs):
    """worker_shutdown: stop promptly and deregister the key(s)."""
    with _HEARTBEATS_LOCK:
        entries = list(_HEARTBEATS.items())
        _HEARTBEATS.clear()
    for _nodename, (thread, stop) in entries:
        stop.set()
        try:
            thread.join(timeout=2.0)
        except Exception:  # pragma: no cover - defensive
            pass


def install():
    """Connect the signal handlers (idempotent via dispatch_uid).

    Imported lazily so the API's health path never pulls in Celery —
    only worker processes ever fire these signals.
    """
    from celery.signals import worker_ready, worker_shutdown

    worker_ready.connect(
        handle_worker_ready, dispatch_uid="apeiro.heartbeat.worker_ready"
    )
    worker_shutdown.connect(
        handle_worker_shutdown,
        dispatch_uid="apeiro.heartbeat.worker_shutdown",
    )
