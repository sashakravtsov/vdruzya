"""Safe Markdown for classic Inbox — Django render + bleach sanitize."""
from __future__ import annotations

import re

import bleach
import markdown as md
from django.utils.html import escape
from django.utils.safestring import mark_safe

ALLOWED_TAGS = frozenset({
    "p", "br", "strong", "em", "del", "code", "pre",
    "a", "ul", "ol", "li", "blockquote", "h3", "h4", "hr",
})
ALLOWED_ATTRS = {
    "a": ["href", "title", "rel", "target"],
}
ALLOWED_PROTOCOLS = ("http", "https", "mailto")

_STRIKE = re.compile(r"~~(.+?)~~", re.S)
_MD = md.Markdown(
    extensions=["nl2br", "sane_lists", "fenced_code"],
    output_format="html",
)


def _force_safe_links(attrs, new=False):
    href = attrs.get((None, "href")) or attrs.get("href") or ""
    href = str(href).strip()
    if not href.lower().startswith(("http://", "https://", "mailto:")):
        return None
    attrs[(None, "rel")] = "nofollow noopener noreferrer"
    attrs[(None, "target")] = "_blank"
    return attrs


def render_message_md(text: str, *, max_len: int = 4000) -> str:
    """Return sanitized HTML for a message body (empty → '')."""
    raw = (text or "").strip()
    if not raw:
        return ""
    raw = raw[:max_len]
    # Lightweight GFM-ish strike without extra extensions
    raw = _STRIKE.sub(r"<del>\1</del>", raw)
    try:
        _MD.reset()
        html = _MD.convert(raw)
    except Exception:
        return f"<p>{escape(raw)}</p>"
    cleaned = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    try:
        cleaned = bleach.linkify(
            cleaned,
            callbacks=[_force_safe_links],
            skip_tags=["pre", "code"],
            parse_email=False,
        )
    except Exception:
        pass
    return cleaned


def render_message_md_safe(text: str):
    """mark_safe wrapper for templates / JSON preview."""
    html = render_message_md(text)
    return mark_safe(html) if html else ""
