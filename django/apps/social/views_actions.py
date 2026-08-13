from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.social.forms import CommentForm
from apps.social.models import Comment, Post, SocialProfile
from apps.social.models.legacy import Reaction
from apps.social.services import bump_news, now as _now, profile_of


@login_required
def profile_edit(request):
    from apps.social.profile_page import build_edit_context
    from apps.social import relationship as relmod

    me = profile_of(request.user)
    ctx = build_edit_context(me, request)
    form = ctx["form"]
    if request.method == "POST" and form.is_valid():
        old_partner_id = me.relationship_with_id
        obj = form.save(commit=False)
        obj.updated_at = _now()
        obj.save()
        if ctx["section"] in ("basic", "contact") and (obj.city or obj.hometown):
            from apps.social import osm
            osm.ensure_profile_geo(obj, force=True, network=True)
        # Relationship confirmation (classic partner must accept)
        partner = obj.relationship_with
        status = obj.relationship_status or ""
        if partner and status in relmod.PARTNER_STATUSES:
            if partner.id != old_partner_id:
                relmod.clear_partner_requests(obj)
            relmod.request_partner(obj, partner, status)
        else:
            relmod.clear_partner_requests(obj)
        messages.success(request, "Профиль сохранён.")
        return redirect(f"{request.path}?section={ctx['section']}")
    return render(request, "social/profile_edit.html", ctx)


@login_required
@require_POST
def relationship_accept(request, pk, req_id):
    from apps.social import relationship as relmod

    me = profile_of(request.user)
    if not me or me.id != pk:
        messages.error(request, "Нельзя подтвердить.")
        return redirect(request.POST.get("next") or "friends")
    if relmod.accept(me, req_id):
        messages.success(request, "Отношения подтверждены.")
    else:
        messages.error(request, "Заявка не найдена.")
    return redirect(request.POST.get("next") or "friends")


@login_required
@require_POST
def relationship_decline(request, pk, req_id):
    from apps.social import relationship as relmod

    me = profile_of(request.user)
    if not me or me.id != pk:
        messages.error(request, "Нельзя отклонить.")
        return redirect(request.POST.get("next") or "friends")
    if relmod.decline(me, req_id):
        messages.info(request, "Заявка отклонена.")
    else:
        messages.error(request, "Заявка не найдена.")
    return redirect(request.POST.get("next") or "friends")


@login_required
@require_POST
def feed_hide_actor(request, pk):
    from apps.social import feed_hide as fh

    me = profile_of(request.user)
    if fh.hide_actor(me, pk):
        messages.info(request, "Истории этого человека скрыты из ленты.")
    else:
        messages.error(request, "Нельзя скрыть.")
    return redirect(request.POST.get("next") or "feed")


@login_required
@require_POST
def feed_unhide_actor(request, pk):
    from apps.social import feed_hide as fh

    me = profile_of(request.user)
    if fh.unhide_actor(me, pk):
        messages.success(request, "Человек снова виден в ленте.")
    else:
        messages.error(request, "Не найдено.")
    return redirect(request.POST.get("next") or "feed")


@login_required
@require_POST
def feed_hide_story(request):
    from apps.social import feed_hide as fh

    me = profile_of(request.user)
    key = request.POST.get("story_key") or ""
    if fh.hide_story(me, key):
        messages.info(request, "Запись скрыта из ленты.")
    else:
        messages.error(request, "Нельзя скрыть запись.")
    return redirect(request.POST.get("next") or "feed")


@login_required
@require_POST
def family_request(request):
    from apps.social import family as fam

    me = profile_of(request.user)
    if fam.request(me, request.POST.get("person"), request.POST.get("kind") or ""):
        messages.success(request, "Запрос отправлен — ждёт подтверждения.")
    else:
        messages.error(request, "Не удалось добавить.")
    return redirect(request.POST.get("next") or "friends")


@login_required
@require_POST
def family_accept(request, pk):
    from apps.social import family as fam

    me = profile_of(request.user)
    if fam.accept(me, pk):
        messages.success(request, "Семейная связь подтверждена.")
    else:
        messages.error(request, "Заявка не найдена.")
    return redirect(request.POST.get("next") or "friends")


@login_required
@require_POST
def family_decline(request, pk):
    from apps.social import family as fam

    me = profile_of(request.user)
    if fam.decline(me, pk):
        messages.info(request, "Заявка отклонена.")
    else:
        messages.error(request, "Заявка не найдена.")
    return redirect(request.POST.get("next") or "friends")


@login_required
@require_POST
def family_remove(request, pk):
    from apps.social import family as fam

    me = profile_of(request.user)
    if fam.remove(me, pk):
        messages.info(request, "Семейная связь удалена.")
    else:
        messages.error(request, "Нельзя удалить.")
    return redirect(request.POST.get("next") or f"/profile/{me.id}?tab=info")


@login_required
@require_POST
def post_create(request):
    from apps.social.throttle import throttle
    from apps.social.wall_compose import create_wall_post

    @throttle("posts", 20, 60)
    def _go(req):
        return create_wall_post(req)

    return _go(request)


@login_required
@require_POST
def note_create(request):
    """FB Notes publish — kind=note, title in media_label."""
    from apps.social.throttle import throttle
    from apps.social.wall_compose import create_note

    @throttle("posts", 20, 60)
    def _go(req):
        return create_note(req)

    return _go(request)


@login_required
@require_POST
def status_update(request):
    from apps.social.wall_compose import update_status
    return update_status(request)


