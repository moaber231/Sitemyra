from pathlib import Path

from PIL import Image
from pixelmatch.contrib.PIL import pixelmatch


def compare_screenshots(
    previous_path: str,
    current_path: str,
    diff_path: str,
    threshold: float = 0.5,
) -> dict:
    """Pixel-compare two PNGs (identical semantics to the original:
    pixelmatch color threshold 0.1, percentage vs the caller's
    `threshold`, diff PNG written only when changed).

    Memory-safety change: every PIL image (including the lazy file
    handles behind Image.open) is closed deterministically in `finally`
    — screenshot checks run every few minutes per monitor, so leaked
    image objects would accumulate in the long-lived browser worker.
    """
    previous = None
    current = None
    diff = None
    try:
        with Image.open(previous_path) as prev_raw, Image.open(current_path) as cur_raw:
            # convert() fully decodes into new images; the file-backed
            # handles are released when the with-block exits.
            previous = prev_raw.convert("RGBA")
            current = cur_raw.convert("RGBA")

        if previous.size != current.size:
            return {
                "changed": True,
                "percentage": 100.0,
            }

        diff = Image.new(
            "RGBA",
            previous.size,
        )

        changed_pixels = pixelmatch(
            previous,
            current,
            diff,
            threshold=0.1,
        )

        total_pixels = previous.width * previous.height

        percentage = (
            changed_pixels / total_pixels * 100
            if total_pixels
            else 0
        )

        changed = percentage >= float(threshold)

        if changed:
            Path(diff_path).parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            diff.save(diff_path)

        return {
            "changed": changed,
            "percentage": round(percentage, 4),
        }
    finally:
        for image in (previous, current, diff):
            if image is not None:
                try:
                    image.close()
                except Exception:
                    pass
