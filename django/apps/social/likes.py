"""FB 2009 Like — one attach/toggle core for all reaction tables."""
from __future__ import annotations

from django.db.models import Count

from apps.social.models.legacy import (
    CommentReaction, GroupCommentReaction, GroupPostReaction,
    PhotoCommentReaction, PhotoReaction, Reaction,
)
from apps.social.services import bump_news, now


def _attach(rows, model, fk: str, viewer=None):
    rows = list(rows or [])
    ids = [r.id for r in rows if getattr(r, "id", None)]
    counts = dict.fromkeys(ids, 0)
    mine: set = set()
    if ids:
        for row in (
            model.objects.filter(**{f"{fk}__in": ids}, type="like")
            .values(fk).annotate(n=Count("id"))
        ):
            counts[row[fk]] = row["n"]
        if viewer:
            mine = set(
                model.objects.filter(
                    **{f"{fk}__in": ids}, social_user=viewer, type="like",
                ).values_list(fk, flat=True)
            )
    for r in rows:
        r.n_likes = counts.get(r.id, 0)
        r.liked_by_me = r.id in mine
    return rows


def _toggle(me, obj, model, fk: str) -> str:
    if not me or not obj:
        return ""
    q = {fk: obj, "social_user": me, "type": "like"}
    row = model.objects.filter(**q).first()
    if row:
        row.delete()
        bump_news()
        return "unliked"
    model.objects.create(**{fk: obj, "social_user": me, "type": "like", "created_at": now()})
    bump_news()
    return "liked"


def attach_likes(posts, viewer=None):
    rows = _attach(posts, Reaction, "post_id", viewer)
    try:
        from apps.social import era2014 as e14
        e14.attach_saves(rows, viewer)
    except Exception:
        for r in rows:
            if not hasattr(r, "saved_by_me"):
                r.saved_by_me = False
    return rows


def toggle_like(me, post) -> str:
    return _toggle(me, post, Reaction, "post")


def like_count(post) -> int:
    return Reaction.objects.filter(post=post, type="like").count()


def attach_photo_likes(photos, viewer=None):
    return _attach(photos, PhotoReaction, "photo_id", viewer)


def toggle_photo_like(me, photo) -> str:
    return _toggle(me, photo, PhotoReaction, "photo")


def attach_comment_likes(comments, viewer=None):
    return _attach(comments, CommentReaction, "comment_id", viewer)


def toggle_comment_like(me, comment) -> str:
    return _toggle(me, comment, CommentReaction, "comment")


def attach_photo_comment_likes(comments, viewer=None):
    return _attach(comments, PhotoCommentReaction, "comment_id", viewer)


def toggle_photo_comment_like(me, comment) -> str:
    return _toggle(me, comment, PhotoCommentReaction, "comment")


def attach_group_comment_likes(comments, viewer=None):
    return _attach(comments, GroupCommentReaction, "comment_id", viewer)


def toggle_group_comment_like(me, comment) -> str:
    return _toggle(me, comment, GroupCommentReaction, "comment")


def attach_group_post_likes(posts, viewer=None):
    return _attach(posts, GroupPostReaction, "post_id", viewer)


def toggle_group_post_like(me, post) -> str:
    return _toggle(me, post, GroupPostReaction, "post")
