"""Classic FB photo tags — Photos of Me + tag approval (mid-2006 / ~2009)."""
from __future__ import annotations

from apps.social.albums import can_edit, can_view, visible_q
from apps.social.models import Album, Photo, PhotoTag, SocialProfile, profile_related
from apps.social.notify import push
from apps.social.services import accepted_friends, bump_news, friend_ids, now


def tags_for(photo, limit=40):
    return list(
        PhotoTag.objects.filter(photo=photo)
        .select_related("social_user", "tagged_by")
        .defer(*profile_related("social_user__"), *profile_related("tagged_by__"))
        .order_by("id")[:limit]
    )


def can_tag(me, album) -> bool:
    """Album owner or a friend who can see the album may tag."""
    if not me or not album:
        return False
    if can_edit(album, me):
        return True
    if not can_view(album, me):
        return False
    return album.social_user_id in friend_ids(me)


def can_untag(me, tag, album) -> bool:
    if not me or not tag:
        return False
    if tag.social_user_id == me.id:
        return True
    if tag.tagged_by_id == me.id:
        return True
    return can_edit(album, me)


def tag_candidates(me, photo, limit=40):
    """Friends of tagger not already tagged on this photo."""
    if not me:
        return []
    taken = set(PhotoTag.objects.filter(photo=photo).values_list("social_user_id", flat=True))
    return list(
        accepted_friends(me).exclude(id__in=taken).order_by("name")[:limit]
    )


def add_tag(me, photo, album, person_id: int):
    if not can_tag(me, album):
        return None
    try:
        person_id = int(person_id)
    except (TypeError, ValueError):
        return None
    existing = PhotoTag.objects.filter(photo=photo, social_user_id=person_id).first()
    if existing:
        return existing
    if person_id not in friend_ids(me) and person_id != me.id:
        return None
    person = SocialProfile.objects.filter(pk=person_id).first()
    if not person:
        return None
    t = now()
    # Self-tag is approved; tagging someone else needs their confirmation.
    status = "approved" if person_id == me.id else "pending"
    tag = PhotoTag.objects.create(
        photo=photo, social_user=person, tagged_by=me, status=status, created_at=t,
    )
    if person_id != me.id:
        push(
            person_id,
            title="Отметка на фото",
            body=f"{me.name} отметил(а) вас на фото — подтвердите",
            type="photo_tag",
            url=f"/albums/{album.id}/photos/{photo.id}",
        )
    bump_news()
    return tag


def remove_tag(me, tag, album) -> bool:
    if not can_untag(me, tag, album):
        return False
    tag.delete()
    bump_news()
    return True


def pending_for(me, limit=20):
    if not me:
        return []
    return list(
        PhotoTag.objects.filter(social_user=me, status="pending")
        .select_related("photo", "photo__album", "tagged_by")
        .defer(*profile_related("tagged_by__"), *profile_related("photo__album__social_user__"))
        .order_by("-id")[:limit]
    )


def approve(me, tag_id) -> bool:
    tag = (
        PhotoTag.objects.filter(pk=tag_id, social_user=me, status="pending")
        .select_related("photo", "photo__album", "tagged_by")
        .first()
    )
    if not tag:
        return False
    tag.status = "approved"
    tag.save(update_fields=["status"])
    if tag.tagged_by_id and tag.tagged_by_id != me.id:
        push(
            tag.tagged_by_id,
            title="Отметка на фото",
            body=f"{me.name} подтвердил(а) отметку на фото",
            type="photo_tag",
            url=f"/albums/{tag.photo.album_id}/photos/{tag.photo_id}",
        )
    bump_news()
    return True


def decline(me, tag_id) -> bool:
    tag = PhotoTag.objects.filter(pk=tag_id, social_user=me, status="pending").first()
    if not tag:
        return False
    tag.delete()
    bump_news()
    return True


def photos_of(profile, viewer, limit=40):
    """Photos where profile is tagged (approved) and viewer may see the album."""
    album_ids = list(
        PhotoTag.objects.filter(social_user=profile, status="approved")
        .values_list("photo__album_id", flat=True)[:300]
    )
    if not album_ids:
        return []
    visible = set(
        Album.objects.filter(id__in=album_ids).filter(visible_q(viewer)).values_list("id", flat=True)
    )
    if not visible:
        return []
    # Avoid DISTINCT over SocialProfile JSON columns (PG has no json equality).
    photo_ids = list(
        PhotoTag.objects.filter(
            social_user=profile, status="approved", photo__album_id__in=visible,
        )
        .exclude(photo__path="")
        .order_by("-photo_id")
        .values_list("photo_id", flat=True)[: limit * 3]
    )
    seen, ordered = set(), []
    for pid in photo_ids:
        if pid in seen:
            continue
        seen.add(pid)
        ordered.append(pid)
        if len(ordered) >= limit:
            break
    if not ordered:
        return []
    by_id = {
        p.id: p
        for p in Photo.objects.filter(id__in=ordered)
        .select_related("album", "album__social_user")
        .defer(*profile_related("album__social_user__"))
    }
    return [by_id[i] for i in ordered if i in by_id]
