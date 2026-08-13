#!/usr/bin/env python
"""Ensure poker app tables (profiles, rooms, championships, games, learning)."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db import connection

SQL = """
CREATE TABLE IF NOT EXISTS poker_profiles (
  social_user_id bigint PRIMARY KEY,
  chips bigint NOT NULL DEFAULT 1000000,
  games integer NOT NULL DEFAULT 0,
  wins integer NOT NULL DEFAULT 0,
  losses integer NOT NULL DEFAULT 0,
  ties integer NOT NULL DEFAULT 0,
  biggest_pot bigint NOT NULL DEFAULT 0,
  puzzle_solved integer NOT NULL DEFAULT 0,
  puzzle_streak integer NOT NULL DEFAULT 0,
  best_puzzle_streak integer NOT NULL DEFAULT 0,
  last_puzzle_on date,
  learn_xp integer NOT NULL DEFAULT 0,
  bankrupt_until timestamp with time zone,
  reset_count integer NOT NULL DEFAULT 0,
  rating integer NOT NULL DEFAULT 1200,
  rated_games integer NOT NULL DEFAULT 0,
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
ALTER TABLE poker_profiles ADD COLUMN IF NOT EXISTS rating integer NOT NULL DEFAULT 1200;
ALTER TABLE poker_profiles ADD COLUMN IF NOT EXISTS rated_games integer NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS poker_championships (
  id bigserial PRIMARY KEY,
  week_key varchar(12) NOT NULL,
  title varchar(120) NOT NULL,
  starts_on date NOT NULL,
  ends_on date NOT NULL,
  status varchar(12) NOT NULL DEFAULT 'open',
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS poker_championships_week_uniq
  ON poker_championships (week_key);

CREATE TABLE IF NOT EXISTS poker_champ_entries (
  id bigserial PRIMARY KEY,
  championship_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  points integer NOT NULL DEFAULT 0,
  wins integer NOT NULL DEFAULT 0,
  losses integer NOT NULL DEFAULT 0,
  ties integer NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS poker_champ_entries_uniq
  ON poker_champ_entries (championship_id, social_user_id);
CREATE INDEX IF NOT EXISTS poker_champ_entries_standings_idx
  ON poker_champ_entries (championship_id, points DESC);

CREATE TABLE IF NOT EXISTS poker_rooms (
  id bigserial PRIMARY KEY,
  title varchar(80) NOT NULL,
  owner_id bigint NOT NULL,
  stake_key varchar(16) NOT NULL DEFAULT 'micro',
  is_private boolean NOT NULL DEFAULT false,
  join_code varchar(12) NOT NULL DEFAULT '',
  p1_id bigint,
  p2_id bigint,
  status varchar(16) NOT NULL DEFAULT 'open',
  current_game_id bigint,
  in_champ boolean NOT NULL DEFAULT true,
  hands_played integer NOT NULL DEFAULT 0,
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS poker_rooms_status_idx ON poker_rooms (status, updated_at DESC);
CREATE INDEX IF NOT EXISTS poker_rooms_code_idx ON poker_rooms (join_code) WHERE join_code <> '';

CREATE TABLE IF NOT EXISTS poker_games (
  id bigserial PRIMARY KEY,
  p1_id bigint NOT NULL,
  p2_id bigint NOT NULL,
  invited_by_id bigint,
  status varchar(16) NOT NULL DEFAULT 'pending',
  result varchar(12) NOT NULL DEFAULT '*',
  winner_id bigint,
  small_blind integer NOT NULL DEFAULT 500,
  big_blind integer NOT NULL DEFAULT 1000,
  buy_in integer NOT NULL DEFAULT 20000,
  button smallint NOT NULL DEFAULT 1,
  to_act smallint NOT NULL DEFAULT 1,
  street varchar(12) NOT NULL DEFAULT 'preflop',
  pot bigint NOT NULL DEFAULT 0,
  p1_stack bigint NOT NULL DEFAULT 0,
  p2_stack bigint NOT NULL DEFAULT 0,
  p1_bet bigint NOT NULL DEFAULT 0,
  p2_bet bigint NOT NULL DEFAULT 0,
  p1_hole varchar(16) NOT NULL DEFAULT '',
  p2_hole varchar(16) NOT NULL DEFAULT '',
  board varchar(40) NOT NULL DEFAULT '',
  deck text NOT NULL DEFAULT '',
  last_action varchar(120) NOT NULL DEFAULT '',
  hand_label varchar(120) NOT NULL DEFAULT '',
  room_id bigint,
  championship_id bigint,
  is_rated boolean NOT NULL DEFAULT true,
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
ALTER TABLE poker_games ADD COLUMN IF NOT EXISTS room_id bigint;
ALTER TABLE poker_games ADD COLUMN IF NOT EXISTS championship_id bigint;
ALTER TABLE poker_games ADD COLUMN IF NOT EXISTS is_rated boolean NOT NULL DEFAULT true;
CREATE INDEX IF NOT EXISTS poker_games_p1_idx ON poker_games (p1_id, id DESC);
CREATE INDEX IF NOT EXISTS poker_games_p2_idx ON poker_games (p2_id, id DESC);
CREATE INDEX IF NOT EXISTS poker_games_status_idx ON poker_games (status, updated_at DESC);
CREATE INDEX IF NOT EXISTS poker_games_room_idx ON poker_games (room_id, id DESC);
CREATE INDEX IF NOT EXISTS poker_games_champ_idx ON poker_games (championship_id, id DESC);

CREATE TABLE IF NOT EXISTS poker_actions (
  id bigserial PRIMARY KEY,
  game_id bigint NOT NULL,
  ply integer NOT NULL,
  actor_id bigint NOT NULL,
  action varchar(16) NOT NULL,
  amount bigint NOT NULL DEFAULT 0,
  street varchar(12) NOT NULL DEFAULT '',
  pot_after bigint NOT NULL DEFAULT 0,
  created_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS poker_actions_game_idx ON poker_actions (game_id, ply);

CREATE TABLE IF NOT EXISTS poker_lesson_progress (
  id bigserial PRIMARY KEY,
  social_user_id bigint NOT NULL,
  lesson_slug varchar(40) NOT NULL,
  quiz_ok boolean NOT NULL DEFAULT false,
  completed_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS poker_lesson_progress_uniq
  ON poker_lesson_progress (social_user_id, lesson_slug);

CREATE TABLE IF NOT EXISTS poker_puzzle_progress (
  id bigserial PRIMARY KEY,
  social_user_id bigint NOT NULL,
  puzzle_id varchar(40) NOT NULL,
  attempts integer NOT NULL DEFAULT 0,
  solved_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS poker_puzzle_progress_uniq
  ON poker_puzzle_progress (social_user_id, puzzle_id);
"""


def main():
    with connection.cursor() as cur:
        cur.execute(SQL)
    print("OK   poker modules")


if __name__ == "__main__":
    main()
