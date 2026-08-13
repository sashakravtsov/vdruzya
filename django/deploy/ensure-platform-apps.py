#!/usr/bin/env python
"""Ensure first-party Platform app tables (installs / Causes / Truth / OAuth)."""
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

CREATE TABLE IF NOT EXISTS dev_apps (
  id bigserial PRIMARY KEY,
  owner_id bigint NOT NULL,
  slug varchar(40) NOT NULL,
  name varchar(80) NOT NULL,
  category varchar(20) NOT NULL DEFAULT 'utilities',
  blurb varchar(200) NOT NULL DEFAULT '',
  detail varchar(500) NOT NULL DEFAULT '',
  website_url varchar(255) NOT NULL DEFAULT '',
  published boolean NOT NULL DEFAULT false,
  featured boolean NOT NULL DEFAULT false,
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
-- Upgrade columns before indexes that reference them
ALTER TABLE dev_apps ADD COLUMN IF NOT EXISTS callback_url varchar(255) NOT NULL DEFAULT '';
ALTER TABLE dev_apps ADD COLUMN IF NOT EXISTS api_key varchar(48) NOT NULL DEFAULT '';
ALTER TABLE dev_apps ADD COLUMN IF NOT EXISTS api_secret varchar(64) NOT NULL DEFAULT '';
CREATE UNIQUE INDEX IF NOT EXISTS dev_apps_slug_uniq ON dev_apps (slug);
CREATE INDEX IF NOT EXISTS dev_apps_owner_idx ON dev_apps (owner_id, id DESC);
CREATE UNIQUE INDEX IF NOT EXISTS dev_apps_api_key_uniq ON dev_apps (api_key)
  WHERE api_key <> '';

CREATE TABLE IF NOT EXISTS app_oauth_codes (
  id bigserial PRIMARY KEY,
  app_slug varchar(40) NOT NULL,
  social_user_id bigint NOT NULL,
  code varchar(64) NOT NULL,
  redirect_uri varchar(255) NOT NULL DEFAULT '',
  created_at timestamp without time zone,
  used_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS app_oauth_codes_code_uniq ON app_oauth_codes (code);
CREATE INDEX IF NOT EXISTS app_oauth_codes_app_idx ON app_oauth_codes (app_slug, id DESC);

CREATE TABLE IF NOT EXISTS app_access_tokens (
  id bigserial PRIMARY KEY,
  app_slug varchar(40) NOT NULL,
  social_user_id bigint NOT NULL,
  token varchar(80) NOT NULL,
  created_at timestamp without time zone,
  expires_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS app_access_tokens_token_uniq ON app_access_tokens (token);
CREATE INDEX IF NOT EXISTS app_access_tokens_app_user_idx
  ON app_access_tokens (app_slug, social_user_id);
"""


def main():
    with connection.cursor() as cur:
        cur.execute(SQL)
        for t in (
            "app_installs", "app_cause_joins", "app_truth_asks", "dev_apps",
            "app_oauth_codes", "app_access_tokens",
        ):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), t
        # Backfill credentials for existing apps
        from apps.social.models import DevApp
        from apps.social import platform_oauth as oauth
        for app in DevApp.objects.all()[:200]:
            oauth.ensure_app_credentials(app)
    print("OK   platform apps schema")


if __name__ == "__main__":
    main()
