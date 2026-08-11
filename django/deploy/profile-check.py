#!/usr/bin/env python
"""Smoke probe: classic Profile."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client

from apps.accounts.models import User
from apps.social.services import profile_of, wall_posts_for


def ok(label):
    print(f"OK   {label}")


def main():
    u = User.objects.filter(email="alexandr@vdruzya.ru").first() or User.objects.first()
    assert u, "no user"
    me = profile_of(u)
    c = Client(HTTP_HOST="vdruzya.ru")
    c.force_login(u)

    r = c.get(f"/profile/{me.id}", secure=True)
    assert r.status_code == 200
    assert me.name.encode() in r.content
    assert "Информация".encode() in r.content
    assert "Мини-лента".encode() in r.content
    assert "Фото".encode() in r.content
    assert "Стена".encode() in r.content
    ok("own profile sections")

    r = c.get("/profile/edit", secure=True)
    assert r.status_code == 200
    assert "Основная информация".encode() in r.content
    assert "Контакты".encode() in r.content
    assert "Работа".encode() in r.content
    assert "Ищу".encode() in r.content
    ok("profile edit sections")

    r = c.post("/profile/edit", {
        "name": me.name,
        "slug": me.slug,
        "headline": me.headline or "",
        "bio": me.bio or "",
        "city": me.city or "Москва",
        "hometown": me.hometown or "",
        "country": me.country or "",
        "gender": me.gender or "male",
        "birthday": me.birthday.isoformat() if me.birthday else "",
        "birthday_visibility": me.birthday_visibility or "day_month",
        "relationship_status": me.relationship_status or "",
        "political_views": me.political_views or "",
        "religious_views": me.religious_views or "",
        "interests": me.interests or "",
        "hobbies": me.hobbies or "",
        "workplace": me.workplace or "",
        "education_note": me.education_note or "",
        "website": me.website or "",
        "phone": me.phone or "",
        "favorite_music": me.favorite_music or "",
        "favorite_movies": me.favorite_movies or "",
        "favorite_tv": me.favorite_tv or "",
        "favorite_books": me.favorite_books or "",
        "favorite_games": me.favorite_games or "",
        "favorite_quotes": me.favorite_quotes or "",
        "languages_text": me.languages_label(),
        "looking_for_choices": ["friendship"],
    }, secure=True)
    assert r.status_code in (301, 302)
    me.refresh_from_db()
    assert isinstance(me.looking_for, list) and "friendship" in me.looking_for
    ok("profile save looking_for")

    list(wall_posts_for(me, 5, viewer=me))
    ok("wall_posts_for visibility")

    print("ALL profile probes passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print("FAIL", e, file=sys.stderr)
        raise
