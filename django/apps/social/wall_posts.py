"""Profile wall posts — short builders; services.wall_posts_for re-exports."""
from __future__ import annotations

from django.db.models import Count, Prefetch, Q

from apps.social.models import POST_DEFER, Block, Comment, Post, profile_related
from apps.social.services import post_visible_q

_FILTERS = {
    "photos": lambda qs, profile: qs.filter(kind="photo"),
    "links": lambda qs, profile: qs.filter(kind="link"),
    "videos": lambda qs, profile: qs.filter(kind="video"),
    "shares": lambda qs, profile: qs.filter(kind="share"),
    "friends": lambda qs, profile: qs.exclude(social_user=profile),
    "mine": lambda qs, profile: qs.filter(social_user=profile),
}


def _base_qs(profile):
    key = f"wall:{profile.id}"
    return (
        Post.objects.filter(
            Q(topic=key)
            | (
                Q(social_user=profile)
                & ~Q(topic__startswith="wall:")
                & ~Q(topic__startswith="page:")
                & ~Q(topic__startswith="gift:")
            )
        )
        .exclude(kind__in=("status", "picture", "poll", "note", "gift", "checkin"))
        .exclude(topic__in=("status", "picture", "note"))
        .exclude(topic__startswith="page:")
        .exclude(topic__startswith="gift:")
        .exclude(topic__startswith="place:")
        .exclude(topic__startswith="event:")
        .select_related("social_user", "shared_post", "shared_post__social_user")
        .defer(*POST_DEFER, *profile_related("social_user__"), *profile_related("shared_post__social_user__"))
        .prefetch_related(
            "media",
            Prefetch(
                "comments",
                queryset=Comment.objects.select_related("social_user")
                .defer(*profile_related("social_user__")).order_by("id"),
            ),
        )
        .annotate(n_comments=Count("comments", distinct=True))
    )


def _apply_filter(qs, profile, wall_filter):
    fn = _FILTERS.get((wall_filter or "all").lower())
    return fn(qs, profile) if fn else qs


def _visibility(qs, profile, viewer):
    if viewer and viewer.id == profile.id:
        return qs
    qs = qs.filter(post_visible_q(viewer))
    if viewer:
        qs = qs.exclude(social_user_id__in=Block.objects.filter(blocker=viewer).values("blocked_id"))
    return qs


def _hydrate(posts, viewer):
    from apps.social.likes import attach_likes
    from apps.social.shares import attach_share_flags
    from apps.social import post_tags as ptags
    from apps.social.classic_extra import hydrate_posted

    posts = attach_likes(posts, viewer)
    attach_share_flags(posts, viewer)
    ptags.tags_for_posts(posts)
    for p in posts:
        if getattr(p, "kind", None) in ("link", "video"):
            hydrate_posted(p)
        shared = getattr(p, "shared_post", None)
        if shared and getattr(shared, "kind", None) in ("link", "video"):
            hydrate_posted(shared)
    if viewer:
        for p in posts:
            p.tag_candidates = ptags.tag_candidates(viewer, p) if ptags.can_tag(viewer, p) else []
    return posts


def wall_posts_for(profile, limit=20, viewer=None, wall_filter="all"):
    """Notes on this wall (`wall:{id}`). Legacy own posts without wall topic still listed."""
    qs = _visibility(_apply_filter(_base_qs(profile), profile, wall_filter), profile, viewer)
    return _hydrate(list(qs.order_by("-id")[:limit]), viewer)
