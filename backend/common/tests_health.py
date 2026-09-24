"""Regression tests for GET /api/health/ (post-Phase-G reliability fix).

The health endpoint used to run a live Celery ``control.inspect()``
broadcast per probe. Measured failures (docs/RESOURCE-BUDGET.md §6):

* ~2.1 s per single probe (the reply drain always waits out the full
  timeout), and
* 17/20 concurrent probes still blocked at 45 s — shared kombu pidbox
  producer pool, ``queue.get()`` with no timeout — each wedged request
  pinning one Postgres connection until ``max_connections`` exhaustion.

These tests lock in the replacement (a Redis TTL-registry scan, see
``config/worker_heartbeat.py``): the response shape, the absence of any
broadcast, behavior under concurrency, and the registry's TTL/dust-off
semantics.
"""

import socket
import threading
import time
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from celery.app.control import Control
from django.conf import settings
from django.db import connection
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse


def _assert_shape(testcase, body):
    """The pre-fix response contract: status + postgres/redis/celery."""
    testcase.assertSetEqual(set(body), {"status", "checks"})
    testcase.assertIn(body["status"], ("ok", "degraded", "error"))
    testcase.assertSetEqual(
        set(body["checks"]), {"postgres", "redis", "celery"}
    )
    for check in body["checks"].values():
        testcase.assertIn(check["status"], ("ok", "degraded", "error"))


class HealthResponseShapeTests(TestCase):
    def test_response_shape_preserved(self):
        response = self.client.get(reverse("health"))
        self.assertIn(response.status_code, (200, 503))
        body = response.json()
        _assert_shape(self, body)
        self.assertEqual(body["checks"]["postgres"]["status"], "ok")
        celery = body["checks"]["celery"]
        if celery["status"] == "ok":
            self.assertIsInstance(celery["workers"], list)
            self.assertTrue(celery["workers"])
        elif celery["status"] == "degraded":
            self.assertEqual(celery["detail"], "no workers responded")
        else:  # redis unreachable in this environment
            self.assertIn("error", celery)

    def test_health_never_touches_celery_broadcast(self):
        """The core regression guard: no inspect()/broadcast per probe.

        On the old implementation ``Control.inspect`` fired inside the
        view, raised through ``_check_celery``'s except and surfaced as
        ``status == "error"`` — failing this assertion.
        """
        with patch.object(
            Control,
            "inspect",
            side_effect=AssertionError("broadcast in health path"),
        ), patch.object(
            Control,
            "broadcast",
            side_effect=AssertionError("broadcast in health path"),
        ):
            response = self.client.get(reverse("health"))
        self.assertIn(response.status_code, (200, 503))
        celery = response.json()["checks"]["celery"]
        self.assertIn(celery["status"], ("ok", "degraded"))


class HealthConcurrencyTests(TestCase):
    """20 concurrent probes must all finish fast and leak nothing.

    Pre-fix, the same 20-thread pattern wedged 17/20 for >45 s and left
    +17 pinned Postgres connections (live repro: 7 → 24).
    """

    N = 20

    @staticmethod
    def _pg_connections():
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_stat_activity")
            return int(cursor.fetchone()[0])

    @staticmethod
    def _probe(barrier, results, index):
        from django.db import connections

        client = Client()
        try:
            barrier.wait(timeout=10)
            start = time.monotonic()
            response = client.get(reverse("health"))
            results[index] = (
                response.status_code,
                time.monotonic() - start,
                response.json(),
            )
        except Exception as exc:  # recorded, asserted below
            results[index] = ("exception", 0.0, str(exc)[:200])
        finally:
            # Harness cleanup: django.test.client deliberately
            # disconnects close_old_connections from request_finished
            # (django/test/client.py), so thread connections stay open
            # until released here. Production keeps the receiver
            # connected (CONN_MAX_AGE=0) — verified live: 7 -> 7
            # pg_stat_activity rows across 40 requests.
            connections.close_all()

    def _run_concurrent_probes(self):
        barrier = threading.Barrier(self.N)
        results = [None] * self.N
        threads = [
            threading.Thread(
                target=self._probe, args=(barrier, results, index)
            )
            for index in range(self.N)
        ]
        wall_start = time.monotonic()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        wall = time.monotonic() - wall_start
        return threads, results, wall

    def test_twenty_concurrent_probes_all_complete_quickly(self):
        threads, results, wall = self._run_concurrent_probes()
        wedged = [t for t in threads if t.is_alive()]
        self.assertFalse(
            wedged, f"{len(wedged)} health probes still wedged after 30s"
        )
        self.assertEqual(len([r for r in results if r]), self.N)
        # Old code: 0/20 done at 45 s (HTTP) / 3/20 at 40 s (in-process).
        self.assertLess(
            wall, 15.0, f"20 concurrent health probes took {wall:.1f}s"
        )
        for code, elapsed, body in results:
            self.assertIn(code, (200, 503), f"unexpected status {code}: {body}")
            self.assertLess(elapsed, 10.0)
            _assert_shape(self, body)

    def test_concurrent_probes_do_not_pin_database_connections(self):
        before = self._pg_connections()
        threads, results, _wall = self._run_concurrent_probes()
        after = self._pg_connections()  # measure BEFORE asserting thread
        # state: wedged probes never reach their finally-cleanup, so the
        # pinned-session symptom (+1 per wedged request; 17 in the live
        # repro) trips this count even while threads are stuck.
        alive = [t for t in threads if t.is_alive()]
        self.assertEqual(len([r for r in results if r]), self.N)
        # Old code: +1 connection per wedged request (17 in the live
        # repro, 20 here). Slack of 10 allows unrelated beat/worker
        # background polls in the shared dev database while still
        # failing loudly on any per-request pinning regression.
        self.assertLessEqual(
            after - before,
            10,
            f"health probes pinned DB connections: {before} -> {after}",
        )
        self.assertFalse(alive, f"{len(alive)} health probes wedged")


