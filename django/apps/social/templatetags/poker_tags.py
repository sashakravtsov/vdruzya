"""Template helpers for Poker canvas."""
from django import template

from apps.social.poker import engine

register = template.Library()


@register.filter
def poker_card(card: str) -> dict:
    return engine.card_view(card or "")


@register.filter
def poker_cards(cards) -> list:
    return [engine.card_view(c) for c in (cards or [])]


@register.filter
def poker_opp_name(game, me):
    if not game or not me:
        return ""
    if game.p1_id == me.id:
        return game.p2.name
    return game.p1.name
