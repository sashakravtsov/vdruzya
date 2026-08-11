"""Thin FBVs: groups wall/react, blocks, stickers, education/work."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.social.forms import CommunityPostForm, EducationForm, ExperienceForm
from apps.social.models import (
    Block, Community, CommunityMember, CommunityPost, CommunityPostComment, CommunityPostReaction,
    Message, SocialProfile, Sticker,
)
from apps.social.services import now, profile_of


def _member(me, group):
    return bool(me and CommunityMember.objects.filter(community=group, social_user=me).exists())


@login_required
@require_POST
def group_post(request, pk):
    from django.core.cache import cache
    from apps.social.attach import attach_group
    from apps.social.polls import attach_group_poll
    from apps.social.throttle import throttle

    @throttle("gposts", 20, 60)
    def _go(req):
        me, group = profile_of(req.user), get_object_or_404(Community, pk=pk)
        is_mem = _member(me, group)
        is_admin = CommunityMember.objects.filter(
            community=group, social_user=me, role__in=("admin", "moderator", "creator")
        ).exists()
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
        from apps.social.wall_meta import MOOD_KEYS
        mood = form.cleaned_data.get("mood") or ""
        p.mood = mood if mood in MOOD_KEYS else None
        p.emoji = (form.cleaned_data.get("emoji") or "").strip()[:16] or None
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
def block_toggle(request, pk):
    from apps.social import friendship as fr
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
def education_add(request):
    me, form = profile_of(request.user), EducationForm(request.POST)
    if me and form.is_valid():
        row = form.save(commit=False)
        row.social_user = me
        row.save()
        messages.success(request, "Образование добавлено.")
    return redirect("profile.edit")


@login_required
@require_POST
def experience_add(request):
    me, form = profile_of(request.user), ExperienceForm(request.POST)
    if me and form.is_valid():
        row = form.save(commit=False)
        row.social_user = me
        row.description = row.description or ""
        row.save()
        messages.success(request, "Опыт добавлен.")
    return redirect("profile.edit")


@login_required
@require_POST
def sticker_send(request, conversation_id):
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
    from apps.social.models import Conversation

    me = profile_of(request.user)
    conv = get_object_or_404(Conversation, pk=conversation_id)
    sticker = get_object_or_404(Sticker, pk=request.POST.get("sticker_id"), is_active=True)
    if me:
        body = sticker.phrase or sticker.title
        m = Message.objects.create(
            conversation=conv, social_user=me, body=body, message_type="sticker",
            sticker_id=sticker.id, created_at=now(),
        )
        Conversation.objects.filter(pk=conv.pk).update(updated_at=now())
        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)(
                f"chat_{conversation_id}",
                {"type": "chat.message", "body": m.body, "name": me.name, "id": m.id},
            )
    return redirect(f"/messenger?c={conversation_id}")


@login_required
@require_POST
@transaction.atomic
def join_accept(request, pk, request_id):
    from apps.social.models import CommunityJoinRequest
    me, group = profile_of(request.user), get_object_or_404(Community, pk=pk)
    if not me or not CommunityMember.objects.filter(
        community=group, social_user=me, role__in=("admin", "moderator", "creator", "officer")
    ).exists():
        messages.error(request, "Только админ группы.")
        return redirect("groups.show", pk=pk)
    req = get_object_or_404(CommunityJoinRequest, pk=request_id, community=group, status="pending")
    CommunityMember.objects.get_or_create(community=group, social_user_id=req.social_user_id, defaults={"role": "member"})
    CommunityJoinRequest.objects.filter(pk=req.pk).update(status="accepted")
    messages.success(request, "Заявка принята.")
    return redirect("groups.show", pk=pk)
