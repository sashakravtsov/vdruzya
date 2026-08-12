"""FB 2011 FBVs — Subscribe, Timeline milestones, Open Graph, cover (classic chrome)."""
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.social import era2011 as e11
from apps.social.services import get_profile, profile_of


@login_required
@require_POST
def follow_toggle(request, pk):
    me = profile_of(request.user)
    other = get_profile(pk)
    action = (request.POST.get("action") or "follow").lower()
    if action == "unfollow":
        if e11.unfollow(me, other):
            messages.info(request, f"Вы отписались от {other.name}.")
    else:
        out = e11.follow(me, other)
        if out == "ok":
            messages.success(request, f"Вы подписались на {other.name}.")
        elif out == "pending":
            messages.info(request, "Вы уже подписаны.")
        elif out == "blocked":
            messages.error(request, "Подписка недоступна.")
    return redirect(request.POST.get("next") or other)


@login_required
@require_POST
def milestone_create(request, pk):
    me = profile_of(request.user)
    profile = get_profile(pk)
    if not me or me.id != profile.id:
        messages.error(request, "Нельзя добавить чужой этап.")
        return redirect(profile)
    raw = (request.POST.get("occurred_on") or "").strip()
    try:
        occurred = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Укажите дату в формате ГГГГ-ММ-ДД.")
        return redirect(f"/profile/{pk}?tab=timeline")
    row = e11.add_milestone(
        me,
        title=request.POST.get("title") or "",
        body=request.POST.get("body") or "",
        kind=request.POST.get("kind") or "life",
        occurred_on=occurred,
    )
    if row:
        messages.success(request, "Этап добавлен на Timeline.")
    else:
        messages.error(request, "Не удалось сохранить этап.")
    return redirect(f"/profile/{pk}?tab=timeline&y={occurred.year}")


@login_required
@require_POST
def milestone_delete(request, pk, mid):
    me = profile_of(request.user)
    profile = get_profile(pk)
    if me and me.id == profile.id and e11.delete_milestone(me, mid):
        messages.info(request, "Этап удалён.")
    return redirect(request.POST.get("next") or f"/profile/{pk}?tab=timeline")


@login_required
@require_POST
def og_publish(request):
    me = profile_of(request.user)
    row = e11.publish_og(
        me,
        verb=request.POST.get("verb") or "",
        title=request.POST.get("title") or "",
        url=request.POST.get("url") or "",
        app_slug=request.POST.get("app") or "custom",
    )
    if row:
        messages.success(request, f"История «{e11.og_label(row.verb)}» опубликована.")
    else:
        messages.error(request, "Укажите тип и название.")
    return redirect(request.POST.get("next") or "feed")


@login_required
@require_GET
def og_home(request):
    """Classic Open Graph publisher — listening / reading / watching."""
    from apps.social.models import OgStory

    me = profile_of(request.user)
    recent = list(OgStory.objects.filter(social_user=me).order_by("-id")[:20]) if me else []
    return render(request, "social/og.html", {
        "me": me, "recent": recent, "verbs": sorted(e11.OG_VERBS),
        "verb_labels": e11.OG_LABELS, "nav": "og",
    })


@login_required
@require_POST
def cover_upload(request):
    from django.conf import settings
    from apps.social.media import save_image
    from apps.social.services import bump_news, now

    me = profile_of(request.user)
    f = request.FILES.get("cover")
    if me and f and f.size <= settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
        me.cover_path = save_image(f, "covers")
        me.updated_at = now()
        me.save(update_fields=["cover_path", "updated_at"])
        bump_news()
        messages.success(request, "Обложка профиля обновлена.")
    return redirect(request.POST.get("next") or "/profile/edit?section=picture")


@login_required
@require_POST
def cover_clear(request):
    from apps.social.services import bump_news, now

    me = profile_of(request.user)
    if me and me.cover_path:
        me.cover_path = None
        me.updated_at = now()
        me.save(update_fields=["cover_path", "updated_at"])
        bump_news()
        messages.info(request, "Обложка удалена.")
    return redirect(request.POST.get("next") or "/profile/edit?section=picture")
