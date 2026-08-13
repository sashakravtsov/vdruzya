"""Friendship page / shared / anniversaries — friendship re-exports."""
from __future__ import annotations

from django.db.models import Q

from apps.social.models import Friendship


def friends_since(a, b):
    """When friendship became accepted (max created_at of accepted pair)."""
    if not a or not b or a.id == b.id:
        return None
    dates = [
        d for d in Friendship.objects.filter(
            Q(user=a, friend=b) | Q(user=b, friend=a),
            status="accepted",
        ).values_list("created_at", flat=True)
        if d
    ]
    return max(dates) if dates else None


def shared_groups(a, b, limit=12):
    if not a or not b:
        return []
    from apps.social.models import Community, CommunityMember
    ids_a = set(
        CommunityMember.objects.filter(social_user=a).values_list("community_id", flat=True)
    )
    ids_b = set(
        CommunityMember.objects.filter(social_user=b).values_list("community_id", flat=True)
    )
    shared = ids_a & ids_b
    if not shared:
        return []
    return list(Community.objects.filter(id__in=shared).order_by("name")[:limit])


def shared_photos(a, b, limit=12):
    """Photos where both people are tagged."""
    if not a or not b:
        return []
    from apps.social.models import Photo, PhotoTag
    ids = (
        PhotoTag.objects.filter(social_user=a, status="approved")
        .filter(photo_id__in=PhotoTag.objects.filter(social_user=b, status="approved").values("photo_id"))
        .values_list("photo_id", flat=True)
        .distinct()[:limit]
    )
    photos = list(
        Photo.objects.filter(id__in=ids)
        .select_related("album", "album__social_user")
        .order_by("-id")[:limit]
    )
    return photos


def friendship_page(me, other):
    """Bundle for classic «Смотреть дружбу» page."""
    from apps.social.friendship import mutual_count, mutual_friends, relation_of
    since = friends_since(me, other)
    mutual = mutual_friends(me, other, limit=24)
    rel = relation_of(me, other)
    return {
        "since": since,
        "mutual": mutual,
        "mutual_count": mutual_count(me, other),
        "groups": shared_groups(me, other),
        "photos": shared_photos(me, other),
        "are_friends": bool(rel and rel.status == "accepted"),
    }


def upcoming_anniversaries(viewer=None, days=30, limit=20):
    """Friends whose friendship anniversary falls in the next `days`."""
    from datetime import datetime, timedelta
    from django.utils import timezone

    if not viewer:
        return []
    today = timezone.localdate()
    end = today + timedelta(days=days)
    rows = list(
        Friendship.objects.filter(user=viewer, status="accepted")
        .exclude(friend=viewer)
        .select_related("friend")
        .order_by("id")
    )
    out = []
    for row in rows:
        since = friends_since(viewer, row.friend)
        if not since:
            continue
        if isinstance(since, datetime):
            if timezone.is_aware(since):
                d = timezone.localtime(since).date()
            else:
                d = since.date()
        else:
            d = since
        if d.year >= today.year:
            continue  # not yet a year
        try:
            ann = d.replace(year=today.year)
        except ValueError:
            ann = d.replace(year=today.year, day=28)  # Feb 29
        if ann < today:
            try:
                ann = d.replace(year=today.year + 1)
            except ValueError:
                ann = d.replace(year=today.year + 1, day=28)
        if today <= ann <= end:
            years = ann.year - d.year
            if years >= 1:
                out.append((ann, years, row.friend, d))
    out.sort(key=lambda x: x[0])
    return out[:limit]


