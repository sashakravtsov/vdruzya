#!/usr/bin/env python
"""Ensure FB 2009–2010 classic modules: likes index, places, questions."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db import connection

SQL = """
CREATE TABLE IF NOT EXISTS reactions (
  id bigserial PRIMARY KEY,
  post_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  type varchar(255) NOT NULL DEFAULT 'like',
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS reactions_post_user_type_uniq
  ON reactions (post_id, social_user_id, type);
CREATE INDEX IF NOT EXISTS reactions_post_idx ON reactions (post_id);

CREATE TABLE IF NOT EXISTS places (
  id bigserial PRIMARY KEY,
  name varchar(160) NOT NULL,
  city varchar(120) NOT NULL DEFAULT '',
  address varchar(255) NOT NULL DEFAULT '',
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS places_name_idx ON places (name);

CREATE TABLE IF NOT EXISTS place_checkins (
  id bigserial PRIMARY KEY,
  place_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  message varchar(500) NOT NULL DEFAULT '',
  created_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS place_checkins_place_idx ON place_checkins (place_id);
CREATE INDEX IF NOT EXISTS place_checkins_user_idx ON place_checkins (social_user_id);
CREATE INDEX IF NOT EXISTS place_checkins_created_idx ON place_checkins (created_at DESC);

CREATE TABLE IF NOT EXISTS questions (
  id bigserial PRIMARY KEY,
  social_user_id bigint NOT NULL,
  body varchar(500) NOT NULL,
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS questions_user_idx ON questions (social_user_id);
CREATE INDEX IF NOT EXISTS questions_created_idx ON questions (created_at DESC);

CREATE TABLE IF NOT EXISTS question_answers (
  id bigserial PRIMARY KEY,
  question_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  body varchar(500) NOT NULL,
  created_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS question_answers_q_idx ON question_answers (question_id);

CREATE TABLE IF NOT EXISTS question_votes (
  id bigserial PRIMARY KEY,
  answer_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS question_votes_uniq
  ON question_votes (answer_id, social_user_id);
CREATE INDEX IF NOT EXISTS question_votes_answer_idx ON question_votes (answer_id);
"""


def main():
    with connection.cursor() as cur:
        cur.execute(SQL)
        for t in (
            "reactions", "places", "place_checkins",
            "questions", "question_answers", "question_votes",
        ):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), t
    print("OK   likes + places + questions schema")


if __name__ == "__main__":
    main()
