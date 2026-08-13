"""Template helpers for Poker canvas — cards, chips, names."""
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from apps.social.poker import engine

register = template.Library()


@register.filter
def poker_card(card: str) -> dict:
    if isinstance(card, dict):
        return card
    return engine.card_view(card or "")


@register.filter
def poker_cards(cards) -> list:
    out = []
    for c in cards or []:
        out.append(c if isinstance(c, dict) else engine.card_view(c))
    return out


@register.filter
def poker_opp_name(game, me):
    if not game or not me:
        return ""
    if game.p1_id == me.id:
        return game.p2.name
    return game.p1.name


@register.filter(name="pk_chips")
def pk_chips(n) -> str:
    return engine.format_chips(n)


@register.simple_tag
def pk_card(card, extra="", deal_i=0):
    """Render a face-up playing card (dict from card_view or raw code)."""
    view = card if isinstance(card, dict) else engine.card_view(card or "")
    classes = ["pk-card"]
    if view.get("red"):
        classes.append("red")
    if view.get("suit_name"):
        classes.append(view["suit_name"])
    if extra:
        classes.append(extra.strip())
    rank = escape(view.get("rank") or "?")
    suit = escape(view.get("suit") or "?")
    style = f' style="--deal:{int(deal_i)}"' if deal_i else ""
    html = (
        f'<span class="{" ".join(classes)}"{style} title="{rank}{suit}">'
        f'<span class="pk-corner tl"><i>{rank}</i><u>{suit}</u></span>'
        f'<span class="pk-pip">{suit}</span>'
        f'<span class="pk-corner br"><i>{rank}</i><u>{suit}</u></span>'
        f"</span>"
    )
    return mark_safe(html)


@register.simple_tag
def pk_card_back(extra="", deal_i=0):
    classes = ["pk-card", "back"]
    if extra:
        classes.append(extra.strip())
    style = f' style="--deal:{int(deal_i)}"' if deal_i else ""
    html = (
        f'<span class="{" ".join(classes)}"{style} aria-hidden="true">'
        f'<span class="pk-back-pattern"></span></span>'
    )
    return mark_safe(html)


@register.simple_tag
def pk_chip_stack(amount, extra=""):
    layers = engine.chip_layers(amount)
    if not layers:
        return ""
    items = []
    for i, layer in enumerate(layers):
        items.append(
            f'<span class="pk-chip {escape(layer["color"])}" style="--n:{i}" '
            f'title="{escape(layer["label"])}"></span>'
        )
    cls = "pk-chip-stack"
    if extra:
        cls += " " + extra.strip()
    return mark_safe(
        f'<span class="{cls}" title="{escape(engine.format_chips(amount))}">'
        f'{"".join(items)}</span>'
    )
