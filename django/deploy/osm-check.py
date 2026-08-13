#!/usr/bin/env python
"""Smoke: OSM geo schema + haversine + places geocode path (cached Nominatim)."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db import connection

from apps.social import osm


def ok(msg):
    print(f"OK   {msg}")


def main():
    with connection.cursor() as cur:
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name='geo_cache'")
        assert cur.fetchone(), "geo_cache missing"
        for table, col in (("places", "lat"), ("events", "lon"), ("social_users", "lat")):
            cur.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name=%s AND column_name=%s",
                [table, col],
            )
            assert cur.fetchone(), f"{table}.{col}"
    ok("geo schema")

    d = osm.haversine_km(55.75, 37.62, 59.93, 30.33)
    assert 600 < d < 800, d
    ok("haversine")

    # Cache write/read without requiring live Nominatim
    key = osm._query_key("geocode", "osm-smoke-moscow")
    hit = osm.GeoHit(55.75, 37.62, display_name="Москва", osm_type="relation", osm_id=1)
    osm._cache_put(key, "osm-smoke-moscow", hit)
    got = osm._cache_get(key)
    assert got and abs(got.lat - 55.75) < 0.01 and abs(got.lon - 37.62) < 0.01
    ok("geo_cache roundtrip")

    ctx = osm.map_context(55.75, 37.62, zoom=12, title="Тест")
    assert ctx and "markers_json" in ctx and "openstreetmap.org" in ctx["osm_link"]
    ok("map_context")

    print("ALL OSM probes passed")


if __name__ == "__main__":
    main()
