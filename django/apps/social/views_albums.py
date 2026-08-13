"""Albums / photos FBVs — classic FB Photos."""
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required, login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.social.albums import (
    add_comment, albums_for, albums_with_covers, can_edit, can_view, comments_for,
    delete_comment, delete_photo_file, neighbors, save_photos,
)
from apps.social.forms import AlbumForm, CommentForm, PhotoUploadForm
from apps.social.models import Album, Photo, PhotoComment
from apps.social.services import can_manage_photo_comment, get_profile, now, profile_of


def _forbid(request, album=None):
    return render(
        request, "social/album_locked.html",
        {"album": album, "me": profile_of(request.user) if request.user.is_authenticated else None},
        status=403,
    )


@login_required
@require_http_methods(["GET", "HEAD", "POST"])
def albums(request):
    from apps.social.media import save_image
    me = profile_of(request.user)
    form = AlbumForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid() and me:
        a = form.save(commit=False)
        a.social_user, a.created_at, a.updated_at = me, now(), now()
        cover = form.cleaned_data.get("cover")
        if cover:
            a.cover_path = save_image(cover, "albums")
        a.save()
        messages.success(request, "Альбом создан.")
        return redirect("albums.show", album_id=a.id)
    items = (
        albums_with_covers(Album.objects.filter(social_user=me))
        .annotate(n=Count("photos"))
        .order_by("-id")
    ) if me else []
    return render(
        request, "social/albums.html",
        {"albums": items, "form": form, "me": me, "owner": me, "is_own": True},
    )


@login_not_required
def profile_albums(request, pk):
    owner = get_profile(pk)
    me = profile_of(request.user) if request.user.is_authenticated else None
    return render(
        request, "social/albums.html",
        {
            "owner": owner, "albums": albums_for(owner, me, 40), "me": me,
            "is_own": bool(me and me.id == owner.id), "form": None,
        },
    )


@login_not_required
def album_show(request, album_id):
    album = get_object_or_404(Album.objects.select_related("social_user"), pk=album_id)
    me = profile_of(request.user) if request.user.is_authenticated else None
    if not can_view(album, me):
        return _forbid(request, album)
    owner = can_edit(album, me)
    photos = list(album.photos.all().order_by("id")[:120])
    return render(
        request, "social/album.html",
        {"album": album, "photos": photos, "me": me, "is_owner": owner,
         "upload_form": PhotoUploadForm() if owner else None},
    )


@login_required
@require_http_methods(["GET", "POST"])
def album_edit(request, album_id):
    from apps.social.media import save_image
    me = profile_of(request.user)
    album = get_object_or_404(Album, pk=album_id)
    if not can_edit(album, me):
        return _forbid(request, album)
    form = AlbumForm(request.POST or None, request.FILES or None, instance=album)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        cover = form.cleaned_data.get("cover")
        if cover:
            obj.cover_path = save_image(cover, "albums")
        obj.updated_at = now()
        obj.save()
        messages.success(request, "Альбом сохранён.")
        return redirect("albums.show", album_id=album.id)
    return render(request, "social/album_edit.html", {"form": form, "album": album, "me": me})


@login_required
@require_POST
def album_delete(request, album_id):
    me = profile_of(request.user)
    album = get_object_or_404(Album, pk=album_id)
    if not can_edit(album, me):
        messages.error(request, "Нельзя удалить.")
        return redirect("albums")
    for p in album.photos.all():
        delete_photo_file(p)
    album.delete()
    messages.success(request, "Альбом удалён.")
    return redirect("albums")


@login_required
@require_POST
def photo_upload(request, album_id):
    me = profile_of(request.user)
    album = get_object_or_404(Album, pk=album_id)
    if not can_edit(album, me):
        messages.error(request, "Нельзя загружать.")
        return redirect("albums.show", album_id=album_id)
    form = PhotoUploadForm(request.POST, request.FILES)
    files = list(request.FILES.getlist("photo") or [])
    if not files:
        messages.error(request, "Выберите одно или несколько изображений (JPEG, PNG, GIF).")
        return redirect("albums.show", album_id=album_id)
    if not form.is_valid():
        # title is optional — still accept files
        title = (request.POST.get("title") or "").strip()
    else:
        title = form.cleaned_data.get("title") or ""
    n, skipped = save_photos(album, files, title)
    if n:
        msg = "Фото добавлено." if n == 1 else f"Добавлено фото: {n}."
        if skipped:
            msg += f" Пропущено: {skipped}."
        messages.success(request, msg)
    else:
        messages.error(request, "Не удалось загрузить (размер/формат). JPEG, PNG, GIF · до 3 МБ.")
    return redirect("albums.show", album_id=album_id)


