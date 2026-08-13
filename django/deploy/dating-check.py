#!/usr/bin/env python
"""Smoke: Знакомства — discovery, swipe, match, engagement, canvas."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client, override_settings

from apps.accounts.models import User
from apps.social.dating import service as dating
from apps.social.dating import tips
from apps.social.services import profile_of


def ok(label):
    print(f"OK   {label}")


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "dating-check",
        }
    }
)
def main():
    assert len(tips.TIPS) >= 5
    assert tips.tip_by_slug("icebreaker")
    assert tips.PROMPTS
    ok("curriculum")

    users = list(User.objects.order_by("id")[:3])
    assert len(users) >= 1
    me = profile_of(users[0])
    p = dating.get_or_create_profile(me)
    assert p.discoverable
    dating.save_profile(
        me,
        {
            "headline": "Кофе и разговоры",
            "about": "Люблю долгие прогулки и живую музыку по вечерам.",
            "intent": "dating",
            "age_min": 18,
            "age_max": 99,
            "gender_pref": "any",
            "discoverable": True,
            "prompt1_key": "weekend",
            "prompt1_answer": "Рынок и кино",
            "prompt2_key": "song",
            "prompt2_answer": "Anything jazz",
        },
    )
    strip = dating.engagement_strip(me)
    assert strip["goals"]["total"] >= 4
    assert strip["completeness"]["pct"] >= 50
    ok("profile + engagement")

    if len(users) >= 2:
        peer_user = users[1]
        peer = profile_of(peer_user)
        dating.get_or_create_profile(peer)
        dating.save_profile(
            peer,
            {
                "headline": "Новые встречи",
                "about": "Ищу интересных людей в городе для живого общения.",
                "intent": "chat",
                "age_min": 18,
                "age_max": 99,
                "gender_pref": "any",
                "discoverable": True,
                "prompt1_key": "food",
                "prompt1_answer": "На выставку",
            },
        )
        # clear prior swipes between pair for idempotent probe
        from apps.social.dating.models import DatingSwipe, DatingMatch

        DatingSwipe.objects.filter(from_user=me, to_user=peer).delete()
        DatingSwipe.objects.filter(from_user=peer, to_user=me).delete()
        a, b = (me, peer) if me.id < peer.id else (peer, me)
        DatingMatch.objects.filter(user_a=a, user_b=b).delete()

        dating.swipe(peer, me.id, "like")
        result = dating.swipe(me, peer.id, "like")
        assert result.get("match")
        likes = dating.likes_you(me)
        matches = dating.my_matches(me)
        assert any(m["peer"].id == peer.id for m in matches)
        mid = next(m["match"].id for m in matches if m["peer"].id == peer.id)
        assert dating.unmatch(me, mid)
        assert not any(m["peer"].id == peer.id for m in dating.my_matches(me))
        ok("mutual match + unmatch")
    else:
        ok("match skipped (need 2+ users)")

    c = Client()
    c.force_login(users[0])
    for tab in ("discover", "likes", "matches", "profile", "tips", "spark"):
        resp = c.get(f"/apps/dating/canvas?tab={tab}", secure=True)
        assert resp.status_code == 200, tab
        body = resp.content
        assert "Знакомства".encode() in body
        assert b"<iframe" not in body.lower()
        assert b"<details" not in body.lower()
    discover = c.get("/apps/dating/canvas?tab=discover", secure=True).content
    assert "Цели дня".encode() in discover or "серия".encode() in discover
    assert b"dating-app" in discover
    tips_html = c.get("/apps/dating/canvas?tab=tips", secure=True).content
    assert "Школа".encode() in tips_html or "совет".encode() in tips_html.lower()
    matches_html = c.get("/apps/dating/canvas?tab=matches", secure=True).content
    assert "удалить матч".encode() in matches_html or "Матчей ещё нет".encode() in matches_html
    ok("canvas tabs")
    print("ALL dating probes passed")


if __name__ == "__main__":
    main()
