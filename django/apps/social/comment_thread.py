"""Comment thread packing — vd.comment_thread stays thin."""
from __future__ import annotations

from django.urls import reverse


def _pack(c, *, can_delete, delete_url, like_url=None, me=None):
    return {
        "c": c, "can_delete": can_delete, "delete_url": delete_url,
        "like_url": like_url, "me": me,
        "n_likes": getattr(c, "n_likes", 0) or 0,
        "liked_by_me": bool(getattr(c, "liked_by_me", False)),
    }


def _attach_likes(kind, rows, me):
    if kind == "wall":
        from apps.social.likes import attach_comment_likes
        attach_comment_likes(rows, me)
    elif kind == "photo":
        from apps.social.likes import attach_photo_comment_likes
        attach_photo_comment_likes(rows, me)
    elif kind == "group":
        from apps.social.likes import attach_group_comment_likes
        attach_group_comment_likes(rows, me)


def _pack_one(c, *, kind, me, group, album, photo):
    from apps.social.services import (
        can_manage_group_comment, can_manage_photo_comment, can_manage_wall_comment,
    )
    if kind == "group":
        return _pack(
            c,
            can_delete=can_manage_group_comment(me, c, group),
            delete_url=reverse("groups.comments.delete", args=[group.id, c.id]),
            like_url=reverse("groups.comments.like", args=[group.id, c.id]) if me else None,
            me=me,
        )
    if kind == "photo":
        return _pack(
            c,
            can_delete=can_manage_photo_comment(me, c, album),
            delete_url=reverse(
                "albums.photos.comment.delete", args=[album.id, photo.id, c.id],
            ),
            like_url=reverse(
                "albums.photos.comment.like", args=[album.id, photo.id, c.id],
            ) if me else None,
            me=me,
        )
    return _pack(
        c,
        can_delete=can_manage_wall_comment(me, c),
        delete_url=reverse("comments.delete", args=[c.id]),
        like_url=reverse("comments.like", args=[c.id]),
        me=me,
    )


def build_thread(me, comments, *, preview=2, kind="wall", group=None, album=None, photo=None,
                 expand=False, next_url=""):
    rows = list(comments or [])
    _attach_likes(kind, rows, me)
    if preview is None or preview == "":
        keep = 2
    else:
        keep = int(preview)
    if expand or keep <= 0 or len(rows) <= keep:
        older, recent = [], rows
    else:
        older, recent = rows[:-keep], rows[-keep:]
    pack = lambda c: _pack_one(c, kind=kind, me=me, group=group, album=album, photo=photo)
    return {
        "older": [pack(c) for c in older],
        "recent": [pack(c) for c in recent],
        "older_n": len(older),
        "next": next_url,
        "uid": getattr(rows[0], "id", 0) if rows else 0,
    }
