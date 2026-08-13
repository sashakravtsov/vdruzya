#!/usr/bin/env python
"""Ensure dating (Знакомства) tables."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db import connection

SQL = """
CREATE TABLE IF NOT EXISTS dating_profiles (
  social_user_id bigint PRIMARY KEY,
  headline varchar(120) NOT NULL DEFAULT '',
  about text NOT NULL DEFAULT '',
  intent varchar(24) NOT NULL DEFAULT 'dating',
  prompts_json text NOT NULL DEFAULT '[]',
  age_min integer NOT NULL DEFAULT 18,
  age_max integer NOT NULL DEFAULT 99,
  gender_pref varchar(12) NOT NULL DEFAULT 'any',
  discoverable boolean NOT NULL DEFAULT true,
  superlikes_left integer NOT NULL DEFAULT 3,
  superlikes_on date,
  views_today integer NOT NULL DEFAULT 0,
  likes_today integer NOT NULL DEFAULT 0,
  daily_on date,
  streak integer NOT NULL DEFAULT 0,
  best_streak integer NOT NULL DEFAULT 0,
  last_active_on date,
  matches_n integer NOT NULL DEFAULT 0,
  likes_sent integer NOT NULL DEFAULT 0,
  likes_got integer NOT NULL DEFAULT 0,
  spark_points integer NOT NULL DEFAULT 0,
  achievements text NOT NULL DEFAULT '',
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS dating_profiles_spark_idx
  ON dating_profiles (discoverable, spark_points DESC);

CREATE TABLE IF NOT EXISTS dating_swipes (
  id bigserial PRIMARY KEY,
  from_id bigint NOT NULL,
  to_id bigint NOT NULL,
  action varchar(12) NOT NULL,
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS dating_swipes_uniq ON dating_swipes (from_id, to_id);
CREATE INDEX IF NOT EXISTS dating_swipes_to_idx ON dating_swipes (to_id, action, id DESC);
CREATE INDEX IF NOT EXISTS dating_swipes_from_idx ON dating_swipes (from_id, id DESC);

CREATE TABLE IF NOT EXISTS dating_matches (
  id bigserial PRIMARY KEY,
  user_a_id bigint NOT NULL,
  user_b_id bigint NOT NULL,
  opener varchar(200) NOT NULL DEFAULT '',
  seen_a boolean NOT NULL DEFAULT false,
  seen_b boolean NOT NULL DEFAULT false,
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS dating_matches_uniq ON dating_matches (user_a_id, user_b_id);
CREATE INDEX IF NOT EXISTS dating_matches_a_idx ON dating_matches (user_a_id, id DESC);
CREATE INDEX IF NOT EXISTS dating_matches_b_idx ON dating_matches (user_b_id, id DESC);

CREATE TABLE IF NOT EXISTS dating_visits (
  id bigserial PRIMARY KEY,
  viewer_id bigint NOT NULL,
  viewed_id bigint NOT NULL,
  created_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS dating_visits_viewed_idx ON dating_visits (viewed_id, id DESC);
CREATE INDEX IF NOT EXISTS dating_visits_viewer_idx ON dating_visits (viewer_id, id DESC);
"""


def main():
    with connection.cursor() as cur:
        cur.execute(SQL)
    print("OK   dating modules")


if __name__ == "__main__":
    main()
