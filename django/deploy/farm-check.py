#!/usr/bin/env python
"""Smoke: Ферма — plant/harvest, economy, bankruptcy, canvas."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from datetime import timedelta

from django.test import Client, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.social.farm import catalog
from apps.social.farm import lessons
from apps.social.farm import service as farm
from apps.social.farm.models import FarmPlot
from apps.social.services import profile_of


def ok(label):
    print(f"OK   {label}")


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "farm-check",
        }
    }
)
def main():
    assert catalog.STARTING_CHIPS == 1_000_000
    assert catalog.BANKRUPT_HOURS == 24
    assert catalog.crop_by_slug("wheat")
    assert len(lessons.LESSONS) >= 6
    assert lessons.lesson_by_slug("bankruptcy")
    ok("catalog + curriculum")

    users = list(User.objects.order_by("id")[:2])
    assert users
    me = profile_of(users[0])
    p = farm.get_or_create_profile(me)
    assert p.chips >= 1000
    plots = farm.plots_view(me)
    assert len(plots) >= catalog.START_PLOTS
    # isolate a plot for the probe
    FarmPlot.objects.filter(owner=me).update(
        state="empty", crop_slug="", watered=False, fertilized=False,
        stolen=False, planted_at=None, ready_at=None, wither_at=None, helper_id=None,
    )
    plots = farm.plots_view(me)
    empty = next(x for x in plots if x["state"] == "empty")
    pl = farm.plant(me, empty["id"], "wheat")
    pl = FarmPlot.objects.get(pk=pl.id)
    assert pl.state == "growing", pl.state
    # keep firmly in growing window for water
    pl.ready_at = timezone.now().replace(tzinfo=None) + timedelta(minutes=5)
    pl.wither_at = pl.ready_at + timedelta(hours=6)
    pl.watered = False
    pl.save(update_fields=["ready_at", "wither_at", "watered", "state"])
    farm.water_plot(me, pl.id)
    pl = FarmPlot.objects.get(pk=pl.id)
    assert pl.watered
    pl.ready_at = timezone.now().replace(tzinfo=None) - timedelta(seconds=1)
    pl.state = "growing"
    pl.save(update_fields=["ready_at", "state"])
    res = farm.harvest(me, pl.id)
    assert res["amount"] > 0
    ok("plant water harvest")

    # bankruptcy path
    p = farm.get_or_create_profile(me)
    FarmPlot.objects.filter(owner=me).update(state="empty", crop_slug="")
    from apps.social.farm.models import FarmAnimal

    FarmAnimal.objects.filter(owner=me).delete()
    p.chips = 100
    p.bankrupt_until = None
    p.save(update_fields=["chips", "bankrupt_until"])
    farm.engagement_strip(me)
    p.refresh_from_db()
    assert farm.is_bankrupt(p)
    p.bankrupt_until = timezone.now().replace(tzinfo=None) - timedelta(minutes=1)
    p.save(update_fields=["bankrupt_until"])
    farm.reset_after_bankruptcy(me)
    p.refresh_from_db()
    assert p.chips == catalog.STARTING_CHIPS
    ok("bankruptcy + reset")

    c = Client()
    c.force_login(users[0])
    for tab in ("field", "barn", "shop", "neighbors", "learn", "bank"):
        resp = c.get(f"/apps/farm/canvas?tab={tab}", secure=True)
        assert resp.status_code == 200, tab
        body = resp.content
        assert "Ферма".encode() in body
        assert b"farm-app" in body
        assert b"<iframe" not in body.lower()
        assert b"<details" not in body.lower()
    field = c.get("/apps/farm/canvas?tab=field", secure=True).content
    assert "Цели дня".encode() in field or "гряд".encode() in field
    learn = c.get("/apps/farm/canvas?tab=learn", secure=True).content
    assert "Банкротство".encode() in learn or "Агрошкола".encode() in learn or "школ".encode() in learn.lower()
    ok("canvas tabs")
    print("ALL farm probes passed")


if __name__ == "__main__":
    main()
