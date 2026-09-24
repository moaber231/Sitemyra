"""Artifact object storage: local disk (dev) or S3/MinIO (production).

Keys (never filesystem paths) are stored on ``ChangeDiff.artifact_path``:

    artifacts/<monitor_id>/<check_id>/<uuid4hex>.<ext>

The frontend only ever receives a same-origin download URL; internal
paths such as ``/app/storage/...`` are never exposed. Objects are
private by default; downloads are authorized per-request (owner check)
and S3 delivery uses short-lived presigned URLs generated server-side.
"""

import logging
import os
import re
import shutil
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)

KEY_PREFIX = "artifacts/"
_SAFE_EXT = re.compile(r"^[a-z0-9]{1,8}$")
_SAFE_KEY = re.compile(
    r"^artifacts/[A-Za-z0-9-]{1,60}/[A-Za-z0-9-]{1,60}/[0-9a-fA-F]{1,64}\.[a-z0-9]{1,8}$"
)


class StorageError(Exception):
    """Explicit storage failure (missing config, not found, provider error)."""


def backend_name() -> str:
    return "s3" if os.getenv("ARTIFACT_STORAGE", "local").strip().lower() == "s3" else "local"


def local_root() -> Path:
    return Path(os.getenv("ARTIFACT_LOCAL_ROOT", "/app/storage/monitor-artifacts"))


def _bucket() -> str:
    return os.getenv("AWS_STORAGE_BUCKET_NAME", "").strip()


def is_s3_configured() -> bool:
    return bool(_bucket())


def url_expires_seconds() -> int:
    try:
        return max(60, min(86400, int(os.getenv("ARTIFACT_URL_EXPIRES_SECONDS", "900"))))
    except ValueError:
        return 900


def storage_status() -> dict:
    backend = backend_name()
    if backend == "s3":
        configured = is_s3_configured()
        return {
            "backend": "s3",
            "configured": configured,
            "status": "ready" if configured else "misconfigured",
            "detail": (
                "Object storage ready."
                if configured
                else "ARTIFACT_STORAGE=s3 but AWS_STORAGE_BUCKET_NAME is not set."
            ),
        }
    return {
        "backend": "local",
        "configured": True,
        "status": "ready-local",
        "detail": "Local disk storage (development; ephemeral in containers).",
    }


def build_key(monitor_id, check_id, extension: str) -> str:
    ext = (extension or "").lstrip(".").lower()
    if not _SAFE_EXT.match(ext):
        raise StorageError(f"Refused unsafe artifact extension: {extension!r}")
    return f"{KEY_PREFIX}{monitor_id}/{check_id}/{uuid4().hex}.{ext}"


def _validate_key(key: str) -> str:
    """Return the key if it is a safe storage key, else raise."""
    if not key or not isinstance(key, str):
        raise StorageError("Missing artifact key.")
    if _SAFE_KEY.match(key):
        return key
    raise StorageError("Refused unsafe artifact key.")


def is_legacy_local_path(key: str) -> bool:
    """Pre-Phase-5 rows store absolute local paths; readable, never exposed."""
    try:
        return bool(key) and isinstance(key, str) and os.path.isabs(key)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# S3 client (lazy; boto3 only required when the s3 backend is used)
# ---------------------------------------------------------------------------

_s3_client_instance = None


def _s3_client():
    global _s3_client_instance
    if _s3_client_instance is not None:
        return _s3_client_instance
    if not is_s3_configured():
        raise StorageError(
            "Object storage is not configured. Set AWS_STORAGE_BUCKET_NAME "
            "(and credentials/endpoint) or use ARTIFACT_STORAGE=local."
        )
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        raise StorageError("boto3 is not installed; cannot use s3 storage.")
    endpoint = os.getenv("AWS_S3_ENDPOINT_URL", "").strip() or None
    addressing = os.getenv("AWS_S3_ADDRESSING_STYLE", "").strip() or None
    config_kwargs = {"signature_version": "s3v4"}
    if addressing:
        config_kwargs["s3"] = {"addressing_style": addressing}
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=os.getenv("AWS_STORAGE_REGION", "").strip() or None,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "").strip() or None,
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "").strip() or None,
        config=Config(**config_kwargs),
    )
    _ensure_bucket(client)
    _s3_client_instance = client
    return client


