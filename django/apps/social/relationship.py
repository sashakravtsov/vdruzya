"""Classic FB relationship confirmation — partner must accept."""
from __future__ import annotations

from apps.social.models import RelationshipRequest
from apps.social.notify import push
from apps.social.services import bump_news, now


PARTNER_STATUSES = frozenset({
    "in_a_relationship", "engaged", "married", "complicated",
})


def pending_for(profile) -> RelationshipRequest | None:
    if not profile or not profile.relationship_with_id:
        return None
    return (
        RelationshipRequest.objects.filter(
            requester=profile, partner_id=profile.relationship_with_id, status="pending",
        ).first()
    )


def incoming_for(me, limit=20):
    if not me:
        return []
    return list(
        RelationshipRequest.objects.filter(partner=me, status="pending")
        .select_related("requester")
        .order_by("-id")[:limit]
    )


def request_partner(me, partner, status: str) -> RelationshipRequest | None:
    """After profile save: open/refresh pending request when partner set."""
    if not me or not partner or me.id == partner.id:
        return None
    if (status or "") not in PARTNER_STATUSES:
        RelationshipRequest.objects.filter(requester=me, status="pending").delete()
        return None
    # Already mutual listing?
    if (
        partner.relationship_with_id == me.id
        and (partner.relationship_status or "") in PARTNER_STATUSES
    ):
        RelationshipRequest.objects.filter(requester=me, partner=partner).update(
            status="accepted", updated_at=now(),
        )
        RelationshipRequest.objects.filter(requester=me, status="pending").exclude(
            partner=partner,
        ).delete()
        return None
    existing = RelationshipRequest.objects.filter(requester=me, partner=partner).first()
    t = now()
    notify = False
    if existing:
        if existing.status == "accepted":
            RelationshipRequest.objects.filter(requester=me, status="pending").exclude(
                pk=existing.pk,
            ).delete()
            return existing
        if existing.status == "pending":
            RelationshipRequest.objects.filter(requester=me, status="pending").exclude(
                pk=existing.pk,
            ).delete()
            return existing
        existing.status = "pending"
        existing.updated_at = t
        existing.save(update_fields=["status", "updated_at"])
        row = existing
        notify = True
    else:
        row = RelationshipRequest.objects.create(
            requester=me, partner=partner, status="pending", created_at=t, updated_at=t,
        )
        notify = True
    RelationshipRequest.objects.filter(requester=me, status="pending").exclude(pk=row.pk).delete()
    if notify:
        push(
            partner.id,
            title="Отношения",
            body=f"{me.name} указал(а) вас в отношениях",
            type="relationship",
            url=f"/profile/{me.id}",
        )
        bump_news()
    return row


def clear_partner_requests(me):
    RelationshipRequest.objects.filter(requester=me, status="pending").delete()


def accept(me, request_id) -> bool:
    row = RelationshipRequest.objects.filter(
        pk=request_id, partner=me, status="pending",
    ).select_related("requester").first()
    if not row:
        return False
    t = now()
    req = row.requester
    status = req.relationship_status or "in_a_relationship"
    if status not in PARTNER_STATUSES:
        status = "in_a_relationship"
    me.relationship_with = req
    me.relationship_status = status
    me.updated_at = t
    me.save(update_fields=["relationship_with", "relationship_status", "updated_at"])
    if req.relationship_with_id != me.id:
        req.relationship_with = me
        req.updated_at = t
        req.save(update_fields=["relationship_with", "updated_at"])
    row.status = "accepted"
    row.updated_at = t
    row.save(update_fields=["status", "updated_at"])
    push(
        req.id,
        title="Отношения",
        body=f"{me.name} подтвердил(а) отношения",
        type="relationship",
        url=f"/profile/{me.id}",
    )
    bump_news()
    return True


def decline(me, request_id) -> bool:
    row = RelationshipRequest.objects.filter(
        pk=request_id, partner=me, status="pending",
    ).select_related("requester").first()
    if not row:
        return False
    t = now()
    req = row.requester
    if req.relationship_with_id == me.id:
        req.relationship_with = None
        req.updated_at = t
        req.save(update_fields=["relationship_with", "updated_at"])
    row.status = "declined"
    row.updated_at = t
    row.save(update_fields=["status", "updated_at"])
    bump_news()
    return True
