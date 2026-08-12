"""Events FBVs — classic Facebook Events."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.social import events as ev
from apps.social.forms import EventForm
from apps.social.services import profile_of

_TABS = ("upcoming", "past", "hosting", "going", "invited")


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
    going = ev.guests(event, "going")
    maybe = ev.guests(event, "maybe")
    return render(
        request, "social/event.html",
        {
            "event": event, "me": me, "status": status, "is_host": is_host,
            "going": going, "maybe": maybe,
            "n_going": ev.guest_count(event, "going"),
            "n_maybe": ev.guest_count(event, "maybe"),
            "invite_friends": ev.invite_candidates(me, event) if is_host else [],
            "nav": "events",
        },
    )


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
