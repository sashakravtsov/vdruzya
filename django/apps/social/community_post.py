"""CommunityPost topic/body helpers — model properties stay thin."""
from __future__ import annotations


def pack_topic(subject: str, body: str) -> str:
    """Store discussion as subject\\n\\nbody (no separate title column)."""
    subject = (subject or "").strip()[:120]
    body = (body or "").strip()
    if subject:
        return f"{subject}\n\n{body}" if body else subject
    return body


def subject_of(post) -> str:
    """Discussion topic subject; empty on wall posts."""
    if (post.topic or "") == "wall":
        return ""
    body = post.body or ""
    if "\n\n" in body:
        return body.split("\n\n", 1)[0].strip()[:120]
    return body.split("\n", 1)[0].strip()[:120]


def body_text_of(post) -> str:
    """Message body without subject (discussion) or full wall body.

    Wall video posts pack storage:<path>\\n\\nblurb — never surface the path.
    """
    body = post.body or ""
    if (post.topic or "") == "wall":
        if (post.kind or "") == "video" or body.startswith("storage:"):
            from apps.social.classic_extra import unpack_link_body
            _url, blurb = unpack_link_body(body)
            return (blurb or "").strip()
        return body
    if "\n\n" in body:
        return body.split("\n\n", 1)[1]
    parts = body.split("\n", 1)
    return parts[1] if len(parts) > 1 else ""


def title_line_of(post) -> str:
    if (post.kind or "") == "video":
        return "Видео"
    line = subject_of(post) or (post.body or "").strip().split("\n", 1)[0].strip()
    if line.startswith("storage:"):
        return "Видео"
    if not line:
        return "Фото" if post.kind == "photo" or post.media_path else "Тема"
    return line[:80] + ("…" if len(line) > 80 else "")


def absolute_url(post) -> str:
    base = f"/groups/{post.community_id}"
    if post.topic == "wall":
        return f"{base}?tab=wall#topic-{post.id}"
    return f"{base}?tab=discussion&topic={post.id}"
