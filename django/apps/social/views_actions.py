from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.social.forms import CommentForm, MessageForm, PostForm, ProfileForm
from apps.social.models import (
    Comment,
    Conversation,
    Message,
    Post,
    Reaction,
    SavedPost,
    SocialProfile,
    UserFollow,
)
from apps.social.services import now as _now, profile_of


@login_required
def profile_edit(request):
    from apps.social.forms import EducationForm, ExperienceForm
    from apps.social.models import Education, Experience
    me = profile_of(request.user)
    form = ProfileForm(request.POST or None, instance=me)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.updated_at = _now()
        obj.save()
        messages.success(request, "Профиль сохранён.")
        return redirect(obj)
    return render(
        request,
        "social/profile_edit.html",
        {
            "form": form,
            "me": me,
            "edu_form": EducationForm(),
            "exp_form": ExperienceForm(),
            "education": Education.objects.filter(social_user=me)[:20],
            "experiences": Experience.objects.filter(social_user=me)[:20],
        },
    )


@login_required
@require_POST
def post_create(request):
    from django.core.cache import cache
    from apps.social.polls import attach_post_poll
    from apps.social.services import friend_ids
    from apps.social.throttle import throttle
    from apps.social.attach import attach_wall
    from apps.social.wall_meta import MOOD_KEYS, TOPIC_KEYS

    @throttle("posts", 20, 60)
    def _go(req):
        me = profile_of(req.user)
        form = PostForm(req.POST, req.FILES)
        if not (form.is_valid() and me):
            return redirect(req.POST.get("next") or "feed")
        post = form.save(commit=False)
        post.social_user = me
        post.body = (post.body or "").strip()
        labels = [x.strip() for x in (form.cleaned_data.get("poll_options") or "").splitlines() if x.strip()]
        files = list(req.FILES.getlist("photo"))
        albums = req.POST.getlist("album_photos")
        topic = form.cleaned_data.get("topic") or "thought"
        post.topic = topic if topic in TOPIC_KEYS else "thought"
        mood = form.cleaned_data.get("mood") or ""
        post.mood = mood if mood in MOOD_KEYS else None
        post.emoji = (form.cleaned_data.get("emoji") or "").strip()[:16] or None
        post.sticker = (form.cleaned_data.get("sticker") or "").strip() or None
        wall_to = req.POST.get("wall_to")
        if wall_to:
            target = get_object_or_404(SocialProfile, pk=wall_to)
            if target.id != me.id and target.id not in friend_ids(me):
                messages.error(req, "Писать на стену могут только друзья.")
                return redirect(target)
            post.topic = f"wall:{target.id}"
            post.visibility = "friends"
        if len(labels) >= 2:
            post.kind = "poll"
        elif files or albums or post.sticker:
            post.kind = "photo" if (files or albums) else "text"
        else:
            post.kind = "text"
        post.created_at = post.updated_at = _now()
        post.save()
        path = attach_wall(post, files, me, albums)
        if path:
            post.media_path = path
            if post.kind == "text":
                post.kind = "photo"
            post.save(update_fields=["media_path", "kind"])
        if post.kind == "poll":
            attach_post_poll(post, labels)
        cache.delete(f"news:{me.id}:60")
        messages.success(req, "Запись опубликована.")
        return redirect(req.POST.get("next") or "feed")

    return _go(request)


@login_required
@require_POST
def status_update(request):
    from apps.social.forms import StatusForm
    from django.core.cache import cache
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
        cache.delete(f"news:{me.id}:60")
        messages.success(request, "Статус обновлён.")
    return redirect(request.POST.get("next") or "feed")


@login_required
@require_POST
def comment_create(request, post_id):
    me = profile_of(request.user)
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST)
    if form.is_valid() and me:
        c = form.save(commit=False)
        c.post, c.social_user, c.created_at = post, me, _now()
        c.save()
    return redirect(request.POST.get("next") or "feed")


