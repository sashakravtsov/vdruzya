"""Template helpers for the Chess canvas."""
from django import template

from apps.social.chess import engine

register = template.Library()


@register.filter
def chess_result_label(result: str) -> str:
    return {
        "1-0": "победа белых",
        "0-1": "победа чёрных",
        "1/2-1/2": "ничья",
        "*": "идёт",
    }.get(result or "*", result or "")


@register.filter
def chess_glyph(piece: str) -> str:
    return engine.PIECE_UNI.get(piece or "", "")


@register.simple_tag
def chess_board(fen: str, flip: bool = False):
    return engine.board_rows(fen, flip=bool(flip))


@register.filter
def lesson_done(slug: str, done_slugs) -> bool:
    try:
        return slug in done_slugs
    except TypeError:
        return False
