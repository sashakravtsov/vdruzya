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
from apps.social.models import Education, Post, SocialProfile
from apps.social.profile_page import can_write_wall
from apps.social.services import can_manage_wall_post, friend_ids, now, profile_of, wall_posts_for


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
    assert b"?tab=wall" in r.content
    assert b"?tab=info" in r.content
    assert b"?tab=photos" in r.content
    assert b"?tab=friends" in r.content
    assert "Мини-лента".encode() in r.content
    assert "Стена".encode() in r.content
    assert "Группы".encode() in r.content
    assert b'name="headline"' in r.content  # status in header
    assert "<h4>Статус</h4>".encode() not in r.content
    ok("own profile wall tab")

    r = c.get(f"/profile/{me.id}?tab=info", secure=True)
    assert r.status_code == 200
    assert "Информация".encode() in r.content
    assert "Мини-лента".encode() not in r.content
    assert "Основная информация".encode() in r.content
    ok("profile info tab")

    r = c.get("/feed", secure=True)
    assert r.status_code == 200
    assert "Лента новостей".encode() in r.content
    assert b"wallposter" not in r.content  # no wall compose on news feed
    assert "Что у вас нового".encode() in r.content
    ok("news feed")

    r = c.get("/pokes", secure=True)
    assert r.status_code == 200
    assert "Подмигивания".encode() in r.content
    ok("pokes inbox")

    r = c.get("/search?name=а&city=", secure=True)
    assert r.status_code == 200
    assert "Найти людей".encode() in r.content
    ok("advanced search")

    r = c.get("/profile/edit", secure=True)
    assert r.status_code == 200
    assert "Основная информация".encode() in r.content
    assert "Контакты".encode() in r.content or "Контактная информация".encode() in r.content
    assert "Приватность".encode() in r.content
    assert "Интересуюсь".encode() in r.content
    assert "Имя в сети".encode() in r.content
    assert "Работа".encode() in r.content
    assert "Ищу".encode() in r.content
    assert "Игры".encode() not in r.content
    assert b"profile" in r.content  # back link to own profile
    ok("profile edit sections")

    other = SocialProfile.objects.filter(id__in=friend_ids(me)).exclude(id=me.id).first()
    assert other, "need a friend"

    r = c.post("/profile/edit", {
        "name": me.name,
        "slug": me.slug,
        "headline": "__profile_status_check__",
        "bio": me.bio or "",
        "city": me.city or "Москва",
        "hometown": me.hometown or "",
        "country": me.country or "",
        "gender": me.gender or "male",
        "birthday": me.birthday.isoformat() if me.birthday else "",
        "birthday_visibility": me.birthday_visibility or "day_month",
        "relationship_status": "in_a_relationship",
        "relationship_with": str(other.id),
        "political_views": me.political_views or "",
        "religious_views": me.religious_views or "",
        "interests": me.interests or "",
        "hobbies": me.hobbies or "",
        "workplace": me.workplace or "",
        "education_note": me.education_note or "",
        "website": me.website or "",
        "phone": me.phone or "",
        "telegram_username": "aim_classic",
        "show_phone": "on" if me.show_phone else "",
        "show_email": "on" if me.show_email else "",
        "profile_visibility": me.profile_visibility or "public",
        "wall_write": me.wall_write or "friends",
        "wall_view": me.wall_view or "public",
        "favorite_music": me.favorite_music or "",
        "favorite_movies": me.favorite_movies or "",
        "favorite_tv": me.favorite_tv or "",
        "favorite_books": me.favorite_books or "",
        "favorite_quotes": me.favorite_quotes or "",
        "languages_text": me.languages_label(),
        "looking_for_choices": ["friendship"],
        "interested_in_choices": ["women"],
    }, secure=True)
    assert r.status_code in (301, 302), getattr(r, "context", None) and r.context["form"].errors
    me.refresh_from_db()
    assert isinstance(me.looking_for, list) and "friendship" in me.looking_for
    assert isinstance(me.interested_in, list) and "women" in me.interested_in
    assert me.telegram_username == "aim_classic"
    assert me.relationship_with_id == other.id
    ok("profile save looking_for + partner + screen name")

    r = c.get(f"/profile/{me.id}?tab=info", secure=True)
    assert other.name.encode() in r.content
    assert b"aim_classic" in r.content
    r = c.get(f"/profile/{me.id}", secure=True)
    assert b"__profile_status_check__" in r.content
    ok("partner + screen name + status on profile")

    list(wall_posts_for(me, 5, viewer=me))
    ok("wall_posts_for visibility")

    edu = Education.objects.create(
        social_user=me, institution="__edu_check__", degree="BA", field="CS",
        start_year=2004, end_year=2008,
    )
    r = c.get(f"/profile/edit?edu={edu.id}", secure=True)
    assert r.status_code == 200
    assert b"__edu_check__" in r.content
    r = c.post(f"/profile/education/{edu.id}", {
        "institution": "__edu_check_edited__",
        "degree": "BA", "field": "CS", "start_year": "2004", "end_year": "2008",
    }, secure=True)
    assert r.status_code in (301, 302)
    edu.refresh_from_db()
    assert edu.institution == "__edu_check_edited__"
    Education.objects.filter(pk=edu.id).delete()
    ok("education edit")

    t = now()
    note = Post.objects.create(
        social_user=other,
        body="__profile_check_wall_note__",
        topic=f"wall:{me.id}",
        visibility="friends",
        kind="text",
        created_at=t,
        updated_at=t,
    )
    assert can_manage_wall_post(me, note)
    stranger = SocialProfile.objects.exclude(id__in={me.id, other.id}).first()
    if stranger:
        assert not can_manage_wall_post(stranger, note)
        assert not can_write_wall(stranger, me, None)

    r = c.get(f"/profile/{me.id}", secure=True)
    assert b"__profile_check_wall_note__" in r.content
    assert f'action="/posts/{note.id}/delete"'.encode() in r.content
    ok("wall note + owner delete UI")

    r = c.post(f"/posts/{note.id}/delete", {"next": f"/profile/{me.id}"}, secure=True)
    assert r.status_code in (301, 302)
    assert not Post.objects.filter(pk=note.id).exists()
    ok("wall owner deletes guest note")

    prev = me.profile_visibility or "public"
    me.profile_visibility = "friends"
    me.save(update_fields=["profile_visibility"])
    fids = friend_ids(me) | {me.id, other.id}
    stranger = SocialProfile.objects.exclude(id__in=fids).exclude(user_id__isnull=True).first()
    assert stranger, "need non-friend for limited profile"
    c2 = Client(HTTP_HOST="vdruzya.ru")
    c2.force_login(User.objects.get(pk=stranger.user_id))
    r = c2.get(f"/profile/{me.id}", secure=True)
    assert r.status_code == 200
    assert "Ограниченный профиль".encode() in r.content
    assert "Мини-лента".encode() not in r.content
    ok("limited profile for non-friend")
    me.profile_visibility = prev
    me.save(update_fields=["profile_visibility"])

    print("ALL profile probes passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print("FAIL", e, file=sys.stderr)
        raise
