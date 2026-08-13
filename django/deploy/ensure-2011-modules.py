#!/usr/bin/env python
"""Ensure FB 2011 classic modules: Subscribe, Timeline milestones, Open Graph stories."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db import connection

SQL = """
CREATE TABLE IF NOT EXISTS profile_follows (
  id bigserial PRIMARY KEY,
  follower_id bigint NOT NULL,
  followee_id bigint NOT NULL,
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS profile_follows_uniq
  ON profile_follows (follower_id, followee_id);
CREATE INDEX IF NOT EXISTS profile_follows_follower_idx ON profile_follows (follower_id);
CREATE INDEX IF NOT EXISTS profile_follows_followee_idx ON profile_follows (followee_id);

CREATE TABLE IF NOT EXISTS timeline_milestones (
  id bigserial PRIMARY KEY,
  social_user_id bigint NOT NULL,
  title varchar(255) NOT NULL,
  body varchar(500) NOT NULL DEFAULT '',
  kind varchar(40) NOT NULL DEFAULT 'life',
  occurred_on date NOT NULL,
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS timeline_milestones_user_idx ON timeline_milestones (social_user_id);
CREATE INDEX IF NOT EXISTS timeline_milestones_date_idx ON timeline_milestones (occurred_on DESC);

CREATE TABLE IF NOT EXISTS og_stories (
  id bigserial PRIMARY KEY,
  social_user_id bigint NOT NULL,
  verb varchar(32) NOT NULL,
  object_title varchar(255) NOT NULL,
  object_url varchar(255) NOT NULL DEFAULT '',
  app_slug varchar(40) NOT NULL DEFAULT 'custom',
  created_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS og_stories_user_idx ON og_stories (social_user_id);
CREATE INDEX IF NOT EXISTS og_stories_created_idx ON og_stories (created_at DESC);
CREATE INDEX IF NOT EXISTS og_stories_verb_idx ON og_stories (verb);

ALTER TABLE social_users ADD COLUMN IF NOT EXISTS cover_path varchar(255);

ALTER TABLE messages ADD COLUMN IF NOT EXISTS reply_to_id bigint;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS sticker_id bigint;
CREATE INDEX IF NOT EXISTS messages_reply_to_idx ON messages (reply_to_id);
CREATE INDEX IF NOT EXISTS messages_sticker_idx ON messages (sticker_id);
"""


def main():
    with connection.cursor() as cur:
        cur.execute(SQL)
        for t in ("profile_follows", "timeline_milestones", "og_stories"):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), f"missing {t}"
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='social_users' AND column_name='cover_path'"
        )
        assert cur.fetchone(), "missing social_users.cover_path"
        for col in ("reply_to_id", "sticker_id"):
            cur.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name='messages' AND column_name=%s", [col]
            )
            assert cur.fetchone(), f"missing messages.{col}"
    print("OK   2011 modules schema")


if __name__ == "__main__":
    main()
