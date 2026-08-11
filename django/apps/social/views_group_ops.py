"""Group ops FBVs — edit, members, message, deletes, invite, events, polls. Keep short."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods

from apps.social.forms import CommunityPostForm, GroupForm
from apps.social.models import (
    Community, CommunityJoinRequest, CommunityMember, CommunityPollOption, CommunityPost,
    CommunityPostComment, CommunityPostReaction, Conversation, ConversationMember, Event,
    Notification, SocialProfile,
)
from apps.social.polls import vote_group_option
from apps.social.services import now, profile_of

_ADMIN = ("admin", "moderator", "creator", "officer")


def _admin(me, group):
    return bool(me and CommunityMember.objects.filter(community=group, social_user=me, role__in=_ADMIN).exists())


def _member(me, group):
    return bool(me and CommunityMember.objects.filter(community=group, social_user=me).exists())


@login_required
def group_edit(request, pk):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    if not _admin(me, group):
        messages.error(request, "Только администратор.")
        return redirect("groups.show", pk=pk)
    form = GroupForm(request.POST or None, request.FILES or None, instance=group)
    if request.method == "POST" and form.is_valid():
        from apps.social.media import save_image
        obj = form.save(commit=False)
        cover = request.FILES.get("cover")
        if cover:
            obj.cover_path = save_image(cover, "groups")
        obj.updated_at = now()
        obj.save()
        cache.delete(f"news:{me.id}:60")
        messages.success(request, "Группа обновлена.")
        return redirect(obj)
    return render(request, "social/group_edit.html", {"group": group, "form": form, "me": me})


@login_required
def group_members(request, pk):
    group = get_object_or_404(Community, pk=pk)
    me = profile_of(request.user)
    rows = (
        CommunityMember.objects.filter(community=group)
        .select_related("social_user")
        .defer("social_user__looking_for", "social_user__languages")
        .order_by("social_user__name")[:200]
    )
    return render(
        request, "social/group_members.html",
        {
            "group": group, "rows": rows, "n_members": CommunityMember.objects.filter(community=group).count(),
            "me": me, "is_admin": _admin(me, group),
        },
    )


@login_required
@require_POST
def join_reject(request, pk, request_id):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    if not _admin(me, group):
        return redirect("groups.show", pk=pk)
    req = get_object_or_404(CommunityJoinRequest, pk=request_id, community=group, status="pending")
    CommunityJoinRequest.objects.filter(pk=req.pk).update(status="rejected")
    messages.info(request, "Заявка отклонена.")
    return redirect("groups.show", pk=pk)


@login_required
@require_POST
def join_cancel(request, pk):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    CommunityJoinRequest.objects.filter(community=group, social_user=me, status="pending").delete()
    messages.info(request, "Заявка отозвана.")
    return redirect("groups.show", pk=pk)


@login_required
@require_POST
@transaction.atomic
def group_message(request, pk):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    if not me or not group.messaging_enabled:
        messages.error(request, "Чат группы недоступен.")
        return redirect("groups.show", pk=pk)
    # Open groups: any logged-in user may start a thread (Laravel CommunityPolicy::message).
    if group.privacy == "closed" and not _member(me, group):
        messages.error(request, "Чат доступен участникам.")
        return redirect("groups.show", pk=pk)
    conv = Conversation.objects.filter(community_id=group.id).order_by("id").first()
    if not conv:
        t = now()
        conv = Conversation.objects.create(title=group.name, community_id=group.id, created_at=t, updated_at=t)
        ids = list(CommunityMember.objects.filter(community=group).values_list("social_user_id", flat=True)[:40])
        if me.id not in ids:
            ids.append(me.id)
        ConversationMember.objects.bulk_create(
            [ConversationMember(conversation=conv, social_user_id=i) for i in ids],
            ignore_conflicts=True,
        )
    elif not ConversationMember.objects.filter(conversation=conv, social_user=me).exists():
        ConversationMember.objects.create(conversation=conv, social_user=me)
    return redirect(f"/messenger?c={conv.id}")


@login_required
@require_POST
def group_post_delete(request, pk, post_id):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    post = get_object_or_404(CommunityPost, pk=post_id, community=group)
    if not me or (post.social_user_id != me.id and not _admin(me, group)):
        messages.error(request, "Нельзя удалить.")
        return redirect("groups.show", pk=pk)
    CommunityPostComment.objects.filter(post=post).delete()
    post.delete()
    cache.delete(f"news:{me.id}:60")
    messages.success(request, "Запись удалена.")
    return redirect("groups.show", pk=pk)


def _post_redirect(pk, post):
    if getattr(post, "topic", None) == "wall":
        return redirect(f"/groups/{pk}#topic-{post.id}")
    return redirect(f"/groups/{pk}?topic={post.id}#topic-{post.id}")


@login_required
@require_POST
def group_comment_delete(request, pk, comment_id):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    c = get_object_or_404(CommunityPostComment.objects.select_related("post"), pk=comment_id, post__community=group)
    if not me or (c.social_user_id != me.id and not _admin(me, group)):
        return redirect("groups.show", pk=pk)
    post = c.post
    c.delete()
    messages.success(request, "Комментарий удалён.")
    return _post_redirect(pk, post)


@login_required
@require_http_methods(["GET", "POST"])
def group_post_edit(request, pk, post_id):
    from apps.social.attach import attach_group
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    post = get_object_or_404(CommunityPost, pk=post_id, community=group)
    if not me or (post.social_user_id != me.id and not _admin(me, group)):
        messages.error(request, "Нельзя редактировать.")
        return redirect("groups.show", pk=pk)
    form = CommunityPostForm(request.POST or None, request.FILES or None, instance=post)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.body = (obj.body or "").strip()
        board = form.cleaned_data.get("board")
        if board in ("wall", "discussion"):
            obj.topic = board
        if _admin(me, group):
            obj.posted_as_community = bool(request.POST.get("as_community"))
        obj.updated_at = now()
        obj.save(update_fields=["body", "topic", "posted_as_community", "updated_at"])
        path = attach_group(obj, list(request.FILES.getlist("photo")), me, request.POST.getlist("album_photos"))
        if path and not obj.media_path:
            obj.media_path = path
            if obj.kind == "text":
                obj.kind = "photo"
            obj.save(update_fields=["media_path", "kind"])
        messages.success(request, "Запись обновлена.")
        return redirect("groups.show", pk=pk)
    form.fields["board"].initial = post.topic if post.topic in ("wall", "discussion") else "discussion"
    return render(request, "social/group_post_edit.html", {"group": group, "post": post, "form": form, "me": me, "is_admin": _admin(me, group)})


@login_required
@require_POST
def group_comment_update(request, pk, comment_id):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    c = get_object_or_404(CommunityPostComment.objects.select_related("post"), pk=comment_id, post__community=group)
    body = (request.POST.get("body") or "").strip()
    if me and c.social_user_id == me.id and body:
        c.body = body[:2000]
        c.save(update_fields=["body"])
        messages.success(request, "Комментарий обновлён.")
    return _post_redirect(pk, c.post)


@login_required
@require_POST
def group_poll_vote(request, pk, post_id):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    post = get_object_or_404(CommunityPost, pk=post_id, community=group, kind="poll")
    if not _member(me, group):
        return redirect("groups.show", pk=pk)
    opt = get_object_or_404(CommunityPollOption, pk=request.POST.get("option_id"), poll__post=post)
    vote_group_option(me, opt)
    return redirect(f"/groups/{pk}?topic={post_id}#topic-{post_id}")


@login_required
@require_POST
def group_invite(request, pk):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    if not _member(me, group):
        return redirect("groups.show", pk=pk)
    friend = get_object_or_404(SocialProfile, pk=request.POST.get("friend_id"))
    if CommunityMember.objects.filter(community=group, social_user=friend).exists():
        messages.info(request, "Уже в группе.")
        return redirect("groups.show", pk=pk)
    t = now()
    Notification.objects.create(
        social_user=friend, type="group_invite", title=f"Приглашение в «{group.name}»",
        body=f"{me.name} приглашает вас в группу.", url=group.get_absolute_url(),
        seen=False, created_at=t,
    )
    messages.success(request, f"Приглашение отправлено: {friend.name}.")
    return redirect("groups.show", pk=pk)


@login_required
@require_POST
def group_event_create(request, pk):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    if not _admin(me, group):
        return redirect("groups.show", pk=pk)
    title = (request.POST.get("title") or "").strip()[:160]
    place = (request.POST.get("place") or "").strip()[:160] or "—"
    raw = (request.POST.get("starts_at") or "").strip()
    starts = None
    if raw:
        from django.utils.dateparse import parse_datetime
        starts = parse_datetime(raw.replace("T", " ") + (":00" if len(raw) == 16 else ""))
        if starts and getattr(starts, "tzinfo", None):
            starts = starts.replace(tzinfo=None)
    if title and starts:
        from apps.social import events as ev
        event = ev.create_event(
            me, title=title, place=place, starts_at=starts, community=group,
        )
        if event:
            ev.set_rsvp(me, event, "going")
            messages.success(request, "Событие создано.")
        else:
            messages.error(request, "Не удалось создать событие.")
    else:
        messages.error(request, "Укажите название и дату.")
    return redirect("groups.show", pk=pk)


@login_required
@require_POST
def member_manage(request, pk, user_id):
    """Admin: remove / promote / demote members."""
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    if not _admin(me, group):
        messages.error(request, "Только администратор.")
        return redirect("groups.members", pk=pk)
    row = get_object_or_404(CommunityMember, community=group, social_user_id=user_id)
    action = request.POST.get("action")
    if action == "remove":
        if row.role == "admin" and not CommunityMember.objects.filter(
            community=group, role="admin"
        ).exclude(pk=row.pk).exists():
            messages.error(request, "Нельзя удалить единственного админа.")
        else:
            row.delete()
            messages.success(request, "Участник удалён.")
    elif action in ("member", "officer", "admin", "moderator"):
        row.role = action
        row.save(update_fields=["role"])
        messages.success(request, "Роль обновлена.")
    return redirect("groups.members", pk=pk)


@login_required
@require_POST
def group_post(request, pk):
    from apps.social.attach import attach_group
    from apps.social.polls import attach_group_poll
    from apps.social.throttle import throttle

    @throttle("gposts", 20, 60)
    def _go(req):
        me, group = profile_of(req.user), get_object_or_404(Community, pk=pk)
        is_mem = _member(me, group)
        is_admin = _admin(me, group)
        if group.posting_policy == "admins" and not is_admin:
            messages.error(req, "Писать могут только администраторы.")
            return redirect("groups.show", pk=pk)
        if group.posting_policy != "everyone" and not is_mem:
            messages.error(req, "Сначала вступите в группу.")
            return redirect("groups.show", pk=pk)
        form = CommunityPostForm(req.POST, req.FILES)
        if not form.is_valid():
            return redirect("groups.show", pk=pk)
        p = form.save(commit=False)
        p.community, p.social_user = group, me
        p.topic = form.cleaned_data.get("board") or "discussion"
        p.posted_as_community = bool(is_admin and req.POST.get("as_community"))
        labels = [x.strip() for x in (form.cleaned_data.get("poll_options") or "").splitlines() if x.strip()]
        files = list(req.FILES.getlist("photo"))
        albums = req.POST.getlist("album_photos")
        p.created_at = p.updated_at = now()
        p.body = (p.body or "").strip()
        if len(labels) >= 2:
            p.kind = "poll"
        elif files or albums:
            p.kind = "photo"
        else:
            p.kind = "text"
        p.save()
        if p.kind == "poll":
            attach_group_poll(p, labels)
        path = attach_group(p, files, me, albums)
        if path:
            p.media_path = path
            if p.kind == "text":
                p.kind = "photo"
            p.save(update_fields=["media_path", "kind"])
        cache.delete(f"news:{me.id}:60")
        messages.success(req, "Запись в группе опубликована.")
        if p.topic == "wall":
            return redirect(f"/groups/{pk}#topic-{p.id}")
        return redirect(f"/groups/{pk}?topic={p.id}#board")

    return _go(request)


@login_required
@require_POST
def group_comment(request, pk, post_id):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    post = get_object_or_404(CommunityPost, pk=post_id, community=group)
    body = (request.POST.get("body") or "").strip()
    if me and _member(me, group) and body:
        CommunityPostComment.objects.create(post=post, social_user=me, body=body, created_at=now())
    if post.topic == "wall":
        return redirect(f"/groups/{pk}#topic-{post.id}")
    return redirect(f"/groups/{pk}?topic={post.id}#board")


@login_required
@require_POST
@transaction.atomic
def group_react(request, pk, post_id):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    post = get_object_or_404(CommunityPost, pk=post_id, community=group)
    if me and _member(me, group):
        row = CommunityPostReaction.objects.filter(post=post, social_user=me, type="like").first()
        if row:
            row.delete()
        else:
            CommunityPostReaction.objects.create(post=post, social_user=me, type="like", created_at=now())
    return redirect("groups.show", pk=pk)


@login_required
@require_POST
@transaction.atomic
def join_accept(request, pk, request_id):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    if not _admin(me, group):
        messages.error(request, "Только админ группы.")
        return redirect("groups.show", pk=pk)
    req = get_object_or_404(CommunityJoinRequest, pk=request_id, community=group, status="pending")
    CommunityMember.objects.get_or_create(community=group, social_user_id=req.social_user_id, defaults={"role": "member"})
    CommunityJoinRequest.objects.filter(pk=req.pk).update(status="accepted")
    messages.success(request, "Заявка принята.")
    return redirect("groups.show", pk=pk)


@login_required
@require_POST
def group_join(request, pk):
    me = profile_of(request.user)
    group = get_object_or_404(Community, pk=pk)
    if not me:
        return redirect("groups.show", pk=pk)
    if CommunityMember.objects.filter(community=group, social_user=me).exists():
        return redirect("groups.show", pk=pk)
    if group.join_mode == "open" and group.privacy != "closed":
        CommunityMember.objects.create(community=group, social_user=me, role="member", created_at=now())
        messages.success(request, f"Вы в группе «{group.name}».")
        cache.delete(f"news:{me.id}:60")
    else:
        CommunityJoinRequest.objects.get_or_create(
            community=group, social_user=me,
            defaults={"status": "pending", "created_at": now()},
        )
        messages.info(request, "Заявка на вступление отправлена.")
    return redirect("groups.show", pk=pk)


@login_required
@require_POST
def group_leave(request, pk):
    me = profile_of(request.user)
    group = get_object_or_404(Community, pk=pk)
    row = CommunityMember.objects.filter(community=group, social_user=me).first()
    if not row:
        return redirect("groups.show", pk=pk)
    if row.role == "admin" and not CommunityMember.objects.filter(community=group, role="admin").exclude(pk=row.pk).exists():
        messages.error(request, "Нельзя выйти: вы единственный администратор.")
        return redirect("groups.show", pk=pk)
    row.delete()
    cache.delete(f"news:{me.id}:60")
    messages.success(request, f"Вы вышли из «{group.name}».")
    return redirect("groups")