def _ensure_bucket(client) -> None:
    """Create the bucket if missing (MinIO dev convenience; no-op on AWS)."""
    from botocore.exceptions import ClientError

    bucket = _bucket()
    try:
        client.head_bucket(Bucket=bucket)
        return
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code not in ("404", "NoSuchBucket", "NotFound"):
            raise StorageError(f"Cannot access storage bucket: {code or 'error'}")
    try:
        region = os.getenv("AWS_STORAGE_REGION", "").strip()
        if region and region != "us-east-1":
            client.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        else:
            client.create_bucket(Bucket=bucket)
    except Exception:
        raise StorageError(
            "Storage bucket is missing and could not be created. "
            "Check AWS_STORAGE_BUCKET_NAME and credentials."
        )


def _key_prefix() -> str:
    prefix = os.getenv("AWS_STORAGE_PREFIX", "").strip().strip("/")
    return f"{prefix}/" if prefix else ""


def _s3_key(key: str) -> str:
    return f"{_key_prefix()}{key}"


# ---------------------------------------------------------------------------
# Public API (key in, bytes out — backends selected per call)
# ---------------------------------------------------------------------------


def save_bytes(monitor_id, check_id, content: bytes, extension: str) -> str:
    """Persist artifact bytes; return the storage key."""
    key = build_key(monitor_id, check_id, extension)
    if backend_name() == "s3":
        from botocore.exceptions import ClientError

        content_type = _content_type(key)
        try:
            _s3_client().put_object(
                Bucket=_bucket(),
                Key=_s3_key(key),
                Body=content,
                ContentType=content_type,
            )
        except ClientError:
            logger.exception("Artifact upload failed")
            raise StorageError("Artifact upload failed.")
        return key
    root = local_root()
    path = root / key[len(KEY_PREFIX):]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return key


def load_bytes(key: str) -> bytes:
    """Read artifact bytes. Legacy absolute paths read from local disk."""
    if is_legacy_local_path(key):
        try:
            return Path(key).read_bytes()
        except Exception:
            raise StorageError("Artifact not found.")
    _validate_key(key)
    if backend_name() == "s3":
        from botocore.exceptions import ClientError

        try:
            response = _s3_client().get_object(Bucket=_bucket(), Key=_s3_key(key))
            return response["Body"].read()
        except ClientError:
            raise StorageError("Artifact not found.")
    path = local_root() / key[len(KEY_PREFIX):]
    try:
        return path.read_bytes()
    except OSError:
        raise StorageError("Artifact not found.")


def delete_key(key: str) -> bool:
    """Delete the stored object. Missing objects report False, not error."""
    if is_legacy_local_path(key):
        # Confine legacy deletes to the local artifacts root.
        try:
            path = Path(key).resolve()
            path.relative_to(local_root().resolve())
        except Exception:
            return False
        try:
            path.unlink(missing_ok=True)
            try:
                path.parent.rmdir()
            except OSError:
                pass
        except OSError:
            return False
        return True
    _validate_key(key)
    if backend_name() == "s3":
        from botocore.exceptions import ClientError

        try:
            _s3_client().delete_object(Bucket=_bucket(), Key=_s3_key(key))
        except ClientError:
            logger.exception("Artifact delete failed")
            raise StorageError("Artifact delete failed.")
        return True
    path = local_root() / key[len(KEY_PREFIX):]
    try:
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass
    except OSError:
        return False
    return True


def size_of(key: str) -> int:
    """Byte size of one stored object (0 when undeterminable).

    Retention logs reclaimed bytes (plan D8): the size must be read
    BEFORE the object is deleted.
    """
    if is_legacy_local_path(key):
        try:
            return Path(key).stat().st_size
        except OSError:
            return 0
    _validate_key(key)
    if backend_name() == "s3":
        from botocore.exceptions import ClientError

        try:
            head = _s3_client().head_object(
                Bucket=_bucket(), Key=_s3_key(key)
            )
            return int(head.get("ContentLength", 0))
        except ClientError:
            return 0
    try:
        return (local_root() / key[len(KEY_PREFIX):]).stat().st_size
    except OSError:
        return 0


