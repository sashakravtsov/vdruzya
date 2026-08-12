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


def main():
    with connection.cursor() as cur:
        cur.execute(SQL)
        for t in ("friend_lists", "friend_list_members", "marketplace_listings", "photo_tags"):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), t
    print("OK   friend_lists + marketplace + photo_tags")


if __name__ == "__main__":
    main()
