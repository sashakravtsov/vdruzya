#!/usr/bin/env python
"""Ensure classic 2006–09 module tables (friend lists + marketplace + photo tags)."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db import connection

SQL = """
CREATE TABLE IF NOT EXISTS friend_lists (
  id bigserial PRIMARY KEY,
  social_user_id bigint NOT NULL,
  name varchar(120) NOT NULL,
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS friend_lists_user_idx ON friend_lists (social_user_id);

CREATE TABLE IF NOT EXISTS friend_list_members (
  id bigserial PRIMARY KEY,
  friend_list_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS friend_list_members_uniq
  ON friend_list_members (friend_list_id, social_user_id);
CREATE INDEX IF NOT EXISTS friend_list_members_user_idx ON friend_list_members (social_user_id);

CREATE TABLE IF NOT EXISTS marketplace_listings (
  id bigserial PRIMARY KEY,
  social_user_id bigint NOT NULL,
  title varchar(160) NOT NULL,
  price varchar(40) NOT NULL DEFAULT '',
  place varchar(120) NOT NULL DEFAULT '',
  description text NOT NULL DEFAULT '',
  photo_path varchar(255) NULL,
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS marketplace_listings_user_idx ON marketplace_listings (social_user_id);
CREATE INDEX IF NOT EXISTS marketplace_listings_created_idx ON marketplace_listings (created_at DESC);

CREATE TABLE IF NOT EXISTS photo_tags (
  id bigserial PRIMARY KEY,
  photo_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  tagged_by_id bigint NULL,
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS photo_tags_photo_user_uniq
  ON photo_tags (photo_id, social_user_id);
CREATE INDEX IF NOT EXISTS photo_tags_user_idx ON photo_tags (social_user_id);
CREATE INDEX IF NOT EXISTS photo_tags_photo_idx ON photo_tags (photo_id);
"""


ALTER = """
ALTER TABLE photo_tags ADD COLUMN IF NOT EXISTS status varchar(20) NOT NULL DEFAULT 'approved';
UPDATE photo_tags SET status = 'approved' WHERE status IS NULL OR status = '';
CREATE INDEX IF NOT EXISTS photo_tags_pending_idx ON photo_tags (social_user_id, status);
ALTER TABLE marketplace_listings ADD COLUMN IF NOT EXISTS photo_path varchar(255) NULL;
ALTER TABLE conversation_members ADD COLUMN IF NOT EXISTS muted_at timestamp without time zone NULL;
"""


def main():
    with connection.cursor() as cur:
        cur.execute(SQL)
        cur.execute(ALTER)
        for t in ("friend_lists", "friend_list_members", "marketplace_listings", "photo_tags"):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), t
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='photo_tags' AND column_name='status'"
        )
        assert cur.fetchone(), "photo_tags.status"
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='marketplace_listings' AND column_name='photo_path'"
        )
        assert cur.fetchone(), "marketplace_listings.photo_path"
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='conversation_members' AND column_name='muted_at'"
        )
        assert cur.fetchone(), "conversation_members.muted_at"
    print("OK   friend_lists + marketplace + photo_tags + inbox mute")


if __name__ == "__main__":
    main()
