#!/usr/bin/env python
"""Ensure farm (Ферма) tables."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db import connection

SQL = """
CREATE TABLE IF NOT EXISTS farm_profiles (
  social_user_id bigint PRIMARY KEY,
  chips bigint NOT NULL DEFAULT 1000000,
  xp integer NOT NULL DEFAULT 0,
  plots_unlocked integer NOT NULL DEFAULT 6,
  harvests integer NOT NULL DEFAULT 0,
  plants integer NOT NULL DEFAULT 0,
  helps integer NOT NULL DEFAULT 0,
  steals integer NOT NULL DEFAULT 0,
  water_cans integer NOT NULL DEFAULT 5,
  fertilizer integer NOT NULL DEFAULT 1,
  boosts integer NOT NULL DEFAULT 0,
  play_streak integer NOT NULL DEFAULT 0,
  best_streak integer NOT NULL DEFAULT 0,
  last_play_on date,
  daily_bonus_on date,
  bankrupt_until timestamp without time zone,
  reset_count integer NOT NULL DEFAULT 0,
  achievements text NOT NULL DEFAULT '',
  lesson_slugs text NOT NULL DEFAULT '',
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);

CREATE TABLE IF NOT EXISTS farm_plots (
  id bigserial PRIMARY KEY,
  owner_id bigint NOT NULL,
  idx integer NOT NULL DEFAULT 0,
  crop_slug varchar(24) NOT NULL DEFAULT '',
  state varchar(12) NOT NULL DEFAULT 'empty',
  planted_at timestamp without time zone,
  watered boolean NOT NULL DEFAULT false,
  fertilized boolean NOT NULL DEFAULT false,
  ready_at timestamp without time zone,
  wither_at timestamp without time zone,
  stolen boolean NOT NULL DEFAULT false,
  helper_id bigint
);
CREATE UNIQUE INDEX IF NOT EXISTS farm_plots_owner_idx_uniq ON farm_plots (owner_id, idx);
CREATE INDEX IF NOT EXISTS farm_plots_owner_state_idx ON farm_plots (owner_id, state);

CREATE TABLE IF NOT EXISTS farm_animals (
  id bigserial PRIMARY KEY,
  owner_id bigint NOT NULL,
  kind varchar(24) NOT NULL,
  fed_at timestamp without time zone,
  ready_at timestamp without time zone,
  created_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS farm_animals_owner_idx ON farm_animals (owner_id, id);

CREATE TABLE IF NOT EXISTS farm_visit_logs (
  id bigserial PRIMARY KEY,
  actor_id bigint NOT NULL,
  owner_id bigint NOT NULL,
  plot_id bigint,
  kind varchar(12) NOT NULL,
  amount integer NOT NULL DEFAULT 0,
  created_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS farm_visit_logs_owner_idx ON farm_visit_logs (owner_id, id DESC);
CREATE INDEX IF NOT EXISTS farm_visit_logs_actor_idx ON farm_visit_logs (actor_id, id DESC);

-- Prefer timestamptz for plot/animal timers under USE_TZ.
DO $$ BEGIN
  ALTER TABLE farm_plots
    ALTER COLUMN planted_at TYPE timestamp with time zone USING planted_at AT TIME ZONE 'UTC',
    ALTER COLUMN ready_at TYPE timestamp with time zone USING ready_at AT TIME ZONE 'UTC',
    ALTER COLUMN wither_at TYPE timestamp with time zone USING wither_at AT TIME ZONE 'UTC';
EXCEPTION WHEN others THEN NULL;
END $$;
DO $$ BEGIN
  ALTER TABLE farm_animals
    ALTER COLUMN fed_at TYPE timestamp with time zone USING fed_at AT TIME ZONE 'UTC',
    ALTER COLUMN ready_at TYPE timestamp with time zone USING ready_at AT TIME ZONE 'UTC',
    ALTER COLUMN created_at TYPE timestamp with time zone USING created_at AT TIME ZONE 'UTC';
EXCEPTION WHEN others THEN NULL;
END $$;
DO $$ BEGIN
  ALTER TABLE farm_profiles
    ALTER COLUMN bankrupt_until TYPE timestamp with time zone USING bankrupt_until AT TIME ZONE 'UTC',
    ALTER COLUMN created_at TYPE timestamp with time zone USING created_at AT TIME ZONE 'UTC',
    ALTER COLUMN updated_at TYPE timestamp with time zone USING updated_at AT TIME ZONE 'UTC';
EXCEPTION WHEN others THEN NULL;
END $$;
"""


def main():
    with connection.cursor() as cur:
        cur.execute(SQL)
    print("OK   farm modules")


if __name__ == "__main__":
    main()
