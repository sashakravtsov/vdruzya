"""Invite codes for registration / friend bootstrap — friendship re-exports."""
from __future__ import annotations

from apps.social.models import SocialProfile
from apps.social.services import now


def ensure_invite_code(me):
    if me.invite_code:
        return me.invite_code
    import secrets
    code = secrets.token_urlsafe(8)[:12]
    while SocialProfile.objects.filter(invite_code=code).exists():
        code = secrets.token_urlsafe(8)[:12]
    me.invite_code = code
    me.updated_at = now()
    me.save(update_fields=["invite_code", "updated_at"])
    return code


def invite_url(me, request=None):
    code = ensure_invite_code(me)
    if request:
        return request.build_absolute_uri(f"/i/{code}")
    return f"https://vdruzya.ru/i/{code}"


def invite_code_from_request(request):
    for src in (
        (request.POST.get("invite") if hasattr(request, "POST") else None),
        request.GET.get("invite"),
        request.COOKIES.get("vdruzya_invite"),
    ):
        code = (src or "").strip()
        if code:
            return code
    return ""


def find_inviter(code):
    code = (code or "").strip()
    return SocialProfile.objects.filter(invite_code=code).first() if code else None


def registration_requires_invite():
    return SocialProfile.objects.exists()


def apply_invite(request, me, code=None):
    if not me:
        return None
    code = (code or invite_code_from_request(request) or "").strip()
    inviter = find_inviter(code)
    if not inviter or inviter.id == me.id:
        return None
    if not me.invited_by_id:
        me.invited_by = inviter
        me.updated_at = now()
        me.save(update_fields=["invited_by", "updated_at"])
    from apps.social.friendship import send_request
    send_request(me, inviter)
    return inviter


