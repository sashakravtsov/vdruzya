"""Shared Markdown compose chrome — editor context, album attach, preview."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from apps.social import emoji_classic as emo
from apps.social.gifts import catalog
from apps.social.markdown_msg import render_message_md
from apps.social.models import Album, Photo
from apps.social.services import now, profile_of
from apps.social.throttle import throttle


def editor_context(*, stickers=True):
    """Template vars for Markdown + emoji (+ stickers when enabled)."""
    return {
        "emojis": emo.EMOJIS,
        "text_emotes": emo.TEXT_EMOTES,
        "stickers": (catalog()[:40] if stickers else []),
    }


def parse_album_photo_ids(request, *, limit=5) -> list[int]:
    raw = request.POST.getlist("album_photo")
    out: list[int] = []
    for x in raw:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
        if len(out) >= limit:
            break
    return out


def owned_photos(me, ids: list[int], *, limit=5):
    if not me or not ids:
        return []
    return list(
        Photo.objects.filter(pk__in=ids[:limit], album__social_user=me)
        .exclude(path="")
        .select_related("album")[:limit]
    )


def attach_album_photos_wall(post, photo_ids, me, *, max_photos=5):
    from apps.social.models import PostMedia
    photos = owned_photos(me, photo_ids, limit=max_photos)
    if not photos:
        return None
    t = now()
    rows = [
        PostMedia(post=post, path=p.path, photo_id=p.id, sort_order=i, created_at=t)
        for i, p in enumerate(photos)
    ]
    PostMedia.objects.bulk_create(rows)
    post.media_path = rows[0].path
    if (post.kind or "text") == "text":
        post.kind = "photo"
    post.save(update_fields=["media_path", "kind"])
    return rows[0].path


def attach_album_photos_group(post, photo_ids, me, *, max_photos=50):
    from apps.social.models import CommunityPostMedia
    photos = owned_photos(me, photo_ids, limit=max_photos)
    if not photos:
        return None
    t = now()
    rows = [
        CommunityPostMedia(
            post=post, path=p.path, photo_id=p.id,
            sort_order=i, created_at=t, updated_at=t,
        )
        for i, p in enumerate(photos)
    ]
    CommunityPostMedia.objects.bulk_create(rows)
    post.media_path = rows[0].path
    if (post.kind or "text") == "text":
        post.kind = "photo"
    post.save(update_fields=["media_path", "kind"])
    return rows[0].path


@login_required
@require_POST
@throttle("msg", 60, 60)
def compose_preview(request):
    me = profile_of(request.user)
    if not me:
        return JsonResponse({"error": "auth"}, status=403)
    body = (request.POST.get("body") or "")[:4000]
    html = render_message_md(body)
    return JsonResponse({
        "ok": True,
        "html": html or "<p class=\"muted\">Пусто — напишите текст.</p>",
        "empty": not bool(body.strip()),
    })


@login_required
@require_GET
def album_picker(request, album_id=None):
    """FBDialog HTML: albums list or photos in one album (own albums only)."""
    me = profile_of(request.user)
    if not me:
        return render(request, "social/_compose_album_picker.html", {"error": "auth"}, status=403)
    if album_id:
        album = get_object_or_404(Album, pk=album_id, social_user=me)
        photos = list(Photo.objects.filter(album=album).exclude(path="").order_by("-id")[:60])
        return render(request, "social/_compose_album_picker.html", {
            "album": album, "photos": photos, "albums": None,
        })
    albums = list(Album.objects.filter(social_user=me).order_by("-id")[:40])
    return render(request, "social/_compose_album_picker.html", {
        "album": None, "photos": None, "albums": albums,
    })
