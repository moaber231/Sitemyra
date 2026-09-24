"""Phase F retention tests — plan D8: env cap, orphan sweep, empty-dir
prune, byte logging, monitor-delete cleanup, idempotent re-run.

Every class gets a PRIVATE artifact root: the sweep's counts stay
deterministic no matter what files earlier tests left behind.
"""
import os
import shutil
import tempfile
import time
from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from common import artifact_storage
from common.artifact_storage import StorageError
from monitors.models import ChangeDiff, Monitor, MonitorCheck
from monitors.tasks import cleanup_expired_artifacts


def _user(email="retention@example.com"):
    return User.objects.create_user(email, "a-strong-password")


def _monitor(user, name="R"):
    return Monitor.objects.create(
        user=user, name=name, url="https://example.com"
    )


def _check(monitor, days_ago=0):
    return MonitorCheck.objects.create(
        monitor=monitor,
        checked_at=timezone.now() - timedelta(days=days_ago),
        status_code=200,
        response_time_ms=10,
        content_hash="c" * 64,
    )


class _PrivateRootMixin:
    def _use_private_root(self):
        # Default temp dir: this runs inside the test container, where
        # /tmp always exists (no shared host path assumptions).
        self._root = tempfile.mkdtemp(prefix="retention-root-")
        self.addCleanup(shutil.rmtree, self._root, ignore_errors=True)
        env = mock.patch.dict(
            os.environ,
            {
                "ARTIFACT_STORAGE": "local",
                "ARTIFACT_LOCAL_ROOT": self._root,
            },
            clear=False,
        )
        env.start()
        self.addCleanup(env.stop)
        return self._root

    @staticmethod
    def _age(key_or_path, seconds=3600):
        """Backdate mtime past the sweep's grace window: freshly
        written objects belong to possibly-in-flight checks and are
        deliberately never swept (write-object-then-row invariant)."""
        parts = str(key_or_path).split("/")
        if parts[0] == "artifacts":
            parts = parts[1:]
        path = (
            key_or_path
            if os.path.isabs(str(key_or_path))
            else os.path.join(os.environ["ARTIFACT_LOCAL_ROOT"], *parts)
        )
        os.utime(path, (time.time() - seconds, time.time() - seconds))
        return path


class RetentionCapTests(_PrivateRootMixin, TestCase):
    """plan D8: ARTIFACT_RETENTION_DAYS is a CAP — min(plan, env)."""

    def setUp(self):
        self._use_private_root()
        self.user = _user()

    @override_settings(ARTIFACT_RETENTION_DAYS=3)
    def test_env_cap_shortens_plan_retention(self):
        # Free plan keeps 7d; the 3d cap must shorten it: a 4d-old
        # check survives the plan alone but not the cap.
        monitor = _monitor(self.user)
        stale = _check(monitor, days_ago=4)
        fresh = _check(monitor, days_ago=1)

        totals = cleanup_expired_artifacts()

        self.assertEqual(totals["checks_deleted"], 1)
        self.assertFalse(MonitorCheck.objects.filter(id=stale.id).exists())
        self.assertTrue(MonitorCheck.objects.filter(id=fresh.id).exists())

    @override_settings(ARTIFACT_RETENTION_DAYS=30)
    def test_env_cap_never_extends_plan_retention(self):
        # Cap 30 > plan 7: the plan still governs — an 8d-old check
        # goes even though it would survive the cap alone.
        monitor = _monitor(self.user)
        stale = _check(monitor, days_ago=8)
        fresh = _check(monitor, days_ago=6)

        totals = cleanup_expired_artifacts()

        self.assertEqual(totals["checks_deleted"], 1)
        self.assertFalse(MonitorCheck.objects.filter(id=stale.id).exists())
        self.assertTrue(MonitorCheck.objects.filter(id=fresh.id).exists())

    @override_settings(ARTIFACT_RETENTION_DAYS=0)
    def test_zero_cap_means_plan_only(self):
        monitor = _monitor(self.user)
        kept = _check(monitor, days_ago=6)  # within Free 7d
        gone = _check(monitor, days_ago=9)

        totals = cleanup_expired_artifacts()

        self.assertEqual(totals["checks_deleted"], 1)
        self.assertFalse(MonitorCheck.objects.filter(id=gone.id).exists())
        self.assertTrue(MonitorCheck.objects.filter(id=kept.id).exists())