def iter_storage_objects():
    """Yield ``(logical_key, size_bytes, mtime_epoch)`` per object.

    The retention orphan sweep (plan D8) walks storage through this on
    both backends: local files and S3 objects both surface as logical
    ``artifacts/<monitor>/<check>/<file>`` keys, plus legacy flat files
    (surfaced as their absolute path, which is how old rows reference
    them). ``mtime`` lets the sweep keep files younger than its grace
    window — objects are written before their rows commit, and an
    in-flight check's file must never be swept.
    """
    if backend_name() == "s3":
        from botocore.exceptions import ClientError

        prefix = _key_prefix() + KEY_PREFIX
        client = _s3_client()
        token = None
        try:
            while True:
                kwargs = {"Bucket": _bucket(), "Prefix": prefix}
                if token:
                    kwargs["ContinuationToken"] = token
                page = client.list_objects_v2(**kwargs)
                logical_prefix = _key_prefix()
                for entry in page.get("Contents", []):
                    s3_key = entry["Key"]
                    logical = s3_key
                    if logical_prefix and logical.startswith(logical_prefix):
                        logical = logical[len(logical_prefix):]
                    modified = entry.get("LastModified")
                    mtime = (
                        modified.timestamp() if modified else 0.0
                    )
                    yield logical, int(entry.get("Size", 0)), mtime
                if not page.get("IsTruncated"):
                    break
                token = page.get("NextContinuationToken")
        except ClientError:
            logger.exception("Artifact listing failed")
            return
        return

    root = local_root()
    if not root.is_dir():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
            rel = path.relative_to(root)
        except (OSError, ValueError):
            continue
        if len(rel.parts) == 3:
            # Normal layout (monitor/check/file) -> logical storage key.
            yield (
                f"{KEY_PREFIX}{'/'.join(rel.parts)}",
                stat.st_size,
                stat.st_mtime,
            )
        else:
            # Pre-Phase-5 flat/legacy file: referenced by absolute path.
            yield str(path), stat.st_size, stat.st_mtime


def delete_prefix(monitor_id) -> tuple[int, int]:
    """Delete every object under ``artifacts/<monitor_id>/``.

    Used by the Monitor post_delete signal (plan D8) so a deleted
    monitor leaves no artifact objects behind (rows already cascade).
    Returns ``(files, bytes)``; never raises — a storage hiccup must
    not fail a monitor delete (failures surface in the caller's log).
    """
    monitor_id = str(monitor_id)
    if not re.match(r"^[A-Za-z0-9-]{1,64}$", monitor_id):
        return 0, 0

    if backend_name() == "s3":
        from botocore.exceptions import ClientError

        total_files = 0
        total_bytes = 0
        try:
            client = _s3_client()
            prefix = f"{_key_prefix()}{KEY_PREFIX}{monitor_id}/"
            token = None
            while True:
                kwargs = {"Bucket": _bucket(), "Prefix": prefix}
                if token:
                    kwargs["ContinuationToken"] = token
                page = client.list_objects_v2(**kwargs)
                batch = page.get("Contents", [])
                if batch:
                    total_bytes += sum(
                        int(obj.get("Size", 0)) for obj in batch
                    )
                    total_files += len(batch)
                    client.delete_objects(
                        Bucket=_bucket(),
                        Delete={
                            "Objects": [
                                {"Key": obj["Key"]} for obj in batch
                            ]
                        },
                    )
                if not page.get("IsTruncated"):
                    break
                token = page.get("NextContinuationToken")
        except ClientError:
            logger.exception(
                "Monitor artifact prefix delete failed [monitor_id=%s]",
                monitor_id,
            )
            return 0, 0
        return total_files, total_bytes

    # Local: one directory tree per monitor (KEY_PREFIX stripped on
    # write), so the whole prefix is a single rmtree.
    directory = local_root() / monitor_id
    files = 0
    total_bytes = 0
    if directory.is_dir():
        for path in directory.rglob("*"):
            if path.is_file():
                files += 1
                try:
                    total_bytes += path.stat().st_size
                except OSError:
                    pass
        shutil.rmtree(directory, ignore_errors=True)
    return files, total_bytes


def presigned_get_url(key: str, expires_in: int | None = None) -> str:
    """Short-lived S3 download URL. Credentials never leave the server."""
    _validate_key(key)
    if backend_name() != "s3":
        raise StorageError("Signed URLs require the s3 storage backend.")
    try:
        return _s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": _bucket(), "Key": _s3_key(key)},
            ExpiresIn=expires_in or url_expires_seconds(),
        )
    except Exception:
        logger.exception("Artifact signed URL failed")
        raise StorageError("Could not create artifact download URL.")


def _content_type(key: str) -> str:
    if key.endswith(".png"):
        return "image/png"
    if key.endswith((".html", ".htm")):
        return "text/html"
    if key.endswith(".txt"):
        return "text/plain"
    return "application/octet-stream"
