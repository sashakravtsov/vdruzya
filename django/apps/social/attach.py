"""Attach photos to wall / group posts — shared helper, no duplicates."""
from apps.social.media import save_image
from apps.social.models import CommunityPostMedia, Photo, PostMedia
from apps.social.services import now

_MAX = 10


def _album_rows(me, album_ids, limit, make_row):
    rows = []
    for raw in (album_ids or [])[:limit]:
        if not str(raw).isdigit():
            continue
        ph = Photo.objects.filter(pk=int(raw), album__social_user=me).exclude(path="").first()
        if ph:
            rows.append(make_row(ph.path, ph.id, len(rows)))
    return rows


def attach_wall(post, files, me, album_ids=()):
    t, rows = now(), []
    for f in (files or [])[:_MAX]:
        rows.append(PostMedia(post=post, path=save_image(f, "posts"), photo_id=None, sort_order=len(rows), created_at=t))
    rows += _album_rows(
        me, album_ids, max(0, _MAX - len(rows)),
        lambda path, pid, i: PostMedia(post=post, path=path, photo_id=pid, sort_order=i, created_at=t),
    )
    if not rows:
        return None
    PostMedia.objects.bulk_create(rows)
    return rows[0].path


def attach_group(post, files, me, album_ids=()):
    t, rows = now(), []
    for f in files or []:
        rows.append(CommunityPostMedia(
            post=post, path=save_image(f, "groups"), photo_id=None,
            sort_order=len(rows), created_at=t, updated_at=t,
        ))
    rows += _album_rows(
        me, album_ids, 50,
        lambda path, pid, i: CommunityPostMedia(
            post=post, path=path, photo_id=pid, sort_order=i, created_at=t, updated_at=t,
        ),
    )
    if not rows:
        return None
    CommunityPostMedia.objects.bulk_create(rows)
    return rows[0].path
