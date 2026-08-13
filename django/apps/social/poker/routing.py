"""WebSocket URL routes for poker realtime."""
from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"^ws/poker/game/(?P<game_id>\d+)/$", consumers.PokerGameConsumer.as_asgi()),
    re_path(r"^ws/poker/room/(?P<room_id>\d+)/$", consumers.PokerRoomConsumer.as_asgi()),
]
