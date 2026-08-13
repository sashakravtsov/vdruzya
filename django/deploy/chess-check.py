#!/usr/bin/env python
"""Smoke: chess app — engine, forms, lessons, puzzles, weekly championship, canvas."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.core.management import call_command
from django.test import Client

from apps.accounts.models import User
from apps.social.chess import engine
from apps.social.chess import forms as chess_forms
from apps.social.chess import lessons
from apps.social.chess import puzzles
from apps.social.chess import service as chess
from apps.social.services import profile_of


def ok(label):
    print(f"OK   {label}")


def main():
    fen, san = engine.make_move(engine.START_FEN, "e2", "e4")
    assert san.startswith("e4"), san
    assert engine.game_status(fen) == "active"
    mat = engine.material_view(engine.START_FEN)
    assert mat["advantage"] == 0
    assert len(lessons.LESSONS) >= 20
    assert lessons.CATALOG.get("board")
    ok("engine + lessons catalog")

    for pz in puzzles.PUZZLES:
        fen2, _san = engine.make_move(pz["fen"], pz["answer"][0], pz["answer"][1])
        assert engine.game_status(fen2) == "checkmate", pz["id"]
        assert puzzles.check_answer(pz, pz["answer"][0], pz["answer"][1])
    ok(f"puzzles mate-in-1 ({len(puzzles.PUZZLES)})")

    form = chess_forms.MoveForm(data={"game_id": 1, "from_sq": "e2", "to_sq": "e4"})
    assert form.is_valid()
    bad = chess_forms.MoveForm(data={"game_id": 1, "from_sq": "xx", "to_sq": "e4"})
    assert not bad.is_valid()
    ok("django forms validation")

    champ = chess.ensure_week_championship()
    assert champ.week_key and champ.status == "open"
    call_command("ensure_chess_week")
    ok("weekly championship + management command")

    users = list(User.objects.order_by("id")[:2])
    assert len(users) >= 1
    me = profile_of(users[0])
    r = chess.get_or_create_rating(me)
    assert r.rating == 1200 or r.games >= 0
    meta = chess.learn_stats(me)
    assert meta["total"] >= 20
    strip = chess.engagement_strip(me, champ)
    assert "your_move_n" in strip
    ok("rating + learn + engagement strip")

    c = Client()
    c.force_login(users[0])
    for tab in ("play", "stats", "ratings", "champs", "learn", "puzzles"):
        resp = c.get(f"/apps/chess/canvas?tab={tab}", secure=True)
        assert resp.status_code == 200, tab
        body = resp.content
        assert "Шахматы".encode() in body
        assert b"Wordstat" not in body
        assert b"<iframe" not in body.lower()
        assert b"<details" not in body.lower()
    play = c.get("/apps/chess/canvas?tab=play", secure=True).content
    assert "Вызвать на партию".encode() in play
    assert "Ваш ход".encode() in play or "Новый вызов".encode() in play
    assert "Часы".encode() in play
    assert "24 часа на партию".encode() in play
    puzzles_html = c.get("/apps/chess/canvas?tab=puzzles", secure=True).content
    assert "Задачи".encode() in puzzles_html
    assert b"chess-board" in puzzles_html
    assert b"data-chess-live" in puzzles_html
    assert b"application/json" in puzzles_html
    assert "серия".encode() in puzzles_html.lower() or "Серия".encode() in puzzles_html
    legal = engine.legal_moves_map(engine.START_FEN, "w")
    assert "e2" in legal and "e4" in legal["e2"]
    ok("canvas tabs + pro UI helpers")
    print("ALL chess probes passed")


if __name__ == "__main__":
    main()
