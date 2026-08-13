#!/usr/bin/env python
"""Ensure OSM geo columns + Nominatim cache (Places / Events / Nearby / Safety / Market)."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db import connection

SQL = """
CREATE TABLE IF NOT EXISTS geo_cache (
  id bigserial PRIMARY KEY,
  query_key varchar(64) NOT NULL,
  query_text varchar(500) NOT NULL DEFAULT '',
  lat double precision,
  lon double precision,
  display_name varchar(500) NOT NULL DEFAULT '',
  osm_type varchar(20) NOT NULL DEFAULT '',
  osm_id bigint,
  payload text NOT NULL DEFAULT '',
  created_at timestamp without time zone,
  updated_at timestamp without time zone
);
CREATE UNIQUE INDEX IF NOT EXISTS geo_cache_query_key_uniq ON geo_cache (query_key);
CREATE INDEX IF NOT EXISTS geo_cache_updated_idx ON geo_cache (updated_at DESC);

ALTER TABLE places ADD COLUMN IF NOT EXISTS lat double precision;
ALTER TABLE places ADD COLUMN IF NOT EXISTS lon double precision;
ALTER TABLE places ADD COLUMN IF NOT EXISTS osm_type varchar(20) NOT NULL DEFAULT '';
ALTER TABLE places ADD COLUMN IF NOT EXISTS osm_id bigint;
CREATE INDEX IF NOT EXISTS places_geo_idx ON places (lat, lon) WHERE lat IS NOT NULL AND lon IS NOT NULL;

ALTER TABLE events ADD COLUMN IF NOT EXISTS lat double precision;
ALTER TABLE events ADD COLUMN IF NOT EXISTS lon double precision;
CREATE INDEX IF NOT EXISTS events_geo_idx ON events (lat, lon) WHERE lat IS NOT NULL AND lon IS NOT NULL;

ALTER TABLE marketplace_listings ADD COLUMN IF NOT EXISTS lat double precision;
ALTER TABLE marketplace_listings ADD COLUMN IF NOT EXISTS lon double precision;

ALTER TABLE safety_events ADD COLUMN IF NOT EXISTS lat double precision;
ALTER TABLE safety_events ADD COLUMN IF NOT EXISTS lon double precision;
ALTER TABLE safety_events ADD COLUMN IF NOT EXISTS radius_km double precision NOT NULL DEFAULT 50;

ALTER TABLE social_users ADD COLUMN IF NOT EXISTS lat double precision;
ALTER TABLE social_users ADD COLUMN IF NOT EXISTS lon double precision;
"""


def main():
    with connection.cursor() as cur:
        cur.execute(SQL)
        cur.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name=%s", ["geo_cache"]
        )
        assert cur.fetchone(), "geo_cache"
        for table, col in (
            ("places", "lat"), ("places", "lon"),
            ("events", "lat"), ("events", "lon"),
            ("marketplace_listings", "lat"), ("marketplace_listings", "lon"),
            ("safety_events", "lat"), ("safety_events", "radius_km"),
            ("social_users", "lat"), ("social_users", "lon"),
        ):
            cur.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name=%s AND column_name=%s",
                [table, col],
            )
            assert cur.fetchone(), f"{table}.{col}"
    print("OK   OSM geo schema")


if __name__ == "__main__":
    main()
