"""Wall ops: edit, share, show, poll vote — short FBVs."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods

from apps.social.forms import CommentForm, PostForm
from apps.social.models import Comment, PollOption, Post
from apps.social.polls import vote_post_option
from apps.social.services import feed_queryset, now, profile_of


@login_required
@require_http_methods(["GET", "POST"])
def post_edit(request, post_id):
    from apps.social.attach import attach_wall
    from apps.social.wall_meta import MOOD_KEYS, TOPIC_KEYS
    me = profile_of(request.user)
    post = get_object_or_404(Post, pk=post_id)
    if not me or post.social_user_id != me.id:
        messages.error(request, "Нельзя редактировать.")
        return redirect(request.GET.get("next") or "feed")
    form = PostForm(request.POST or None, request.FILES or None, instance=post)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.body = (obj.body or "").strip()
        if not str(obj.topic or "").startswith("wall:"):
            topic = form.cleaned_data.get("topic") or "thought"
            obj.topic = topic if topic in TOPIC_KEYS else "thought"
        mood = form.cleaned_data.get("mood") or ""
        obj.mood = mood if mood in MOOD_KEYS else None
        obj.emoji = (form.cleaned_data.get("emoji") or "").strip()[:16] or None
        obj.sticker = (form.cleaned_data.get("sticker") or "").strip() or None
        obj.updated_at = now()
        obj.save(update_fields=["body", "visibility", "topic", "mood", "emoji", "sticker", "updated_at"])
        path = attach_wall(obj, list(request.FILES.getlist("photo")), me, request.POST.getlist("album_photos"))
        if path and not obj.media_path:
            obj.media_path = path
            if obj.kind == "text":
                obj.kind = "photo"
            obj.save(update_fields=["media_path", "kind"])
        cache.delete(f"news:{me.id}:60")
        messages.success(request, "Запись обновлена.")
        return redirect(request.POST.get("next") or "feed")
    return render(request, "social/post_edit.html", {"form": form, "post": post, "me": me})


@login_required
@require_POST
def comment_update(request, comment_id):
    me = profile_of(request.user)
    c = get_object_or_404(Comment, pk=comment_id)
    body = (request.POST.get("body") or "").strip()
    if me and c.social_user_id == me.id and body:
        c.body = body[:2000]
        c.save(update_fields=["body"])
        messages.success(request, "Комментарий обновлён.")
    return redirect(request.POST.get("next") or "feed")


@login_required
@require_POST
def post_share(request, post_id):
    me = profile_of(request.user)
    src = get_object_or_404(Post, pk=post_id)
    if not me:
        return redirect("feed")
    body = (request.POST.get("body") or "").strip()[:1200]
    vis = request.POST.get("visibility") or "public"
    if vis not in ("public", "friends", "private"):
        vis = "public"
    t = now()
    Post.objects.create(
        social_user=me, shared_post=src, body=body, visibility=vis,
        kind="share", topic="thought", created_at=t, updated_at=t,
    )
    cache.delete(f"news:{me.id}:60")
    messages.success(request, "Публикация добавлена на стену.")
    return redirect(request.POST.get("next") or "feed")


def post_show(request, post_id):
    me = profile_of(request.user) if request.user.is_authenticated else None
    post = get_object_or_404(
        feed_queryset(me).select_related("shared_post", "shared_post__social_user"),
        pk=post_id,
    )
    return render(
        request, "social/post_show.html",
        {"post": post, "me": me, "form": None, "comment_form": CommentForm() if me else None},
    )


@login_required
@require_POST
def poll_vote(request, post_id):
    me = profile_of(request.user)
    post = get_object_or_404(Post, pk=post_id, kind="poll")
    opt = get_object_or_404(PollOption, pk=request.POST.get("option_id"), poll__post=post)
    if me:
        vote_post_option(me, opt)
    return redirect(request.POST.get("next") or "feed")
