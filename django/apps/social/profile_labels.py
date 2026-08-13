"""SocialProfile display labels — model methods stay thin."""
from __future__ import annotations

from django.utils import timezone


def birthday_display(profile) -> str | None:
    if not profile.birthday:
        return None
    vis = profile.birthday_visibility or "day_month"
    if vis == "hide":
        return None
    months = "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split()
    d, m, y = profile.birthday.day, months[profile.birthday.month - 1], profile.birthday.year
    now = timezone.now().date()
    age = now.year - y - ((now.month, now.day) < (profile.birthday.month, profile.birthday.day))
    if vis == "full":
        return f"{d} {m} {y} ({age})"
    if vis == "age":
        return str(age)
    return f"{d} {m}"


def languages_label(profile) -> str:
    data = profile.languages
    if isinstance(data, list):
        return ", ".join(map(str, data))
    return str(data or "")


def looking_for_label(profile) -> str:
    raw = profile.looking_for
    if not isinstance(raw, list) or not raw:
        return ""
    labels = {
        "friendship": "Дружба", "dating": "Знакомства",
        "relationship": "Отношения", "networking": "Деловые контакты",
    }
    return ", ".join(labels.get(str(x), str(x)) for x in raw)


def interested_in_label(profile) -> str:
    raw = profile.interested_in
    if not isinstance(raw, list) or not raw:
        return ""
    labels = {"men": "Мужчины", "women": "Женщины"}
    return ", ".join(labels.get(str(x), str(x)) for x in raw)
