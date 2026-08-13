"""Wall / Notes / Status publish helpers — views_actions stays thin."""
from __future__ import annotations

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect

from apps.social.forms import NoteForm, PostForm, StatusForm
from apps.social.models import Friendship, Place, Post, SocialProfile
from apps.social.services import bump_news, now, profile_of


def create_wall_post(request):
    from apps.social.attach import apply_wall_uploads
    from apps.social.compose_ui import attach_album_photos_wall, parse_album_photo_ids
    from apps.social.profile_page import can_write_wall, wall_post_visibility

    me = profile_of(request.user)
    form = PostForm(request.POST, request.FILES, simple=True)
    if not (form.is_valid() and me):
        return redirect(request.POST.get("next") or "feed")
    target = get_object_or_404(SocialProfile, pk=request.POST.get("wall_to") or me.id)
    rel = None
    if target.id != me.id:
        rel = Friendship.objects.filter(
            Q(user=me, friend=target) | Q(user=target, friend=me)
        ).first()
    if not can_write_wall(me, target, rel):
        messages.error(request, "Писать на стену нельзя.")
        return redirect(target)
    post = form.save(commit=False)
    post.social_user = me
    text = (post.body or "").strip()
    post.body = text
    post.topic = f"wall:{target.id}"
    post.visibility = wall_post_visibility(target)
    post.kind = "text"
    post.created_at = post.updated_at = now()
    post.save()
    apply_wall_uploads(post, list(request.FILES.getlist("photo")), me, max_photos=5, blurb=text)
    attach_album_photos_wall(post, parse_album_photo_ids(request), me, max_photos=5)
    bump_news()
    messages.success(request, "Запись опубликована.")
    return redirect(request.POST.get("next") or target)


def create_note(request):
    from apps.social.media import try_save_image
    me = profile_of(request.user)
    form = NoteForm(request.POST, request.FILES)
    go = request.POST.get("next") or (f"{me.get_absolute_url()}?tab=notes" if me else "feed")
    if not (form.is_valid() and me):
        messages.error(request, "Укажите заголовок и текст.")
        return redirect(go)
    d = form.cleaned_data
    t = now()
    Post.objects.create(
        social_user=me, body=d["body"], kind="note", topic="note",
        media_label=d["title"], media_path=try_save_image(d.get("photo"), "notes"),
        visibility=d["visibility"], created_at=t, updated_at=t,
    )
    bump_news()
    messages.success(request, "Заметка опубликована.")
    return redirect(go)


def update_status(request):
    from apps.social import era2010 as e10
    me = profile_of(request.user)
    places = list(Place.objects.order_by("name")[:80]) if me else []
    form = StatusForm(request.POST, places=places)
    if me and form.is_valid():
        headline = (form.cleaned_data.get("headline") or "").strip() or None
        place_id = form.cleaned_data.get("place")
        place = Place.objects.filter(pk=place_id).first() if place_id else None
        display = headline or ""
        if place:
            suffix = f"в «{place.name}»"
            display = f"{display} {suffix}".strip() if display else suffix
        me.headline = display or None
        me.updated_at = now()
        me.save(update_fields=["headline", "updated_at"])
        if place:
            e10.place_checkin(me, place, headline or "")
        elif display:
            t = now()
            Post.objects.create(
                social_user=me, body=display, visibility="public",
                kind="status", topic="status", created_at=t, updated_at=t,
            )
        bump_news()
        messages.success(request, "Статус обновлён.")
    return redirect(request.POST.get("next") or me or "feed")
