"""FB 2009 Like — classic «Мне нравится» on wall notes (reactions table)."""
from __future__ import annotations

from django.db.models import Count

from apps.social.models.legacy import Reaction
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
