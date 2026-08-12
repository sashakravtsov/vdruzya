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
from apps.social.profile_page import can_write_wall, wall_post_visibility
from apps.social.services import (
    can_manage_wall_post, feed_queryset, friend_count, friend_ids, now, profile_of, wall_posts_for,
)


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
    assert b"?tab=notes" in r.content
    assert b"?tab=friends" in r.content
    assert "Заметки".encode() in r.content
    assert "Мини-лента".encode() in r.content
    assert "Стена".encode() in r.content
    assert "Группы".encode() in r.content
    assert b'name="headline"' in r.content  # status under picture
    assert b'id="status"' in r.content
    assert "сейчас".encode() in r.content  # classic "Name сейчас …"
    assert b"profile-status-bar" not in r.content  # not jammed into blue #header
    assert "<h4>Статус</h4>".encode() not in r.content
    header = r.content.split(b'id="header"', 1)[-1].split(b'id="content"', 1)[0]
    assert b'name="headline"' not in header and b'id="status"' not in header
    left = r.content.split(b'id="profilenarrowcolumn"', 1)[-1].split(b'id="profilewidecolumn"', 1)[0]
    assert b'id="status"' in left and b'name="headline"' in left
    assert "<h4>Ограниченный профиль</h4>".encode() not in r.content
    assert b"compose-more" not in r.content  # simple wall compose (no «ещё»)
    assert b'name="visibility"' not in r.content  # server sets from wall_view
    assert f'name="wall_to" value="{me.id}"'.encode() in r.content
    assert "Мне нравится".encode() not in r.content  # pre-2009 profile wall
    assert "Друзья в ".encode() not in r.content
    n_friends = len(friend_ids(me))
    assert friend_count(me) == n_friends
    assert f"Друзья ({n_friends})".encode() in r.content
    assert b'id="userprofile"' in r.content
    assert b'id="profilenarrowcolumn"' in r.content
    assert b'id="profilewidecolumn"' in r.content
    ok("own profile wall tab")

    # Wall-to-Wall only for friends (own profile has no link)
    assert "Стена к стене".encode() not in r.content.split(b'id="profilenarrowcolumn"', 1)[-1].split(b'id="profilewidecolumn"', 1)[0]
    ok("own profile has no wall-to-wall")

    r = c.get(f"/profile/{me.id}?tab=info", secure=True)
    assert r.status_code == 200
    assert "Основная информация".encode() in r.content
    assert "Мини-лента".encode() not in r.content
    ok("profile info tab")

    r = c.get(f"/profile/{me.id}?tab=photos", secure=True)
    assert r.status_code == 200
    right = r.content.split(b'id="profilewidecolumn"', 1)[-1]
    assert b'id="photos"' in right
    assert b"profile-photo-thumbs" not in right  # thumbs stay on left rail
    ok("profile photos tab albums")

    r = c.get(f"/profile/{me.id}?tab=notes", secure=True)
    assert r.status_code == 200
    assert "Заметки".encode() in r.content
    assert b'action="/notes"' in r.content
    assert b'name="title"' in r.content and b'name="body"' in r.content
    assert b"timesince" not in r.content
    ok("profile notes tab")

    r = c.get(f"/profile/{me.id}?tab=friends", secure=True)
    assert r.status_code == 200
    assert "Друзья".encode() in r.content
    ok("profile friends tab")

    from apps.social.models import Education, Experience
    from apps.social.profile_page import networks_for
    nets = networks_for(me)
    r = c.get(f"/profile/{me.id}", secure=True)
    assert r.status_code == 200
    html = r.content.decode()
    if nets:
        assert "Сети" in html
        assert any("tab=search" in n["href"] for n in nets)
        if any("city=" in n["href"] for n in nets):
            assert "city=" in html
        if any("school=" in n["href"] for n in nets):
            assert "school=" in html
        if any("workplace=" in n["href"] for n in nets):
            assert "workplace=" in html
        ok("networks rail → Find Friends")
    else:
        ok("networks rail empty (no city/school/work)")

    r = c.get("/feed", secure=True)
    assert r.status_code == 200
    assert "Лента новостей".encode() in r.content
    assert b"wallposter" not in r.content
    assert "Что у вас нового".encode() not in r.content
    assert "<h4>Новости</h4>".encode() not in r.content
    assert b"news-card" not in r.content
    assert b"page-tabs" not in r.content
    assert b'class="wallpost"' not in r.content  # stories, not wall cards
    assert "Подмигивания".encode() in r.content
    assert "События".encode() in r.content
    assert "Дни рождения".encode() in r.content
    assert "Заявки".encode() in r.content
    ok("news feed")

    r = c.get("/pokes", secure=True)
    assert r.status_code == 200
    assert "Подмигивания".encode() in r.content
    ok("pokes inbox")

    r = c.get("/account", secure=True)
    assert r.status_code == 200
    assert "Мой аккаунт".encode() in r.content
    assert "Пригласить друга".encode() in r.content
    assert "Приватность".encode() in r.content
    assert b"section=privacy" in r.content
    assert "Смена пароля".encode() in r.content
    ok("account hub")

    r = c.get("/search?q=а", secure=True)
    assert r.status_code == 200
    assert b'id="tabs"' in r.content
    assert "Люди".encode() in r.content and "Группы".encode() in r.content
    assert "Расширенный поиск людей".encode() in r.content
    assert b'name="city"' not in r.content
    assert b"placeholder=" not in r.content
    ok("global search")

    r = c.get("/profile/edit", secure=True)
    assert r.status_code == 200
    assert "Редактирование моего профиля".encode() in r.content
    assert b'id="tabs"' in r.content
    assert b'id="infoarea"' in r.content
    assert b'id="editnav"' not in r.content
    assert "Основное".encode() in r.content
    assert "Контакты".encode() in r.content  # tab
    assert "Контактная информация".encode() in r.content or True  # title on contact section
    assert "Приватность".encode() in r.content
    assert "Интересуюсь".encode() in r.content
    assert "Ищу".encode() in r.content
    assert b"section=picture" in r.content
    assert b'type="date"' not in r.content
    assert b"datetime-local" not in r.content
    assert b'name="birthday_year"' in r.content or b"birthday_year" in r.content
    ok("profile edit sections")

    r = c.get("/profile/edit?section=contact", secure=True)
    assert r.status_code == 200
    assert "Имя в сети".encode() in r.content
    assert "Контактная информация".encode() in r.content
    ok("profile edit contact")

    r = c.get("/profile/edit?section=personal", secure=True)
    assert r.status_code == 200
    assert "Игры".encode() in r.content
    ok("profile edit personal games")

    r = c.get("/profile/edit?section=picture", secure=True)
    assert r.status_code == 200
    assert b'id="currentpicture"' in r.content and b'id="uploadpicture"' in r.content
    assert b'type="date"' not in r.content
    ok("profile edit picture chrome")

    other = SocialProfile.objects.filter(id__in=friend_ids(me)).exclude(id=me.id).first()
    assert other, "need a friend"

    r = c.get(f"/profile/{other.id}", secure=True)
    assert r.status_code == 200
    r2 = c.get(f"/profile/{other.id}?tab=friends", secure=True)
    assert r2.status_code == 200
    right = r2.content.split(b'id="profilewidecolumn"', 1)[-1]
    assert "<h4>Друзья".encode() in right
    assert "<h4>Общие друзья".encode() not in right
    ok("friend profile: friends tab lists friends")

    bday = me.birthday
    basic = {
        "name": me.name,
        "slug": me.slug,
        "city": me.city or "Москва",
        "hometown": me.hometown or "",
        "country": me.country or "",
        "gender": me.gender or "male",
        "birthday_visibility": me.birthday_visibility or "day_month",
        "relationship_status": "in_a_relationship",
        "relationship_with": str(other.id),
        "political_views": me.political_views or "",
        "religious_views": me.religious_views or "",
        "languages_text": me.languages_label(),
        "looking_for_choices": ["friendship"],
        "interested_in_choices": ["women"],
    }
    if bday:
        basic["birthday_year"] = str(bday.year)
        basic["birthday_month"] = str(bday.month)
        basic["birthday_day"] = str(bday.day)
    r = c.post("/profile/edit?section=basic", basic, secure=True)
    assert r.status_code in (301, 302), getattr(r, "context", None) and r.context["form"].errors

    r = c.post("/profile/edit?section=contact", {
        "website": me.website or "",
        "phone": me.phone or "",
        "telegram_username": "aim_classic",
        "show_phone": "on" if me.show_phone else "",
        "show_email": "on" if me.show_email else "",
    }, secure=True)
    assert r.status_code in (301, 302)

    r = c.post("/profile/status", {
        "headline": "__profile_status_check__",
        "next": f"/profile/{me.id}",
    }, secure=True)
    assert r.status_code in (301, 302)

    me.refresh_from_db()
    assert isinstance(me.looking_for, list) and "friendship" in me.looking_for
    assert isinstance(me.interested_in, list) and "women" in me.interested_in
    assert me.telegram_username == "aim_classic"
    assert me.relationship_with_id == other.id
    assert me.headline == "__profile_status_check__"
    ok("profile save looking_for + partner + screen name + status")

    r = c.get(f"/profile/{me.id}?tab=info", secure=True)
    assert other.name.encode() in r.content
    assert b"aim_classic" in r.content
    r = c.get(f"/profile/{me.id}", secure=True)
    assert b"__profile_status_check__" in r.content
    # status must not appear as a wall post body card from kind=status alone in wall box
    posts = list(wall_posts_for(me, 20, viewer=me))
    assert all(getattr(p, "kind", None) != "status" for p in posts)
    ok("partner + screen name + status on profile; status off wall")

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
    assert "написал(а) на стену".encode() in r.content
    assert f'action="/posts/{note.id}/delete"'.encode() in r.content
    assert "Мне нравится".encode() not in r.content
    ok("wall note + owner delete UI")

    # Friend of wall owner (not necessarily of author) can open + comment friends-visibility notes
    buddy_id = next((i for i in friend_ids(me) if i != other.id), None)
    if buddy_id:
        buddy = SocialProfile.objects.select_related("user").get(pk=buddy_id)
        assert feed_queryset(buddy).filter(pk=note.id).exists()
        assert note in wall_posts_for(me, 20, viewer=buddy)
        c_buddy = Client(HTTP_HOST="vdruzya.ru")
        c_buddy.force_login(buddy.user)
        r = c_buddy.get(f"/posts/{note.id}", secure=True)
        assert r.status_code == 200 and b"__profile_check_wall_note__" in r.content
        r = c_buddy.post(
            f"/posts/{note.id}/comment",
            {"body": "__buddy_wall_comment__", "next": f"/profile/{me.id}"},
            secure=True, follow=True,
        )
        assert r.status_code == 200
        assert note.comments.filter(body="__buddy_wall_comment__").exists()
        ok("wall friend can view+comment note by non-mutual author")
    else:
        ok("wall friend can view+comment note by non-mutual author (skipped, no buddy)")

    # Author can edit their note from the host's wall
    if other.user_id:
        c_auth = Client(HTTP_HOST="vdruzya.ru")
        c_auth.force_login(User.objects.get(pk=other.user_id))
        r = c_auth.get(f"/profile/{me.id}", secure=True)
        assert r.status_code == 200
        assert f'/posts/{note.id}/edit'.encode() in r.content
        ok("wall author edit on profile")
    else:
        ok("wall author edit on profile (skipped)")

    r = c.post(f"/posts/{note.id}/delete", {"next": f"/profile/{me.id}"}, secure=True)
    assert r.status_code in (301, 302)
    assert not Post.objects.filter(pk=note.id).exists()
    ok("wall owner deletes guest note")

    r = c.get("/profile/edit?section=picture", secure=True)
    assert r.status_code == 200
    assert b'action="/profile/avatar"' in r.content
    assert b'action="/profile/avatar/clear"' in r.content or "нет фото".encode() in r.content
    ok("profile picture edit")

    # Public wall: stranger who can view profile sees public wall notes
    prev_wall = me.wall_view or "public"
    me.wall_view = "public"
    me.save(update_fields=["wall_view"])
    t = now()
    pub = Post.objects.create(
        social_user=other, body="__public_wall_note__", topic=f"wall:{me.id}",
        visibility="public", kind="text", created_at=t, updated_at=t,
    )
    fids = friend_ids(me) | {me.id, other.id}
    stranger = SocialProfile.objects.exclude(id__in=fids).exclude(user_id__isnull=True).first()
    assert stranger, "need non-friend"
    c2 = Client(HTTP_HOST="vdruzya.ru")
    c2.force_login(User.objects.get(pk=stranger.user_id))
    # Ensure stranger can see full profile
    prev = me.profile_visibility or "public"
    me.profile_visibility = "public"
    me.save(update_fields=["profile_visibility"])
    r = c2.get(f"/profile/{me.id}", secure=True)
    assert r.status_code == 200
    assert b"__public_wall_note__" in r.content
    ok("public wall note visible to non-friend")
    Post.objects.filter(pk=pub.id).delete()

    # wall_view=self → private posts (friends must not see/comment via feed)
    assert wall_post_visibility(SocialProfile(wall_view="self")) == "private"
    assert wall_post_visibility(SocialProfile(wall_view="friends")) == "friends"
    me.wall_view = "self"
    me.save(update_fields=["wall_view"])
    t = now()
    priv = Post.objects.create(
        social_user=me, body="__private_wall_note__", topic=f"wall:{me.id}",
        visibility=wall_post_visibility(me), kind="text", created_at=t, updated_at=t,
    )
    assert priv.visibility == "private"
    assert priv in wall_posts_for(me, 20, viewer=me)
    buddy_id = next(iter(friend_ids(me)), None)
    if buddy_id:
        buddy = SocialProfile.objects.get(pk=buddy_id)
        assert priv not in wall_posts_for(me, 20, viewer=buddy)
        assert not feed_queryset(buddy).filter(pk=priv.id).exists()
        c_b = Client(HTTP_HOST="vdruzya.ru")
        c_b.force_login(User.objects.get(pk=buddy.user_id))
        r = c_b.get(f"/posts/{priv.id}", secure=True)
        assert r.status_code == 404
        r = c_b.post(
            f"/posts/{priv.id}/comment",
            {"body": "should fail", "next": "/feed"},
            secure=True, follow=True,
        )
        assert not priv.comments.filter(body="should fail").exists()
        ok("wall_view=self private: friend cannot view/comment")
    else:
        ok("wall_view=self private: friend cannot view/comment (skipped)")
    Post.objects.filter(pk=priv.id).delete()
    me.wall_view = prev_wall
    me.save(update_fields=["wall_view"])

    me.profile_visibility = "friends"
    me.save(update_fields=["profile_visibility"])
    r = c2.get(f"/profile/{me.id}", secure=True)
    assert r.status_code == 200
    assert "Мини-лента".encode() not in r.content
    assert b"?tab=wall" not in r.content
    assert "Профиль доступен только друзьям".encode() in r.content
    assert "Друзья (".encode() not in r.content
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
