"""Artifact persistence (key-based; local disk or S3 via common storage).

``save_artifact`` returns a storage *key* (never a filesystem path) that
is stored on ``ChangeDiff.artifact_path``. Pre-Phase-5 rows may still
hold absolute local paths; those remain readable via the storage layer
but are never exposed through the API.
"""

from pathlib import Path

from common.artifact_storage import (
    StorageError,
    delete_key,
    load_bytes,
    local_root,
    save_bytes,
)

# Kept for backward-compatible imports; new code must use keys.
# Env-driven (ARTIFACT_LOCAL_ROOT) — no hardcoded container path
# anywhere in the app (plan D10).
BASE_DIR = local_root()


def save_artifact(
    monitor_id,
    check_id,
    content: bytes,
    extension: str,
) -> str:
    return save_bytes(monitor_id, check_id, content, extension)


def save_text_artifact(
    monitor_id,
    check_id,
    content: str,
    extension: str = "txt",
) -> str:
    return save_bytes(monitor_id, check_id, content.encode("utf-8"), extension)


def load_artifact(key: str) -> bytes:
    return load_bytes(key)


def delete_artifact(key: str) -> bool:
    return delete_key(key)


__all__ = [
    "BASE_DIR",
    "StorageError",
    "delete_artifact",
    "load_artifact",
    "local_root",
    "save_artifact",
    "save_text_artifact",
]