class OrphanSweepTests(_PrivateRootMixin, TestCase):
    def setUp(self):
        self._use_private_root()
        self.user = _user()
        self.monitor = _monitor(self.user)

    def test_orphans_die_live_objects_survive(self):
        # LIVE: fresh check — kept even without a diff row (check +
        # diff commit together, so a live fresh check is sufficient).
        live_check = _check(self.monitor, days_ago=1)
        live_key = artifact_storage.save_bytes(
            self.monitor.id, live_check.id, b"live-bytes-1234", "png"
        )

        # ORPHAN (a): monitor never existed (missed signal / hard kill).
        ghost_monitor_id = "11111111-2222-3333-4444-555555555555"
        ghost_key = artifact_storage.save_bytes(
            ghost_monitor_id,
            "22222222-2222-3333-4444-555555555555",
            b"ghost",
            "png",
        )
        # ORPHAN (b): live monitor, check row gone (rolled-back commit).
        dead_check_id = "33333333-2222-3333-4444-555555555555"
        dead_key = artifact_storage.save_bytes(
            self.monitor.id, dead_check_id, b"dead-row", "png"
        )
        # ORPHAN (c): legacy flat file no ChangeDiff references.
        legacy_path = os.path.join(self._root, "legacy-no-row.html")
        with open(legacy_path, "wb") as fh:
            fh.write(b"<html>old</html>")

        for key in (ghost_key, dead_key, legacy_path):
            self._age(key)

        totals = cleanup_expired_artifacts()

        self.assertEqual(totals["orphans_deleted"], 3)
        self.assertEqual(
            artifact_storage.load_bytes(live_key), b"live-bytes-1234"
        )
        for key in (ghost_key, dead_key):
            with self.assertRaises(StorageError):
                artifact_storage.load_bytes(key)
        self.assertFalse(os.path.exists(legacy_path))
        # The dead monitor's directory is gone; the storage root stays.
        self.assertFalse(
            os.path.isdir(os.path.join(self._root, ghost_monitor_id))
        )
        self.assertTrue(os.path.isdir(self._root))

    def test_stale_check_file_swept_even_without_diff_row(self):
        stale = _check(self.monitor, days_ago=9)  # Free plan: 7d
        key = artifact_storage.save_bytes(
            self.monitor.id, stale.id, b"stale", "png"
        )
        self._age(key)

        totals = cleanup_expired_artifacts()

        # DB phase removed the stale row; the sweep removed the object
        # that no diff row ever referenced.
        self.assertEqual(totals["checks_deleted"], 1)
        self.assertEqual(totals["orphans_deleted"], 1)
        self.assertEqual(totals["bytes_reclaimed"], 5)
        with self.assertRaises(StorageError):
            artifact_storage.load_bytes(key)

    def test_grace_window_protects_write_then_row_window(self):
        # A file whose check row has NOT committed yet must survive the
        # sweep (objects are written before rows by design). Simulated
        # with a fresh mtime: the row is "not there yet".
        fresh_key = artifact_storage.save_bytes(
            self.monitor.id,
            "eeeeeeee-2222-3333-4444-555555555555",
            b"pending",
            "png",
        )

        totals = cleanup_expired_artifacts()

        self.assertEqual(totals["orphans_deleted"], 0)
        self.assertEqual(artifact_storage.load_bytes(fresh_key), b"pending")


