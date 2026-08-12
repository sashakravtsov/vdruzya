"""Attach photos to wall / group posts — shared helper, no duplicates."""
from apps.social.media import save_image
from apps.social.models import CommunityPostMedia, PostMedia
from apps.social.services import now

_MAX_GROUP = 50


def attach_wall(post, files, me, *, max_photos=1):
    """Profile wall note — classic FB: one uploaded photo."""
    cap = max(0, int(max_photos))
    t, rows = now(), []
    for f in (files or [])[:cap]:
        rows.append(PostMedia(post=post, path=save_image(f, "posts"), photo_id=None, sort_order=len(rows), created_at=t))
    if not rows:
        return None
    PostMedia.objects.bulk_create(rows)
    return rows[0].path


def attach_group(post, files, me):
    t, rows = now(), []
    for f in (files or [])[:_MAX_GROUP]:
        rows.append(CommunityPostMedia(
            post=post, path=save_image(f, "groups"), photo_id=None,
            sort_order=len(rows), created_at=t, updated_at=t,
        ))
    if not rows:
        return None
    CommunityPostMedia.objects.bulk_create(rows)
    return rows[0].path
