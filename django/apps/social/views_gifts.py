"""Gifts FBVs — classic Facebook Gifts on stickers catalog."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.social import gifts as gf
from apps.social.forms import GiftSendForm
from apps.social.models import SocialProfile
from apps.social.services import profile_of


@login_required
@require_http_methods(["GET", "HEAD"])
def gifts_home(request):
    me = profile_of(request.user)
    tab = request.GET.get("tab") or "shop"
    if tab not in ("shop", "received", "sent"):
        tab = "shop"
    received = sent = []
    if tab == "received" and me:
        received = gf.attach_stickers(gf.gifts_for(me, limit=40))
        gf.mark_gift_notices_seen(me)
    elif tab == "sent" and me:
        from apps.social.models import Post
        sent = gf.attach_stickers(list(
            Post.objects.filter(social_user=me, kind="gift").order_by("-id")[:40]
        ))
        for p in sent:
            rid = gf.recipient_id_from_topic(p.topic)
            p.gift_to_id = rid
        ids = {p.gift_to_id for p in sent if p.gift_to_id}
        by_id = SocialProfile.objects.in_bulk(ids) if ids else {}
        for p in sent:
            p.gift_to = by_id.get(p.gift_to_id)
    return render(request, "social/gifts.html", {
        "me": me, "tab": tab, "catalog": gf.catalog() if tab == "shop" else [],
        "received": received, "sent": sent, "nav": "gifts",
    })


@login_required
@require_http_methods(["GET", "POST"])
def gift_send(request):
    me = profile_of(request.user)
    initial = {}
    to_id = request.GET.get("to") or request.POST.get("to")
    gift = request.GET.get("gift") or request.POST.get("gift")
    if to_id:
        initial["to"] = to_id
    if gift:
        initial["gift"] = gift
    form = GiftSendForm(request.POST or None, initial=None if request.method == "POST" else initial)
    form.fields["to"].queryset = SocialProfile.objects.filter(
        id__in=[f.id for f in gf.friends_for_send(me, 80)]
    ).order_by("name")
    if request.method == "POST":
        if form.is_valid():
            other = form.cleaned_data["to"]
            sticker = gf.get_sticker(form.cleaned_data["gift"])
            status = gf.can_send(me, other)
            if status != "ok":
                messages.error(request, {
                    "self": "Нельзя отправить подарок себе.",
                    "blocked": "Пользователь недоступен.",
                    "not_friend": "Подарки только друзьям.",
                }.get(status, "Не удалось отправить."))
            else:
                post = gf.send_gift(me, other, sticker, form.cleaned_data.get("message") or "")
                if post:
                    messages.success(request, f"Подарок «{sticker.title}» отправлен.")
                    return redirect(other)
                messages.error(request, "Не удалось отправить подарок.")
        else:
            messages.error(request, "Выберите друга и подарок.")
    sticker_preview = None
    if gift:
        try:
            sticker_preview = gf.get_sticker(gift)
        except Exception:
            sticker_preview = None
    return render(request, "social/gift_send.html", {
        "me": me, "form": form, "catalog": gf.catalog(),
        "sticker_preview": sticker_preview, "nav": "gifts",
    })


@login_required
@require_POST
def gift_send_quick(request, pk):
    """Send from profile action (gift + optional message)."""
    me = profile_of(request.user)
    other = get_object_or_404(SocialProfile, pk=pk)
    sticker = gf.get_sticker(request.POST.get("gift") or "")
    status = gf.can_send(me, other)
    if status != "ok":
        messages.error(request, "Подарки только друзьям.")
        return redirect(request.POST.get("next") or other)
    post = gf.send_gift(me, other, sticker, request.POST.get("message") or "")
    if post:
        messages.success(request, f"Подарок «{sticker.title}» отправлен.")
    else:
        messages.error(request, "Не удалось отправить.")
    return redirect(request.POST.get("next") or other)
