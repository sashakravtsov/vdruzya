#!/usr/bin/env python
"""Smoke: poker app — engine, rooms, rating, championship, canvas."""
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
    cv = engine.card_view("Ah")
    assert cv["red"] and cv["rank"] == "A" and cv["suit_name"] == "hearts"
    assert engine.format_chips(1_000_000) == "1 000 000"
    assert engine.chip_layers(12500)
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
    nw, nl = poker.elo_update(1200, 1200, draw=False)
    assert nw > 1200 > nl
    ok("economy + elo")

    users = list(User.objects.order_by("id")[:2])
    assert len(users) >= 1
    me = profile_of(users[0])
    prof = poker.get_or_create_profile(me)
    assert prof.chips >= 0
    assert int(getattr(prof, "rating", 1200) or 1200) >= 100
    strip = poker.engagement_strip(me)
    assert "chips" in strip and "bankrupt" in strip and "rating" in strip
    champ = poker.ensure_week_championship()
    assert champ.week_key
    meta = poker.learn_stats(me)
    assert meta["total"] >= 8
    ok("profile + champ + learn stats")

    room = poker.create_room(me, title="Smoke HU", stake_key="micro", is_private=True, in_champ=True)
    assert room.is_private and room.join_code
    assert poker.room_for(me, room.id)
    if len(users) >= 2:
        peer = profile_of(users[1])
        poker.get_or_create_profile(peer)
        joined = poker.join_room(peer, join_code=room.join_code)
        assert joined.p2_id == peer.id
        g = poker.start_room_hand(me, room.id)
        assert g.status == "active" and g.room_id == room.id
        assert g.championship_id
        view = poker.table_view(g, me)
        assert "my_cards" in view and "board_slots" in view
        assert len(view["board_slots"]) == 5
        assert "street_label" in view and view["pot_fmt"] is not None
        ok("private room + deal")
    else:
        ok("private room create (single user)")

    c = Client()
    c.force_login(users[0])
    for tab in ("play", "rooms", "learn", "puzzles", "bank", "leaders", "ratings", "champs"):
        resp = c.get(f"/apps/poker/canvas?tab={tab}", secure=True)
        assert resp.status_code == 200, tab
        body = resp.content
        assert "Покер".encode() in body
        assert b"<iframe" not in body.lower()
        assert b"<details" not in body.lower()
    play = c.get("/apps/poker/canvas?tab=play", secure=True).content
    assert "Вызвать на раздачу".encode() in play or "Банкротство".encode() in play
    assert "рейтинг".encode() in play.lower() or "Рейтинг".encode() in play
    rooms = c.get("/apps/poker/canvas?tab=rooms", secure=True).content
    assert "Создать комнату".encode() in rooms
    assert "Войти по коду".encode() in rooms
    assert "Лобби столов".encode() in rooms
    assert b"poker-table.js" in rooms or b"poker-mini-felt" in rooms
    ratings = c.get("/apps/poker/canvas?tab=ratings", secure=True).content
    assert "Рейтинг Elo".encode() in ratings
    champs = c.get("/apps/poker/canvas?tab=champs", secure=True).content
    assert "Чемпионат".encode() in champs or champ.title.encode() in champs
    learn = c.get("/apps/poker/canvas?tab=learn", secure=True).content
    assert "Система обучения".encode() in learn
    bank = c.get("/apps/poker/canvas?tab=bank", secure=True).content
    assert "1".encode() in bank and "000".encode() in bank
    puzzles_html = c.get("/apps/poker/canvas?tab=puzzles", secure=True).content
    assert "Задача дня".encode() in puzzles_html
    ok("canvas rooms + rating + champ UI")
    print("ALL poker probes passed")


if __name__ == "__main__":
    main()
