"""Profile Info tab boxes — short builders (no fat info_boxes)."""
from __future__ import annotations

from django.urls import reverse
from django.utils.html import format_html, format_html_join

from apps.social.templatetags.vd import birthday_tags, external_url


def _tag(text):
    from apps.social.profile_page import _tag as tag
    return tag(text)


def _tags(text):
    from apps.social.profile_page import _tags as tags
    return tags(text)


def _people_link(text, **params):
    from apps.social.profile_page import _people_link as pl
    return pl(text, **params)


def _ru(val):
    from apps.social.profile_page import _ru as ru
    return ru(val)


def _box(title, section, rows=None, subsections=None):
    if not rows and not subsections:
        return None
    out = {"title": title, "section": section}
    if rows:
        out["rows"] = rows
    if subsections:
        out["subsections"] = subsections
    return out


def _basic_rows(profile) -> list:
    rows = []
    if profile.gender:
        rows.append(("Пол", _people_link(_ru(profile.gender), gender=profile.gender), False))
    if profile.birthday_display():
        rows.append(("День рождения", birthday_tags(profile), False))
    if profile.city:
        city = _people_link(profile.city, city=profile.city)
        if profile.country:
            city = format_html("{}, {}", city, profile.country)
        rows.append(("Город", city, False))
    if profile.hometown:
        rows.append(("Родной город", _people_link(profile.hometown, city=profile.hometown), False))
    if profile.relationship_status:
        rows.append(("Отношения", _relationship_html(profile), False))
    fam_html = _family_html(profile)
    if fam_html:
        rows.append(("Семья", fam_html, False))
    if profile.interested_in_label():
        rows.append(("Интересуюсь", _tags(profile.interested_in_label()), False))
    if profile.looking_for_label():
        rows.append(("Ищу", _tags(profile.looking_for_label()), False))
    if profile.political_views:
        rows.append(("Политика", _tag(_ru(profile.political_views)), False))
    if profile.religious_views:
        rows.append(("Религия", _tag(profile.religious_views), False))
    if profile.languages_label():
        rows.append(("Языки", _tags(profile.languages_label()), False))
    if profile.created_at:
        rows.append(("На сайте с", profile.created_at, True))
    return rows


def _relationship_html(profile):
    rel = _tag(_ru(profile.relationship_status))
    partner = getattr(profile, "relationship_with", None)
    if not partner:
        return rel
    from apps.social import relationship as relmod
    pending = relmod.pending_for(profile)
    tpl = '{} с <a href="{}">{}</a>'
    if pending:
        tpl += ' <span class="muted">(ожидает подтверждения)</span>'
    return format_html(tpl, rel, reverse("profile", args=[partner.id]), partner.name)


def _family_html(profile):
    from apps.social import family as fam
    family_rows = fam.approved_for(profile)
    if not family_rows:
        return None
    return format_html_join(
        ", ",
        '{} — <a href="{}">{}</a>',
        (
            (fam.label(link.kind), reverse("profile", args=[link.to_user_id]), link.to_user.name)
            for link in family_rows
        ),
    )


def _contact_rows(profile) -> list:
    rows = []
    email = getattr(getattr(profile, "user", None), "email", None)
    if profile.show_email and email:
        rows.append(("E-mail", email, False))
    if profile.show_phone and profile.phone:
        rows.append(("Телефон", profile.phone, False))
    if profile.telegram_username:
        rows.append(("Имя в сети", profile.telegram_username, False))
    if profile.website:
        rows.append((
            "Сайт",
            format_html(
                '<a href="{}" rel="nofollow noopener">{}</a>',
                external_url(profile.website), profile.website,
            ),
            False,
        ))
    return rows


def _personal_rows(profile) -> list:
    rows = []
    for label, val, linked in (
        ("Обо мне", profile.bio, False),
        ("Интересы", profile.interests, True),
        ("Хобби", profile.hobbies, True),
        ("Музыка", profile.favorite_music, True),
        ("Фильмы", profile.favorite_movies, True),
        ("ТВ", profile.favorite_tv, True),
        ("Книги", profile.favorite_books, True),
        ("Игры", profile.favorite_games, True),
        ("Цитаты", profile.favorite_quotes, False),
    ):
        if val:
            rows.append((label, _tags(val) if linked else val, False))
    return rows


def _edu_items(education, profile) -> dict | None:
    if not (education or profile.education_note):
        return None
    items = []
    for e in education:
        line = _people_link(e.institution, school=e.institution)
        if e.degree:
            line = format_html("{} — {}", line, e.degree)
        if e.field:
            line = format_html("{}, {}", line, e.field)
        if e.start_year or e.end_year:
            line = format_html(
                '{} <span class="muted">({}–{})</span>',
                line, e.start_year or "", e.end_year or "",
            )
        items.append(line)
    return {
        "h5": "Образование",
        "note": _people_link(profile.education_note, school=profile.education_note) if profile.education_note else "",
        "items": items,
    }


def _work_items(experiences, profile) -> dict | None:
    if not (experiences or profile.workplace):
        return None
    items = []
    for e in experiences:
        line = format_html("<b>{}</b> · {}", e.position, _people_link(e.company_name, workplace=e.company_name))
        if e.period:
            line = format_html('{} <span class="muted">{}</span>', line, e.period)
        if e.description:
            line = format_html('{}<div class="muted">{}</div>', line, e.description)
        items.append(line)
    return {
        "h5": "Работа",
        "note": _people_link(profile.workplace, workplace=profile.workplace) if profile.workplace else "",
        "items": items,
    }


def info_boxes(profile, education, experiences) -> list[dict]:
    """Structured Info tab — compose short box builders."""
    boxes = []
    for title, section, rows in (
        ("Основная информация", "basic", _basic_rows(profile)),
        ("Контактная информация", "contact", _contact_rows(profile)),
        ("Личная информация", "personal", _personal_rows(profile)),
    ):
        b = _box(title, section, rows=rows)
        if b:
            boxes.append(b)
    subs = [s for s in (_edu_items(education, profile), _work_items(experiences, profile)) if s]
    if subs:
        boxes.append(_box("Образование и работа", "eduwork", subsections=subs))
    return boxes
