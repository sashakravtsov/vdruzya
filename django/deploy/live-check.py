#!/usr/bin/env python3
"""Probe first-party LIVE WebSocket wiring (farm/dating/chess + shared client)."""
from __future__ import annotations

import asyncio
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
    from django.contrib.auth import get_user_model
    from django.urls import re_path
    from channels.routing import URLRouter
    from channels.testing import WebsocketCommunicator

    from apps.social.live.routing import websocket_urlpatterns
    from apps.social.live.consumers import FarmLiveConsumer, DatingLiveConsumer
    from apps.social.services import profile_of

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
        "static/js/user-live.js",
        "static/js/chess-board.js",
        "static/js/poker-realtime.js",
        "static/js/poker-table.js",
    ):
        path = os.path.join(ROOT, rel)
        assert os.path.isfile(path), rel
        data = open(path, encoding="utf-8").read()
        assert "location.reload" not in data, rel
        if "live-client" in rel:
            assert "WebSocket" in data
    ok("live JS clients present (no reload)")

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

    User = get_user_model()
    user = User.objects.order_by("id").first()
    assert user is not None
    me = profile_of(user)
    assert me is not None

    async def _ws_farm():
        app = URLRouter([re_path(r"^ws/farm/$", FarmLiveConsumer.as_asgi())])
        c = WebsocketCommunicator(app, "/ws/farm/")
        c.scope["user"] = user
        connected, _ = await c.connect()
        assert connected
        hello = await c.receive_json_from(timeout=5)
        state = await c.receive_json_from(timeout=5)
        assert hello.get("type") == "hello"
        assert state.get("type") == "state"
        assert state.get("payload", {}).get("ok")
        await c.send_json_to({"action": "ping"})
        pong = await c.receive_json_from(timeout=5)
        assert pong.get("type") == "pong"
        await c.send_json_to({"action": "refresh"})
        refreshed = await c.receive_json_from(timeout=5)
        assert refreshed.get("type") == "state"
        plots = (state.get("payload") or {}).get("plots") or []
        empty = next((p for p in plots if p.get("state") == "empty"), None)
        if empty:
            await c.send_json_to({"action": "plant", "plot_id": empty["id"], "crop": "wheat"})
            result = await c.receive_json_from(timeout=5)
            assert result.get("type") == "action_result"
            # may fail if bankrupt / locked crop — still must not crash socket
            if result.get("payload", {}).get("ok"):
                follow = await c.receive_json_from(timeout=5)
                assert follow.get("type") == "state"
        await c.disconnect()

    async def _ws_dating():
        app = URLRouter([re_path(r"^ws/dating/$", DatingLiveConsumer.as_asgi())])
        c = WebsocketCommunicator(app, "/ws/dating/")
        c.scope["user"] = user
        connected, _ = await c.connect()
        assert connected
        await c.receive_json_from(timeout=5)  # hello
        state = await c.receive_json_from(timeout=5)
        assert state.get("type") == "state"
        await c.send_json_to({"action": "ping"})
        assert (await c.receive_json_from(timeout=5)).get("type") == "pong"
        await c.disconnect()

    asyncio.run(_ws_farm())
    ok("farm consumer hello/state/ping")
    asyncio.run(_ws_dating())
    ok("dating consumer hello/state/ping")

    print("ALL live probes passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
