"""Classic Facebook Events helpers."""
import re
from datetime import datetime

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime

from apps.social.models import Event, EventAttendee, Notification, SocialProfile
from apps.social.services import friend_ids, now

STATUSES = ("going", "maybe", "declined")
_LABEL = {"going": "Иду", "maybe": "Возможно", "declined": "Не иду"}
_RU_DT = re.compile(
    r"^(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$"
)


def parse_starts(raw):
    """Accept classic text dates: ДД.ММ.ГГГГ ЧЧ:ММ or ISO YYYY-MM-DD[T ]HH:MM."""
    raw = (raw or "").strip()
    if not raw:
        return None
    m = _RU_DT.match(raw)
    if m:
        try:
            return datetime(
                int(m[3]), int(m[2]), int(m[1]),
                int(m[4] or 0), int(m[5] or 0), int(m[6] or 0),
            )
        except ValueError:
            return None
    iso = raw.replace("T", " ")
    if len(iso) == 16:
        iso += ":00"
    starts = parse_datetime(iso)
    if starts and getattr(starts, "tzinfo", None):
        starts = starts.replace(tzinfo=None)
    return starts


def create_event(me, *, title, place="", description="", starts_at=None, community=None):
    title = (title or "").strip()[:255]
    if not me or not title or not starts_at:
        return None
    t = now()
    return Event.objects.create(
        title=title,
        place=(place or "").strip()[:255] or "—",
        description=(description or "").strip()[:4000],
        starts_at=starts_at,
        host=me,
        community=community,
        created_at=t,
        updated_at=t,
    )


def get_event(pk):
    return get_object_or_404(Event.objects.select_related("host", "community"), pk=pk)


def annotate_counts(qs):
    # Avoid DISTINCT over SocialProfile JSON columns (PG has no json equality).
    return qs.annotate(
        n_going=Count("attendees", filter=Q(attendees__status="going")),
        n_maybe=Count("attendees", filter=Q(attendees__status="maybe")),
    )


def list_events(me, tab="upcoming"):
    """Tabs: upcoming | past | hosting | going | invited."""
    qs = annotate_counts(
        Event.objects.select_related("host", "community").defer(
            "host__looking_for", "host__interested_in", "host__languages",
        )
    )
    t = now()
    if tab == "past":
        return qs.filter(starts_at__lt=t).order_by("-starts_at")[:50]
    if tab == "hosting" and me:
        return qs.filter(host=me).order_by("starts_at")[:50]
    if tab == "going" and me:
        return qs.filter(attendees__social_user=me, attendees__status="going").order_by("starts_at")[:50]
    if tab == "invited" and me:
        return qs.filter(attendees__social_user=me, attendees__status="maybe").order_by("starts_at")[:50]
    return qs.filter(starts_at__gte=t).order_by("starts_at")[:50]


def my_status(me, event) -> str:
    if not me:
        return ""
    row = EventAttendee.objects.filter(event=event, social_user=me).values_list("status", flat=True).first()
    return row or ""


def statuses_map(me, event_ids):
    if not me or not event_ids:
        return {}
    return dict(
        EventAttendee.objects.filter(social_user=me, event_id__in=event_ids).values_list("event_id", "status")
    )


def set_rsvp(me, event, status: str):
    status = (status or "").strip()
    if not me or status not in STATUSES:
        return False
    t = now()
    row, created = EventAttendee.objects.get_or_create(
        event=event, social_user=me,
        defaults={"status": status, "created_at": t, "updated_at": t},
    )
    if not created and row.status != status:
        row.status, row.updated_at = status, t
        row.save(update_fields=["status", "updated_at"])
    if event.host_id and event.host_id != me.id and status == "going":
        Notification.objects.create(
            social_user_id=event.host_id,
            title="RSVP",
            body=f"{me.name} идёт на «{event.title}»"[:255],
            seen=False, type="event_rsvp", url=f"/events/{event.id}", created_at=t,
        )
    return True


def guests(event, status="going", limit=60):
    return list(
        SocialProfile.objects.filter(event_rsvps__event=event, event_rsvps__status=status)
        .order_by("name")[:limit]
    )


def guest_count(event, status="going") -> int:
    return EventAttendee.objects.filter(event=event, status=status).count()


def invite_friends(me, event, friend_ids_list):
    """Host invites friends → maybe RSVP + notification."""
    if not me or not event:
        return 0
    if event.host_id:
        if event.host_id != me.id:
            return 0
    elif my_status(me, event) != "going":
        return 0
    allowed = friend_ids(me)
    ids = [int(i) for i in friend_ids_list if str(i).isdigit() and int(i) in allowed]
    if not ids:
        return 0
    t = now()
    n = 0
    for fid in ids:
        row, created = EventAttendee.objects.get_or_create(
            event=event, social_user_id=fid,
            defaults={"status": "maybe", "created_at": t, "updated_at": t},
        )
        if created or row.status == "declined":
            if not created:
                row.status, row.updated_at = "maybe", t
                row.save(update_fields=["status", "updated_at"])
            Notification.objects.create(
                social_user_id=fid,
                title="Приглашение на событие",
                body=f"{me.name} приглашает на «{event.title}»"[:255],
                seen=False, type="event_invite", url=f"/events/{event.id}", created_at=t,
            )
            n += 1
    return n


def invite_candidates(me, event, limit=24):
    if not me:
        return []
    taken = set(EventAttendee.objects.filter(event=event).values_list("social_user_id", flat=True))
    taken.add(me.id)
    return list(
        SocialProfile.objects.filter(id__in=friend_ids(me)).exclude(id__in=taken).order_by("name")[:limit]
    )


def status_label(status):
    return _LABEL.get(status, "")
