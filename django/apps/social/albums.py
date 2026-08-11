"""Album visibility + photo media helpers."""
from pathlib import Path

from django.conf import settings
from django.db.models import Q

from apps.social.media import save_image
from apps.social.models import Photo
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
    n, label0 = 0, (title or "").strip()
    for f in (files or [])[:10]:
        if getattr(f, "size", 0) > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
            continue
        path = save_image(f, "photos")
        label = (label0 or Path(getattr(f, "name", "") or "photo").stem)[:120] or "Фото"
        Photo.objects.create(
            album=album, title=label, path=path, color="#A3D6F5",
            created_at=now(), updated_at=now(),
        )
        n += 1
    if n:
        album.updated_at = now()
        album.save(update_fields=["updated_at"])
    return n


def delete_photo_file(photo):
    from django.core.files.storage import default_storage
    if photo.path:
        try:
            default_storage.delete(photo.path)
        except Exception:
            pass
    photo.delete()


def neighbors(album, photo_id, limit=120):
    ids = list(album.photos.order_by("id").values_list("id", flat=True)[:limit])
    if photo_id not in ids:
        return None, None, 0, 0
    i = ids.index(photo_id)
    return (
        ids[i - 1] if i > 0 else None,
        ids[i + 1] if i + 1 < len(ids) else None,
        len(ids),
        i + 1,
    )
