"""Applications directory — classic FB apps list of built-in modules."""
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.social.services import profile_of

# Built-in apps only — no third-party platform. Classic 2006 chrome catalog.
APPS = (
    {
        "slug": "photos", "name": "Фото",
        "blurb": "Альбомы и фотографии друзей.",
        "url_name": "albums",
    },
    {
        "slug": "groups", "name": "Группы",
        "blurb": "Сообщества по интересам и обсуждения.",
        "url_name": "groups",
    },
    {
        "slug": "events", "name": "События",
        "blurb": "Встречи, вечеринки и приглашения.",
        "url_name": "events",
    },
    {
        "slug": "pages", "name": "Страницы",
        "blurb": "Публичные страницы брендов, мест и личностей.",
        "url_name": "pages",
    },
    {
        "slug": "notes", "name": "Заметки",
        "blurb": "Длинные записи на вашем профиле.",
        "url_name": None,  # profile notes tab
        "path": None,
    },
    {
        "slug": "messages", "name": "Сообщения",
        "blurb": "Входящие письма друзьям.",
        "url_name": "inbox",
    },
    {
        "slug": "pokes", "name": "Подмигивания",
        "blurb": "Лёгкий способ сказать «привет».",
        "url_name": "pokes",
    },
    {
        "slug": "search", "name": "Поиск",
        "blurb": "Найти людей и группы во ВДрузья.",
        "url_name": "search",
    },
)


@login_not_required
@require_http_methods(["GET", "HEAD"])
def apps_home(request):
    me = profile_of(request.user) if request.user.is_authenticated else None
    items = []
    for app in APPS:
        row = dict(app)
        if app["slug"] == "notes" and me:
            row["href"] = f"{me.get_absolute_url()}?tab=notes"
        elif app["slug"] == "notes":
            row["href"] = "/login?next=/feed"
        else:
            row["href"] = None  # resolve in template via url_name
        items.append(row)
    return render(request, "social/apps.html", {"me": me, "apps": items})
