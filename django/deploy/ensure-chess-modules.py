#!/usr/bin/env python
"""Ensure chess app tables (ratings, games, weekly championships)."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db import connection

SQL = """
CREATE TABLE IF NOT EXISTS chess_ratings (
  social_user_id bigint PRIMARY KEY,
  rating integer NOT NULL DEFAULT 1200,
  games integer NOT NULL DEFAULT 0,
  wins integer NOT NULL DEFAULT 0,
  losses integer NOT NULL DEFAULT 0,
  draws integer NOT NULL DEFAULT 0,
  updated_at timestamp without time zone
);

CREATE TABLE IF NOT EXISTS chess_championships (
  id bigserial PRIMARY KEY,
  week_key varchar(12) NOT NULL,
  title varchar(120) NOT NULL,
  starts_on date NOT NULL,
  ends_on date NOT NULL,
  status varchar(12) NOT NULL DEFAULT 'open',
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS chess_championships_week_uniq
  ON chess_championships (week_key);

CREATE TABLE IF NOT EXISTS chess_champ_entries (
  id bigserial PRIMARY KEY,
  championship_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  points integer NOT NULL DEFAULT 0,
  wins integer NOT NULL DEFAULT 0,
  losses integer NOT NULL DEFAULT 0,
  draws integer NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS chess_champ_entries_uniq
  ON chess_champ_entries (championship_id, social_user_id);
CREATE INDEX IF NOT EXISTS chess_champ_entries_standings_idx
  ON chess_champ_entries (championship_id, points DESC);

CREATE TABLE IF NOT EXISTS chess_games (
  id bigserial PRIMARY KEY,
  white_id bigint NOT NULL,
  black_id bigint NOT NULL,
  fen varchar(100) NOT NULL,
  status varchar(16) NOT NULL DEFAULT 'active',
  result varchar(8) NOT NULL DEFAULT '*',
  turn varchar(1) NOT NULL DEFAULT 'w',
  championship_id bigint,
  winner_id bigint,
  moves_count integer NOT NULL DEFAULT 0,
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS chess_games_white_idx ON chess_games (white_id, id DESC);
CREATE INDEX IF NOT EXISTS chess_games_black_idx ON chess_games (black_id, id DESC);
CREATE INDEX IF NOT EXISTS chess_games_champ_idx ON chess_games (championship_id, id DESC);

CREATE TABLE IF NOT EXISTS chess_moves (
  id bigserial PRIMARY KEY,
  game_id bigint NOT NULL,
  ply integer NOT NULL,
  from_sq varchar(2) NOT NULL,
  to_sq varchar(2) NOT NULL,
  san varchar(16) NOT NULL,
  fen_after varchar(100) NOT NULL,
  created_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS chess_moves_game_idx ON chess_moves (game_id, ply);
"""


def main():
    with connection.cursor() as cur:
        cur.execute(SQL)
    print("OK   chess modules")


if __name__ == "__main__":
    main()
