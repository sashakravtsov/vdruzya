"""First-party Шахматы app: play, ratings, weekly championships, lessons."""

__all__ = ["ensure_week_championship", "get_or_create_rating"]


def __getattr__(name):
    if name in __all__:
        from . import service
        return getattr(service, name)
    raise AttributeError(name)
