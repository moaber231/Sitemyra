from pathlib import Path

from PIL import Image
from pixelmatch.contrib.PIL import pixelmatch


def compare_screenshots(
    previous_path: str,
    current_path: str,
    diff_path: str,
    threshold: float = 0.5,
) -> dict:
    previous = Image.open(previous_path).convert("RGBA")
    current = Image.open(current_path).convert("RGBA")

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
