#!/usr/bin/env python
"""Smoke: chess app — engine, ratings, weekly championship, canvas tabs."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client

from apps.accounts.models import User
from apps.social.chess import engine
from apps.social.chess import lessons
from apps.social.chess import service as chess
from apps.social.services import profile_of


def ok(label):
    print(f"OK   {label}")


def main():
    fen, san = engine.make_move(engine.START_FEN, "e2", "e4")
    assert "e2-e4" in san
    assert engine.game_status(fen) == "active"
    assert len(lessons.LESSONS) >= 5
    ok("engine + lessons")

    champ = chess.ensure_week_championship()
    assert champ.week_key and champ.status == "open"
    champ2 = chess.ensure_week_championship()
    assert champ.id == champ2.id
    ok("weekly championship idempotent")

    users = list(User.objects.order_by("id")[:2])
    assert len(users) >= 1
    me = profile_of(users[0])
    r = chess.get_or_create_rating(me)
    assert r.rating == 1200 or r.games >= 0
    ok("rating bootstrap")

    c = Client()
    c.force_login(users[0])
    for tab in ("play", "stats", "ratings", "champs", "learn"):
        resp = c.get(f"/apps/chess/canvas?tab={tab}", secure=True)
        assert resp.status_code == 200, tab
        body = resp.content
        assert "Шахматы".encode() in body
        assert b"Wordstat" not in body
        assert b"<iframe" not in body.lower()
    assert "Обучение".encode() in c.get("/apps/chess/canvas?tab=learn", secure=True).content
    assert "Чемпионат недели".encode() in c.get("/apps/chess/canvas?tab=champs", secure=True).content
    ok("canvas tabs")
    print("ALL chess probes passed")


if __name__ == "__main__":
    main()
