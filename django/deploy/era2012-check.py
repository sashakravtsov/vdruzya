#!/usr/bin/env python
"""Smoke: FB 2012 classic modules (Page Timeline / Collections / App Center)."""
import os
import sys
import uuid
from datetime import date

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.accounts.models import User
from apps.social import era2012 as e12
from apps.social.models import (
    Collection, CollectionItem, Company, CompanyAdmin, PageTimelineMilestone,
)
from apps.social.services import bump_news, news_items, now, profile_of

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def ok(label):
    print(f"OK   {label}")


def main():
    from django.db import connection
    with connection.cursor() as cur:
        for t in ("page_timeline_milestones", "collections", "collection_items"):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), f"missing {t}"
        for table, col in (("companies", "cover_path"), ("collections", "cover_path")):
            cur.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name=%s AND column_name=%s",
                [table, col],
            )
            assert cur.fetchone(), f"missing {table}.{col}"
    ok("schema 2012")

    u = User.objects.filter(email="alexandr@vdruzya.ru").first() or User.objects.first()
    assert u
    me = profile_of(u)
    c = Client(HTTP_HOST="vdruzya.ru")
    c.force_login(u)

    r = c.get("/apps", secure=True)
    assert r.status_code == 200
    assert "Приложения".encode() in r.content
    assert "Приложения".encode() in r.content
    assert "Избранные".encode() in r.content
    assert b"page-tabs" not in r.content
    assert b"display: flex" not in r.content.lower()
    ok("app center catalog")

    r = c.get("/apps/collections", secure=True)
    assert r.status_code == 200
    assert "Коллекции".encode() in r.content
    ok("app detail")

    r = c.get("/collections", secure=True)
    assert r.status_code == 200
    assert "Коллекции".encode() in r.content
    assert "Обложка".encode() in r.content
    title = f"QA Col {uuid.uuid4().hex[:6]}"
    r = c.post("/collections", {
        "title": title, "description": "probe", "visibility": "public",
        "cover": SimpleUploadedFile("col.png", PNG, content_type="image/png"),
    }, secure=True)
    assert r.status_code in (301, 302)
    col = Collection.objects.filter(social_user=me, title=title).first()
    assert col
    assert col.cover_path and col.cover_path.startswith("collections/"), col.cover_path
    r = c.get("/collections", secure=True)
    assert r.status_code == 200 and b"list-thumb" in r.content
    r = c.post(f"/collections/{col.id}/items", {
        "kind": "link", "url": "https://example.com/qa", "title": "QA Link",
    }, secure=True)
    assert r.status_code in (301, 302)
    assert CollectionItem.objects.filter(collection=col, kind="link").exists()
    # Video post item title must use snippet_text (never storage:)
    from apps.social.models import Post
    t = now()
    vpost = Post.objects.create(
        social_user=me, kind="video", topic="video",
        body="storage:videos/qa-col.mp4\n\nколлекция клип",
        media_label="Col Clip", visibility="friends",
        created_at=t, updated_at=t,
    )
    item = e12.add_item(me, col, kind="post", post_id=vpost.id)
    assert item and "storage:" not in (item.title or "")
    assert "коллекция" in (item.title or "") or "Col Clip" in (item.title or "")
    r = c.get(f"/collections/{col.id}", secure=True)
    assert r.status_code == 200 and b"storage:" not in r.content
    assert b"<img" in r.content and col.cover_url.encode() in r.content
    r = c.post(f"/collections/{col.id}/cover/clear", {}, secure=True)
    assert r.status_code in (301, 302)
    col.refresh_from_db()
    assert not col.cover_path
    vpost.delete()
    bump_news()
    feed = news_items(me, limit=80)
    assert any(i.get("kind") == "collection" and i.get("collection") and i["collection"].id == col.id for i in feed)
    ok("collections + cover + feed")

    page = Company.objects.filter(admins__social_user=me).order_by("id").first()
    if not page:
        t = now()
        page = Company.objects.create(
            name=f"QA Page {uuid.uuid4().hex[:5]}",
            slug=f"qa-page-{uuid.uuid4().hex[:8]}",
            industry="other", city="", size="", cover_color="#3B5998",
            description="", created_at=t, updated_at=t,
        )
        CompanyAdmin.objects.create(company=page, social_user=me, role="admin", created_at=t, updated_at=t)
        created_page = True
    else:
        created_page = False

    r = c.post(f"/pages/{page.id}/milestones", {
        "title": f"QA Page MS {uuid.uuid4().hex[:5]}",
        "occurred_on": f"{date.today().year}-03-01",
        "kind": "founded",
        "body": "probe",
    }, secure=True)
    assert r.status_code in (301, 302)
    ms = PageTimelineMilestone.objects.filter(company=page, title__startswith="QA Page MS").order_by("-id").first()
    assert ms
    r = c.get(f"/pages/{page.id}?tab=timeline&y={ms.occurred_on.year}", secure=True)
    assert r.status_code == 200
    assert "Лента".encode() in r.content
    assert ms.title.encode() in r.content
    assert b"page-tabs" not in r.content
    # fan so page milestones appear in feed
    from apps.social.models import CompanyFollower
    CompanyFollower.objects.get_or_create(
        company=page, social_user=me, defaults={"created_at": now(), "updated_at": now()},
    )
    bump_news()
    feed = news_items(me, limit=80)
    assert any(
        i.get("kind") == "page_milestone" and i.get("milestone") and i["milestone"].id == ms.id
        for i in feed
    ), "page milestone missing from feed"
    ok("page timeline + feed")

    # cleanup
    CollectionItem.objects.filter(collection=col).delete()
    Collection.objects.filter(pk=col.id).delete()
    PageTimelineMilestone.objects.filter(pk=ms.id).delete()
    if created_page:
        CompanyAdmin.objects.filter(company=page).delete()
        CompanyFollower.objects.filter(company=page).delete()
        page.delete()
    ok("cleanup")
    print("ALL 2012 classic modules probes passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL", e)
        raise
