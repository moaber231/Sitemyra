"""Accessor for discovered targets.

A target can be a plain dict (the shape ``classify`` produces and the API
serialises) or a ``DiscoveredTarget`` model instance (what the ORM hands
back). Services that consume targets should not care which, so they read
through :func:`target_value`.
"""


def target_value(target, key, default=None):
    if isinstance(target, dict):
        value = target.get(key, default)
    else:
        value = getattr(target, key, default)
    return default if value is None else value
