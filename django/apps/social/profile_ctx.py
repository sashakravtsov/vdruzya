"""Profile show context — short builders; profile_page.build_context re-exports."""
from __future__ import annotations

from django.db.models import Q

from apps.social.albums import albums_for
from apps.social.compose_ui import editor_context
from apps.social.forms import CommentForm, NoteForm, PostForm, StatusForm
from apps.social.models import (
    Album, Community, Company, Education, Experience, Photo, Place,
)
from apps.social.profile_page import (
    TABS, can_view_full, can_view_wall, can_write_wall, friend_tiles,
    info_boxes, networks_for, recent_photos, _relation,
)
from apps.social.services import friend_count, mini_feed, notes_for, wall_posts_for
from apps.social import gifts as gf


def _norm(tab, photos_view, wall_filter):
    tab = tab if tab in TABS else "wall"
    photos_view = (photos_view or "albums").lower()
    if photos_view not in ("albums", "of"):
        photos_view = "albums"
    if wall_filter not in ("all", "photos", "links", "videos", "shares", "friends", "mine"):
        wall_filter = "all"
    return tab, photos_view, wall_filter


def _access(me, profile):
    from apps.social import friendship as fr

    relation, blocked, mutual, mutual_text = _relation(me, profile)
    can_see = fr.can_see_friends(me, profile)
    is_own = bool(me and me.id == profile.id)
    full = can_view_full(me, profile, relation)
    can_wall = can_write_wall(me, profile, relation) if full else False
    show_wall = can_view_wall(me, profile, relation) if full else False
    return {
        "relation": relation, "blocked": blocked, "mutual": mutual,
        "mutual_text": mutual_text, "can_see": can_see, "is_own": is_own,
        "full": full, "can_wall": can_wall, "show_wall": show_wall,
    }


def _info_rails(profile, full, tab):
    if full and tab == "info":
        education = list(Education.objects.filter(social_user=profile)[:10])
        experiences = list(Experience.objects.filter(social_user=profile)[:10])
        return education, experiences, info_boxes(profile, education, experiences), education[:3], experiences[:5]
    edu_rail = list(Education.objects.filter(social_user=profile)[:3])
    exp_rail = list(
        Experience.objects.filter(social_user=profile).exclude(company_name="").order_by("-id")[:5]
    )
    return [], [], [], edu_rail, exp_rail


def _social(me, profile, *, full, can_see, relation, tab):
    communities = (
        list(Community.objects.filter(memberships__social_user=profile).distinct()[:12])
        if full else []
    )
    pages = (
        list(
            Company.objects.filter(
                Q(followers__social_user=profile) | Q(admins__social_user=profile)
            ).distinct().order_by("name")[:12]
        ) if full else []
    )
    friends_rail, friends_are_mutual = friend_tiles(
        me, profile, can_see=can_see, relation=relation, limit=6, prefer_mutual=True,
    )
    if tab == "friends":
        friends_tab, _ = friend_tiles(
            me, profile, can_see=can_see, relation=relation, limit=30, prefer_mutual=False,
        )
    else:
        friends_tab = friends_rail
    return communities, pages, friends_rail, friends_are_mutual, friends_tab


def _photos_notes(profile, me, *, full, tab, photos_view):
    vis = Album.objects.filter(social_user=profile).visible_to(me) if full else Album.objects.none()
    rail = recent_photos(profile, me, 4) if full else []
    albums = albums_for(profile, me, 12) if full and tab == "photos" else []
    tagged = []
    if full and tab == "photos" and photos_view == "of":
        from apps.social.photo_tags import photos_of
        tagged = photos_of(profile, me, limit=40)
    notes = notes_for(profile, 20, viewer=me) if full and tab == "notes" else []
    return vis, rail, albums, tagged, notes


