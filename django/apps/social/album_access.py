"""Album visibility helpers — short only."""
from django.db.models import Q

from apps.social.services import friend_ids


def visible_q(viewer):
    """Filter albums visible to viewer (FB friends/public/private)."""
    if not viewer:
        return Q(visibility="public")
    return (
        Q(visibility="public")
        | Q(social_user=viewer)
        | Q(visibility="friends", social_user_id__in=friend_ids(viewer))
    )


def can_view(album, viewer) -> bool:
    v = album.visibility or "friends"
    if v == "public":
        return True
    if not viewer:
        return False
    if album.social_user_id == viewer.id:
        return True
    if v == "friends":
        return album.social_user_id in friend_ids(viewer)
    return False


def can_edit(album, viewer) -> bool:
    return bool(viewer and album.social_user_id == viewer.id)
