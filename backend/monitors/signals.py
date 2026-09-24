"""Monitor lifecycle signals (plan D8, Phase F)."""
import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Monitor

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=Monitor)
def purge_monitor_artifacts(sender, instance, **kwargs):
    """Remove the deleted monitor's whole artifact prefix.

    Deleting a Monitor cascades its rows (checks, diffs, events) but
    used to leave storage objects behind — the daily orphan sweep only
    caught them a day later at best (and only if it ran). Storage
    failures are logged, never raised: a broken bucket must not fail a
    monitor delete.
    """
    from common.artifact_storage import delete_prefix

    try:
        files, byte_count = delete_prefix(instance.id)
    except Exception:
        logger.exception(
            "monitor artifact purge failed [monitor_id=%s]", instance.id
        )
        return
    if files:
        logger.info(
            "monitor artifacts purged [monitor_id=%s files=%d bytes=%d]",
            instance.id,
            files,
            byte_count,
        )
