#!/usr/bin/env python
"""Seed classic Inbox/Gifts stickers with Twemoji PNGs (CC-BY 4.0).

Downloads 72×72 faces into media storage and upserts sticker_packs/stickers.
Attribution: Twemoji by Twitter / jdecked — https://github.com/jdecked/twemoji
"""
from __future__ import annotations

import os
import sys
import urllib.request

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction

from apps.social.models import Sticker, StickerPack
from apps.social.services import now

# slug, title, phrase, twemoji codepoint (lowercase hex)
STICKERS = [
    ("vd-hello", "Улыбка", "Привет!", "1f600"),
    ("vd-thanks", "Спасибо", "Спасибо!", "1f64f"),
    ("vd-support", "Сердце", "Рядом", "2764"),
    ("vd-fire", "Огонь", "Сильно!", "1f525"),
    ("vd-ok", "Ок", "Ок", "1f44d"),
    ("vd-party", "Праздник", "Ура!", "1f389"),
    ("vd-thinking", "Думаю", "Думаю…", "1f914"),
    ("vd-work", "Сильный", "В деле", "1f4aa"),
    ("tw-grin", "Смех", "Ха-ха", "1f602"),
    ("tw-wink", "Подмигивание", ";)", "1f609"),
    ("tw-love", "Влюблён", "Люблю", "1f60d"),
    ("tw-kiss", "Чмок", "Чмок", "1f618"),
    ("tw-cool", "Круто", "Круто", "1f60e"),
    ("tw-tongue", "Дразнилка", ":P", "1f61b"),
    ("tw-wow", "Вау", "Вау!", "1f62e"),
    ("tw-blush", "Смущение", "Ой", "1f633"),
    ("tw-sad", "Грусть", "Эх", "1f622"),
    ("tw-cry", "Плач", ":(", "1f62d"),
    ("tw-angry", "Злость", "Грр", "1f621"),
    ("tw-think2", "Хм", "Хм…", "1f9d0"),
    ("tw-party-face", "Веселье", "Йо!", "1f973"),
    ("tw-hug", "Обнимашки", "Обнимаю", "1f917"),
    ("tw-clap", "Аплодисменты", "Браво", "1f44f"),
    ("tw-down", "Минус", "Не то", "1f44e"),
    ("tw-hearts", "Сердечки", "❤❤", "1f495"),
    ("tw-broken", "Разбитое", "Ой", "1f494"),
    ("tw-star", "Звезда", "Супер", "2b50"),
    ("tw-gift", "Подарок", "Тебе", "1f381"),
    ("tw-cake", "Торт", "С днём!", "1f382"),
    ("tw-coffee", "Кофе", "Перерыв", "2615"),
    ("tw-sleep", "Сон", "Спокойной", "1f634"),
    ("tw-poop", "Шутка", "Хе-хе", "1f4a9"),
]

CDN = "https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/72x72/{cp}.png"
PACK_SLUG = "vdruzya-start"
PACK_TITLE = "Классика (Twemoji)"


def _fetch(cp: str) -> bytes:
    url = CDN.format(cp=cp)
    req = urllib.request.Request(url, headers={"User-Agent": "vdruzya-sticker-seed/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    if len(data) < 64 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"bad png for {cp}")
    return data


def main():
    t = now()
    pack, _ = StickerPack.objects.get_or_create(
        slug=PACK_SLUG,
        defaults={
            "title": PACK_TITLE,
            "description": "Twemoji CC-BY 4.0 — классические жёлтые смайлы",
            "is_system": True,
            "is_active": True,
            "created_at": t,
            "updated_at": t,
        },
    )
    if pack.title != PACK_TITLE or not pack.is_active:
        pack.title = PACK_TITLE
        pack.description = "Twemoji CC-BY 4.0 — классические жёлтые смайлы"
        pack.is_active = True
        pack.updated_at = t
        pack.save(update_fields=["title", "description", "is_active", "updated_at"])

    n_ok = 0
    with transaction.atomic():
        for i, (slug, title, phrase, cp) in enumerate(STICKERS, start=1):
            raw = _fetch(cp)
            path = f"stickers/{slug}.png"
            if default_storage.exists(path):
                try:
                    default_storage.delete(path)
                except Exception:
                    pass
            saved = default_storage.save(path, ContentFile(raw))
            row, created = Sticker.objects.get_or_create(
                slug=slug,
                defaults={
                    "sticker_pack": pack,
                    "title": title,
                    "phrase": phrase,
                    "image_path": saved,
                    "background_color": "#FFFFFF",
                    "foreground_color": "#333333",
                    "sort_order": i * 10,
                    "is_active": True,
                    "created_at": t,
                    "updated_at": t,
                },
            )
            if not created:
                row.sticker_pack = pack
                row.title = title
                row.phrase = phrase
                row.image_path = saved
                row.background_color = "#FFFFFF"
                row.foreground_color = "#333333"
                row.sort_order = i * 10
                row.is_active = True
                row.updated_at = t
                row.save(update_fields=[
                    "sticker_pack", "title", "phrase", "image_path",
                    "background_color", "foreground_color", "sort_order",
                    "is_active", "updated_at",
                ])
            n_ok += 1

    active = Sticker.objects.filter(sticker_pack=pack, is_active=True, image_path__isnull=False).count()
    assert active >= 24, active
    print(f"OK   twemoji stickers seeded: {n_ok} (active with images: {active})")
    print("NOTE  Twemoji graphics © Twitter / jdecked — CC-BY 4.0")


if __name__ == "__main__":
    main()
