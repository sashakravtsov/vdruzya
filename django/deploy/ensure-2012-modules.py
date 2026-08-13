#!/usr/bin/env python
"""Ensure FB 2012 classic modules: Page Timeline, Collections."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db import connection

SQL = """
ALTER TABLE companies ADD COLUMN IF NOT EXISTS cover_path varchar(255);

CREATE TABLE IF NOT EXISTS page_timeline_milestones (
  id bigserial PRIMARY KEY,
  company_id bigint NOT NULL,
  title varchar(255) NOT NULL,
  body varchar(500) NOT NULL DEFAULT '',
  kind varchar(40) NOT NULL DEFAULT 'life',
  occurred_on date NOT NULL,
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS page_timeline_milestones_company_idx
  ON page_timeline_milestones (company_id);
CREATE INDEX IF NOT EXISTS page_timeline_milestones_date_idx
  ON page_timeline_milestones (occurred_on DESC);

CREATE TABLE IF NOT EXISTS collections (
  id bigserial PRIMARY KEY,
  social_user_id bigint NOT NULL,
  title varchar(160) NOT NULL,
  description varchar(500) NOT NULL DEFAULT '',
  visibility varchar(20) NOT NULL DEFAULT 'friends',
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS collections_user_idx ON collections (social_user_id);

CREATE TABLE IF NOT EXISTS collection_items (
  id bigserial PRIMARY KEY,
  collection_id bigint NOT NULL,
  kind varchar(20) NOT NULL,
  post_id bigint,
  company_id bigint,
  url varchar(500) NOT NULL DEFAULT '',
  title varchar(255) NOT NULL DEFAULT '',
  position integer NOT NULL DEFAULT 0,
  created_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS collection_items_collection_idx ON collection_items (collection_id);
CREATE INDEX IF NOT EXISTS collection_items_post_idx ON collection_items (post_id);
CREATE INDEX IF NOT EXISTS collection_items_company_idx ON collection_items (company_id);
"""


def main():
    with connection.cursor() as cur:
        cur.execute(SQL)
        for t in ("page_timeline_milestones", "collections", "collection_items"):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), f"missing {t}"
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='companies' AND column_name='cover_path'"
        )
        assert cur.fetchone(), "missing companies.cover_path"
    print("OK   2012 modules schema")


if __name__ == "__main__":
    main()
