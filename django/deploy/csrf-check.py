#!/usr/bin/env python3
"""Ensure CSRF trusted origins are wired (prod HTTPS Origin checks)."""
from __future__ import annotations

import os
import sys

import django

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()


def main() -> int:
    from django.conf import settings

    origins = list(getattr(settings, "CSRF_TRUSTED_ORIGINS", []) or [])
    assert origins, "CSRF_TRUSTED_ORIGINS is empty"
    assert any(o.startswith("https://") for o in origins), origins
    print("OK   CSRF_TRUSTED_ORIGINS", origins)

    live = open(os.path.join(ROOT, "static/js/live-client.js"), encoding="utf-8").read()
    assert "csrfFieldHtml" in live and "ensureCsrf" in live
    farm = open(os.path.join(ROOT, "static/js/farm-live.js"), encoding="utf-8").read()
    assert "csrfHtml" in farm or "csrfFieldHtml" in farm
    print("OK   LIVE forms inject CSRF")
    print("ALL csrf probes passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
