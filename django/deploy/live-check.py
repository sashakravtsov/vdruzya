#!/usr/bin/env python3
"""Probe first-party LIVE WebSocket wiring (farm/dating/chess + shared client)."""
from __future__ import annotations

import os
import sys

import django

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()


def ok(msg: str) -> None:
    print(f"OK   {msg}")


def main() -> int:
    from django.conf import settings
    from apps.social.live.routing import websocket_urlpatterns

    assert "channels" in settings.INSTALLED_APPS
    assert getattr(settings, "CHANNEL_LAYERS", None)
    paths = " ".join(str(p.pattern) for p in websocket_urlpatterns)
    assert "ws/farm" in paths
    assert "ws/dating" in paths
    assert "ws/chess" in paths
    assert "ws/poker" in paths
    ok("live websocket_urlpatterns")

    from apps.social.live import consumers, serializers, broadcast

    assert hasattr(consumers, "FarmLiveConsumer")
    assert hasattr(consumers, "DatingLiveConsumer")
    assert hasattr(consumers, "ChessLiveConsumer")
    assert callable(broadcast.notify_farm)
    assert callable(serializers.farm_state)
    assert callable(serializers.dating_state)
    assert callable(serializers.chess_state)
    ok("live package imports")

    for rel in (
        "static/js/live-client.js",
        "static/js/farm-live.js",
        "static/js/dating-live.js",
        "static/js/chess-board.js",
        "static/js/poker-realtime.js",
    ):
        path = os.path.join(ROOT, rel)
        assert os.path.isfile(path), rel
        data = open(path, encoding="utf-8").read()
        if "chess-board" in rel:
            assert "location.reload" not in data
        if "farm-field" not in rel and "farm-live" in rel:
            assert "VdLive" in data
        if "live-client" in rel:
            assert "WebSocket" in data
    ok("live JS clients present (no chess reload)")

    farm_field = open(os.path.join(ROOT, "static/js/farm-field.js"), encoding="utf-8").read()
    assert "location.reload" not in farm_field
    ok("farm-field.js has no reload")

    for tmpl, needle in (
        ("templates/social/apps/canvas_farm.html", 'data-ws-url="/ws/farm/"'),
        ("templates/social/apps/canvas_dating.html", 'data-ws-url="/ws/dating/"'),
        ("templates/social/apps/canvas_chess.html", "/ws/chess/game/"),
        ("templates/social/apps/canvas_poker.html", "/ws/poker/"),
    ):
        html = open(os.path.join(ROOT, tmpl), encoding="utf-8").read()
        assert needle in html, tmpl
        assert "live-client.js" in html or "poker-realtime.js" in html
    ok("canvas LIVE hooks")

    asgi = open(os.path.join(ROOT, "config/asgi.py"), encoding="utf-8").read()
    assert "apps.social.live.routing" in asgi
    ok("ASGI uses live.routing")

    print("ALL live probes passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
