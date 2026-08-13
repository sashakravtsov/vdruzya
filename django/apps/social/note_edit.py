"""Note / post edit helpers — views_wall_ops.post_edit stays thin."""
from __future__ import annotations

from apps.social.forms import NoteForm, PostForm
from apps.social.services import bump_news, now, wall_owner_id


def can_edit(me, post):
    if not me or post.social_user_id != me.id:
        return False, "Нельзя редактировать.", None
    on_wall = (post.topic or "").startswith("wall:")
    is_note = getattr(post, "kind", None) == "note" or (post.topic or "") == "note"
    if on_wall and not is_note:
        oid = wall_owner_id(post)
        return False, "Запись на стене нельзя редактировать — только удалить.", (
            f"/profile/{oid}" if oid else None
        )
    return True, None, is_note


def next_url(request, me, is_note):
    return request.POST.get("next") or request.GET.get("next") or (
        f"/profile/{me.id}?tab=notes" if is_note else "/feed"
    )


def save_note(post, form) -> bool:
    if not form.is_valid():
        return False
    post.media_label = form.cleaned_data["title"]
    post.body = form.cleaned_data["body"]
    post.visibility = form.cleaned_data["visibility"]
    post.kind = "note"
    post.topic = "note"
    post.updated_at = now()
    fields = ["media_label", "body", "visibility", "kind", "topic", "updated_at"]
    from apps.social.media import try_save_image
    path = try_save_image(form.cleaned_data.get("photo"), "notes")
    if path:
        post.media_path = path
        fields.append("media_path")
    post.save(update_fields=fields)
    bump_news()
    return True


def save_post(post, form) -> bool:
    if not form.is_valid():
        return False
    obj = form.save(commit=False)
    obj.body = (obj.body or "").strip()
    obj.updated_at = now()
    obj.save(update_fields=["body", "visibility", "updated_at"])
    bump_news()
    return True


def edit_forms(request, post, is_note):
    if is_note:
        initial = {
            "title": post.media_label or "",
            "body": post.body or "",
            "visibility": post.visibility or "public",
        }
        return NoteForm(
            request.POST or None, request.FILES or None,
            initial=None if request.method == "POST" else initial,
        )
    return PostForm(request.POST or None, request.FILES or None, instance=post, simple=False)
