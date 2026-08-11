"""Albums / photos FBVs — short only, FB 2005."""
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required, login_required
from django.db.models import Count, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.social.album_access import can_edit, can_view, visible_q
from apps.social.album_media import delete_photo_file, neighbors, save_photos
from apps.social.forms import AlbumForm, PhotoUploadForm
from apps.social.models import Album, Photo
from apps.social.services import get_profile, now, profile_of


def _forbid(request, album=None):
    return render(
        request, "social/album_locked.html",
        {"album": album, "me": profile_of(request.user) if request.user.is_authenticated else None},
        status=403,
    )


def albums_for_profile(profile, viewer, limit=4):
    return list(
        Album.objects.filter(social_user=profile).filter(visible_q(viewer))
        .annotate(n=Count("photos")).order_by("-id")[:limit]
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
        Album.objects.filter(social_user=me)
        .annotate(n=Count("photos"))
        .prefetch_related(
            Prefetch("photos", queryset=Photo.objects.exclude(path="").order_by("id"), to_attr="preview")
        )
        .order_by("-id")
    ) if me else []
    return render(request, "social/albums.html", {"albums": items, "form": form, "me": me})


@login_not_required
def profile_albums(request, pk):
    owner = get_profile(pk)
    me = profile_of(request.user) if request.user.is_authenticated else None
    return render(
        request, "social/albums_user.html",
        {"owner": owner, "albums": albums_for_profile(owner, me, 40), "me": me,
         "is_own": bool(me and me.id == owner.id)},
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
    if not form.is_valid():
        messages.error(request, "Укажите название и файл изображения.")
        return redirect("albums.show", album_id=album_id)
    files = list(request.FILES.getlist("photo") or [])
    one = form.cleaned_data.get("photo")
    if one and one not in files:
        files = [one] + files
    n = save_photos(album, files, form.cleaned_data.get("title") or "")
    if n:
        messages.success(request, "Фото добавлено." if n == 1 else f"Добавлено фото: {n}.")
    else:
        messages.error(request, "Файл слишком большой или неверный.")
    return redirect("albums.show", album_id=album_id)


@login_not_required
def photo_show(request, album_id, photo_id):
    album = get_object_or_404(Album.objects.select_related("social_user"), pk=album_id)
    me = profile_of(request.user) if request.user.is_authenticated else None
    if not can_view(album, me):
        return _forbid(request, album)
    photo = get_object_or_404(Photo, pk=photo_id, album=album)
    prev_id, next_id, n, pos = neighbors(album, photo.id)
    return render(
        request, "social/photo.html",
        {"album": album, "photo": photo, "me": me, "is_owner": can_edit(album, me),
         "prev_id": prev_id, "next_id": next_id, "n": n, "pos": pos},
    )


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


@login_required
def compose_album_photos(request):
    """JSON for wall compose album picker."""
    me = profile_of(request.user)
    if not me:
        return JsonResponse({"albums": []})
    rows = []
    for a in Album.objects.filter(social_user=me).order_by("-id")[:20]:
        photos = list(Photo.objects.filter(album=a).exclude(path="").order_by("id")[:24])
        rows.append({
            "id": a.id, "title": a.title, "photos_count": len(photos),
            "photos": [{"id": p.id, "title": p.title, "url": p.url} for p in photos],
        })
    return JsonResponse({"albums": rows})
