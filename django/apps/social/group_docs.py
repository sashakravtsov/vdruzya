"""Classic FB Group Docs helpers."""
from __future__ import annotations

from apps.social.models import GroupDoc, profile_related
from apps.social.services import bump_news, now


def docs_for(group, limit=40):
    return list(
        GroupDoc.objects.filter(community=group)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-id")[:limit]
    )


def doc_create(me, group, *, title, body="") -> GroupDoc | None:
    title = (title or "").strip()[:200]
    body = (body or "").strip()
    if not me or not group or not title:
        return None
    t = now()
    doc = GroupDoc.objects.create(
        community=group, social_user=me, title=title, body=body,
        created_at=t, updated_at=t,
    )
    bump_news()
    return doc


def doc_update(me, doc, *, title, body="") -> bool:
    if not me or not doc or doc.social_user_id != me.id:
        return False
    title = (title or "").strip()[:200]
    if not title:
        return False
    doc.title = title
    doc.body = (body or "").strip()
    doc.updated_at = now()
    doc.save(update_fields=["title", "body", "updated_at"])
    bump_news()
    return True


def doc_delete(me, doc, *, is_admin=False) -> bool:
    if not me or not doc:
        return False
    if doc.social_user_id != me.id and not is_admin:
        return False
    doc.delete()
    bump_news()
    return True