@login_not_required
def photo_show(request, album_id, photo_id):
    from apps.social import photo_tags as pt
    from apps.social.likes import attach_photo_likes

    album = get_object_or_404(Album.objects.select_related("social_user"), pk=album_id)
    me = profile_of(request.user) if request.user.is_authenticated else None
    if not can_view(album, me):
        return _forbid(request, album)
    photo = get_object_or_404(Photo, pk=photo_id, album=album)
    attach_photo_likes([photo], me)
    prev_id, next_id, n, pos = neighbors(album, photo.id)
    tagging = bool(me and pt.can_tag(me, album))
    return render(
        request, "social/photo.html",
        {
            "album": album, "photo": photo, "me": me, "is_owner": can_edit(album, me),
            "prev_id": prev_id, "next_id": next_id, "n": n, "pos": pos,
            "comments": comments_for(photo),
            "comment_form": CommentForm() if me else None,
            "tags": pt.tags_for(photo),
            "tag_candidates": pt.tag_candidates(me, photo) if tagging else [],
            "can_tag": tagging,
        },
    )


@login_required
@require_POST
def photo_like(request, album_id, photo_id):
    from apps.social.likes import toggle_photo_like

    me = profile_of(request.user)
    album = get_object_or_404(Album, pk=album_id)
    photo = get_object_or_404(Photo, pk=photo_id, album=album)
    if not can_view(album, me):
        return _forbid(request, album)
    out = toggle_photo_like(me, photo)
    if out == "liked":
        messages.success(request, "Вам это нравится.")
    elif out == "unliked":
        messages.info(request, "Отметка снята.")
    return redirect("albums.photos.show", album_id=album_id, photo_id=photo_id)


@login_required
@require_POST
def photo_tag(request, album_id, photo_id):
    from apps.social import photo_tags as pt

    me = profile_of(request.user)
    album = get_object_or_404(Album, pk=album_id)
    photo = get_object_or_404(Photo, pk=photo_id, album=album)
    if not can_view(album, me):
        return _forbid(request, album)
    tag = pt.add_tag(me, photo, album, request.POST.get("person"))
    if tag:
        if getattr(tag, "status", "") == "pending":
            messages.success(request, "Отметка отправлена — ждёт подтверждения.")
        else:
            messages.success(request, "Отмечено на фото.")
    else:
        messages.error(request, "Не удалось отметить.")
    return redirect("albums.photos.show", album_id=album_id, photo_id=photo_id)


@login_required
@require_POST
def photo_tag_approve(request, album_id, photo_id, tag_id):
    from apps.social import photo_tags as pt

    me = profile_of(request.user)
    album = get_object_or_404(Album, pk=album_id)
    get_object_or_404(Photo, pk=photo_id, album=album)
    if pt.approve(me, tag_id):
        messages.success(request, "Отметка подтверждена.")
    else:
        messages.error(request, "Нельзя подтвердить.")
    nxt = request.POST.get("next") or f"/albums/{album_id}/photos/{photo_id}"
    return redirect(nxt)


@login_required
@require_POST
def photo_tag_decline(request, album_id, photo_id, tag_id):
    from apps.social import photo_tags as pt

    me = profile_of(request.user)
    album = get_object_or_404(Album, pk=album_id)
    get_object_or_404(Photo, pk=photo_id, album=album)
    if pt.decline(me, tag_id):
        messages.info(request, "Отметка отклонена.")
    else:
        messages.error(request, "Нельзя отклонить.")
    nxt = request.POST.get("next") or f"/albums/{album_id}/photos/{photo_id}"
    return redirect(nxt)


