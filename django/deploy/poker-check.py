#!/usr/bin/env python
"""Smoke: poker app — engine, economy, curriculum, canvas."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client, override_settings

from apps.accounts.models import User
from apps.social.poker import engine
from apps.social.poker import lessons
from apps.social.poker import puzzles
from apps.social.poker import service as poker
from apps.social.services import profile_of


def ok(label):
    print(f"OK   {label}")


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "poker-check",
        }
    }
)
def main():
    # hand ranks
    assert engine.evaluate_five(["Ah", "Kh", "Qh", "Jh", "Th"])[0] == 9
    assert engine.evaluate_five(["9h", "Kh", "Qh", "Jh", "Th"])[0] == 8
    assert engine.hand_name((6, 14, 13)) == "фулл-хаус"
    hole = ["As", "Ad"]
    board = ["2c", "2d", "2h", "9s", "Td"]
    assert engine.best_hand(hole, board)[0] == 6  # full house
    ok("engine hand evaluation")

    dealt = engine.deal_hand("seed-1")
    assert len(dealt["p1_hole"]) == 2 and len(dealt["deck"]) == 48
    ok("engine deal")

    assert len(lessons.LESSONS) >= 8
    assert lessons.lesson_by_slug("bankruptcy-rules")
    assert len(puzzles.PUZZLES) >= 10
    assert puzzles.daily_puzzle()["id"]
    for pz in puzzles.PUZZLES:
        assert puzzles.check_answer(pz, pz["answer"])
    ok("curriculum + puzzles")

    assert poker.STARTING_CHIPS == 1_000_000
    assert poker.BANKRUPT_DAYS == 5
    assert poker.stake_by_key("micro")[4] == 20_000
    ok("economy constants")

    users = list(User.objects.order_by("id")[:2])
    assert len(users) >= 1
    me = profile_of(users[0])
    prof = poker.get_or_create_profile(me)
    assert prof.chips >= 0
    strip = poker.engagement_strip(me)
    assert "chips" in strip and "bankrupt" in strip
    meta = poker.learn_stats(me)
    assert meta["total"] >= 8
    ok("profile + learn stats")

    c = Client()
    c.force_login(users[0])
    for tab in ("play", "learn", "puzzles", "bank", "leaders"):
        resp = c.get(f"/apps/poker/canvas?tab={tab}", secure=True)
        assert resp.status_code == 200, tab
        body = resp.content
        assert "Покер".encode() in body
        assert b"<iframe" not in body.lower()
        assert b"<details" not in body.lower()
    play = c.get("/apps/poker/canvas?tab=play", secure=True).content
    assert "Вызвать на раздачу".encode() in play or "Банкротство".encode() in play
    assert "фишк".encode() in play.lower() or "Фишки".encode() in play
    learn = c.get("/apps/poker/canvas?tab=learn", secure=True).content
    assert "Система обучения".encode() in learn
    assert "Банкротство".encode() in learn
    bank = c.get("/apps/poker/canvas?tab=bank", secure=True).content
    assert "1".encode() in bank and "000".encode() in bank
    puzzles_html = c.get("/apps/poker/canvas?tab=puzzles", secure=True).content
    assert "Задача дня".encode() in puzzles_html
    ok("canvas pro poker UI")
    print("ALL poker probes passed")


if __name__ == "__main__":
    main()
