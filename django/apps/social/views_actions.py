from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.social.forms import CommentForm, PostForm
from apps.social.models import Comment, Post, SocialProfile
from apps.social.models.feed import Reaction
from apps.social.services import bump_news, now as _now, profile_of


@login_required
def profile_edit(request):
    from apps.social.profile_page import build_edit_context

    me = profile_of(request.user)
    ctx = build_edit_context(me, request)
    form = ctx["form"]
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.updated_at = _now()
        obj.save()
        messages.success(request, "Профиль сохранён.")
        return redirect(f"{request.path}?section={ctx['section']}")
    return render(request, "social/profile_edit.html", ctx)


@login_required
@require_POST
def post_create(request):
    from django.db.models import Q
    from apps.social.models import Friendship
    from apps.social.profile_page import can_write_wall
    from apps.social.throttle import throttle
    from apps.social.attach import attach_wall

    @throttle("posts", 20, 60)
    def _go(req):
        from apps.social.profile_page import wall_post_visibility

        me = profile_of(req.user)
        form = PostForm(req.POST, req.FILES, simple=True)
        if not (form.is_valid() and me):
            return redirect(req.POST.get("next") or "feed")
        target = get_object_or_404(SocialProfile, pk=req.POST.get("wall_to") or me.id)
        rel = None
        if target.id != me.id:
            rel = Friendship.objects.filter(
                Q(user=me, friend=target) | Q(user=target, friend=me)
            ).first()
        if not can_write_wall(me, target, rel):
            messages.error(req, "Писать на стену нельзя.")
            return redirect(target)
        post = form.save(commit=False)
        post.social_user = me
        post.body = (post.body or "").strip()
        post.topic = f"wall:{target.id}"
        post.visibility = wall_post_visibility(target)
        files = list(req.FILES.getlist("photo"))
        post.kind = "photo" if files else "text"
        post.created_at = post.updated_at = _now()
        post.save()
        path = attach_wall(post, files, me, max_photos=1)
        if path:
            post.media_path = path
            post.kind = "photo"
            post.save(update_fields=["media_path", "kind"])
        bump_news()
        messages.success(req, "Запись опубликована.")
        return redirect(req.POST.get("next") or target)

    return _go(request)


@login_required
@require_POST
def status_update(request):
    from apps.social.forms import StatusForm
    me = profile_of(request.user)
    form = StatusForm(request.POST)
    if me and form.is_valid():
        headline = (form.cleaned_data.get("headline") or "").strip() or None
        me.headline = headline
        me.updated_at = _now()
        me.save(update_fields=["headline", "updated_at"])
        if headline:
            Post.objects.create(
                social_user=me, body=headline, visibility="public",
                kind="status", topic="status", created_at=_now(), updated_at=_now(),
            )
        bump_news()
        messages.success(request, "Статус обновлён.")
    return redirect(request.POST.get("next") or "feed")


@login_required
@require_POST
def comment_create(request, post_id):
    from django.urls import reverse
    from apps.social.services import feed_queryset

    me = profile_of(request.user)
    post = get_object_or_404(feed_queryset(me), pk=post_id)
    form = CommentForm(request.POST)
    if form.is_valid() and me:
        c = form.save(commit=False)
        c.post, c.social_user, c.created_at = post, me, _now()
        c.save()
        bump_news()
    nxt = request.POST.get("next") or reverse("feed")
    if "#" not in nxt:
        nxt = f"{nxt}#c-{post_id}"
    return redirect(nxt)


@login_required
@require_POST
def poke(request, pk):
    from apps.social import notify
    from apps.social.friendship import other_or_404
    me = profile_of(request.user)
    other = other_or_404(pk)
    out = notify.poke(me, other)
    if out == "ok":
        messages.info(request, f"Вы подмигнули {other.name}.")
    elif out == "pending":
        messages.info(request, "Подмигивание уже отправлено.")
    elif out == "blocked":
        return redirect(request.POST.get("next") or f"/profile/{pk}")
    return redirect(request.POST.get("next") or f"/profile/{pk}")


