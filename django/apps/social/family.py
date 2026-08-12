"""Classic FB Family members — confirm before Info tab shows the link."""
from __future__ import annotations

from apps.social.models.legacy import FamilyLink
from apps.social.notify import push
from apps.social.services import accepted_friends, bump_news, friend_ids, now

KINDS = {
    "sibling": "Брат/сестра",
    "parent": "Родитель",
    "child": "Ребёнок",
    "spouse": "Супруг(а)",
}
MIRROR = {"sibling": "sibling", "parent": "child", "child": "parent", "spouse": "spouse"}


def label(kind: str) -> str:
    return KINDS.get(kind or "", kind or "")


def approved_for(profile, limit=20):
    if not profile:
        return []
    return list(
        FamilyLink.objects.filter(from_user=profile, status="approved")
        .select_related("to_user").order_by("id")[:limit]
    )


def incoming_for(me, limit=20):
    if not me:
        return []
    return list(
        FamilyLink.objects.filter(to_user=me, status="pending")
        .select_related("from_user").order_by("-id")[:limit]
    )


def candidates(me, limit=40):
    if not me:
        return []
    taken = set(
        FamilyLink.objects.filter(from_user=me).exclude(status="declined")
        .values_list("to_user_id", flat=True)
    )
    return list(accepted_friends(me).exclude(id__in=taken).order_by("name")[:limit])


def request(me, other_id, kind: str):
    if not me or kind not in KINDS:
        return None
    try:
        oid = int(other_id)
    except (TypeError, ValueError):
        return None
    if oid == me.id or oid not in friend_ids(me):
        return None
    existing = FamilyLink.objects.filter(from_user=me, to_user_id=oid).first()
    if existing and existing.status in ("pending", "approved"):
        return existing
    t = now()
    if existing:
        existing.kind, existing.status, existing.updated_at = kind, "pending", t
        existing.save(update_fields=["kind", "status", "updated_at"])
        row = existing
    else:
        row = FamilyLink.objects.create(
            from_user=me, to_user_id=oid, kind=kind, status="pending",
            created_at=t, updated_at=t,
        )
    push(
        oid, title="Семья",
        body=f"{me.name} указал(а) вас как: {label(kind)}",
        type="family", url=f"/profile/{me.id}",
    )
    bump_news()
    return row


def accept(me, link_id) -> bool:
    row = FamilyLink.objects.filter(
        pk=link_id, to_user=me, status="pending",
    ).select_related("from_user").first()
    if not row:
        return False
    t = now()
    row.status, row.updated_at = "approved", t
    row.save(update_fields=["status", "updated_at"])
    mirror = MIRROR.get(row.kind, "sibling")
    rev = FamilyLink.objects.filter(from_user=me, to_user=row.from_user).first()
    if rev:
        rev.kind, rev.status, rev.updated_at = mirror, "approved", t
        rev.save(update_fields=["kind", "status", "updated_at"])
    else:
        FamilyLink.objects.create(
            from_user=me, to_user=row.from_user, kind=mirror, status="approved",
            created_at=t, updated_at=t,
        )
    push(
        row.from_user_id, title="Семья",
        body=f"{me.name} подтвердил(а) семейную связь",
        type="family", url=f"/profile/{me.id}",
    )
    bump_news()
    return True


def decline(me, link_id) -> bool:
    row = FamilyLink.objects.filter(pk=link_id, to_user=me, status="pending").first()
    if not row:
        return False
    row.status, row.updated_at = "declined", now()
    row.save(update_fields=["status", "updated_at"])
    bump_news()
    return True


def remove(me, link_id) -> bool:
    row = FamilyLink.objects.filter(pk=link_id, from_user=me).first()
    if not row:
        return False
    FamilyLink.objects.filter(from_user_id=row.to_user_id, to_user=me).delete()
    row.delete()
    bump_news()
    return True
