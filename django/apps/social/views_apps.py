"""Applications / App Center — first-party Platform catalog (FB 2007–12 UX, 2006 chrome)."""
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.social import platform_apps as pa
from apps.social.services import profile_of


@login_not_required
@require_http_methods(["GET", "HEAD"])
def apps_home(request):
    me = profile_of(request.user) if request.user.is_authenticated else None
    cat = (request.GET.get("category") or "").strip().lower()
    tab = (request.GET.get("tab") or "browse").strip().lower()
    if tab not in ("browse", "mine"):
        tab = "browse"
    featured = pa.apps_grouped(featured_only=True) if tab == "browse" else []
    apps = pa.apps_grouped(category=cat or None) if tab == "browse" else []
    all_mine = pa.my_apps(me) if me else []
    mine_apps = all_mine if tab == "mine" else []
    installed = pa.installed_slugs(me) if me else set()
    return render(request, "social/apps.html", {
        "me": me, "apps": apps, "featured": featured, "mine_apps": mine_apps,
        "mine_count": len(all_mine),
        "categories": pa.APP_CATEGORIES, "category": cat, "tab": tab,
        "installed": installed, "nav": "apps",
    })
