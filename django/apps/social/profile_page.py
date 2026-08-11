"""Classic FB Profile page assembly — short helpers, no view bloat."""
from django.db.models import Q

from apps.social.albums import visible_q
from apps.social.forms import CommentForm, PostForm, StatusForm
from apps.social.models import (
    Album, Block, Community, Education, Experience, Friendship, Photo,
)
from apps.social.services import friend_ids, mini_feed, wall_posts_for

TABS = frozenset({"wall", "info", "photos", "friends"})
EDIT_SECTIONS = frozenset({"basic", "contact", "personal", "eduwork", "picture", "privacy"})


def networks_for(profile, education=None) -> list[str]:
    """Classic left-rail Networks: city + schools + workplace."""
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


def profile_albums(profile, viewer, limit=12):
    return list(
        Album.objects.filter(social_user=profile).filter(visible_q(viewer)).order_by("-id")[:limit]
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


def _relation(me, profile):
    if not me or me.id == profile.id:
        return None, False, 0, ""
    from apps.social import friendship as fr

    relation = Friendship.objects.filter(
        Q(user=me, friend=profile) | Q(user=profile, friend=me)
    ).first()
    blocked = Block.objects.filter(blocker=me, blocked=profile).exists()
    mutual = fr.mutual_count(me, profile)
    return relation, blocked, mutual, (fr.mutual_label(mutual) if mutual else "")


def _info_empty(profile, education, experiences) -> bool:
    p = profile
    return not any((
        p.gender, p.birthday, p.city, p.hometown, p.relationship_status,
        p.looking_for_label(), p.interested_in_label(), p.political_views,
        p.religious_views, p.languages_label(), p.bio, p.interests, p.hobbies,
        p.favorite_music, p.favorite_movies, p.favorite_books, p.favorite_quotes,
        p.favorite_tv, p.favorite_games, education, p.education_note,
        experiences, p.workplace, p.telegram_username, p.website,
        p.show_email and getattr(p.user, "email", None),
        p.show_phone and p.phone,
    ))


def build_context(profile, me, tab="wall"):
    """Full template context for classic Profile — load only what the tab needs."""
    from apps.social import friendship as fr

    tab = tab if tab in TABS else "wall"
    relation, blocked, mutual, mutual_text = _relation(me, profile)
    can_see = fr.can_see_friends(me, profile)
    is_own = bool(me and me.id == profile.id)
    full = can_view_full(me, profile, relation)
    can_wall = can_write_wall(me, profile, relation) if full else False
    show_wall = can_view_wall(me, profile, relation) if full else False
    wall = tab == "wall" and full

    edu_rail = list(Education.objects.filter(social_user=profile)[:3])
    communities = (
        list(Community.objects.filter(memberships__social_user=profile).distinct()[:12])
        if full else []
    )
    friends_rail, friends_are_mutual = friend_tiles(
        me, profile, can_see=can_see, relation=relation, limit=6,
    )
    friends_tab = friends_rail
    if tab == "friends":
        friends_tab, _ = friend_tiles(
            me, profile, can_see=can_see, relation=relation, limit=30,
        )
    vis_albums = Album.objects.filter(social_user=profile).filter(visible_q(me))
    rail_photos = recent_photos(profile, me, 4) if full else []

    education = experiences = []
    info_empty = False
    albums = []
    if full and tab == "info":
        education = list(Education.objects.filter(social_user=profile)[:10])
        experiences = list(Experience.objects.filter(social_user=profile)[:10])
        info_empty = _info_empty(profile, education, experiences)
    if full and tab == "photos":
        albums = profile_albums(profile, me, 12)

    return {
        "profile": profile, "me": me, "is_own": is_own, "limited": not full, "tab": tab,
        "friends": friends_rail, "friends_tab": friends_tab,
        "friends_are_mutual": friends_are_mutual,
        "communities": communities,
        "rail_photos": rail_photos,
        "photos": recent_photos(profile, me, 24) if full and tab == "photos" else [],
        "albums": albums,
        "posts": wall_posts_for(profile, 20, viewer=me) if wall and show_wall else [],
        "relation": relation, "blocked": blocked,
        "mutual": mutual, "mutual_text": mutual_text,
        "education": education, "experiences": experiences,
        "info_empty": info_empty,
        "networks": networks_for(profile, edu_rail),
        "stats": {
            "friends": len(friend_ids(profile)),
            "photos": Photo.objects.filter(album__in=vis_albums).count(),
            "groups": (
                Community.objects.filter(memberships__social_user=profile).distinct().count()
                if full else 0
            ),
        },
        "form": PostForm() if wall and can_wall else None,
        "comment_form": CommentForm() if wall and me and show_wall else None,
        "can_wall": can_wall,
        "show_wall": show_wall,
        "can_see_friends": can_see,
        "mini": mini_feed(profile, viewer=me) if wall else [],
        "status_form": StatusForm(initial={"headline": profile.headline or ""}) if is_own else None,
        "wall_owner": profile,
    }