@login_required
@require_POST
@transaction.atomic
def react(request, post_id):
    me = profile_of(request.user)
    post = get_object_or_404(Post, pk=post_id)
    existing = Reaction.objects.filter(post=post, social_user=me, type="like").first()
    if existing:
        existing.delete()
    elif me:
        Reaction.objects.create(post=post, social_user=me, type="like", created_at=_now())
    return redirect(request.POST.get("next") or "feed")


@login_required
@require_POST
def save_post(request, post_id):
    me = profile_of(request.user)
    post = get_object_or_404(Post, pk=post_id)
    row = SavedPost.objects.filter(post=post, social_user=me).first()
    if row:
        row.delete()
    elif me:
        SavedPost.objects.create(post=post, social_user=me, created_at=_now())
    return redirect(request.POST.get("next") or "saved")


@login_required
@require_POST
def post_delete(request, post_id):
    me = profile_of(request.user)
    post = get_object_or_404(Post, pk=post_id)
    if not me or post.social_user_id != me.id:
        messages.error(request, "Нельзя удалить.")
        return redirect(request.POST.get("next") or "feed")
    Comment.objects.filter(post=post).delete()
    Reaction.objects.filter(post=post).delete()
    SavedPost.objects.filter(post=post).delete()
    post.delete()
    messages.success(request, "Запись удалена.")
    return redirect(request.POST.get("next") or "feed")


@login_required
@require_POST
def comment_delete(request, comment_id):
    me = profile_of(request.user)
    c = get_object_or_404(Comment, pk=comment_id)
    if not me or (c.social_user_id != me.id and c.post.social_user_id != me.id):
        return redirect(request.POST.get("next") or "feed")
    c.delete()
    return redirect(request.POST.get("next") or "feed")


@login_required
@require_POST
def follow_toggle(request, pk):
    me, other = profile_of(request.user), get_object_or_404(SocialProfile, pk=pk)
    if me and me.id != other.id:
        row = UserFollow.objects.filter(follower=me, following=other).first()
        if row:
            row.delete()
        else:
            UserFollow.objects.create(follower=me, following=other, created_at=_now())
    return redirect("profile", pk=pk)


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
        messages.success(request, "Аватар обновлён.")
    return redirect("profile.edit")


@login_required
@require_POST
@transaction.atomic
def message_send(request, conversation_id):
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    me = profile_of(request.user)
    conv = get_object_or_404(Conversation, pk=conversation_id)
    form = MessageForm(request.POST)
    if form.is_valid() and me:
        m = form.save(commit=False)
        m.conversation, m.social_user, m.message_type, m.created_at = conv, me, "text", _now()
        m.save()
        Conversation.objects.filter(pk=conv.pk).update(updated_at=_now())
        payload = {"type": "chat.message", "body": m.body, "name": me.name, "id": m.id}
        layer = get_channel_layer()

        def _push():
            if layer:
                async_to_sync(layer.group_send)(f"chat_{conversation_id}", payload)

        transaction.on_commit(_push)
    return redirect(f"/messenger?c={conversation_id}")


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
def education_add(request):
    from apps.social.forms import EducationForm
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
    from apps.social.forms import ExperienceForm
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
    from apps.social.models import Sticker

    me = profile_of(request.user)
    conv = get_object_or_404(Conversation, pk=conversation_id)
    sticker = get_object_or_404(Sticker, pk=request.POST.get("sticker_id"), is_active=True)
    if me:
        body = sticker.phrase or sticker.title
        m = Message.objects.create(
            conversation=conv, social_user=me, body=body, message_type="sticker",
            sticker_id=sticker.id, created_at=_now(),
        )
        Conversation.objects.filter(pk=conv.pk).update(updated_at=_now())
        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)(
                f"chat_{conversation_id}",
                {"type": "chat.message", "body": m.body, "name": me.name, "id": m.id},
            )
    return redirect(f"/messenger?c={conversation_id}")
