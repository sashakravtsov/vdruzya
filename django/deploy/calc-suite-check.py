#!/usr/bin/env python
"""Smoke: calculator suite (50 Wordstat tools) + compact snav."""
import os
import sys
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client

from apps.accounts.models import User
from apps.social.calculators import TOOLS, run_tool, tools_by_topic, popular_tools
from apps.social.calculators import law
from apps.social.services import profile_of


def ok(label):
    print(f"OK   {label}")


def main():
    assert len(TOOLS) == 50, len(TOOLS)
    assert len(tools_by_topic()) >= 5
    assert len(popular_tools()) >= 5
    assert law.VAT_RATE_STANDARD == Decimal("22")
    assert law.CONTRIB_BASE_LIMIT_2026 == Decimal("2979000")

    # VAT 2026: extract 22% from 1220 → 220
    r = run_tool("vat", {"amount": "1220", "rate": "22", "mode": "extract"})
    assert r["ok"] and "220,00" in r["primary"], r
    # legacy 20% still available
    r = run_tool("vat", {"amount": "1200", "rate": "20", "mode": "extract"})
    assert r["ok"] and "200,00" in r["primary"]
    # add 22%
    r = run_tool("vat", {"amount": "1000", "rate": "22", "mode": "add"})
    assert r["ok"] and "220,00" in r["primary"] and "1 220,00" in "".join(r["lines"])

    r = run_tool("vacation", {"earnings_12m": "600000", "days": "14", "months_worked": "12"})
    assert r["ok"] and "23 890,78" in r["primary"]

    r = run_tool("triangle", {"a": "3", "b": "4", "c": "5"})
    assert r["ok"] and r["lines"][0].startswith("Площадь: 6")

    # NDFL: 3_000_000 → 312_000 + 600_000*0.15 = 402_000
    r = run_tool("ndfl", {"income": "3000000"})
    assert r["ok"] and "402 000,00" in r["primary"], r

    # Contributions 2026: 3_000_000 → 2_979_000*0.30 + 21_000*0.151 = 896_871
    r = run_tool("contributions", {"payroll": "3000000", "mode": "general", "injury": "0"})
    assert r["ok"] and "896 871,00" in r["primary"], r

    for t in TOOLS:
        out = run_tool(t["slug"], {})
        assert "ok" in out
    ok("50 tools + formula spot-checks (VAT 22%, NDFL, взносы 2026)")

    user = User.objects.order_by("id").first()
    assert user, "need at least one user"
    profile_of(user)
    c = Client()
    c.force_login(user)
    r = c.get("/apps/calculator/canvas", secure=True)
    assert r.status_code == 200
    body = r.content
    assert "Калькуляторы".encode() in body or "калькулятор".encode() in body.lower()
    assert b"vacation" in body or "Отпускные".encode() in body
    assert b"calc-suite" in body
    assert "Часто ищут".encode() in body
    assert b"<iframe" not in body.lower()
    assert "22%".encode() in body or "НДС".encode() in body

    r = c.post("/apps/calculator/canvas?tool=vat", {
        "tool": "vat", "amount": "1220", "rate": "22", "mode": "extract",
    }, secure=True)
    assert r.status_code == 200 and "220,00".encode() in r.content
    assert "425-ФЗ".encode() in r.content or "22%".encode() in r.content

    r = c.get("/apps/calculator/canvas?q=ндс", secure=True)
    assert r.status_code == 200 and "НДС".encode() in r.content
    ok("canvas index + VAT 22% post + search")

    r = c.get("/feed", secure=True)
    assert r.status_code == 200
    assert b"snav-more" in r.content
    assert "Ещё разделы".encode() in r.content
    assert "Мои друзья".encode() in r.content
    assert "Входящие".encode() in r.content
    ok("compact snav with Ещё разделы")
    print("ALL calc-suite probes passed")


if __name__ == "__main__":
    main()
