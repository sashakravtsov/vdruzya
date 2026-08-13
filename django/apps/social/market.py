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


def market_create(me, *, title, price="", place="", description="", photo=None, lat=None, lon=None):
    from apps.social import osm
    from apps.social.media import try_save_image
    title = (title or "").strip()[:160]
    if not me or not title:
        return None
    t = now()
    path = try_save_image(photo, "market")
    place_s = (place or "").strip()[:120]
    coords = osm.parse_coords(lat, lon)
    if not coords and place_s:
        hit = osm.geocode(place_s)
        if hit:
            coords = (hit.lat, hit.lon)
    row = MarketplaceListing(
        social_user=me,
        title=title,
        price=(price or "").strip()[:40],
        place=place_s,
        description=(description or "").strip()[:4000],
        photo_path=path,
        created_at=t,
        updated_at=t,
    )
    if coords:
        row.lat, row.lon = coords
    row.save()
    from apps.social.services import bump_news
    bump_news()
    return row


def market_update(me, item, *, title, price="", place="", description="", photo=None, lat=None, lon=None):
    from apps.social import osm
    if not me or not item or item.social_user_id != me.id:
        return None
    title = (title or "").strip()[:160]
    if not title:
        return None
    item.title = title
    item.price = (price or "").strip()[:40]
    place_s = (place or "").strip()[:120]
    item.place = place_s
    item.description = (description or "").strip()[:4000]
    item.updated_at = now()
    coords = osm.parse_coords(lat, lon)
    if not coords and place_s:
        hit = osm.geocode(place_s)
        if hit:
            coords = (hit.lat, hit.lon)
    if coords:
        item.lat, item.lon = coords
    from apps.social.media import try_save_image
    fields = ["title", "price", "place", "description", "updated_at"]
    if coords:
        fields.extend(["lat", "lon"])
    path = try_save_image(photo, "market")
    if path:
        item.photo_path = path
        fields.append("photo_path")
    item.save(update_fields=fields)
    return item


