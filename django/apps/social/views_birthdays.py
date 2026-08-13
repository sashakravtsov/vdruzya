"""Birthdays + friendship anniversaries — classic FB directories."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.social import friendship as fr
from apps.social.services import profile_of, upcoming_birthdays


@login_required
@require_http_methods(["GET", "HEAD"])
def birthdays_home(request):
    me = profile_of(request.user)
    items = upcoming_birthdays(me, days=60, limit=80) if me else []
    return render(request, "social/birthdays.html", {
        "me": me, "birthdays": items, "today": timezone.localdate(), "nav": "birthdays",
    })


@login_required
@require_http_methods(["GET", "HEAD"])
def anniversaries_home(request):
    me = profile_of(request.user)
    items = fr.upcoming_anniversaries(me, days=60, limit=80) if me else []
    return render(request, "social/anniversaries.html", {
        "me": me, "items": items, "today": timezone.localdate(), "nav": "anniversaries",
    })
