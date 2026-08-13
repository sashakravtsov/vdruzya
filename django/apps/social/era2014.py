"""FB 2014 helpers — Save + Safety Check."""
from __future__ import annotations

from django.db.models import Q

from apps.social.models import (
    Company, Event, Place, Post, SafetyCheckin, SafetyEvent, SavedItem, SocialProfile,
    profile_related,
)
from apps.social.services import bump_news, friend_ids, now


SAVE_KINDS = ("post", "link", "place", "page", "event")


def list_saves(me, *, kind="", limit=60):
    if not me:
        return []
    qs = (
        SavedItem.objects.filter(social_user=me)
        .select_related("post", "post__social_user", "company", "event", "place")
        .order_by("-id")
    )
    if kind in SAVE_KINDS:
        qs = qs.filter(kind=kind)
    return list(qs[:limit])


def is_saved_post(me, post_id) -> bool:
    if not me or not post_id:
        return False
    return SavedItem.objects.filter(social_user=me, post_id=post_id).exists()


def saved_post_ids(me, post_ids) -> set[int]:
    if not me or not post_ids:
        return set()
    return set(
        SavedItem.objects.filter(social_user=me, post_id__in=post_ids)
        .values_list("post_id", flat=True)
    )


def attach_saves(posts, viewer=None):
    posts = list(posts or [])
    ids = [p.id for p in posts if getattr(p, "id", None)]
    mine = saved_post_ids(viewer, ids) if viewer else set()
    for p in posts:
        p.saved_by_me = p.id in mine
    return posts


def toggle_save_post(me, post) -> tuple[SavedItem | None, bool]:
    """Returns (row, saved?)."""
    if not me or not post:
        return None, False
    existing = SavedItem.objects.filter(social_user=me, post=post).first()
    if existing:
        existing.delete()
        return None, False
    title = (getattr(post, "media_label", None) or (post.body or "")[:80] or "Запись").strip()
    kind = "link" if getattr(post, "kind", "") == "link" else "post"
    url = ""
    if kind == "link":
        from apps.social.classic_extra import unpack_link_body
        url, _ = unpack_link_body(post.body or "")
    row = SavedItem.objects.create(
        social_user=me, kind=kind, post=post, url=url or "",
        title=title[:255], created_at=now(),
    )
    return row, True


def save_target(me, *, kind, target_id=None, url="", title="") -> SavedItem | None:
    if not me or kind not in SAVE_KINDS:
        return None
    t = now()
    title = (title or "").strip()[:255]
    url = (url or "").strip()[:500]
    if kind == "page" and target_id:
        page = Company.objects.filter(pk=target_id).first()
        if not page:
            return None
        row, _ = SavedItem.objects.get_or_create(
            social_user=me, company=page,
            defaults={"kind": "page", "title": title or page.name, "created_at": t},
        )
        return row
    if kind == "event" and target_id:
        ev = Event.objects.filter(pk=target_id).first()
        if not ev:
            return None
        row, _ = SavedItem.objects.get_or_create(
            social_user=me, event=ev,
            defaults={"kind": "event", "title": title or ev.title, "created_at": t},
        )
        return row
    if kind == "place" and target_id:
        place = Place.objects.filter(pk=target_id).first()
        if not place:
            return None
        row, _ = SavedItem.objects.get_or_create(
            social_user=me, place=place,
            defaults={"kind": "place", "title": title or place.name, "created_at": t},
        )
        return row
    if kind == "link" and url:
        row, _ = SavedItem.objects.get_or_create(
            social_user=me, url=url,
            defaults={"kind": "link", "title": title or url, "created_at": t},
        )
        return row
    return None


def unsave(me, save_id) -> bool:
    if not me or not save_id:
        return False
    n, _ = SavedItem.objects.filter(pk=save_id, social_user=me).delete()
    return bool(n)


def active_safety_events(limit=20):
    return list(SafetyEvent.objects.filter(is_active=True).order_by("-id")[:limit])


def safety_event_get(pk):
    return SafetyEvent.objects.filter(pk=pk).first()


def ensure_safety_geo(event: SafetyEvent) -> bool:
    """Geocode safety event city once for map + radius checks."""
    from apps.social import osm
    if not event:
        return False
    if osm.has_coords(event):
        return True
    city = (event.city or "").strip()
    if not city:
        return False
    hit = osm.geocode(city)
    if not hit:
        return False
    event.lat, event.lon = hit.lat, hit.lon
    if not event.radius_km:
        event.radius_km = 50
    try:
        event.save(update_fields=["lat", "lon", "radius_km"])
    except Exception:
        return False
    return True


