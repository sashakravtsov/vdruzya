#!/usr/bin/env python
"""Smoke: calculator suite (50 Wordstat tools) + compact snav."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client

from apps.accounts.models import User
from apps.social.calculators import TOOLS, run_tool, tools_by_topic
from apps.social.services import profile_of


def ok(label):
    print(f"OK   {label}")


def main():
    assert len(TOOLS) == 50, len(TOOLS)
    assert len(tools_by_topic()) >= 5
    # formula spot-checks
    r = run_tool("vat", {"amount": "1200", "rate": "20", "mode": "extract"})
    assert r["ok"] and "200,00" in r["lines"][0]
    r = run_tool("vacation", {"earnings_12m": "600000", "days": "14", "months_worked": "12"})
    assert r["ok"] and "23 890,78" in r["lines"][1]
    r = run_tool("triangle", {"a": "3", "b": "4", "c": "5"})
    assert r["ok"] and r["lines"][0].startswith("Площадь: 6")
    r = run_tool("ndfl", {"income": "3000000"})
    assert r["ok"] and "402 000,00" in r["lines"][0]
    for t in TOOLS:
        # every tool must reject empty critical input without crashing
        out = run_tool(t["slug"], {})
        assert "ok" in out
    ok("50 tools + formula spot-checks")

    user = User.objects.filter(is_superuser=True).first() or User.objects.order_by("id").first()
    assert user
    me = profile_of(user)
    c = Client()
    c.force_login(user)
    r = c.get("/apps/calculator", secure=True)
    assert r.status_code == 200
    body = r.content
    assert "Калькуляторы".encode() in body or "калькулятор".encode() in body.lower()
    assert b"vacation" in body or "Отпускные".encode() in body
    assert b"<iframe" not in body.lower()
    r = c.post("/apps/calculator?tool=vat", {
        "tool": "vat", "amount": "1200", "rate": "20", "mode": "extract",
    }, secure=True)
    assert r.status_code == 200 and "200,00".encode() in r.content
    ok("canvas index + VAT post")

    r = c.get("/feed", secure=True)
    assert r.status_code == 200
    assert b"snav-more" in r.content
    assert "Ещё разделы".encode() in r.content
    # primary still visible
    assert "Мои друзья".encode() in r.content
    assert "Входящие".encode() in r.content
    ok("compact snav with Ещё разделы")
    print("ALL calc-suite probes passed")


if __name__ == "__main__":
    main()
