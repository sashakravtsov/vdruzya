"""Wall ops: edit + show — short FBVs."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.social.forms import CommentForm, NoteForm, PostForm
from apps.social.models import Post
from apps.social.services import attach_wall_notes, bump_news, feed_queryset, now, profile_of, wall_owner_id


@login_required
@require_http_methods(["GET", "POST"])
def post_edit(request, post_id):
    me = profile_of(request.user)
    post = get_object_or_404(Post, pk=post_id)
    if not me or post.social_user_id != me.id:
        messages.error(request, "Нельзя редактировать.")
        return redirect(request.GET.get("next") or "feed")
    on_wall = (post.topic or "").startswith("wall:")
    is_note = getattr(post, "kind", None) == "note" or (post.topic or "") == "note"
    # FB 2006 wall text: delete-only
    if on_wall and not is_note:
        messages.error(request, "Запись на стене нельзя редактировать — только удалить.")
        oid = wall_owner_id(post)
        return redirect(f"/profile/{oid}" if oid else (request.GET.get("next") or "feed"))
    nxt = request.POST.get("next") or request.GET.get("next") or (
        f"/profile/{me.id}?tab=notes" if is_note else "/feed"
    )
    if is_note:
        initial = {
            "title": post.media_label or "",
            "body": post.body or "",
            "visibility": post.visibility or "public",
        }
        form = NoteForm(request.POST or None, initial=None if request.method == "POST" else initial)
        if request.method == "POST" and form.is_valid():
            post.media_label = form.cleaned_data["title"]
            post.body = form.cleaned_data["body"]
            post.visibility = form.cleaned_data["visibility"]
            post.kind = "note"
            post.topic = "note"
            post.updated_at = now()
            post.save(update_fields=["media_label", "body", "visibility", "kind", "topic", "updated_at"])
            bump_news()
            messages.success(request, "Заметка сохранена.")
            return redirect(nxt)
        return render(
            request, "social/post_edit.html",
            {"form": form, "post": post, "me": me, "next": nxt, "is_note": True},
        )

    form = PostForm(request.POST or None, request.FILES or None, instance=post, simple=False)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.body = (obj.body or "").strip()
        obj.updated_at = now()
        obj.save(update_fields=["body", "visibility", "updated_at"])
        bump_news()
        messages.success(request, "Запись обновлена.")
        return redirect(nxt)
    return render(
        request, "social/post_edit.html",
        {"form": form, "post": post, "me": me, "next": nxt, "is_note": False},
    )


def post_show(request, post_id):
    me = profile_of(request.user) if request.user.is_authenticated else None
    post = get_object_or_404(feed_queryset(me), pk=post_id)
    attach_wall_notes([post])
    if getattr(post, "kind", "") in ("link", "video"):
        from apps.social.classic_extra import hydrate_posted
        hydrate_posted(post)
    from apps.social.likes import attach_likes
    from apps.social.shares import attach_share_flags
    from apps.social import post_tags as ptags
    attach_likes([post], me)
    attach_share_flags([post], me)
    ptags.tags_for_posts([post])
    if me and ptags.can_tag(me, post):
        post.tag_candidates = ptags.tag_candidates(me, post)
    else:
        post.tag_candidates = []
    return render(
        request, "social/post_show.html",
        {"post": post, "me": me, "form": None, "comment_form": CommentForm() if me else None},
    )
