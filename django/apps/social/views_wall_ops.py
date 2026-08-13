"""Wall ops: edit + show — short FBVs."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.social.forms import CommentForm
from apps.social.models import Post
from apps.social.services import attach_wall_notes, feed_queryset, profile_of


@login_required
@require_http_methods(["GET", "POST"])
def post_edit(request, post_id):
    from apps.social import note_edit as ne
    me = profile_of(request.user)
    post = get_object_or_404(Post, pk=post_id)
    ok, err, extra = ne.can_edit(me, post)
    if not ok:
        messages.error(request, err)
        return redirect(extra or request.GET.get("next") or "feed")
    is_note = extra
    nxt = ne.next_url(request, me, is_note)
    form = ne.edit_forms(request, post, is_note)
    if request.method == "POST":
        saved = ne.save_note(post, form) if is_note else ne.save_post(post, form)
        if saved:
            messages.success(request, "Заметка сохранена." if is_note else "Запись обновлена.")
            return redirect(nxt)
    return render(
        request, "social/post_edit.html",
        {"form": form, "post": post, "me": me, "next": nxt, "is_note": is_note},
    )


def post_show(request, post_id):
    me = profile_of(request.user) if request.user.is_authenticated else None
    post = get_object_or_404(feed_queryset(me), pk=post_id)
    attach_wall_notes([post])
    from apps.social.classic_extra import hydrate_posted
    if getattr(post, "kind", "") in ("link", "video"):
        hydrate_posted(post)
    shared = getattr(post, "shared_post", None)
    if shared and getattr(shared, "kind", "") in ("link", "video"):
        hydrate_posted(shared)
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
