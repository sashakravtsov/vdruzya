"""Classic FB Profile page assembly — short helpers, no view bloat."""
from apps.social.albums import visible_q
from apps.social.models import Album, Education, Photo
from apps.social.services import friend_ids


def networks_for(profile, education=None) -> list[str]:
    if education is None:
        education = list(Education.objects.filter(social_user=profile)[:3])
    out = []
    if profile.city:
        out.append(profile.city)
    for e in education[:3]:
        if e.institution and e.institution not in out:
            out.append(e.institution)
    if profile.workplace and profile.workplace not in out:
        out.append(profile.workplace)
    return out


def recent_photos(profile, viewer, limit=8):
    albums = Album.objects.filter(social_user=profile).filter(visible_q(viewer))
    return list(
        Photo.objects.filter(album__in=albums).exclude(path="")
        .select_related("album").order_by("-id")[:limit]
    )


def is_friend(relation) -> bool:
    return bool(relation and relation.status == "accepted")


def can_view_full(me, profile, relation) -> bool:
    """Limited Profile: non-friends see only name/pic/networks/actions."""
    if not me or me.id == profile.id:
        return True
    vis = getattr(profile, "profile_visibility", None) or "public"
    if vis != "friends":
        return True
    return is_friend(relation)


def can_write_wall(me, profile, relation) -> bool:
    if not me:
        return False
    if me.id == profile.id:
        return True
    write = getattr(profile, "wall_write", None) or "friends"
    if write == "self":
        return False
    return is_friend(relation)


def can_view_wall(me, profile, relation) -> bool:
    if me and me.id == profile.id:
        return True
    view = getattr(profile, "wall_view", None) or "public"
    if view == "self":
        return False
    if view == "friends":
        return is_friend(relation)
    return True


def friend_tiles(me, profile, *, can_see: bool, relation, limit=6):
    """Own/friend view: friends. Visitor: mutuals first when available."""
    from apps.social import friendship as fr
    from apps.social.services import accepted_friends

    if me and me.id != profile.id and is_friend(relation):
        mutuals = list(fr.mutual_friends(me, profile, limit))
        if mutuals:
            return mutuals, True
    if can_see:
        return list(accepted_friends(profile, limit)), False
    return [], False
