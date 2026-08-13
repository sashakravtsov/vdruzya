"""Applications / App Center — built-in modules only (FB 2012 catalog)."""
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.social import era2012 as e12
from apps.social.services import profile_of


@login_not_required
@require_http_methods(["GET", "HEAD"])
def apps_home(request):
    me = profile_of(request.user) if request.user.is_authenticated else None
    cat = (request.GET.get("category") or "").strip().lower()
    featured = e12.apps_grouped(featured_only=True)
    apps = e12.apps_grouped(category=cat or None)
    return render(request, "social/apps.html", {
        "me": me, "apps": apps, "featured": featured,
        "categories": e12.APP_CATEGORIES, "category": cat, "nav": "apps",
    })