class _RedisKeyTestBase(SimpleTestCase):
    """Real-Redis registry tests under a unique, self-cleaned prefix."""

    def setUp(self):
        import redis

        self.prefix = f"test-hb:{uuid.uuid4().hex}:"
        self.redis = redis.Redis.from_url(
            settings.REDIS_URL, socket_timeout=3
        )

    def tearDown(self):
        for key in self.redis.scan_iter(match=f"{self.prefix}*"):
            self.redis.delete(key)


class HeartbeatRegistryTests(_RedisKeyTestBase):
    def test_beat_registers_worker_with_ttl(self):
        from config import worker_heartbeat

        worker_heartbeat.beat(self.redis, "celery@reg-test", 30, self.prefix)
        self.assertEqual(
            worker_heartbeat.live_workers(self.redis, self.prefix),
            ["celery@reg-test"],
        )
        ttl = self.redis.ttl(
            worker_heartbeat.heartbeat_key("celery@reg-test", self.prefix)
        )
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, 30)

    def test_expired_keys_are_not_listed(self):
        from config import worker_heartbeat

        key = worker_heartbeat.heartbeat_key("celery@stale", self.prefix)
        self.redis.set(key, "{}", px=50)
        time.sleep(0.2)
        self.assertEqual(
            worker_heartbeat.live_workers(self.redis, self.prefix), []
        )

    def test_remove_deregisters_worker(self):
        from config import worker_heartbeat

        worker_heartbeat.beat(self.redis, "celery@bye", 30, self.prefix)
        worker_heartbeat.remove(self.redis, "celery@bye", self.prefix)
        self.assertEqual(
            worker_heartbeat.live_workers(self.redis, self.prefix), []
        )

    def test_foreign_keys_are_ignored(self):
        from config import worker_heartbeat

        self.redis.set(f"{self.prefix}unrelated", "x", ex=30)
        other = f"test-hb:{uuid.uuid4().hex}:celery@other"
        self.redis.set(other, "x", ex=30)
        try:
            self.assertEqual(
                worker_heartbeat.live_workers(self.redis, self.prefix),
                ["unrelated"],
            )
        finally:
            self.redis.delete(other)

    def test_ttl_env_knob_is_clamped(self):
        from config import worker_heartbeat

        knob = "WORKER_HEARTBEAT_TTL_S"
        self.assertEqual(
            worker_heartbeat.heartbeat_ttl_seconds({knob: "60"}), 60
        )
        self.assertEqual(
            worker_heartbeat.heartbeat_ttl_seconds({knob: "1"}), 3
        )
        self.assertEqual(
            worker_heartbeat.heartbeat_ttl_seconds({knob: "99999"}), 3600
        )
        self.assertEqual(
            worker_heartbeat.heartbeat_ttl_seconds({knob: "abc"}), 15
        )
        self.assertEqual(worker_heartbeat.heartbeat_ttl_seconds({}), 15)


