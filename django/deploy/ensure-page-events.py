#!/usr/bin/env python
"""Ensure events.company_id exists for Page Events (unmanaged schema)."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db import connection


SQL = """
ALTER TABLE events
  ADD COLUMN IF NOT EXISTS company_id bigint NULL;
ALTER TABLE events
  ADD COLUMN IF NOT EXISTS cover_path varchar(255) NULL;
"""

# Soft FK index (no hard REFERENCES — companies may be cleaned independently)
INDEX = """
CREATE INDEX IF NOT EXISTS events_company_id_idx ON events (company_id);
"""

# Classic gift tiles: seed colors when stickers have none
COLORS = """
UPDATE stickers SET background_color = v.bg, foreground_color = v.fg
FROM (VALUES
  ('vd-hello', '#3B5998', '#FFFFFF'),
  ('vd-thanks', '#6D84B4', '#FFFFFF'),
  ('vd-support', '#23487E', '#FFFFFF'),
  ('vd-fire', '#C45A11', '#FFFFFF'),
  ('vd-ok', '#3B5998', '#FFFFFF'),
  ('vd-party', '#8A2E6B', '#FFFFFF'),
  ('vd-thinking', '#5C6B7A', '#FFFFFF'),
  ('vd-work', '#2F5233', '#FFFFFF')
) AS v(slug, bg, fg)
WHERE stickers.slug = v.slug
  AND (stickers.background_color IS NULL OR stickers.background_color = '');
"""


def main():
    with connection.cursor() as cur:
        cur.execute(SQL)
        cur.execute(INDEX)
        cur.execute(COLORS)
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='events' AND column_name='company_id'"
        )
        assert cur.fetchone(), "company_id missing"
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='events' AND column_name='cover_path'"
        )
        assert cur.fetchone(), "cover_path missing"
    print("OK   events.company_id + cover_path + gift sticker colors")


if __name__ == "__main__":
    main()
