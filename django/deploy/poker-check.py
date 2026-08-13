#!/usr/bin/env python
"""Smoke: poker — multi-seat, rooms, rating, champ, engagement, canvas."""
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
from apps.social.poker import multi as multi_eng
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
    assert engine.evaluate_five(["Ah", "Kh", "Qh", "Jh", "Th"])[0] == 9
    cv = engine.card_view("Ah")
    assert cv["red"] and cv["suit_name"] == "hearts"
    assert engine.format_chips(1_000_000) == "1 000 000"
    ok("engine")

    seats = multi_eng.empty_room_seats(6)
    seats = multi_eng.room_add_user(seats, 1)
    seats = multi_eng.room_add_user(seats, 2)
    seats = multi_eng.room_add_user(seats, 3)
    assert multi_eng.room_seat_count(seats) == 3
    deck = engine.new_deck("multi-seed")
    hs = multi_eng.new_hand_seats([1, 2, 3], 20_000, deck)
    hs, to_act, pot, cur = multi_eng.post_blinds(hs, 0, 500, 1000)
    assert pot == 1500 and cur == 1000
    assert to_act == 0  # 3-handed: UTG after BB=2 → next is 0? button=0, sb=1, bb=2, utg=0 yes
    hs2, pot2, cur2, lab, paid = multi_eng.apply_action(hs, to_act, "fold", 0, cur, 1000, pot)
    assert hs2[to_act]["folded"]
    ok("multi engine blinds/fold")

    assert len(lessons.LESSONS) >= 13
    assert lessons.lesson_by_slug("multi-rooms")
    assert lessons.lesson_by_slug("multiway-pots")
    assert lessons.lesson_by_slug("live-tables")
    assert len(puzzles.PUZZLES) >= 15
    assert "мультивей" in puzzles.THEMES
    ok("curriculum expanded")

    assert poker.STARTING_CHIPS == 1_000_000
    assert 6 in poker.SEAT_CHOICES
    nw, nl = poker.elo_update(1200, 1200, draw=False)
    assert nw > 1200 > nl
    ok("economy + seats")

    users = list(User.objects.order_by("id")[:3])
    assert len(users) >= 1
    me = profile_of(users[0])
    prof = poker.get_or_create_profile(me)
    assert int(getattr(prof, "rating", 1200) or 1200) >= 100
    strip = poker.engagement_strip(me)
    assert "goals" in strip and "badges" in strip and "rating" in strip
    champ = poker.ensure_week_championship()
    assert champ.week_key
    ok("engagement strip")

    room = poker.create_room(
        me, title="Smoke 6max", stake_key="micro", is_private=True, in_champ=True, max_seats=6,
    )
    assert room.max_seats == 6 and room.join_code
    meta = poker.room_view(room, me)
    assert meta["max_seats"] == 6 and meta["filled_n"] >= 1
    dealt = None
    if len(users) >= 2:
        peer = profile_of(users[1])
        poker.get_or_create_profile(peer)
        poker.join_room(peer, join_code=room.join_code)
        if len(users) >= 3:
            p3 = profile_of(users[2])
            poker.get_or_create_profile(p3)
            poker.join_room(p3, join_code=room.join_code)
        dealt = poker.start_room_hand(me, room.id)
        assert dealt.mode == "multi" and dealt.status == "active"
        view = poker.table_view(dealt, me)
        assert view["mode"] == "multi" and view["players_n"] >= 2
        assert view["multi_seats"]
        ok("multi room deal")
    else:
        ok("multi room create (single user)")

    # daily bonus idempotent path
    try:
        poker.claim_daily_bonus(me)
        poker.claim_daily_bonus(me)
        raise AssertionError("second bonus should fail")
    except ValueError:
        pass
    ok("daily bonus")

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
    assert "Цели дня".encode() in play
    rooms = c.get("/apps/poker/canvas?tab=rooms", secure=True).content
    assert "Создать комнату".encode() in rooms
    assert "Мест".encode() in rooms or b"max_seats" in rooms or "мест".encode() in rooms
    learn = c.get("/apps/poker/canvas?tab=learn", secure=True).content
    assert "Групповые столы".encode() in learn
    bank = c.get("/apps/poker/canvas?tab=bank", secure=True).content
    assert "Ачивки".encode() in bank
    ok("canvas multi + engagement UI")

    from django.conf import settings

    assert "channels" in settings.INSTALLED_APPS
    assert getattr(settings, "CHANNEL_LAYERS", None)
    from apps.social.poker.routing import websocket_urlpatterns

    assert websocket_urlpatterns
    ok("channels + poker websocket routes")

    from apps.social.poker import realtime as rt

    room_api = c.get(f"/apps/poker/api/room/{room.id}", secure=True)
    assert room_api.status_code == 200
    assert room_api.json().get("type") == "room"
    room_html = c.get(f"/apps/poker/canvas?tab=room&id={room.id}", secure=True).content
    assert b"poker-realtime.js" in room_html
    assert b"/ws/poker/room/" in room_html
    if dealt is not None:
        snap = rt.serialize_table(dealt, me)
        assert snap["type"] == "table" and "board_slots" in snap
        api = c.get(f"/apps/poker/api/game/{dealt.id}", secure=True)
        assert api.status_code == 200
        assert api.json().get("type") == "table"
        table_html = c.get(f"/apps/poker/canvas?tab=table&id={dealt.id}", secure=True).content
        assert b"poker-realtime.js" in table_html
        assert b"data-ws-url" in table_html
        assert b"/ws/poker/game/" in table_html
        ok("poker JSON API + LIVE canvas hooks")
    else:
        ok("poker room LIVE hooks (deal skipped: need 2+ users)")

    print("ALL poker probes passed")


if __name__ == "__main__":
    main()
