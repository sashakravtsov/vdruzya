#!/usr/bin/env python
"""Ensure FB 2014 classic modules: Save + Safety Check."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db import connection

SQL = """
CREATE TABLE IF NOT EXISTS saved_items (
  id bigserial PRIMARY KEY,
  social_user_id bigint NOT NULL,
  kind varchar(20) NOT NULL DEFAULT 'post',
  post_id bigint,
  company_id bigint,
  event_id bigint,
  place_id bigint,
  url varchar(500) NOT NULL DEFAULT '',
  title varchar(255) NOT NULL DEFAULT '',
  created_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS saved_items_user_idx ON saved_items (social_user_id, id DESC);
CREATE INDEX IF NOT EXISTS saved_items_post_idx ON saved_items (post_id);
CREATE UNIQUE INDEX IF NOT EXISTS saved_items_user_post_uniq
  ON saved_items (social_user_id, post_id) WHERE post_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS saved_items_user_page_uniq
  ON saved_items (social_user_id, company_id) WHERE company_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS saved_items_user_event_uniq
  ON saved_items (social_user_id, event_id) WHERE event_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS saved_items_user_place_uniq
  ON saved_items (social_user_id, place_id) WHERE place_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS saved_items_user_url_uniq
  ON saved_items (social_user_id, url) WHERE url <> '' AND post_id IS NULL
    AND company_id IS NULL AND event_id IS NULL AND place_id IS NULL;

CREATE TABLE IF NOT EXISTS safety_events (
  id bigserial PRIMARY KEY,
  title varchar(255) NOT NULL,
  city varchar(120) NOT NULL DEFAULT '',
  body varchar(500) NOT NULL DEFAULT '',
  is_active boolean NOT NULL DEFAULT true,
  starts_at timestamp without time zone,
  ends_at timestamp without time zone,
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS safety_events_active_idx ON safety_events (is_active, id DESC);

CREATE TABLE IF NOT EXISTS safety_checkins (
  id bigserial PRIMARY KEY,
  event_id bigint NOT NULL,
  social_user_id bigint NOT NULL,
  status varchar(20) NOT NULL DEFAULT 'safe',
  marked_by_id bigint,
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS safety_checkins_uniq ON safety_checkins (event_id, social_user_id);
CREATE INDEX IF NOT EXISTS safety_checkins_user_idx ON safety_checkins (social_user_id);
CREATE INDEX IF NOT EXISTS safety_checkins_event_idx ON safety_checkins (event_id, status);
"""


def main():
    with connection.cursor() as cur:
        cur.execute(SQL)
        for t in ("saved_items", "safety_events", "safety_checkins"):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), f"missing {t}"
    print("OK   2014 modules schema")


if __name__ == "__main__":
    main()
