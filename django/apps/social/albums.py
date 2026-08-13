"""Album visibility + photo media helpers — classic FB Photos."""
from pathlib import Path

from django.conf import settings
from django.db.models import Count, Q

from apps.social.media import try_save_image
from apps.social.models import Album, Photo, PhotoComment, profile_related
from apps.social.services import friend_ids, now

_VIS = {"public": "Всем", "friends": "Друзьям", "private": "Только мне"}


def visibility_label(album_or_vis) -> str:
    raw = getattr(album_or_vis, "visibility", album_or_vis) or "friends"
    return _VIS.get(str(raw).strip().lower(), _VIS["friends"])


def visible_q(viewer):
    """Match can_view: empty/None ≡ friends (Album default)."""
    public = Q(visibility="public")
    friends = Q(visibility="friends") | Q(visibility="") | Q(visibility__isnull=True)
    if not viewer:
        return public
    return public | Q(social_user=viewer) | (friends & Q(social_user_id__in=friend_ids(viewer)))


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


def albums_with_covers(qs):
    return qs.with_covers()


def albums_for(profile, viewer, limit=40):
    """Visible albums for a profile — covers + photo count (single listing helper)."""
    return list(
        Album.objects.filter(social_user=profile)
        .visible_to(viewer)
        .with_covers()
        .annotate(n=Count("photos"))
        .order_by("-id")[:limit]
    )


def save_photos(album, files, title=""):
    """Save up to 10 photos; Pillow-process each. Returns (saved_count, skipped_count)."""
    n, skipped, label0, first_path = 0, 0, (title or "").strip(), None
    max_bytes = getattr(settings, "FILE_UPLOAD_MAX_MEMORY_SIZE", 3 * 1024 * 1024)
    for f in (files or [])[:10]:
        size = getattr(f, "size", 0) or 0
        if size > max_bytes * 4:  # allow TemporaryUploadedFile a bit over in-memory cap
            skipped += 1
            continue
        path = try_save_image(f, "photos")
        if not path:
            skipped += 1
            continue
        label = (label0 or Path(getattr(f, "name", "") or "photo").stem)[:120] or "Фото"
        Photo.objects.create(
            album=album, title=label, path=path, color="#A3D6F5",
            created_at=now(), updated_at=now(),
        )
        if first_path is None:
            first_path = path
        n += 1
    if n:
        fields = ["updated_at"]
        album.updated_at = now()
        if first_path and not album.cover_path:
            album.cover_path = first_path
            fields.append("cover_path")
        album.save(update_fields=fields)
    return n, skipped


def delete_photo_file(photo):
    from django.core.files.storage import default_storage
    PhotoComment.objects.filter(photo=photo).delete()
    if photo.path:
        try:
            default_storage.delete(photo.path)
        except Exception:
            pass
    photo.delete()


def neighbors(album, photo_id):
    ids = list(album.photos.order_by("id").values_list("id", flat=True))
    if photo_id not in ids:
        return None, None, 0, 0
    i = ids.index(photo_id)
    return (
        ids[i - 1] if i > 0 else None,
        ids[i + 1] if i + 1 < len(ids) else None,
        len(ids),
        i + 1,
    )


def comments_for(photo, limit=80):
    return list(
        PhotoComment.objects.filter(photo=photo)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("id")[:limit]
    )


def add_comment(me, photo, album, body: str):
    body = (body or "").strip()[:1000]
    if not me or not body or not can_view(album, me):
        return None
    return PhotoComment.objects.create(photo=photo, social_user=me, body=body, created_at=now())


def delete_comment(me, comment: PhotoComment, album) -> bool:
    if not me or not comment:
        return False
    if comment.social_user_id != me.id and not can_edit(album, me):
        return False
    comment.delete()
    return True