def in_affected_area(me, event: SafetyEvent) -> bool:
    from apps.social import osm
    if not me or not event:
        return False
    ensure_safety_geo(event)
    osm.ensure_profile_geo(me)
    if osm.has_coords(event) and osm.has_coords(me):
        return osm.within_radius(event, me, event.radius_km or 50)
    city = (event.city or "").strip()
    if not city:
        return True
    mine = ((me.city or "") + " " + (me.hometown or "")).lower()
    return city.lower() in mine or (me.city or "").lower() == city.lower()


def my_checkin(me, event):
    if not me or not event:
        return None
    return SafetyCheckin.objects.filter(event=event, social_user=me).first()


def mark_safe(me, event, *, status="safe", for_user=None, marked_by=None):
    """Mark self or a friend as safe / out_of_area."""
    if not me or not event or not event.is_active:
        return None
    target = for_user or me
    if for_user and for_user.id != me.id:
        if for_user.id not in friend_ids(me):
            return None
    status = status if status in ("safe", "out_of_area") else "safe"
    t = now()
    row = SafetyCheckin.objects.filter(event=event, social_user=target).first()
    if row:
        row.status = status
        row.marked_by = marked_by or me
        row.updated_at = t
        row.save(update_fields=["status", "marked_by", "updated_at"])
    else:
        row = SafetyCheckin.objects.create(
            event=event, social_user=target, status=status,
            marked_by=marked_by or me, created_at=t, updated_at=t,
        )
    if status == "safe":
        _notify_friends_safe(target, event)
        bump_news()
    return row


def _notify_friends_safe(person, event):
    from apps.social import notify
    fids = friend_ids(person)
    title = f"{person.name}: в безопасности"
    body = event.title
    url = f"/safety/{event.id}"
    for fid in list(fids)[:80]:
        notify.push(fid, title=title, body=body, type="safety", url=url)


def friend_checkins(me, event, limit=40):
    if not me or not event:
        return []
    fids = friend_ids(me) | {me.id}
    return list(
        SafetyCheckin.objects.filter(event=event, social_user_id__in=fids, status="safe")
        .select_related("social_user", "marked_by")
        .order_by("-updated_at", "-id")[:limit]
    )


def friends_needing_check(me, event, limit=30):
    """Friends in affected area without a check-in yet (OSM radius or city)."""
    from apps.social import osm
    if not me or not event:
        return []
    fids = friend_ids(me)
    if not fids:
        return []
    checked = set(
        SafetyCheckin.objects.filter(event=event, social_user_id__in=fids)
        .values_list("social_user_id", flat=True)
    )
    qs = SocialProfile.objects.filter(id__in=fids - checked).defer(*profile_related()).order_by("name")
    ensure_safety_geo(event)
    if osm.has_coords(event):
        rows = list(qs[:120])
        out = []
        for p in rows:
            osm.ensure_profile_geo(p, network=False)
            if osm.has_coords(p) and osm.within_radius(event, p, event.radius_km or 50):
                out.append(p)
            elif not osm.has_coords(p):
                city = (event.city or "").strip()
                if city and (
                    city.lower() in (p.city or "").lower()
                    or city.lower() in (p.hometown or "").lower()
                ):
                    out.append(p)
            if len(out) >= limit:
                break
        return out
    city = (event.city or "").strip()
    if city:
        qs = qs.filter(Q(city__icontains=city) | Q(hometown__icontains=city))
    return list(qs[:limit])


def ensure_demo_event():
    """Seed one inactive-ready active event for probes if none exist."""
    if SafetyEvent.objects.filter(is_active=True).exists():
        return SafetyEvent.objects.filter(is_active=True).order_by("-id").first()
    t = now()
    return SafetyEvent.objects.create(
        title="Проверка безопасности",
        city="",
        body="Отметьтесь, если с вами всё в порядке — друзья увидят это в ленте.",
        is_active=True, starts_at=t, created_at=t, updated_at=t,
    )


def _add_safety_stories(items, blocked, fids, limit):
    if not fids:
        return
    qs = (
        SafetyCheckin.objects.filter(social_user_id__in=fids, status="safe")
        .select_related("social_user", "event", "marked_by")
        .order_by("-updated_at", "-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for row in qs[:limit]:
        if not row.event_id or not getattr(row.event, "is_active", False):
            continue
        items.append({
            "kind": "safety", "at": row.updated_at or row.created_at,
            "actor": row.social_user, "event": row.event, "checkin": row,
        })
