from django.core.cache import cache

from apps.social import chat as ch
from apps.social.models import Notification
from apps.social.services import profile_of


def classic(request):
    me = profile_of(request.user) if getattr(request.user, "is_authenticated", False) else None
    unread_n = unread_m = 0
    if me:
        key = f"nav:{me.id}"
        cached = cache.get(key)
        if cached:
            unread_n, unread_m = cached
        else:
            unread_n = Notification.objects.filter(social_user=me, seen=False).count()
            unread_m = ch.unread_count(me)
            cache.set(key, (unread_n, unread_m), 30)
    return {
        "me": me,
        "unread_notifications": unread_n,
        "unread_messages": unread_m,
        "is_home": bool(request.resolver_match and request.resolver_match.url_name == "home"),
        "nav": (request.resolver_match.url_name if request.resolver_match else "") or "",
    }
