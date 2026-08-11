"""Classic FB Profile page assembly — short helpers, no view bloat."""
from django.db.models import Q

from apps.social.albums import visible_q
from apps.social.forms import CommentForm, PostForm, StatusForm
from apps.social.models import (
    Album, Block, Community, Education, Experience, Friendship, Photo,
)
from apps.social.services import friend_ids, mini_feed, wall_posts_for


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
    if me and me.id == profile.id:
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


def build_context(profile, me, tab="wall"):
    """Full template context for classic Profile."""
    from apps.social import friendship as fr

    tab = tab if tab in ("wall", "info", "photos", "friends") else "wall"
    relation = blocked = None
    can_see = fr.can_see_friends(me, profile)
    if me and me.id != profile.id:
        relation = Friendship.objects.filter(
            Q(user=me, friend=profile) | Q(user=profile, friend=me)
        ).first()
        blocked = Block.objects.filter(blocker=me, blocked=profile).exists()
        mutual = fr.mutual_count(me, profile)
        mutual_text = fr.mutual_label(mutual) if mutual else ""
    else:
        mutual, mutual_text = 0, ""

    is_own = bool(me and me.id == profile.id)
    full = can_view_full(me, profile, relation)
    can_wall = can_write_wall(me, profile, relation) if full else False
    show_wall = can_view_wall(me, profile, relation) if full else False

    education = list(Education.objects.filter(social_user=profile)[:10]) if full else []
    experiences = list(Experience.objects.filter(social_user=profile)[:10]) if full else []
    friend_limit = 30 if tab == "friends" else 6
    friends, friends_are_mutual = friend_tiles(
        me, profile, can_see=can_see, relation=relation, limit=friend_limit,
    )
    photo_limit = 24 if tab == "photos" else 8
    vis_albums = Album.objects.filter(social_user=profile).filter(visible_q(me))
    return {
        "profile": profile, "me": me, "is_own": is_own, "limited": not full, "tab": tab,
        "friends": friends, "friends_are_mutual": friends_are_mutual,
        "communities": (
            list(Community.objects.filter(memberships__social_user=profile).distinct()[:12])
            if full else []
        ),
        "photos": recent_photos(profile, me, photo_limit) if full else [],
        "posts": wall_posts_for(profile, 20, viewer=me) if show_wall else [],
        "relation": relation, "blocked": blocked,
        "mutual": mutual, "mutual_text": mutual_text,
        "education": education, "experiences": experiences,
        "networks": networks_for(profile, education if full else None),
        "stats": {
            "friends": len(friend_ids(profile)),
            "photos": Photo.objects.filter(album__in=vis_albums).count(),
            "groups": (
                Community.objects.filter(memberships__social_user=profile).count() if full else 0
            ),
        },
        "form": PostForm() if can_wall else None,
        "comment_form": CommentForm() if me and show_wall else None,
        "can_wall": can_wall,
        "show_wall": show_wall,
        "can_see_friends": can_see,
        "album_photos": list(
            Photo.objects.filter(album__social_user=me).exclude(path="").order_by("-id")[:12]
        ) if me and can_wall else [],
        "mini": mini_feed(profile, viewer=me) if full else [],
        "status_form": StatusForm(initial={"headline": profile.headline or ""}) if is_own else None,
    }
