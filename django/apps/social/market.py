"""Marketplace listings — classic_extra re-exports."""
from __future__ import annotations

from django.db.models import Q

from apps.social.models import MarketplaceListing
from apps.social.services import now


def market_list(q="", place="", *, mine=False, viewer=None, limit=40):
    qs = MarketplaceListing.objects.select_related("social_user").order_by("-id")
    if mine and viewer:
        qs = qs.filter(social_user=viewer)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if place:
        qs = qs.filter(place__icontains=place)
    return list(qs[:limit])


def market_create(me, *, title, price="", place="", description="", photo=None):
    from apps.social.media import try_save_image
    title = (title or "").strip()[:160]
    if not me or not title:
        return None
    t = now()
    path = try_save_image(photo, "market")
    row = MarketplaceListing.objects.create(
        social_user=me,
        title=title,
        price=(price or "").strip()[:40],
        place=(place or "").strip()[:120],
        description=(description or "").strip()[:4000],
        photo_path=path,
        created_at=t,
        updated_at=t,
    )
    from apps.social.services import bump_news
    bump_news()
    return row


def market_update(me, item, *, title, price="", place="", description="", photo=None):
    if not me or not item or item.social_user_id != me.id:
        return None
    title = (title or "").strip()[:160]
    if not title:
        return None
    item.title = title
    item.price = (price or "").strip()[:40]
    item.place = (place or "").strip()[:120]
    item.description = (description or "").strip()[:4000]
    item.updated_at = now()
    from apps.social.media import try_save_image
    fields = ["title", "price", "place", "description", "updated_at"]
    path = try_save_image(photo, "market")
    if path:
        item.photo_path = path
        fields.append("photo_path")
    item.save(update_fields=fields)
    return item


