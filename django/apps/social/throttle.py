"""Tiny cache throttle — no fat middleware."""
from functools import wraps
from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect


def throttle(action: str, limit=12, window=60):
    def deco(view):
        @wraps(view)
        def wrap(request, *args, **kwargs):
            uid = getattr(request.user, "pk", None) or request.META.get("REMOTE_ADDR", "x")
            key = f"th:{action}:{uid}"
            n = cache.get(key, 0)
            if n >= limit:
                messages.error(request, "Слишком часто. Подождите минуту.")
                return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "/")
            cache.set(key, n + 1, window)
            return view(request, *args, **kwargs)
        return wrap
    return deco