@login_required
@require_POST
def photo_tag_delete(request, album_id, photo_id, tag_id):
    from apps.social import photo_tags as pt
    from apps.social.models import PhotoTag

    me = profile_of(request.user)
    album = get_object_or_404(Album, pk=album_id)
    photo = get_object_or_404(Photo, pk=photo_id, album=album)
    tag = get_object_or_404(PhotoTag, pk=tag_id, photo=photo)
    if pt.remove_tag(me, tag, album):
        messages.info(request, "Отметка удалена.")
    else:
        messages.error(request, "Нельзя удалить отметку.")
    return redirect("albums.photos.show", album_id=album_id, photo_id=photo_id)


@login_required
@require_POST
def photo_comment(request, album_id, photo_id):
    me = profile_of(request.user)
    album = get_object_or_404(Album, pk=album_id)
    photo = get_object_or_404(Photo, pk=photo_id, album=album)
    form = CommentForm(request.POST)
    if not (form.is_valid() and add_comment(me, photo, album, form.cleaned_data["body"])):
        messages.error(request, "Не удалось добавить комментарий.")
    return redirect("albums.photos.show", album_id=album_id, photo_id=photo_id)


@login_required
@require_POST
def photo_comment_delete(request, album_id, photo_id, comment_id):
    me = profile_of(request.user)
    album = get_object_or_404(Album, pk=album_id)
    comment = get_object_or_404(PhotoComment, pk=comment_id, photo_id=photo_id, photo__album=album)
    if not can_manage_photo_comment(me, comment, album) or not delete_comment(me, comment, album):
        messages.error(request, "Нельзя удалить.")
    else:
        from apps.social.models.legacy import PhotoCommentReaction
        PhotoCommentReaction.objects.filter(comment_id=comment_id).delete()
    return redirect("albums.photos.show", album_id=album_id, photo_id=photo_id)


@login_required
@require_POST
def photo_comment_like(request, album_id, photo_id, comment_id):
    from apps.social.likes import toggle_photo_comment_like

    me = profile_of(request.user)
    album = get_object_or_404(Album, pk=album_id)
    if not can_view(album, me):
        return _forbid(request, album)
    comment = get_object_or_404(PhotoComment, pk=comment_id, photo_id=photo_id, photo__album=album)
    out = toggle_photo_comment_like(me, comment)
    if out == "liked":
        messages.success(request, "Вам это нравится.")
    elif out == "unliked":
        messages.info(request, "Отметка снята.")
    return redirect("albums.photos.show", album_id=album_id, photo_id=photo_id)


@login_required
@require_POST
def photo_caption(request, album_id, photo_id):
    me = profile_of(request.user)
    album = get_object_or_404(Album, pk=album_id)
    photo = get_object_or_404(Photo, pk=photo_id, album=album)
    if not can_edit(album, me):
        return _forbid(request, album)
    title = (request.POST.get("title") or "").strip()[:120]
    if not title:
        messages.error(request, "Укажите название.")
        return redirect("albums.photos.show", album_id=album_id, photo_id=photo_id)
    photo.title, photo.updated_at = title, now()
    photo.save(update_fields=["title", "updated_at"])
    messages.success(request, "Подпись сохранена.")
    return redirect("albums.photos.show", album_id=album_id, photo_id=photo_id)


@login_required
@require_POST
def photo_cover(request, album_id, photo_id):
    me = profile_of(request.user)
    album = get_object_or_404(Album, pk=album_id)
    photo = get_object_or_404(Photo, pk=photo_id, album=album)
    if not can_edit(album, me) or not photo.path:
        messages.error(request, "Нельзя.")
        return redirect("albums.photos.show", album_id=album_id, photo_id=photo_id)
    album.cover_path, album.updated_at = photo.path, now()
    album.save(update_fields=["cover_path", "updated_at"])
    messages.success(request, "Обложка альбома обновлена.")
    return redirect("albums.show", album_id=album_id)


@login_required
@require_POST
def photo_delete(request, album_id, photo_id):
    me = profile_of(request.user)
    album = get_object_or_404(Album, pk=album_id)
    photo = get_object_or_404(Photo, pk=photo_id, album=album)
    if not can_edit(album, me):
        messages.error(request, "Нельзя удалить.")
        return redirect("albums.show", album_id=album_id)
    if album.cover_path and album.cover_path == photo.path:
        album.cover_path, album.updated_at = None, now()
        album.save(update_fields=["cover_path", "updated_at"])
    delete_photo_file(photo)
    messages.success(request, "Фото удалено.")
    return redirect("albums.show", album_id=album_id)
