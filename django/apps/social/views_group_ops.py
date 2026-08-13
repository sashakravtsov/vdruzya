"""Group ops FBVs — edit, members, message, deletes, invite, events. Keep short."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods

from apps.social.forms import CommentForm, CommunityPostForm, GroupForm
from apps.social.models import (
    Community, CommunityJoinRequest, CommunityMember, CommunityPost,
    CommunityPostComment, Notification, SocialProfile, profile_related,
)
from apps.social.services import bump_news, can_manage_group_comment, is_group_admin, now, profile_of


def _member(me, group):
    return bool(me and CommunityMember.objects.filter(community=group, social_user=me).exists())


@login_required
def group_edit(request, pk):
    from apps.social.media import try_save_image

    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    if not is_group_admin(me, group):
        messages.error(request, "Только администратор.")
        return redirect("groups.show", pk=pk)
    form = GroupForm(request.POST or None, request.FILES or None, instance=group)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        path = try_save_image(form.cleaned_data.get("picture"), "groups")
        if path:
            obj.cover_path = path
        obj.updated_at = now()
        obj.save()
        bump_news()
        messages.success(request, "Группа обновлена.")
        return redirect(obj)
    return render(request, "social/group_edit.html", {"group": group, "form": form, "me": me})


def delete_group(me, group) -> bool:
    """Admin-only hard delete of a Group and related classic chrome data."""
    if not me or not group or not is_group_admin(me, group):
        return False
    from apps.social.models import (
        CommunityPostMedia, Conversation, ConversationMember, Event, EventAttendee,
        GroupDoc, Message,
    )
    from apps.social.models.era2014 import SavedItem
    from apps.social.models.legacy import GroupCommentReaction, GroupPostReaction

    with transaction.atomic():
        post_ids = list(
            CommunityPost.objects.filter(community=group).values_list("id", flat=True)
        )
        if post_ids:
            cids = list(
                CommunityPostComment.objects.filter(post_id__in=post_ids).values_list("id", flat=True)
            )
            if cids:
                GroupCommentReaction.objects.filter(comment_id__in=cids).delete()
            GroupPostReaction.objects.filter(post_id__in=post_ids).delete()
            CommunityPostComment.objects.filter(post_id__in=post_ids).delete()
            CommunityPostMedia.objects.filter(post_id__in=post_ids).delete()
            CommunityPost.objects.filter(id__in=post_ids).delete()
        from apps.social.cascade import purge_wall_posts
        from apps.social.models import Post
        for event in Event.objects.filter(community=group):
            purge_wall_posts(list(Post.objects.filter(topic=event.topic_key).values_list("id", flat=True)))
            EventAttendee.objects.filter(event=event).delete()
            SavedItem.objects.filter(event=event).delete()
            event.delete()
        GroupDoc.objects.filter(community=group).delete()
        CommunityJoinRequest.objects.filter(community=group).delete()
        CommunityMember.objects.filter(community=group).delete()
        conv_ids = list(
            Conversation.objects.filter(community_id=group.id).values_list("id", flat=True)
        )
        if conv_ids:
            Message.objects.filter(conversation_id__in=conv_ids).delete()
            ConversationMember.objects.filter(conversation_id__in=conv_ids).delete()
            Conversation.objects.filter(id__in=conv_ids).delete()
        group.delete()
    bump_news()
    return True


@login_required
@require_POST
def group_delete(request, pk):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    name = group.name
    if delete_group(me, group):
        messages.info(request, f"Группа «{name}» удалена.")
        return redirect("groups")
    messages.error(request, "Удалить может только администратор.")
    return redirect("groups.show", pk=pk)


@login_required
def group_members(request, pk):
    group = get_object_or_404(Community, pk=pk)
    me = profile_of(request.user)
    rows = (
        CommunityMember.objects.filter(community=group)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("social_user__name")[:200]
    )
    return render(
        request, "social/group_members.html",
        {
            "group": group, "rows": rows, "n_members": CommunityMember.objects.filter(community=group).count(),
            "me": me, "is_admin": is_group_admin(me, group),
        },
    )


@login_required
@require_POST
def join_reject(request, pk, request_id):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    if not is_group_admin(me, group):
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
def group_post_delete(request, pk, post_id):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    post = get_object_or_404(CommunityPost, pk=post_id, community=group)
    if not me or (post.social_user_id != me.id and not is_group_admin(me, group)):
        messages.error(request, "Нельзя удалить.")
        return redirect("groups.show", pk=pk)
    from apps.social.models.legacy import GroupCommentReaction, GroupPostReaction
    cids = list(CommunityPostComment.objects.filter(post=post).values_list("id", flat=True))
    if cids:
        GroupCommentReaction.objects.filter(comment_id__in=cids).delete()
    GroupPostReaction.objects.filter(post=post).delete()
    CommunityPostComment.objects.filter(post=post).delete()
    post.delete()
    bump_news()
    messages.success(request, "Запись удалена.")
    return redirect("groups.show", pk=pk)


def _post_redirect(pk, post):
    if getattr(post, "topic", None) == "wall":
        return redirect(f"/groups/{pk}?tab=wall#topic-{post.id}")
    return redirect(f"/groups/{pk}?tab=discussion&topic={post.id}")


@login_required
@require_POST
def group_comment_delete(request, pk, comment_id):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    c = get_object_or_404(CommunityPostComment.objects.select_related("post"), pk=comment_id, post__community=group)
    if not can_manage_group_comment(me, c, group):
        return redirect("groups.show", pk=pk)
    post = c.post
    from apps.social.models.legacy import GroupCommentReaction
    GroupCommentReaction.objects.filter(comment=c).delete()
    c.delete()
    messages.success(request, "Комментарий удалён.")
    return _post_redirect(pk, post)


@login_required
@require_POST
def group_comment_like(request, pk, comment_id):
    from apps.social.likes import toggle_group_comment_like

    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    if not _member(me, group) and group.privacy == "closed":
        messages.error(request, "Группа закрыта.")
        return redirect("groups.show", pk=pk)
    c = get_object_or_404(CommunityPostComment.objects.select_related("post"), pk=comment_id, post__community=group)
    out = toggle_group_comment_like(me, c)
    if out == "liked":
        messages.success(request, "Вам это нравится.")
    elif out == "unliked":
        messages.info(request, "Отметка снята.")
    return _post_redirect(pk, c.post)


@login_required
@require_POST
def group_post_like(request, pk, post_id):
    from apps.social.likes import toggle_group_post_like

    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    if not _member(me, group) and group.privacy == "closed":
        messages.error(request, "Группа закрыта.")
        return redirect("groups.show", pk=pk)
    post = get_object_or_404(CommunityPost, pk=post_id, community=group)
    out = toggle_group_post_like(me, post)
    if out == "liked":
        messages.success(request, "Вам это нравится.")
    elif out == "unliked":
        messages.info(request, "Отметка снята.")
    return _post_redirect(pk, post)


@login_required
@require_http_methods(["GET", "POST"])
def group_post_edit(request, pk, post_id):
    from apps.social.attach import apply_group_uploads
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    post = get_object_or_404(CommunityPost, pk=post_id, community=group)
    if not me or (post.social_user_id != me.id and not is_group_admin(me, group)):
        messages.error(request, "Нельзя редактировать.")
        return redirect("groups.show", pk=pk)
    if post.topic == "wall":
        messages.error(request, "Запись на стене нельзя редактировать — только удалить.")
        return redirect(f"/groups/{pk}?tab=wall#topic-{post.id}")
    form = CommunityPostForm(request.POST or None, request.FILES or None, instance=post)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        # discussion topics stay on the board (no flip to wall via edit)
        obj.topic = "discussion"
        body = (obj.body or "").strip()
        if obj.topic == "discussion":
            obj.body = CommunityPost.pack_topic(form.cleaned_data.get("subject") or "", body)
        else:
            obj.body = body
        if is_group_admin(me, group):
            obj.posted_as_community = bool(request.POST.get("as_community"))
        obj.updated_at = now()
        obj.save(update_fields=["body", "topic", "posted_as_community", "updated_at"])
        # Discussion: photos only (video stays on group wall).
        apply_group_uploads(obj, list(request.FILES.getlist("photo")), me, blurb=body)
        messages.success(request, "Запись обновлена.")
        return redirect(obj)
    form.fields["board"].initial = post.topic if post.topic in ("wall", "discussion") else "discussion"
    return render(request, "social/group_post_edit.html", {"group": group, "post": post, "form": form, "me": me, "is_admin": is_group_admin(me, group)})


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
    if not is_group_admin(me, group):
        return redirect("groups.show", pk=pk)
    from apps.social import events as ev
    from apps.social.forms import EventForm
    form = EventForm(request.POST, request.FILES)
    if form.is_valid():
        event = ev.create_event(
            me,
            title=form.cleaned_data["title"],
            place=form.cleaned_data.get("place") or "—",
            starts_at=form.cleaned_data["starts_at"],
            community=group,
            cover=form.cleaned_data.get("cover"),
        )
        if event:
            ev.set_rsvp(me, event, "going")
            messages.success(request, "Событие создано.")
        else:
            messages.error(request, "Не удалось создать событие.")
    else:
        messages.error(request, "Укажите название и дату.")
    return redirect(f"/groups/{pk}?tab=events")


@login_required
@require_POST
def member_manage(request, pk, user_id):
    """Admin: remove / promote / demote members."""
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    if not is_group_admin(me, group):
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
    from apps.social.attach import apply_group_uploads
    from apps.social.throttle import throttle

    @throttle("gposts", 20, 60)
    def _go(req):
        me, group = profile_of(req.user), get_object_or_404(Community, pk=pk)
        is_mem = _member(me, group)
        is_admin = is_group_admin(me, group)
        if not is_mem:
            messages.error(req, "Сначала вступите в группу.")
            return redirect("groups.show", pk=pk)
        if group.posting_policy == "admins" and not is_admin:
            messages.error(req, "Писать могут только администраторы.")
            return redirect("groups.show", pk=pk)
        form = CommunityPostForm(req.POST, req.FILES)
        if not form.is_valid():
            messages.error(req, "Проверьте тему и текст.")
            return redirect("groups.show", pk=pk)
        p = form.save(commit=False)
        p.community, p.social_user = group, me
        p.topic = form.cleaned_data.get("board") or "discussion"
        p.posted_as_community = bool(is_admin and req.POST.get("as_community"))
        files = list(req.FILES.getlist("photo"))
        p.created_at = p.updated_at = now()
        body = (p.body or "").strip()
        if p.topic == "discussion":
            p.body = CommunityPost.pack_topic(form.cleaned_data.get("subject") or "", body)
        else:
            p.body = body
        p.kind = "text"
        p.save()
        apply_group_uploads(p, files, me, blurb=body)
        from apps.social.compose_ui import attach_album_photos_group, parse_album_photo_ids
        attach_album_photos_group(p, parse_album_photo_ids(req, limit=50), me)
        bump_news()
        messages.success(req, "Тема создана." if p.topic == "discussion" else "Запись на стене опубликована.")
        if p.topic == "wall":
            return redirect(f"/groups/{pk}?tab=wall#topic-{p.id}")
        return redirect(f"/groups/{pk}?tab=discussion&topic={p.id}")

    return _go(request)


@login_required
@require_POST
def group_comment(request, pk, post_id):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    post = get_object_or_404(CommunityPost, pk=post_id, community=group)
    form = CommentForm(request.POST)
    if me and _member(me, group) and form.is_valid():
        t = now()
        CommunityPostComment.objects.create(
            post=post, social_user=me, body=form.cleaned_data["body"], created_at=t,
        )
        CommunityPost.objects.filter(pk=post.pk).update(updated_at=t)
        bump_news()
    if post.topic == "wall":
        return redirect(f"/groups/{pk}?tab=wall#c-gpost-{post.id}")
    return redirect(f"/groups/{pk}?tab=discussion&topic={post.id}")


@login_required
@require_POST
@transaction.atomic
def join_accept(request, pk, request_id):
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    if not is_group_admin(me, group):
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
        bump_news()
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
    bump_news()
    messages.success(request, f"Вы вышли из «{group.name}».")
    return redirect("groups")


@login_required
@require_http_methods(["GET", "POST"])
def group_docs(request, pk):
    """Create doc (POST) or redirect to docs tab (GET)."""
    from apps.social import group_docs as gdocs
    from apps.social.forms import GroupDocForm
    from apps.social.group_page import access

    me = profile_of(request.user)
    group = get_object_or_404(Community, pk=pk)
    is_member, is_admin, can_view, can_post, _ = access(me, group)
    if not can_view:
        messages.error(request, "Группа закрыта.")
        return redirect("groups")
    if request.method == "GET":
        return redirect(f"/groups/{pk}?tab=docs")
    if not can_post:
        messages.error(request, "Писать документы нельзя.")
        return redirect(f"/groups/{pk}?tab=docs")
    form = GroupDocForm(request.POST)
    if form.is_valid():
        doc = gdocs.doc_create(me, group, title=form.cleaned_data["title"], body=form.cleaned_data.get("body") or "")
        if doc:
            messages.success(request, "Документ создан.")
            return redirect(doc)
    messages.error(request, "Укажите название.")
    return redirect(f"/groups/{pk}?tab=docs")


@login_required
@require_http_methods(["GET", "POST"])
def group_doc_show(request, pk, doc_id):
    from apps.social import group_docs as gdocs
    from apps.social.forms import GroupDocForm
    from apps.social.group_page import access
    from apps.social.models import GroupDoc

    me = profile_of(request.user)
    group = get_object_or_404(Community, pk=pk)
    is_member, is_admin, can_view, can_post, _ = access(me, group)
    doc = get_object_or_404(GroupDoc.objects.select_related("social_user"), pk=doc_id, community=group)
    if not can_view:
        messages.error(request, "Группа закрыта.")
        return redirect("groups")
    form = None
    if me and doc.social_user_id == me.id:
        form = GroupDocForm(
            request.POST or None,
            initial=None if request.method == "POST" else {"title": doc.title, "body": doc.body},
        )
        if request.method == "POST" and form.is_valid():
            if gdocs.doc_update(me, doc, title=form.cleaned_data["title"], body=form.cleaned_data.get("body") or ""):
                messages.success(request, "Документ сохранён.")
                return redirect(doc)
            messages.error(request, "Не удалось сохранить.")
    return render(request, "social/group_doc.html", {
        "me": me, "group": group, "doc": doc, "form": form,
        "is_admin": is_admin, "is_member": is_member, "nav": "groups",
    })


@login_required
@require_POST
def group_doc_delete(request, pk, doc_id):
    from apps.social import group_docs as gdocs
    from apps.social.group_page import access
    from apps.social.models import GroupDoc

    me = profile_of(request.user)
    group = get_object_or_404(Community, pk=pk)
    _, is_admin, can_view, _, _ = access(me, group)
    doc = get_object_or_404(GroupDoc, pk=doc_id, community=group)
    if not can_view:
        return redirect("groups")
    if gdocs.doc_delete(me, doc, is_admin=is_admin):
        messages.success(request, "Документ удалён.")
    else:
        messages.error(request, "Нельзя удалить.")
    return redirect(f"/groups/{pk}?tab=docs")
