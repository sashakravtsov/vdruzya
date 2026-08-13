from django.core.cache import cache

from apps.social import chat as ch
from apps.social import platform_apps as pa
from apps.social.services import profile_of


def classic(request):
    me = profile_of(request.user) if getattr(request.user, "is_authenticated", False) else None
    unread_m = 0
    sidebar_apps = []
    if me:
        key = f"nav:{me.id}"
        cached = cache.get(key)
        if cached is not None:
            # Tolerate old cache tuples (unread_n, unread_m)
            unread_m = cached[1] if isinstance(cached, (tuple, list)) else cached
        else:
            unread_m = ch.unread_count(me)
            cache.set(key, unread_m, 30)
        sidebar_apps = pa.my_apps(me)
    return {
        "me": me,
        "unread_messages": unread_m,
        "is_home": bool(request.resolver_match and request.resolver_match.url_name == "home"),
        "nav": (request.resolver_match.url_name if request.resolver_match else "") or "",
        "sidebar_apps": sidebar_apps,
        "sidebar_apps_key": ",".join(a["slug"] for a in sidebar_apps),
    }
