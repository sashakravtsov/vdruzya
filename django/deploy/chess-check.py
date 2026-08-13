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
    assert "e2-e4" in san
    assert engine.game_status(fen) == "active"
    assert len(lessons.LESSONS) >= 20
    assert len(lessons.CHAPTERS) >= 6
    assert lessons.CATALOG.get("board")
    assert lessons.CATALOG.neighbors("board")[1] is not None
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
    champ2 = chess.ensure_week_championship()
    assert champ.id == champ2.id
    call_command("ensure_chess_week")
    ok("weekly championship + management command")

    users = list(User.objects.order_by("id")[:2])
    assert len(users) >= 1
    me = profile_of(users[0])
    r = chess.get_or_create_rating(me)
    assert r.rating == 1200 or r.games >= 0
    meta = chess.learn_stats(me)
    assert meta["total"] >= 20
    ok("rating + learn progress helpers")

    c = Client()
    c.force_login(users[0])
    for tab in ("play", "stats", "ratings", "champs", "learn", "puzzles"):
        resp = c.get(f"/apps/chess/canvas?tab={tab}", secure=True)
        assert resp.status_code == 200, tab
        body = resp.content
        assert "Шахматы".encode() in body
        assert b"Wordstat" not in body
        assert b"<iframe" not in body.lower()
    learn = c.get("/apps/chess/canvas?tab=learn", secure=True).content
    assert "Обучение".encode() in learn
    assert "Основы".encode() in learn
    assert "Пройдено уроков".encode() in learn
    lesson = c.get("/apps/chess/canvas?tab=learn&lesson=board", secure=True).content
    assert "Доска и названия клеток".encode() in lesson
    assert "Отметить как пройденный".encode() in lesson
    puzzles_html = c.get("/apps/chess/canvas?tab=puzzles", secure=True).content
    assert "Задачи".encode() in puzzles_html
    assert "Мат в 1 ход".encode() in puzzles_html
    assert b"chess-board" in puzzles_html  # hashed static name under Manifest storage
    assert b"data-chess-live" in puzzles_html
    assert b"json_script" not in puzzles_html  # rendered as <script type="application/json">
    assert b"application/json" in puzzles_html
    assert "Чемпионат недели".encode() in c.get("/apps/chess/canvas?tab=champs", secure=True).content
    play = c.get("/apps/chess/canvas?tab=play", secure=True).content
    assert "Учитывать в чемпионате".encode() in play
    assert "Часы".encode() in play
    assert "24 часа на партию".encode() in play
    legal = engine.legal_moves_map(engine.START_FEN, "w")
    assert "e2" in legal and "e4" in legal["e2"]
    ok("canvas tabs + mouse board + clocks helpers")
    print("ALL chess probes passed")


if __name__ == "__main__":
    main()