@login_required
@require_POST
def comment_create(request, post_id):
    from django.urls import reverse
    from apps.social.services import feed_queryset

    me = profile_of(request.user)
    post = get_object_or_404(feed_queryset(me), pk=post_id)
    form = CommentForm(request.POST)
    if form.is_valid() and me:
        Comment.objects.create(
            post=post, social_user=me, body=form.cleaned_data["body"], created_at=_now(),
        )
        bump_news()
    nxt = request.POST.get("next") or reverse("feed")
    if "#" not in nxt:
        nxt = f"{nxt}#c-wall-{post_id}"
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
def post_like(request, post_id):
    from apps.social.likes import toggle_like
    from apps.social.services import post_visible_q

    me = profile_of(request.user)
    post = get_object_or_404(Post, pk=post_id)
    if not Post.objects.filter(pk=post.id).filter(post_visible_q(me)).exists():
        messages.error(request, "Запись недоступна.")
        return redirect(request.POST.get("next") or "feed")
    out = toggle_like(me, post)
    if out == "liked":
        messages.success(request, "Вам это нравится.")
    elif out == "unliked":
        messages.info(request, "Отметка снята.")
    return redirect(request.POST.get("next") or post.get_absolute_url())


@login_required
@require_POST
def post_share(request, post_id):
    from apps.social.shares import share_to_wall
    from apps.social.services import post_visible_q

    me = profile_of(request.user)
    post = get_object_or_404(Post, pk=post_id)
    if not Post.objects.filter(pk=post.id).filter(post_visible_q(me)).exists():
        messages.error(request, "Запись недоступна.")
        return redirect(request.POST.get("next") or "feed")
    shared = share_to_wall(me, post, request.POST.get("body") or "")
    if not shared:
        messages.error(request, "Нельзя поделиться этой записью.")
        return redirect(request.POST.get("next") or post.get_absolute_url())
    messages.success(request, "Запись появилась на вашей стене.")
    return redirect(request.POST.get("next") or f"/profile/{me.id}")


@login_required
@require_POST
def post_delete(request, post_id):
    from apps.social.services import can_manage_wall_post
    from apps.social.models.legacy import CommentReaction, PostTag
    me = profile_of(request.user)
    post = get_object_or_404(Post, pk=post_id)
    if not can_manage_wall_post(me, post):
        messages.error(request, "Нельзя удалить.")
        return redirect(request.POST.get("next") or "feed")
    cids = list(Comment.objects.filter(post=post).values_list("id", flat=True))
    if cids:
        CommentReaction.objects.filter(comment_id__in=cids).delete()
    Comment.objects.filter(post=post).delete()
    Reaction.objects.filter(post=post).delete()
    PostTag.objects.filter(post=post).delete()
    post.delete()
    messages.success(request, "Запись удалена.")
    return redirect(request.POST.get("next") or "feed")


@login_required
@require_POST
def comment_delete(request, comment_id):
    from apps.social.services import can_manage_wall_comment
    from apps.social.models.legacy import CommentReaction
    me = profile_of(request.user)
    c = get_object_or_404(Comment.objects.select_related("post"), pk=comment_id)
    if not can_manage_wall_comment(me, c):
        return redirect(request.POST.get("next") or "feed")
    CommentReaction.objects.filter(comment=c).delete()
    c.delete()
    bump_news()
    return redirect(request.POST.get("next") or "feed")


@login_required
@require_POST
def comment_like(request, comment_id):
    from apps.social.likes import toggle_comment_like
    from apps.social.services import post_visible_q

    me = profile_of(request.user)
    c = get_object_or_404(Comment.objects.select_related("post"), pk=comment_id)
    if not Post.objects.filter(pk=c.post_id).filter(post_visible_q(me)).exists():
        messages.error(request, "Комментарий недоступен.")
        return redirect(request.POST.get("next") or "feed")
    out = toggle_comment_like(me, c)
    if out == "liked":
        messages.success(request, "Вам это нравится.")
    elif out == "unliked":
        messages.info(request, "Отметка снята.")
    return redirect(request.POST.get("next") or c.post.get_absolute_url())


@login_required
@require_POST
def post_tag(request, post_id):
    from apps.social import post_tags as ptags
    from apps.social.services import post_visible_q

    me = profile_of(request.user)
    post = get_object_or_404(Post, pk=post_id)
    if not Post.objects.filter(pk=post.id).filter(post_visible_q(me)).exists():
        messages.error(request, "Запись недоступна.")
        return redirect(request.POST.get("next") or "feed")
    tag = ptags.add_tag(me, post, request.POST.get("person"))
    if tag:
        messages.success(request, "Отмечено.")
    else:
        messages.error(request, "Не удалось отметить.")
    return redirect(request.POST.get("next") or post.get_absolute_url())


@login_required
@require_POST
def post_tag_delete(request, post_id, tag_id):
    from apps.social import post_tags as ptags
    from apps.social.models import PostTag

    me = profile_of(request.user)
    post = get_object_or_404(Post, pk=post_id)
    tag = get_object_or_404(PostTag, pk=tag_id, post=post)
    if ptags.remove_tag(me, tag):
        messages.info(request, "Отметка снята.")
    else:
        messages.error(request, "Нельзя удалить отметку.")
    return redirect(request.POST.get("next") or post.get_absolute_url())


@login_required
@require_POST
def avatar_upload(request):
    from apps.social.media import try_save_image
    me = profile_of(request.user)
    path = try_save_image(request.FILES.get("avatar"), "avatars") if me else None
    if path:
        me.avatar_path = path
        me.updated_at = _now()
        me.save(update_fields=["avatar_path", "updated_at"])
        Post.objects.create(
            social_user=me, body="", visibility="friends",
            kind="photo", topic="picture", media_path=me.avatar_path,
            created_at=_now(), updated_at=_now(),
        )
        bump_news()
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

