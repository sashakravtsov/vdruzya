"""Classic FB share-to-wall (repost) — uses posts.shared_post_id."""
from __future__ import annotations

from apps.social.models import Post
from apps.social.services import bump_news, now, post_visible_q


def can_share(me, post) -> bool:
    if not me or not post:
        return False
    if post.social_user_id == me.id:
        return False
    kind = getattr(post, "kind", None) or ""
    if kind in ("status", "picture", "gift", "checkin"):
        return False
    return Post.objects.filter(pk=post.id).filter(post_visible_q(me)).exists()


def root_post(post):
    """Unwrap one level of share to the original note."""
    if getattr(post, "kind", None) == "share" and getattr(post, "shared_post_id", None):
        return post.shared_post or post
    return post


def share_to_wall(me, post, blurb="") -> Post | None:
    if not can_share(me, post):
        return None
    src = root_post(post)
    t = now()
    blurb = (blurb or "").strip()[:2000]
    shared = Post.objects.create(
        social_user=me,
        body=blurb,
        kind="share",
        topic=f"wall:{me.id}",
        visibility="friends",
        shared_post=src,
        media_label=(src.media_label or "")[:255] or None,
        created_at=t,
        updated_at=t,
    )
    bump_news()
    return shared


def attach_share_flags(posts, viewer=None):
    """Set post.can_share for wall/permalink actions."""
    posts = list(posts or [])
    for p in posts:
        p.can_share = bool(
            viewer
            and p.social_user_id != viewer.id
            and (getattr(p, "kind", None) or "") not in ("status", "picture", "gift", "checkin")
        )
    return posts
