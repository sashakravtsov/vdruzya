#!/usr/bin/env python
"""Smoke: chess app — engine, curriculum, puzzles, engagement, canvas."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.core.management import call_command
from django.test import Client, override_settings

from apps.accounts.models import User
from apps.social.chess import engine
from apps.social.chess import forms as chess_forms
from apps.social.chess import interactives
from apps.social.chess import lessons
from apps.social.chess import puzzles
from apps.social.chess import service as chess
from apps.social.services import profile_of


def ok(label):
    print(f"OK   {label}")


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "chess-check",
        }
    }
)
def main():
    fen, san = engine.make_move(engine.START_FEN, "e2", "e4")
    assert san.startswith("e4"), san
    assert len(lessons.LESSONS) >= 28
    assert len(lessons.CHAPTERS) >= 8
    assert lessons.CATALOG.get("pawn").get("drill")
    assert lessons.CATALOG.get("board").get("quiz")
    assert lessons.CATALOG.get("fork-theme").get("drill")
    assert lessons.CATALOG.get("skewer-theme").get("quiz")
    assert len(interactives.INTERACTIVES) >= 20
    ok("engine + interactive curriculum")

    for slug, data in interactives.INTERACTIVES.items():
        d = data.get("drill")
        if not d:
            continue
        engine.make_move(d["fen"], d["answer"][0], d["answer"][1])
    ok("lesson drills legal")

    for pz in puzzles.PUZZLES:
        fen2, _san = engine.make_move(pz["fen"], pz["answer"][0], pz["answer"][1])
        if "Мат" in pz["goal"]:
            assert engine.game_status(fen2) == "checkmate", pz["id"]
        assert puzzles.check_answer(pz, pz["answer"][0], pz["answer"][1])
    assert puzzles.daily_puzzle()["id"]
    assert len(puzzles.PUZZLES) >= 24
    assert "отвлечение" in puzzles.THEMES
    assert "висячие" in puzzles.THEMES
    assert puzzles.next_unsolved(set())["id"]
    ok(f"puzzles + daily ({len(puzzles.PUZZLES)})")

    files = engine.board_files(False)
    assert files[0] == "a" and files[-1] == "h"
    assert engine.board_files(True)[0] == "h"
    rows = engine.board_rows(engine.START_FEN, flip=False)
    assert rows[0][0]["sq"] == "a8" and rows[0][0]["rank"] == "8"
    assert rows[-1][0]["sq"] == "a1" and rows[-1][0]["rank"] == "1"
    flipped = engine.board_rows(engine.START_FEN, flip=True)
    assert flipped[0][0]["sq"] == "h1" and flipped[0][0]["rank"] == "1"
    ok("board coordinates")

    form = chess_forms.MoveForm(data={"game_id": 1, "from_sq": "e2", "to_sq": "e4"})
    assert form.is_valid()
    ok("django forms validation")

    champ = chess.ensure_week_championship()
    call_command("ensure_chess_week")
    ok("weekly championship")

    users = list(User.objects.order_by("id")[:2])
    assert len(users) >= 1
    me = profile_of(users[0])
    chess.get_or_create_rating(me)
    meta = chess.learn_stats(me)
    assert meta["total"] >= 28
    assert meta["next_lesson"]
    assert meta["skill"]["level"] >= 1
    assert "daily" in meta
    assert "goals" in meta and meta["goals"]["total"] == 3
    strip = chess.engagement_strip(me, champ)
    assert "skill" in strip
    assert "goals" in strip
    assert isinstance(strip.get("badges"), list)
    pz_meta = chess.puzzle_stats(me)
    assert pz_meta["theme_progress"]
    assert chess.time_control_label(86400)
    ok("learn path + engagement + goals")

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
    assert "Продолжить обучение".encode() in play or "Вызвать на партию".encode() in play
    assert "навык".encode() in play
    assert "Сегодня".encode() in play
    learn = c.get("/apps/chess/canvas?tab=learn", secure=True).content
    assert "Система обучения".encode() in learn or "Путь".encode() in learn
    assert "Тактика".encode() in learn
    pawn = c.get("/apps/chess/canvas?tab=learn&lesson=pawn", secure=True).content
    assert "Тренажёр".encode() in pawn
    assert "Проверка".encode() in pawn
    assert b"data-chess-live" in pawn
    assert "Показать подсказку".encode() in pawn
    fork = c.get("/apps/chess/canvas?tab=learn&lesson=fork-theme", secure=True).content
    assert "Тренажёр".encode() in fork
    puzzles_html = c.get("/apps/chess/canvas?tab=puzzles", secure=True).content
    assert "Задача дня".encode() in puzzles_html
    assert "вилка".encode() in puzzles_html
    assert "отвлечение".encode() in puzzles_html
    assert "Показать подсказку".encode() in puzzles_html
    assert b"chess-board" in puzzles_html
    assert b"chess-coord" in puzzles_html
    ok("canvas pro learn/puzzles UI")
    print("ALL chess probes passed")


if __name__ == "__main__":
    main()
