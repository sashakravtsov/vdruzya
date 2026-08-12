"""Events FBVs — classic Facebook Events (+ wall / photos)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.social import events as ev
from apps.social.forms import EventForm, PostForm
from apps.social.models import POST_DEFER, Comment, Post, profile_related
from apps.social.services import bump_news, now, profile_of

_TABS = ("upcoming", "past", "hosting", "going", "invited")
_SHOW_TABS = ("wall", "photos", "guests")


def _can_post(me, event, status) -> bool:
    if not me:
        return False
    if event.host_id == me.id:
        return True
    return status in ("going", "maybe")


def _event_posts(event, *, photos_only=False, limit=30):
    qs = (
        Post.objects.filter(topic=event.topic_key)
        .exclude(kind__in=("status", "picture", "poll", "share", "note", "gift"))
        .select_related("social_user")
        .defer(*POST_DEFER, *profile_related("social_user__"))
        .prefetch_related(
            "media",
            Prefetch(
                "comments",
                queryset=Comment.objects.select_related("social_user")
                .defer(*profile_related("social_user__")).order_by("id"),
            ),
        )
        .annotate(n_comments=Count("comments", distinct=True))
        .order_by("-id")
    )
    if photos_only:
        qs = qs.filter(kind="photo").exclude(media_path__isnull=True).exclude(media_path="")
    return list(qs[:limit])


@login_required
def events_home(request):
    me = profile_of(request.user)
    form = EventForm(request.POST or None)
    if request.method == "POST" and me:
        if form.is_valid():
            event = ev.create_event(
                me,
                title=form.cleaned_data["title"],
                place=form.cleaned_data.get("place") or "—",
                description=form.cleaned_data.get("description") or "",
                starts_at=form.cleaned_data["starts_at"],
            )
            if event:
                ev.set_rsvp(me, event, "going")
                messages.success(request, "Событие создано.")
                return redirect("events.show", event_id=event.id)
        messages.error(request, "Укажите название и дату.")
        return redirect("events")

    tab = request.GET.get("tab") or "upcoming"
    if tab not in _TABS:
        tab = "upcoming"
    items = list(ev.list_events(me, tab))
    mine = ev.statuses_map(me, [e.id for e in items])
    for e in items:
        e.my_status = mine.get(e.id, "")
    if tab == "invited" and me:
        from apps.social.models import Notification
        Notification.objects.filter(social_user=me, type="event_invite", seen=False).update(seen=True)
    return render(
        request, "social/events.html",
        {"events": items, "me": me, "tab": tab, "form": form, "nav": "events"},
    )


@login_required
def event_show(request, event_id):
    me = profile_of(request.user)
    event = ev.get_event(event_id)
    status = ev.my_status(me, event)
    is_host = bool(me and event.host_id == me.id)
    can_post = _can_post(me, event, status)
    show_tab = (request.GET.get("tab") or "wall").lower()
    if show_tab not in _SHOW_TABS:
        show_tab = "wall"
    going = ev.guests(event, "going")
    maybe = ev.guests(event, "maybe")
    posts = _event_posts(event, photos_only=(show_tab == "photos"))
    if show_tab == "wall":
        wall_posts = posts
        photos = [p for p in _event_posts(event, photos_only=True, limit=12)]
    else:
        wall_posts = []
        photos = posts if show_tab == "photos" else []
    return render(
        request, "social/event.html",
        {
            "event": event, "me": me, "status": status, "is_host": is_host,
            "can_post": can_post, "show_tab": show_tab,
            "going": going, "maybe": maybe,
            "n_going": ev.guest_count(event, "going"),
            "n_maybe": ev.guest_count(event, "maybe"),
            "invite_friends": ev.invite_candidates(me, event) if is_host else [],
            "wall_posts": wall_posts, "photos": photos,
            "form": PostForm(simple=True) if can_post else None,
            "nav": "events",
        },
    )


@login_required
@require_POST
def event_post(request, event_id):
    from apps.social.attach import attach_wall
    from apps.social.throttle import throttle

    @throttle("posts", 20, 60)
    def _go(req):
        me = profile_of(req.user)
        event = ev.get_event(event_id)
        status = ev.my_status(me, event)
        if not _can_post(me, event, status):
            messages.error(req, "Писать на стену события могут участники.")
            return redirect(event)
        form = PostForm(req.POST, req.FILES, simple=True)
        go = req.POST.get("next") or (event.get_absolute_url() + "?tab=wall")
        if not form.is_valid():
            messages.error(req, "Напишите текст или выберите фото.")
            return redirect(go)
        post = form.save(commit=False)
        post.social_user = me
        post.body = (post.body or "").strip()
        post.topic = event.topic_key
        post.visibility = "friends"
        files = list(req.FILES.getlist("photo"))
        post.kind = "photo" if files else "text"
        post.created_at = post.updated_at = now()
        post.save()
        path = attach_wall(post, files, me, max_photos=1)
        if path:
            post.media_path = path
            post.kind = "photo"
            post.save(update_fields=["media_path", "kind"])
            go = event.get_absolute_url() + "?tab=photos"
        bump_news()
        messages.success(req, "Опубликовано.")
        return redirect(go)

    return _go(request)


@login_required
@require_POST
def event_post_delete(request, event_id, post_id):
    me = profile_of(request.user)
    event = ev.get_event(event_id)
    post = get_object_or_404(Post, pk=post_id, topic=event.topic_key)
    if not (me and (post.social_user_id == me.id or event.host_id == me.id)):
        messages.error(request, "Нельзя удалить.")
        return redirect(event)
    post.delete()
    bump_news()
    messages.info(request, "Удалено.")
    return redirect(request.POST.get("next") or event.get_absolute_url())


@login_required
@require_POST
def event_rsvp(request, event_id):
    me = profile_of(request.user)
    event = ev.get_event(event_id)
    status = (request.POST.get("status") or "").strip()
    if status not in ev.STATUSES:
        status = "" if ev.my_status(me, event) == "going" else "going"
    if status:
        ev.set_rsvp(me, event, status)
    elif me:
        from apps.social.models import EventAttendee
        EventAttendee.objects.filter(event=event, social_user=me).delete()
    return redirect(request.POST.get("next") or event.get_absolute_url())


@login_required
@require_POST
def event_invite(request, event_id):
    me = profile_of(request.user)
    event = ev.get_event(event_id)
    n = ev.invite_friends(me, event, request.POST.getlist("friends"))
    if n:
        messages.success(request, f"Приглашено: {n}.")
    else:
        messages.info(request, "Некого приглашать или нет прав.")
    return redirect(request.POST.get("next") or event.get_absolute_url())