class ByteLoggingTests(_PrivateRootMixin, TestCase):
    def setUp(self):
        self._use_private_root()

    def test_reclaimed_bytes_and_counts_are_logged(self):
        user = _user("bytes@example.com")
        monitor = _monitor(user)
        stale = _check(monitor, days_ago=9)
        stale_key = artifact_storage.save_bytes(
            monitor.id, stale.id, b"x" * 111, "png"
        )
        ChangeDiff.objects.create(
            monitor=monitor,
            previous_check=stale,
            current_check=stale,
            diff_type="screenshot",
            summary="stale",
            artifact_path=stale_key,
        )
        # One sweep-side orphan of a known size.
        ghost_key = artifact_storage.save_bytes(
            "99999999-2222-3333-4444-555555555555",
            "88888888-2222-3333-4444-555555555555",
            b"y" * 42,
            "png",
        )
        self._age(ghost_key)

        with self.assertLogs("monitors.tasks", level="INFO") as logs:
            totals = cleanup_expired_artifacts()

        self.assertEqual(totals["files_deleted"], 1)
        self.assertEqual(totals["orphans_deleted"], 1)
        self.assertEqual(totals["bytes_reclaimed"], 111 + 42)
        self.assertTrue(
            any("bytes=153" in line for line in logs.output),
            logs.output,
        )


class MonitorDeleteCleanupTests(_PrivateRootMixin, TestCase):
    def setUp(self):
        self._use_private_root()

    def test_monitor_delete_purges_its_artifact_prefix(self):
        user = _user("purge@example.com")
        keep = _monitor(user, "keep")
        keep_check = _check(keep, days_ago=1)
        keep_key = artifact_storage.save_bytes(
            keep.id, keep_check.id, b"keep", "png"
        )

        doomed = _monitor(user, "doomed")
        doomed_check = _check(doomed, days_ago=1)
        doomed_key = artifact_storage.save_bytes(
            doomed.id, doomed_check.id, b"doomed", "png"
        )
        ChangeDiff.objects.create(
            monitor=doomed,
            previous_check=doomed_check,
            current_check=doomed_check,
            diff_type="dom",
            summary="x",
            artifact_path=doomed_key,
        )

        doomed_id = doomed.id  # .delete() nulls instance.pk — capture it
        doomed.delete()  # post_delete -> delete_prefix

        self.assertFalse(
            os.path.isdir(os.path.join(self._root, str(doomed_id)))
        )
        with self.assertRaises(StorageError):
            artifact_storage.load_bytes(doomed_key)
        self.assertEqual(artifact_storage.load_bytes(keep_key), b"keep")
        self.assertFalse(
            MonitorCheck.objects.filter(monitor_id=doomed_id).exists()
        )
        self.assertFalse(
            ChangeDiff.objects.filter(monitor_id=doomed_id).exists()
        )

    def test_monitor_delete_survives_storage_failure(self):
        user = _user("purge-fail@example.com")
        monitor = _monitor(user)

        monitor_id = monitor.id
        with mock.patch(
            "common.artifact_storage.delete_prefix",
            side_effect=RuntimeError("bucket exploded"),
        ):
            monitor.delete()  # must NOT raise

        self.assertFalse(Monitor.objects.filter(id=monitor_id).exists())


class IdempotencyTests(_PrivateRootMixin, TestCase):
    def setUp(self):
        self._use_private_root()

    def test_second_run_is_a_clean_noop(self):
        user = _user("idem@example.com")
        monitor = _monitor(user)
        stale = _check(monitor, days_ago=9)
        stale_key = artifact_storage.save_bytes(
            monitor.id, stale.id, b"old", "png"
        )
        self._age(stale_key)
        orphan_key = artifact_storage.save_bytes(
            "abababab-2222-3333-4444-555555555555",
            "cdcdcdcd-2222-3333-4444-555555555555",
            b"orphan",
            "png",
        )
        self._age(orphan_key)

        first = cleanup_expired_artifacts()
        self.assertGreater(
            first["checks_deleted"]
            + first["orphans_deleted"]
            + first["dirs_pruned"],
            0,
        )

        second = cleanup_expired_artifacts()
        self.assertEqual(second["checks_deleted"], 0)
        self.assertEqual(second["diffs_deleted"], 0)
        self.assertEqual(second["files_deleted"], 0)
        self.assertEqual(second["orphans_deleted"], 0)
        self.assertEqual(second["bytes_reclaimed"], 0)
        self.assertEqual(second["dirs_pruned"], 0)
        # The storage root itself is never pruned.
        self.assertTrue(os.path.isdir(self._root))