class HeartbeatThreadTests(_RedisKeyTestBase):
    def test_heartbeat_thread_registers_then_cleans_up_on_stop(self):
        from config import worker_heartbeat

        thread, stop = worker_heartbeat.start_heartbeat(
            "celery@hb-test",
            ttl=10,
            interval=0.05,
            client=self.redis,
            prefix=self.prefix,
        )
        try:
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                if worker_heartbeat.live_workers(
                    self.redis, self.prefix
                ):
                    break
                time.sleep(0.02)
            self.assertEqual(
                worker_heartbeat.live_workers(self.redis, self.prefix),
                ["celery@hb-test"],
            )
            ttl = self.redis.ttl(
                worker_heartbeat.heartbeat_key("celery@hb-test", self.prefix)
            )
            self.assertGreater(ttl, 0)
        finally:
            stop.set()
            thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(
            worker_heartbeat.live_workers(self.redis, self.prefix), []
        )

    def test_transient_redis_failure_does_not_kill_thread(self):
        from config import worker_heartbeat

        calls = []
        real_beat = worker_heartbeat.beat

        def flaky(client, nodename, ttl, prefix=worker_heartbeat.KEY_PREFIX):
            calls.append(nodename)
            if len(calls) == 1:
                raise ConnectionError("redis blip")
            return real_beat(client, nodename, ttl, prefix)

        with patch.object(worker_heartbeat, "beat", side_effect=flaky):
            thread, stop = worker_heartbeat.start_heartbeat(
                "celery@flaky",
                ttl=5,
                interval=0.05,
                client=self.redis,
                prefix=self.prefix,
            )
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and len(calls) < 2:
                time.sleep(0.02)
            stop.set()
            thread.join(timeout=3)
        self.assertGreaterEqual(
            len(calls), 2, "heartbeat thread died on first write failure"
        )
        self.assertFalse(thread.is_alive())


class HeartbeatSignalTests(SimpleTestCase):
    """Signal handlers: nodename normalization, registry, failure safety."""

    def tearDown(self):
        from config import worker_heartbeat

        with worker_heartbeat._HEARTBEATS_LOCK:
            worker_heartbeat._HEARTBEATS.clear()

    def test_ready_handler_uses_consumer_hostname_verbatim(self):
        from config import worker_heartbeat

        sender = SimpleNamespace(hostname="celery@full-nodename")
        with patch.object(
            worker_heartbeat,
            "start_heartbeat",
            return_value=(MagicMock(), threading.Event()),
        ) as start:
            worker_heartbeat.handle_worker_ready(sender=sender)
        self.assertEqual(start.call_args[0][0], "celery@full-nodename")

    def test_ready_handler_prefixes_bare_hostname(self):
        from config import worker_heartbeat

        sender = SimpleNamespace(hostname="0e0114cc8674")
        with patch.object(
            worker_heartbeat,
            "start_heartbeat",
            return_value=(MagicMock(), threading.Event()),
        ) as start:
            worker_heartbeat.handle_worker_ready(sender=sender)
        self.assertEqual(start.call_args[0][0], "celery@0e0114cc8674")

    def test_ready_handler_falls_back_to_socket_hostname(self):
        from config import worker_heartbeat

        with patch.object(
            worker_heartbeat,
            "start_heartbeat",
            return_value=(MagicMock(), threading.Event()),
        ) as start:
            worker_heartbeat.handle_worker_ready(sender=None)
        self.assertEqual(
            start.call_args[0][0],
            f"celery@{socket.gethostname()}",
        )

    def test_ready_handler_never_raises_over_diagnostics_failure(self):
        from config import worker_heartbeat

        with patch.object(
            worker_heartbeat,
            "start_heartbeat",
            side_effect=ConnectionError("redis down"),
        ):
            self.assertIsNone(
                worker_heartbeat.handle_worker_ready(sender=None)
            )

    def test_shutdown_stops_thread_and_clears_registry(self):
        from config import worker_heartbeat

        stop = threading.Event()
        thread = MagicMock()
        with worker_heartbeat._HEARTBEATS_LOCK:
            worker_heartbeat._HEARTBEATS["celery@x"] = (thread, stop)
        worker_heartbeat.handle_worker_shutdown()
        self.assertTrue(stop.is_set())
        thread.join.assert_called_once()
        with worker_heartbeat._HEARTBEATS_LOCK:
            self.assertEqual(worker_heartbeat._HEARTBEATS, {})

    def test_install_is_idempotent(self):
        from celery.signals import worker_ready

        from config import worker_heartbeat

        worker_heartbeat.install()
        worker_heartbeat.install()
        matches = [
            lookup
            for lookup, _receiver in worker_ready.receivers
            if lookup[0] == "apeiro.heartbeat.worker_ready"
        ]
        self.assertEqual(len(matches), 1)
