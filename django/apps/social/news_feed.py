"""Split helpers for news feed — keep news_items short."""
from django.db.models import Count, Q

from apps.social.models import Community, CommunityMember, CommunityPost, Photo


def visible_group_q(member_ids):
    return Q(community__privacy="public") | Q(community_id__in=member_ids) | Q(community__privacy="")


def add_group_posts(items, blocked, member_ids, limit):
    qs = (
        CommunityPost.objects.select_related("social_user", "community")
        .defer("social_user__looking_for", "social_user__languages")
        .prefetch_related("poll__options", "media")
        .annotate(likes=Count("reactions", distinct=True), n_comments=Count("comments", distinct=True))
        .filter(visible_group_q(member_ids))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for p in qs[:limit]:
        items.append({"kind": "group_post", "at": p.created_at, "post": p, "actor": p.social_user, "group": p.community})


def add_joins(items, blocked, member_ids, limit):
    qs = (
        CommunityMember.objects.select_related("social_user", "community")
        .defer("social_user__looking_for", "social_user__languages")
        .filter(visible_group_q(member_ids))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for m in qs[:limit]:
        items.append({"kind": "joined", "at": m.created_at, "actor": m.social_user, "group": m.community})


def add_created(items, blocked, member_ids):
    qs = Community.objects.select_related("creator").filter(creator__isnull=False).order_by("-id")
    if blocked:
        qs = qs.exclude(creator_id__in=blocked)
    for g in qs[:20]:
        if g.privacy == "closed" and g.id not in member_ids:
            continue
        items.append({"kind": "created", "at": g.created_at, "actor": g.creator, "group": g})


def add_photos(items, blocked, limit):
    qs = (
        Photo.objects.select_related("album", "album__social_user")
        .exclude(path__isnull=True).exclude(path="")
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(album__social_user_id__in=blocked)
    for ph in qs[:limit]:
        items.append({
            "kind": "photos", "at": ph.created_at, "photo": ph,
            "actor": ph.album.social_user, "album": ph.album,
        })
