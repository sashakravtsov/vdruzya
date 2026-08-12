"""Album visibility + photo media helpers."""
from pathlib import Path

from django.conf import settings
from django.db.models import Q

from apps.social.media import save_image
from apps.social.models import Photo, PhotoComment, profile_related
from apps.social.services import friend_ids, now


def visible_q(viewer):
    if not viewer:
        return Q(visibility="public")
    return (
        Q(visibility="public")
        | Q(social_user=viewer)
        | Q(visibility="friends", social_user_id__in=friend_ids(viewer))
    )


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


def save_photos(album, files, title=""):
    n, label0, first_path = 0, (title or "").strip(), None
    for f in (files or [])[:10]:
        if getattr(f, "size", 0) > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
            continue
        path = save_image(f, "photos")
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
    return n


def albums_with_covers(qs):
    """Annotate first photo path so cover_url works when cover_path is empty."""
    from django.db.models import OuterRef, Subquery

    first = (
        Photo.objects.filter(album_id=OuterRef("pk"))
        .exclude(path="")
        .order_by("id")
        .values("path")[:1]
    )
    return qs.annotate(_first_photo_path=Subquery(first))


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