def _follow_timeline(me, profile, *, full, is_own, tab):
    from apps.social import era2011 as e11

    following = e11.is_following(me, profile) if me and not is_own else False
    n_followers = e11.follow_count(profile) if full else 0
    n_following = e11.following_count(profile) if full and is_own else 0
    timeline = {}
    if full and tab == "timeline":
        try:
            y = int(getattr(profile, "_timeline_year", 0) or 0) or None
        except (TypeError, ValueError):
            y = None
        timeline = e11.timeline_bundle(profile, me, year=y)
        timeline["milestone_kinds"] = e11.MILESTONE_KINDS
    return following, n_followers, n_following, timeline


def _stats(profile, *, can_see, full, vis_albums, n_followers, n_following):
    return {
        "friends": friend_count(profile) if can_see else 0,
        "photos": Photo.objects.filter(album__in=vis_albums).count() if full else 0,
        "groups": (
            Community.objects.filter(memberships__social_user=profile).distinct().count()
            if full else 0
        ),
        "pages": (
            Company.objects.filter(
                Q(followers__social_user=profile) | Q(admins__social_user=profile)
            ).distinct().count() if full else 0
        ),
        "followers": n_followers,
        "following": n_following,
    }


def build_context(profile, me, tab="wall", photos_view="albums", wall_filter="all"):
    """Full template context for classic Profile — load only what the tab needs."""
    tab, photos_view, wall_filter = _norm(tab, photos_view, wall_filter)
    a = _access(me, profile)
    wall = tab == "wall" and a["full"]
    education, experiences, boxes, edu_rail, exp_rail = _info_rails(profile, a["full"], tab)
    communities, pages, friends_rail, friends_are_mutual, friends_tab = _social(
        me, profile, full=a["full"], can_see=a["can_see"], relation=a["relation"], tab=tab,
    )
    vis_albums, rail_photos, albums, tagged_photos, notes = _photos_notes(
        profile, me, full=a["full"], tab=tab, photos_view=photos_view,
    )
    gifts = gf.attach_stickers(gf.gifts_for(profile, limit=12)) if wall and a["show_wall"] else []
    following, n_followers, n_following, timeline = _follow_timeline(
        me, profile, full=a["full"], is_own=a["is_own"], tab=tab,
    )
    return {
        "profile": profile, "me": me, "is_own": a["is_own"], "limited": not a["full"], "tab": tab,
        "friends": friends_rail, "friends_tab": friends_tab,
        "friends_are_mutual": friends_are_mutual,
        "communities": communities, "pages": pages,
        "rail_photos": rail_photos, "albums": albums,
        "photos_view": photos_view, "tagged_photos": tagged_photos,
        "notes": notes, "gifts": gifts,
        "note_form": NoteForm() if a["is_own"] and tab == "notes" else None,
        "posts": wall_posts_for(profile, 20, viewer=me, wall_filter=wall_filter) if wall and a["show_wall"] else [],
        "wall_filter": wall_filter,
        "relation": a["relation"], "blocked": a["blocked"],
        "mutual": a["mutual"], "mutual_text": a["mutual_text"],
        "info_boxes": boxes,
        "networks": networks_for(profile, edu_rail, exp_rail),
        "stats": _stats(
            profile, can_see=a["can_see"], full=a["full"], vis_albums=vis_albums,
            n_followers=n_followers, n_following=n_following,
        ),
        "form": PostForm(simple=True) if wall and a["can_wall"] else None,
        "comment_form": CommentForm() if ((wall and me and a["show_wall"]) or (tab == "notes" and me)) else None,
        **editor_context(stickers=False),
        "can_wall": a["can_wall"], "show_wall": a["show_wall"],
        "can_see_friends": a["can_see"],
        "mini": mini_feed(profile, viewer=me) if wall else [],
        "status_form": (
            StatusForm(
                initial={"headline": profile.headline or ""},
                places=list(Place.objects.order_by("name")[:80]),
            ) if a["is_own"] else None
        ),
        "is_following": following,
        **timeline,
    }
