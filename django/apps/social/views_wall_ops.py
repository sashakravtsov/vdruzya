"""Wall ops: edit, show, comment edit — short FBVs."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods

from apps.social.forms import CommentForm, PostForm
from apps.social.models import Comment, Post
from apps.social.services import feed_queryset, now, profile_of


@login_required
@require_http_methods(["GET", "POST"])
def post_edit(request, post_id):
    from apps.social.attach import attach_wall
    me = profile_of(request.user)
    post = get_object_or_404(Post, pk=post_id)
    if not me or post.social_user_id != me.id:
        messages.error(request, "Нельзя редактировать.")
        return redirect(request.GET.get("next") or "feed")
    form = PostForm(request.POST or None, request.FILES or None, instance=post)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.body = (obj.body or "").strip()
        obj.updated_at = now()
        obj.save(update_fields=["body", "visibility", "updated_at"])
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
