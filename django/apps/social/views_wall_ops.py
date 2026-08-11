"""Wall ops: edit + show — short FBVs."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.social.forms import CommentForm, PostForm
from apps.social.models import Post, SocialProfile
from apps.social.services import attach_wall_notes, feed_queryset, now, profile_of, wall_owner_id


@login_required
@require_http_methods(["GET", "POST"])
def post_edit(request, post_id):
    from apps.social.attach import attach_wall
    from apps.social.profile_page import wall_post_visibility

    me = profile_of(request.user)
    post = get_object_or_404(Post, pk=post_id)
    if not me or post.social_user_id != me.id:
        messages.error(request, "Нельзя редактировать.")
        return redirect(request.GET.get("next") or "feed")
    on_wall = (post.topic or "").startswith("wall:")
    nxt = request.POST.get("next") or request.GET.get("next") or "/feed"
    form = PostForm(request.POST or None, request.FILES or None, instance=post, simple=on_wall)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.body = (obj.body or "").strip()
        obj.updated_at = now()
        fields = ["body", "updated_at"]
        if on_wall:
            oid = wall_owner_id(obj)
            owner = SocialProfile.objects.filter(pk=oid).first() if oid else None
            obj.visibility = wall_post_visibility(owner) if owner else (obj.visibility or "friends")
            fields.append("visibility")
        else:
            fields.append("visibility")
        obj.save(update_fields=fields)
        path = attach_wall(obj, list(request.FILES.getlist("photo")), me, max_photos=1)
        if path and not obj.media_path:
            obj.media_path = path
            obj.kind = "photo"
            obj.save(update_fields=["media_path", "kind"])
        cache.delete(f"news:{me.id}:60")
        messages.success(request, "Запись обновлена.")
        return redirect(nxt)
    return render(
        request, "social/post_edit.html",
        {"form": form, "post": post, "me": me, "next": nxt},
    )


def post_show(request, post_id):
    me = profile_of(request.user) if request.user.is_authenticated else None
    post = get_object_or_404(feed_queryset(me), pk=post_id)
    attach_wall_notes([post])
    return render(
        request, "social/post_show.html",
        {"post": post, "me": me, "form": None, "comment_form": CommentForm() if me else None},
    )
