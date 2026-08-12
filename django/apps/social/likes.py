"""FB 2009 Like — wall posts, photos, and wall comments."""
from __future__ import annotations

from django.db.models import Count

from apps.social.models.legacy import CommentReaction, PhotoReaction, Reaction
from apps.social.services import bump_news, now


def attach_likes(posts, viewer=None):
    """Set post.n_likes and post.liked_by_me on each post."""
    posts = list(posts or [])
    ids = [p.id for p in posts if getattr(p, "id", None)]
    counts = {p.id: 0 for p in posts}
    mine = set()
    if ids:
        for row in (
            Reaction.objects.filter(post_id__in=ids, type="like")
            .values("post_id")
            .annotate(n=Count("id"))
        ):
            counts[row["post_id"]] = row["n"]
        if viewer:
            mine = set(
                Reaction.objects.filter(post_id__in=ids, social_user=viewer, type="like")
                .values_list("post_id", flat=True)
            )
    for p in posts:
        p.n_likes = counts.get(p.id, 0)
        p.liked_by_me = p.id in mine
    return posts


def toggle_like(me, post) -> str:
    """Return 'liked' | 'unliked' | ''."""
    if not me or not post:
        return ""
    existing = Reaction.objects.filter(post=post, social_user=me, type="like").first()
    if existing:
        existing.delete()
        bump_news()
        return "unliked"
    Reaction.objects.create(
        post=post, social_user=me, type="like", created_at=now(),
    )
    bump_news()
    return "liked"


def like_count(post) -> int:
    return Reaction.objects.filter(post=post, type="like").count()


def attach_photo_likes(photos, viewer=None):
    photos = list(photos or [])
    ids = [p.id for p in photos if getattr(p, "id", None)]
    counts = {p.id: 0 for p in photos}
    mine = set()
    if ids:
        for row in (
            PhotoReaction.objects.filter(photo_id__in=ids, type="like")
            .values("photo_id")
            .annotate(n=Count("id"))
        ):
            counts[row["photo_id"]] = row["n"]
        if viewer:
            mine = set(
                PhotoReaction.objects.filter(photo_id__in=ids, social_user=viewer, type="like")
                .values_list("photo_id", flat=True)
            )
    for p in photos:
        p.n_likes = counts.get(p.id, 0)
        p.liked_by_me = p.id in mine
    return photos


def toggle_photo_like(me, photo) -> str:
    if not me or not photo:
        return ""
    existing = PhotoReaction.objects.filter(photo=photo, social_user=me, type="like").first()
    if existing:
        existing.delete()
        bump_news()
        return "unliked"
    PhotoReaction.objects.create(
        photo=photo, social_user=me, type="like", created_at=now(),
    )
    bump_news()
    return "liked"


def attach_comment_likes(comments, viewer=None):
    comments = list(comments or [])
    ids = [c.id for c in comments if getattr(c, "id", None)]
    counts = {c.id: 0 for c in comments}
    mine = set()
    if ids:
        for row in (
            CommentReaction.objects.filter(comment_id__in=ids, type="like")
            .values("comment_id")
            .annotate(n=Count("id"))
        ):
            counts[row["comment_id"]] = row["n"]
        if viewer:
            mine = set(
                CommentReaction.objects.filter(comment_id__in=ids, social_user=viewer, type="like")
                .values_list("comment_id", flat=True)
            )
    for c in comments:
        c.n_likes = counts.get(c.id, 0)
        c.liked_by_me = c.id in mine
    return comments


def toggle_comment_like(me, comment) -> str:
    if not me or not comment:
        return ""
    existing = CommentReaction.objects.filter(comment=comment, social_user=me, type="like").first()
    if existing:
        existing.delete()
        bump_news()
        return "unliked"
    CommentReaction.objects.create(
        comment=comment, social_user=me, type="like", created_at=now(),
    )
    bump_news()
    return "liked"
