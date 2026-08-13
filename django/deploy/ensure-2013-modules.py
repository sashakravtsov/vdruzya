#!/usr/bin/env python
"""Ensure FB 2013 classic modules: hashtags for Graph Search / Trending."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db import connection

SQL = """
CREATE TABLE IF NOT EXISTS hashtags (
  id bigserial PRIMARY KEY,
  name varchar(80) NOT NULL,
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS hashtags_name_uniq ON hashtags (name);

CREATE TABLE IF NOT EXISTS post_hashtags (
  id bigserial PRIMARY KEY,
  post_id bigint NOT NULL,
  hashtag_id bigint NOT NULL,
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS post_hashtags_uniq ON post_hashtags (post_id, hashtag_id);
CREATE INDEX IF NOT EXISTS post_hashtags_hashtag_idx ON post_hashtags (hashtag_id);
CREATE INDEX IF NOT EXISTS post_hashtags_post_idx ON post_hashtags (post_id);
CREATE INDEX IF NOT EXISTS post_hashtags_created_idx ON post_hashtags (created_at DESC);
"""


def main():
    with connection.cursor() as cur:
        cur.execute(SQL)
        for t in ("hashtags", "post_hashtags"):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), f"missing {t}"
    print("OK   2013 modules schema")


if __name__ == "__main__":
    main()
