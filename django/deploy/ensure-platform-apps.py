#!/usr/bin/env python
"""Ensure first-party Platform app tables (installs / Causes / Truth)."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db import connection

SQL = """
CREATE TABLE IF NOT EXISTS app_installs (
  id bigserial PRIMARY KEY,
  social_user_id bigint NOT NULL,
  app_slug varchar(40) NOT NULL,
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS app_installs_user_slug_uniq
  ON app_installs (social_user_id, app_slug);
CREATE INDEX IF NOT EXISTS app_installs_user_idx ON app_installs (social_user_id, id DESC);

CREATE TABLE IF NOT EXISTS app_cause_joins (
  id bigserial PRIMARY KEY,
  social_user_id bigint NOT NULL,
  cause_slug varchar(40) NOT NULL,
  created_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS app_cause_joins_uniq
  ON app_cause_joins (social_user_id, cause_slug);
CREATE INDEX IF NOT EXISTS app_cause_joins_cause_idx ON app_cause_joins (cause_slug);

CREATE TABLE IF NOT EXISTS app_truth_asks (
  id bigserial PRIMARY KEY,
  from_user_id bigint NOT NULL,
  to_user_id bigint NOT NULL,
  question varchar(300) NOT NULL,
  answer varchar(500) NOT NULL DEFAULT '',
  created_at timestamp without time zone,
  answered_at timestamp without time zone
);
CREATE INDEX IF NOT EXISTS app_truth_asks_to_idx ON app_truth_asks (to_user_id, id DESC);
CREATE INDEX IF NOT EXISTS app_truth_asks_from_idx ON app_truth_asks (from_user_id, id DESC);
"""


def main():
    with connection.cursor() as cur:
        cur.execute(SQL)
        for t in ("app_installs", "app_cause_joins", "app_truth_asks"):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), t
    print("OK   platform apps schema")


if __name__ == "__main__":
    main()
