"""Helpers for Networks / Links / Videos / Notes browse / Marketplace / Lists."""
import re
from urllib.parse import urlparse

from django.db.models import Count, Q

from apps.social.models import (
    Education, Experience, FriendList, FriendListMember, MarketplaceListing,
    Post, SocialProfile, POST_DEFER, profile_related,
)
from apps.social.services import friend_ids, now, post_visible_q

_URL = re.compile(r"^https?://", re.I)


def normalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if not _URL.match(raw):
        raw = "http://" + raw
    try:
        p = urlparse(raw)
        if not p.netloc or "." not in p.netloc:
            return ""
    except Exception:
        return ""
    return raw[:500]


def pack_link_body(url: str, blurb: str = "") -> str:
    url = normalize_url(url)
    blurb = (blurb or "").strip()[:2000]
    return f"{url}\n\n{blurb}".strip() if blurb else url


def unpack_link_body(body: str) -> tuple[str, str]:
    body = body or ""
    lines = body.split("\n", 1)
    url = (lines[0] or "").strip()
    blurb = (lines[1] if len(lines) > 1 else "").strip()
    return url, blurb


def create_posted_item(me, *, kind: str, title: str, url: str = "", blurb: str = "",
                       visibility="friends", upload=None):
    """kind: link | video — URL and/or uploaded video file (same media disk as photos)."""
    kind = kind if kind in ("link", "video") else "link"
    title = (title or "").strip()[:160] or ("Видео" if kind == "video" else "Ссылка")
    url = normalize_url(url)
    if not me:
        return None
    t = now()
    media_path = None
    body_url = url
    if kind == "video" and upload is not None:
        from apps.social.media import save_video
        try:
            video_path, poster = save_video(upload, "videos")
        except ValueError:
            return None
        body_url = f"storage:{video_path}"
        media_path = poster
        if not title:
            title = "Видео"
    elif not body_url:
        return None
    return Post.objects.create(
        social_user=me,
        kind=kind,
        topic=kind,
        media_label=title,
        media_path=media_path,
        body=pack_link_body(body_url, blurb),
        visibility=visibility or "friends",
        created_at=t,
        updated_at=t,
    )


def hydrate_posted(post):
    """Attach link_url / link_blurb / video_url / is_file_video for templates."""
    from apps.social.media import media_url
    url, blurb = unpack_link_body(post.body)
    post.link_blurb = blurb
    post.is_file_video = False
    post.video_url = None
    if url.startswith("storage:"):
        path = url[len("storage:"):]
        post.is_file_video = True
        post.video_url = media_url(path)
        post.link_url = post.get_absolute_url()
    else:
        post.link_url = url
        if getattr(post, "kind", "") == "video":
            post.video_url = url
    return post


def list_posted(viewer, kind: str, *, mine=False, limit=40):
    fids = friend_ids(viewer) | {viewer.id} if viewer else set()
    qs = (
        Post.objects.filter(kind=kind, topic=kind)
        .select_related("social_user")
        .defer(*POST_DEFER, *profile_related("social_user__"))
        .filter(post_visible_q(viewer))
        .order_by("-id")
    )
    if mine and viewer:
        qs = qs.filter(social_user=viewer)
    elif viewer:
        qs = qs.filter(social_user_id__in=fids)
    rows = list(qs[:limit])
    for p in rows:
        hydrate_posted(p)
    return rows


def network_catalog(limit=40):
    """Popular city / school / workplace networks from live profile data."""
    cities = list(
        SocialProfile.objects.exclude(city__isnull=True).exclude(city="")
        .values("city").annotate(n=Count("id")).order_by("-n", "city")[:limit]
    )
    schools = list(
        Education.objects.exclude(institution="")
        .values("institution").annotate(n=Count("id")).order_by("-n", "institution")[:limit]
    )
    works = list(
        Experience.objects.exclude(company_name="")
        .values("company_name").annotate(n=Count("id")).order_by("-n", "company_name")[:limit]
    )
    return {
        "cities": [{"label": r["city"], "n": r["n"], "param": "city", "value": r["city"]} for r in cities],
        "schools": [
            {"label": r["institution"], "n": r["n"], "param": "school", "value": r["institution"]}
            for r in schools
        ],
        "works": [
            {"label": r["company_name"], "n": r["n"], "param": "workplace", "value": r["company_name"]}
            for r in works
        ],
    }


def notes_feed(viewer, *, mine=False, limit=40):
    fids = friend_ids(viewer) | {viewer.id} if viewer else set()
    qs = (
        Post.objects.filter(kind="note")
        .select_related("social_user")
        .defer(*POST_DEFER, *profile_related("social_user__"))
        .filter(post_visible_q(viewer))
        .order_by("-id")
    )
    if mine and viewer:
        qs = qs.filter(social_user=viewer)
    elif viewer:
        qs = qs.filter(social_user_id__in=fids)
    return list(qs[:limit])


def market_list(q="", place="", *, mine=False, viewer=None, limit=40):
    qs = MarketplaceListing.objects.select_related("social_user").order_by("-id")
    if mine and viewer:
        qs = qs.filter(social_user=viewer)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if place:
        qs = qs.filter(place__icontains=place)
    return list(qs[:limit])


def market_create(me, *, title, price="", place="", description=""):
    title = (title or "").strip()[:160]
    if not me or not title:
        return None
    t = now()
    row = MarketplaceListing.objects.create(
        social_user=me,
        title=title,
        price=(price or "").strip()[:40],
        place=(place or "").strip()[:120],
        description=(description or "").strip()[:4000],
        created_at=t,
        updated_at=t,
    )
    from apps.social.services import bump_news
    bump_news()
    return row


def market_update(me, item, *, title, price="", place="", description=""):
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
    item.save(update_fields=["title", "price", "place", "description", "updated_at"])
    return item


def lists_for(me):
    if not me:
        return []
    return list(
        FriendList.objects.filter(social_user=me)
        .annotate(n=Count("memberships"))
        .order_by("name")
    )


def owned_list(me, list_id):
    try:
        lid = int(list_id)
    except (TypeError, ValueError):
        return None
    if not me or not lid:
        return None
    return FriendList.objects.filter(pk=lid, social_user=me).first()


def list_member_ids(flist) -> set:
    if not flist:
        return set()
    return set(
        FriendListMember.objects.filter(friend_list=flist).values_list("social_user_id", flat=True)
    )


def list_create(me, name: str):
    name = (name or "").strip()[:120]
    if not me or not name:
        return None
    t = now()
    return FriendList.objects.create(social_user=me, name=name, created_at=t, updated_at=t)


def list_members(flist, limit=200):
    return list(
        SocialProfile.objects.filter(list_memberships__friend_list=flist)
        .order_by("name")[:limit]
    )


def list_add(me, flist, friend_id: int) -> bool:
    if not me or flist.social_user_id != me.id:
        return False
    if friend_id not in friend_ids(me):
        return False
    if FriendListMember.objects.filter(friend_list=flist, social_user_id=friend_id).exists():
        return True
    FriendListMember.objects.create(
        friend_list=flist, social_user_id=friend_id, created_at=now(),
    )
    return True


def list_remove(me, flist, friend_id: int) -> bool:
    if not me or flist.social_user_id != me.id:
        return False
    FriendListMember.objects.filter(friend_list=flist, social_user_id=friend_id).delete()
    return True
