"""Attach photos/video to wall / group posts — shared helper, no duplicates."""
from pathlib import Path

from apps.social.media import save_image, save_video
from apps.social.models import CommunityPostMedia, PostMedia
from apps.social.services import now

_MAX_GROUP = 50
_VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v"}


def split_media_files(files):
    """Partition upload list into (images, videos)."""
    images, videos = [], []
    for f in files or []:
        name = (getattr(f, "name", "") or "").lower()
        ext = Path(name).suffix
        ctype = (getattr(f, "content_type", "") or "").lower()
        if ext in _VIDEO_EXT or ctype.startswith("video/"):
            videos.append(f)
        else:
            images.append(f)
    return images, videos


def attach_wall_video(post, upload, *, blurb: str = "") -> bool:
    """Save one video on the same media disk; set kind=video + storage: body."""
    from apps.social.classic_extra import pack_link_body

    if not upload:
        return False
    try:
        path, poster = save_video(upload, "videos")
    except Exception:
        return False
    post.kind = "video"
    post.body = pack_link_body(f"storage:{path}", blurb or "")
    post.media_path = poster
    post.save(update_fields=["kind", "body", "media_path"])
    return True


def apply_wall_uploads(post, files, me, *, max_photos=5, blurb: str = ""):
    """Apply photos and/or one video to a wall/page/event post. Returns 'video'|'photo'|None.
    Video takes priority: compose text becomes the video blurb (storage: body).
    """
    images, videos = split_media_files(files)
    if videos and attach_wall_video(post, videos[0], blurb=blurb):
        return "video"
    path = attach_wall(post, images, me, max_photos=max_photos)
    if path:
        post.media_path = path
        post.kind = "photo"
        post.save(update_fields=["media_path", "kind"])
        return "photo"
    return None


def attach_wall(post, files, me, *, max_photos=5):
    """Profile wall note — classic chrome, up to max_photos (processed via Pillow)."""
    cap = max(0, int(max_photos))
    t, rows = now(), []
    for f in (files or [])[:cap]:
        try:
            path = save_image(f, "posts")
        except Exception:
            continue
        rows.append(PostMedia(post=post, path=path, photo_id=None, sort_order=len(rows), created_at=t))
    if not rows:
        return None
    PostMedia.objects.bulk_create(rows)
    return rows[0].path


def attach_group(post, files, me):
    t, rows = now(), []
    for f in (files or [])[:_MAX_GROUP]:
        try:
            path = save_image(f, "groups")
        except Exception:
            continue
        rows.append(CommunityPostMedia(
            post=post, path=path, photo_id=None,
            sort_order=len(rows), created_at=t, updated_at=t,
        ))
    if not rows:
        return None
    CommunityPostMedia.objects.bulk_create(rows)
    return rows[0].path
