"""Wall post person-tags — classic «с: Имя»."""
from __future__ import annotations

from apps.social.models import PostTag, SocialProfile, profile_related
from apps.social.services import bump_news, friend_ids, now


def tags_for_posts(posts):
    """Attach post.post_people list for each post."""
    posts = list(posts or [])
    ids = [p.id for p in posts if getattr(p, "id", None)]
    by_post = {i: [] for i in ids}
    if ids:
        rows = (
            PostTag.objects.filter(post_id__in=ids)
            .select_related("social_user")
            .defer(*profile_related("social_user__"))
            .order_by("id")
        )
        for t in rows:
            by_post.setdefault(t.post_id, []).append(t)
    for p in posts:
        p.post_people = by_post.get(p.id, [])
    return posts


def tag_candidates(me, post, limit=40):
    if not me or not post:
        return []
    taken = set(PostTag.objects.filter(post=post).values_list("social_user_id", flat=True))
    taken.add(post.social_user_id)
    fids = friend_ids(me) - taken
    if not fids:
        return []
    return list(
        SocialProfile.objects.filter(id__in=fids)
        .defer(*profile_related())
        .order_by("name")[:limit]
    )


def can_tag(me, post) -> bool:
    if not me or not post:
        return False
    if me.id == post.social_user_id:
        return True
    from apps.social.services import wall_owner_id
    oid = wall_owner_id(post)
    return bool(oid and oid == me.id)


def add_tag(me, post, person_id) -> PostTag | None:
    if not can_tag(me, post):
        return None
    try:
        person_id = int(person_id)
    except (TypeError, ValueError):
        return None
    if person_id == post.social_user_id:
        return None
    if person_id not in friend_ids(me) and person_id != me.id:
        return None
    person = SocialProfile.objects.filter(pk=person_id).first()
    if not person:
        return None
    existing = PostTag.objects.filter(post=post, social_user=person).first()
    if existing:
        return existing
    tag = PostTag.objects.create(
        post=post, social_user=person, tagged_by=me, created_at=now(),
    )
    bump_news()
    return tag


def remove_tag(me, tag) -> bool:
    if not me or not tag:
        return False
    post = tag.post
    if me.id not in (tag.social_user_id, tag.tagged_by_id, getattr(post, "social_user_id", None)):
        return False
    tag.delete()
    bump_news()
    return True