@login_required
@require_POST
def post_delete(request, post_id):
    from apps.social.services import can_manage_wall_post
    me = profile_of(request.user)
    post = get_object_or_404(Post, pk=post_id)
    if not can_manage_wall_post(me, post):
        messages.error(request, "Нельзя удалить.")
        return redirect(request.POST.get("next") or "feed")
    Comment.objects.filter(post=post).delete()
    Reaction.objects.filter(post=post).delete()
    post.delete()
    messages.success(request, "Запись удалена.")
    return redirect(request.POST.get("next") or "feed")


@login_required
@require_POST
def comment_delete(request, comment_id):
    from apps.social.services import can_manage_wall_comment
    me = profile_of(request.user)
    c = get_object_or_404(Comment.objects.select_related("post"), pk=comment_id)
    if not can_manage_wall_comment(me, c):
        return redirect(request.POST.get("next") or "feed")
    c.delete()
    bump_news()
    return redirect(request.POST.get("next") or "feed")


@login_required
@require_POST
def avatar_upload(request):
    from django.conf import settings
    from apps.social.media import save_image
    me = profile_of(request.user)
    f = request.FILES.get("avatar")
    if me and f and f.size <= settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
        me.avatar_path = save_image(f, "avatars")
        me.updated_at = _now()
        me.save(update_fields=["avatar_path", "updated_at"])
        Post.objects.create(
            social_user=me, body="", visibility="friends",
            kind="photo", topic="picture", media_path=me.avatar_path,
            created_at=_now(), updated_at=_now(),
        )
        messages.success(request, "Аватар обновлён.")
    return redirect("/profile/edit?section=picture")


@login_required
@require_POST
def avatar_clear(request):
    me = profile_of(request.user)
    if me and me.avatar_path:
        me.avatar_path = None
        me.updated_at = _now()
        me.save(update_fields=["avatar_path", "updated_at"])
        messages.info(request, "Фото удалено.")
    return redirect("/profile/edit?section=picture")


@login_required
@require_POST
@transaction.atomic
def block_toggle(request, pk):
    from apps.social import friendship as fr
    from apps.social.models import Block
    me, other = profile_of(request.user), get_object_or_404(SocialProfile, pk=pk)
    if me and me.id != other.id:
        if Block.objects.filter(blocker=me, blocked=other).exists():
            fr.unblock_user(me, other)
            messages.info(request, "Пользователь разблокирован.")
        else:
            fr.block_user(me, other)
            messages.info(request, "Пользователь заблокирован.")
    return redirect("profile", pk=pk)


@login_required
@require_POST
def education_save(request, pk=None):
    from apps.social.forms import EducationForm
    from apps.social.models import Education
    return _profile_row_save(
        request, Education, EducationForm, pk,
        msg_edit="Образование сохранено.", msg_add="Образование добавлено.",
    )


@login_required
@require_POST
def education_delete(request, pk):
    from apps.social.models import Education
    return _profile_row_delete(request, Education, pk)


@login_required
@require_POST
def experience_save(request, pk=None):
    from apps.social.forms import ExperienceForm
    from apps.social.models import Experience

    def _prep(obj):
        obj.description = obj.description or ""

    return _profile_row_save(
        request, Experience, ExperienceForm, pk,
        msg_edit="Работа сохранена.", msg_add="Работа добавлена.", prep=_prep,
    )


@login_required
@require_POST
def experience_delete(request, pk):
    from apps.social.models import Experience
    return _profile_row_delete(request, Experience, pk)


def _profile_row_save(request, model, form_cls, pk, *, msg_edit, msg_add, prep=None):
    me = profile_of(request.user)
    row = get_object_or_404(model, pk=pk, social_user=me) if pk else model(social_user=me)
    form = form_cls(request.POST, instance=row)
    if me and form.is_valid():
        obj = form.save(commit=False)
        if prep:
            prep(obj)
        obj.save()
        messages.success(request, msg_edit if pk else msg_add)
    return redirect("/profile/edit?section=eduwork")


def _profile_row_delete(request, model, pk):
    me = profile_of(request.user)
    model.objects.filter(pk=pk, social_user=me).delete()
    messages.info(request, "Запись удалена.")
    return redirect("/profile/edit?section=eduwork")

