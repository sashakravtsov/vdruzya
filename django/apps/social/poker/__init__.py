"""First-party Покер: Texas Hold'em, chips economy, bankruptcy, learning."""

__all__ = ["get_or_create_profile", "STARTING_CHIPS"]


def __getattr__(name):
    if name in __all__:
        from . import service
        return getattr(service, name)
    raise AttributeError(name)
