"""Mini-Feed side stories (joins, photos, tags, gifts) — mini_feed imports."""
from __future__ import annotations

from django.db.models import F, Q

from apps.social.models import Community, CommunityMember, Friendship


def _side_items(profile, limit: int) -> list[dict]:
    from apps.social.models import CompanyFollower, OgStory, Photo, PhotoTag
    from apps.social.era2011 import og_label
    from apps.social.gifts import attach_stickers, gifts_for

    out = []
    for m in (
        CommunityMember.objects.filter(social_user=profile)
        .select_related("community").order_by("-id")[:limit]
    ):
        out.append({"kind": "joined", "at": m.created_at, "group": m.community})
    for g in Community.objects.filter(creator=profile).order_by("-id")[:4]:
        out.append({"kind": "created", "at": g.created_at, "group": g})
    for fan in (
        CompanyFollower.objects.filter(social_user=profile)
        .select_related("company").order_by("-id")[:limit]
    ):
        out.append({"kind": "fan", "at": fan.created_at, "page": fan.company})
    for ph in (
        Photo.objects.filter(album__social_user=profile).exclude(path="")
        .select_related("album").order_by("-id")[:limit]
    ):
        out.append({"kind": "photo", "at": ph.created_at, "photo": ph, "album": ph.album})
    for tag in (
        PhotoTag.objects.filter(social_user=profile, status="approved")
        .select_related("photo", "photo__album", "tagged_by")
        .order_by("-id")[:limit]
    ):
        out.append({
            "kind": "tagged", "at": tag.created_at, "photo": tag.photo,
            "album": tag.photo.album, "by": tag.tagged_by,
        })
    for f in (
        Friendship.objects.filter(status="accepted")
        .filter(Q(user=profile) | Q(friend=profile))
        # Bidirectional edges (A↔B) — one story per pair, same as news_stories.
        .filter(user_id__lt=F("friend_id"))
        .select_related("user", "friend")
        .order_by("-updated_at", "-id")[:limit]
    ):
        other = f.friend if f.user_id == profile.id else f.user
        out.append({"kind": "friend", "at": f.updated_at or f.created_at, "other": other})
    for og in OgStory.objects.filter(social_user=profile).order_by("-id")[:limit]:
        out.append({
            "kind": "og", "at": og.created_at, "og": og,
            "verb_label": og_label(og.verb),
        })
    for gp in attach_stickers(gifts_for(profile, limit=limit)):
        out.append({
            "kind": "gift_got", "at": gp.created_at, "post": gp,
            "from": gp.social_user, "sticker": getattr(gp, "gift_sticker", None),
        })
    return out


