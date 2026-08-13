from django import template
from django.utils.html import escape, format_html, format_html_join
from django.utils.http import urlencode
from django.utils.safestring import mark_safe

register = template.Library()

from apps.social.categories import LABELS as _GROUP_LABELS
from apps.social.page_categories import LABELS as _PAGE_LABELS

_LABELS = {
    "friendship": "Дружба",
    "dating": "Знакомства",
    "relationship": "Отношения",
    "networking": "Деловые контакты",
    "day_month": "День и месяц",
    "full": "Полная дата",
    "age": "Только возраст",
    "hide": "Скрыть",
    "male": "Мужской",
    "female": "Женский",
    "other": "Другой",
    "single": "Не женат(а)",
    "in_a_relationship": "В отношениях",
    "engaged": "Помолвлен(а)",
    "married": "Женат / замужем",
    "complicated": "Всё сложно",
    "open": "Свободные отношения",
    "not_interested": "Не интересуюсь",
    "moderate": "Умеренные",
    "liberal": "Либеральные",
    "conservative": "Консервативные",
    "apolitical": "Вне политики",
    "public": "Открытая",
    "closed": "Закрытая",
    "friends": "Друзьям",
    "private": "Только мне",
    "admin": "админ",
    "officer": "офицер",
    "moderator": "модератор",
    "creator": "создатель",
    "member": "участник",
    **_GROUP_LABELS,
    **_PAGE_LABELS,
}


@register.filter
def fb_when(dt):
    """Classic FB absolute stamp — «12 августа, 15:04» (year if not current)."""
    if not dt:
        return ""
    from django.utils import formats, timezone
    now = timezone.now()
    try:
        if timezone.is_aware(dt) and timezone.is_aware(now):
            same_year = timezone.localtime(dt).year == timezone.localtime(now).year
        else:
            same_year = getattr(dt, "year", None) == getattr(now, "year", None)
    except Exception:
        same_year = True
    fmt = "j E, H:i" if same_year else "j E Y, H:i"
    return formats.date_format(dt, fmt)


@register.filter
def storage_url(path):
    from apps.social.media import media_url
    return media_url(path) or ""


@register.filter
def ru_label(value):
    if value is None or value == "":
        return ""
    key = str(value).strip().lower().replace(" ", "_")
    return _LABELS.get(key, value)


@register.filter
def album_vis(value):
    """Album visibility — public means «Всем» (not group «Открытая»)."""
    from apps.social.albums import visibility_label
    return visibility_label(value)


@register.simple_tag
def avatar(profile, size=50):
    """FB 2005 silhouette — photo or shared nophoto.gif (no letter tiles)."""
    from django.templatetags.static import static

    if not profile:
        return ""
    raw = getattr(profile, "avatar_url", None)
    url = raw() if callable(raw) else raw
    if not url:
        url = static("img/nophoto.gif")
    return mark_safe(
        f'<img src="{escape(url)}" width="{int(size)}" height="{int(size)}" '
        f'alt="" class="avatar">'
    )


@register.filter
def tags(value):
    """Comma-separated interests → linked search tags (FB 2005)."""
    if not value:
        return ""
    parts = [p.strip() for p in str(value).replace(";", ",").split(",") if p.strip()]
    if not parts:
        return ""
    return format_html_join(", ", '<a href="/search?{}">{}</a>', (
        (urlencode({"q": part}), part) for part in parts
    ))


@register.filter
def tag(value):
    """Single value → one search link (FB Sex/Hometown/…)."""
    text = str(value or "").strip()
    if not text:
        return ""
    return format_html('<a href="/search?{}">{}</a>', urlencode({"q": text}), text)


@register.filter
def birthday_tags(profile):
    """Birthday with linked day/month, year, age — FB Basic Info style."""
    if not profile or not getattr(profile, "birthday", None):
        return ""
    vis = getattr(profile, "birthday_visibility", None) or "day_month"
    if vis == "hide":
        return ""
    from django.utils import timezone
    months = "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split()
    b = profile.birthday
    dmy = f"{b.day} {months[b.month - 1]}"
    now = timezone.now().date()
    age = now.year - b.year - ((now.month, now.day) < (b.month, b.day))
    if vis == "age":
        return tag(str(age))
    if vis == "full":
        return format_html("{} {} ({})", tag(dmy), tag(str(b.year)), tag(str(age)))
    return tag(dmy)


@register.filter
def external_url(url):
    """Ensure website href has a scheme (classic Contact Info)."""
    u = (url or "").strip()
    if not u:
        return ""
    if not u.startswith(("http://", "https://", "//")):
        return "https://" + u
    return u


@register.filter
def can_manage_post(me, post):
    from apps.social.services import can_manage_wall_post
    return can_manage_wall_post(me, post)


@register.filter
def can_manage_comment(me, comment):
    from apps.social.services import can_manage_wall_comment
    return can_manage_wall_comment(me, comment)


@register.inclusion_tag("social/_comment_thread.html", takes_context=True)
def comment_thread(context, comments, preview=2, kind="wall", group=None, album=None, photo=None, expand=False):
    """FB-2006: show last `preview` comments; older behind a reveal link. preview=0 → all."""
    from apps.social.comment_thread import build_thread
    return build_thread(
        context.get("me"), comments,
        preview=preview, kind=kind, group=group, album=album, photo=photo,
        expand=expand, next_url=context.get("next") or "",
    )

