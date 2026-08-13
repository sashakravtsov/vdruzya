"""Helpers for Networks / Links / Videos / Notes browse / Marketplace / Lists."""
import re
from urllib.parse import urlparse

from django.db.models import Count

from apps.social.models import (
    Education, Experience, Post, SocialProfile, POST_DEFER, profile_related,
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
    # File videos use storage:<path> — must not run through normalize_url
    # (http:// prefix + netloc check would wipe the path).
    url = (url or "").strip()
    if not url.startswith("storage:"):
        url = normalize_url(url)
    else:
        url = url[:500]
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


from apps.social.market import market_create, market_list, market_update  # noqa: E402
from apps.social.friend_lists import (  # noqa: E402
    list_add, list_create, list_member_ids, list_members, list_remove, lists_for, owned_list,
)
