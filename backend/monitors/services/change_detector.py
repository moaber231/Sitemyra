def detect_change(previous_hash: str, current_hash: str) -> bool:
    """
    Return True when the current content hash differs from
    the previous hash.

    The first successful check establishes the baseline and
    is therefore not considered a change.
    """
    if not previous_hash:
        return False

    return previous_hash != current_hash
