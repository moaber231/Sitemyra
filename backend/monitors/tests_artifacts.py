"""Phase 5 artifact storage tests (local backend + stubbed S3)."""

import io
import os
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from common import artifact_storage
from common.artifact_storage import StorageError
from monitors.models import ChangeDiff, Monitor, MonitorCheck


def _user(email="owner@example.com"):
    return User.objects.create_user(email, "a-strong-password")


def _monitor(user):
    return Monitor.objects.create(
        user=user, name="M", url="https://example.com"
    )


def _check(monitor, days_ago=0):
    return MonitorCheck.objects.create(
        monitor=monitor,
        checked_at=timezone.now() - timedelta(days=days_ago),
        status_code=200,
        response_time_ms=10,
        content_hash="c" * 64,
    )


@override_settings(DEBUG=True)
class LocalStorageTests(TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "ARTIFACT_STORAGE": "local",
                "ARTIFACT_LOCAL_ROOT": "/tmp/opencode/artifacts-test",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_roundtrip(self):
        key = artifact_storage.save_bytes("m1", "c1", b"hello", "png")
        self.assertTrue(key.startswith("artifacts/m1/c1/"))
        self.assertNotIn("/app/", key)
        self.assertEqual(artifact_storage.load_bytes(key), b"hello")
        self.assertTrue(artifact_storage.delete_key(key))
        with self.assertRaises(StorageError):
            artifact_storage.load_bytes(key)

    def test_unsafe_extension_rejected(self):
        with self.assertRaises(StorageError):
            artifact_storage.save_bytes("m", "c", b"x", "../../etc/passwd")

    def test_traversal_key_rejected(self):
        with self.assertRaises(StorageError):
            artifact_storage.load_bytes("artifacts/../../etc/passwd")
        with self.assertRaises(StorageError):
            artifact_storage.load_bytes("/app/storage/monitor-artifacts/x.png"
                                         + "\x00")

    def test_missing_config_s3(self):
        with patch.dict(
            os.environ,
            {"ARTIFACT_STORAGE": "s3", "AWS_STORAGE_BUCKET_NAME": ""},
            clear=False,
        ):
            with self.assertRaises(StorageError):
                artifact_storage.save_bytes("m", "c", b"x", "png")


class ArtifactDownloadTests(APITestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "ARTIFACT_STORAGE": "local",
                "ARTIFACT_LOCAL_ROOT": "/tmp/opencode/artifacts-test",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.owner = _user("owner@example.com")
        self.other = _user("other@example.com")
        self.monitor = _monitor(self.owner)
        check = _check(self.monitor)
        key = artifact_storage.save_bytes(
            self.monitor.id, check.id, b"\x89PNGdata", "png"
        )
        self.diff = ChangeDiff.objects.create(
            monitor=self.monitor,
            previous_check=check,
            current_check=check,
            diff_type="screenshot",
            summary="changed",
            artifact_path=key,
        )

    def _url(self):
        return reverse("artifact-download", kwargs={"diff_id": self.diff.id})

    def test_owner_can_download(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "image/png")
        content = b"".join(response.streaming_content)
        self.assertEqual(content, b"\x89PNGdata")

    def test_cross_tenant_gets_404(self):
        self.client.force_authenticate(self.other)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_rejected(self):
        response = self.client.get(self._url())
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_diffs_never_expose_paths(self):
        import json

        self.client.force_authenticate(self.owner)
        response = self.client.get(f"/api/monitors/{self.monitor.id}/diffs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = json.dumps(response.data, default=str)
        self.assertNotIn("/app/", body)
        self.assertNotIn("artifact_path", body)
        self.assertTrue(
            response.data[0]["artifact_download_url"].endswith("/download/")
        )

    def test_legacy_path_served_but_never_exposed(self):
        import json

        legacy = "/tmp/opencode/artifacts-test/legacy.html"
        os.makedirs(os.path.dirname(legacy), exist_ok=True)
        with open(legacy, "wb") as fh:
            fh.write(b"<html></html>")
        check = _check(self.monitor)
        diff = ChangeDiff.objects.create(
            monitor=self.monitor,
            previous_check=check,
            current_check=check,
            diff_type="dom",
            summary="old",
            artifact_path=legacy,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.get(f"/api/monitors/{self.monitor.id}/diffs/")
        self.assertNotIn("/app/", json.dumps(response.data, default=str))
        dl = self.client.get(
            reverse("artifact-download", kwargs={"diff_id": diff.id})
        )
        self.assertEqual(dl.status_code, status.HTTP_200_OK)


class RetentionTests(TestCase):
    def test_retention_deletes_objects_not_just_rows(self):
        with patch.dict(
            os.environ,
            {
                "ARTIFACT_STORAGE": "local",
                "ARTIFACT_LOCAL_ROOT": "/tmp/opencode/artifacts-test",
            },
            clear=False,
        ):
            from monitors.tasks import cleanup_expired_artifacts

            user = _user()
            monitor = _monitor(user)
            stale = _check(monitor, days_ago=9)  # Free plan keeps 7d
            fresh = _check(monitor, days_ago=1)
            key = artifact_storage.save_bytes(
                monitor.id, stale.id, b"stale", "png"
            )
            ChangeDiff.objects.create(
                monitor=monitor,
                previous_check=stale,
                current_check=stale,
                diff_type="screenshot",
                summary="stale",
                artifact_path=key,
            )
            totals = cleanup_expired_artifacts()
            self.assertEqual(totals["checks_deleted"], 1)
            self.assertEqual(totals["files_deleted"], 1)
            with self.assertRaises(StorageError):
                artifact_storage.load_bytes(key)
            self.assertTrue(MonitorCheck.objects.filter(id=fresh.id).exists())


class S3StorageTests(TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "ARTIFACT_STORAGE": "s3",
                "AWS_STORAGE_BUCKET_NAME": "test-bucket",
                "AWS_STORAGE_REGION": "us-east-1",
                "AWS_ACCESS_KEY_ID": "test",
                "AWS_SECRET_ACCESS_KEY": "test",
                "AWS_S3_ENDPOINT_URL": "",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(setattr, artifact_storage, "_s3_client_instance", None)
        artifact_storage._s3_client_instance = None

    def _stubbed_client(self, stubber_responses):
        import boto3
        from botocore.config import Config
        from botocore.stub import Stubber

        client = boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
            config=Config(signature_version="s3v4"),
        )
        stubber = Stubber(client)
        for method, response, params in stubber_responses:
            if isinstance(response, Exception):
                stubber.add_client_error(
                    method,
                    service_error_code=response.args[0],
                    service_message="",
                )
            else:
                stubber.add_response(method, response, params)
        stubber.activate()
        return client

    def test_save_load_delete(self):
        from botocore.response import StreamingBody

        responses = [
            ("put_object", {}, None),
            (
                "get_object",
                {"Body": StreamingBody(io.BytesIO(b"s3-bytes"), 8)},
                None,
            ),
            ("delete_object", {}, None),
        ]
        artifact_storage._s3_client_instance = self._stubbed_client(responses)
        key = artifact_storage.save_bytes("m1", "c1", b"s3-bytes", "png")
        self.assertTrue(key.startswith("artifacts/m1/c1/"))
        self.assertEqual(artifact_storage.load_bytes(key), b"s3-bytes")
        self.assertTrue(artifact_storage.delete_key(key))

    def test_presigned_url_expires(self):
        artifact_storage._s3_client_instance = self._stubbed_client([])
        url = artifact_storage.presigned_get_url(
            "artifacts/m/c/" + "a" * 32 + ".png", expires_in=300
        )
        self.assertIn("test-bucket", url)
        self.assertIn("X-Amz-Expires=300", url)
        self.assertNotIn("test-secret", url)

    def test_bucket_autocreate(self):
        import boto3
        from botocore.stub import Stubber

        client = boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        stubber = Stubber(client)
        stubber.add_client_error("head_bucket", service_error_code="404")
        stubber.add_response("create_bucket", {}, {"Bucket": "test-bucket"})
        stubber.activate()
        artifact_storage._ensure_bucket(client)  # must not raise
        stubber.assert_no_pending_responses()

    def test_s3_download_redirects_to_signed_url(self):
        owner = _user("s3owner@example.com")
        monitor = _monitor(owner)
        check = _check(monitor)
        diff = ChangeDiff.objects.create(
            monitor=monitor,
            previous_check=check,
            current_check=check,
            diff_type="screenshot",
            summary="s3",
            artifact_path="artifacts/m/c/" + "b" * 32 + ".png",
        )
        artifact_storage._s3_client_instance = self._stubbed_client([])
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(owner)
        response = client.get(
            reverse("artifact-download", kwargs={"diff_id": diff.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("X-Amz-Expires=", response["Location"])
