"""Attach photos to wall / group posts — shared helper, no duplicates."""
from apps.social.media import save_image
from apps.social.models import CommunityPostMedia, Photo, PostMedia
from apps.social.services import now

_MAX_GROUP = 50


def _album_rows(me, album_ids, limit, make_row):
    rows = []
    for raw in (album_ids or [])[:limit]:
        if not str(raw).isdigit():
            continue
        ph = Photo.objects.filter(pk=int(raw), album__social_user=me).exclude(path="").first()
        if ph:
            rows.append(make_row(ph.path, ph.id, len(rows)))
    return rows


def attach_wall(post, files, me, album_ids=(), *, max_photos=1):
    """Profile wall note — classic FB: one photo (album pick optional filler)."""
    cap = max(0, int(max_photos))
    t, rows = now(), []
    for f in (files or [])[:cap]:
        rows.append(PostMedia(post=post, path=save_image(f, "posts"), photo_id=None, sort_order=len(rows), created_at=t))
    rows += _album_rows(
        me, album_ids, max(0, cap - len(rows)),
        lambda path, pid, i: PostMedia(post=post, path=path, photo_id=pid, sort_order=i, created_at=t),
    )
    if not rows:
        return None
    PostMedia.objects.bulk_create(rows)
    return rows[0].path


def attach_group(post, files, me, album_ids=()):
    t, rows = now(), []
    for f in (files or [])[:_MAX_GROUP]:
        rows.append(CommunityPostMedia(
            post=post, path=save_image(f, "groups"), photo_id=None,
            sort_order=len(rows), created_at=t, updated_at=t,
        ))
    rows += _album_rows(
        me, album_ids, max(0, _MAX_GROUP - len(rows)),
        lambda path, pid, i: CommunityPostMedia(
            post=post, path=path, photo_id=pid, sort_order=i, created_at=t, updated_at=t,
        ),
    )
    if not rows:
        return None
    CommunityPostMedia.objects.bulk_create(rows)
    return rows[0].path
