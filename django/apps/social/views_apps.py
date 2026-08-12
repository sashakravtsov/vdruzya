"""Applications directory — classic FB apps list of built-in modules."""
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.social.services import profile_of

# Built-in apps only — no third-party platform. Classic 2006 chrome catalog.
APPS = (
    {"slug": "photos", "name": "Фото", "blurb": "Альбомы и фотографии друзей.", "url_name": "albums"},
    {"slug": "groups", "name": "Группы", "blurb": "Сообщества по интересам и обсуждения.", "url_name": "groups"},
    {"slug": "events", "name": "События", "blurb": "Встречи, вечеринки и приглашения.", "url_name": "events"},
    {"slug": "pages", "name": "Страницы", "blurb": "Публичные страницы брендов, мест и личностей.", "url_name": "pages"},
    {"slug": "notes", "name": "Заметки", "blurb": "Длинные записи — свои и друзей.", "url_name": "notes"},
    {"slug": "links", "name": "Ссылки", "blurb": "Поделитесь интересной ссылкой.", "url_name": "links"},
    {"slug": "videos", "name": "Видео", "blurb": "Ссылки на видеоролики.", "url_name": "videos"},
    {"slug": "marketplace", "name": "Барахолка", "blurb": "Купить и продать вещи рядом.", "url_name": "marketplace"},
    {"slug": "networks", "name": "Сети", "blurb": "Города, школы и места работы.", "url_name": "networks"},
    {"slug": "lists", "name": "Списки друзей", "blurb": "Группируйте друзей по спискам.", "url_name": "friends.lists"},
    {"slug": "messages", "name": "Сообщения", "blurb": "Входящие письма друзьям.", "url_name": "inbox"},
    {"slug": "pokes", "name": "Подмигивания", "blurb": "Лёгкий способ сказать «привет».", "url_name": "pokes"},
    {"slug": "gifts", "name": "Подарки", "blurb": "Отправьте другу виртуальный подарок.", "url_name": "gifts"},
    {"slug": "birthdays", "name": "Дни рождения", "blurb": "Не пропустите дни рождения друзей.", "url_name": "birthdays"},
    {"slug": "mobile", "name": "Мобильная версия", "blurb": "ВДрузья с телефона.", "url_name": "mobile"},
    {"slug": "search", "name": "Поиск", "blurb": "Найти людей и группы во ВДрузья.", "url_name": "search"},
)


@login_not_required
@require_http_methods(["GET", "HEAD"])
def apps_home(request):
    me = profile_of(request.user) if request.user.is_authenticated else None
    return render(request, "social/apps.html", {"me": me, "apps": list(APPS), "nav": "apps"})
