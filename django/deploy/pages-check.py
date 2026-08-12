#!/usr/bin/env python
"""Smoke probe: Pages + Apps catalog."""
import os
import sys
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client

from apps.accounts.models import User
from apps.social.models import Company, CompanyAdmin, CompanyFollower, Post
from apps.social.services import news_items, profile_of, wall_posts_for


def ok(label):
    print(f"OK   {label}")


def main():
    u = User.objects.filter(email="alexandr@vdruzya.ru").first() or User.objects.first()
    assert u, "no user"
    me = profile_of(u)
    c = Client(HTTP_HOST="vdruzya.ru")
    c.force_login(u)

    r = c.get("/apps", secure=True)
    assert r.status_code == 200 and "Приложения".encode() in r.content
    assert "Страницы".encode() in r.content and "Фото".encode() in r.content
    assert "Подарки".encode() in r.content
    ok("apps catalog")

    r = c.get("/pages", secure=True)
    assert r.status_code == 200 and "Страницы".encode() in r.content
    assert b'id="tabs"' in r.content
    assert b' required' not in r.content and b'required="' not in r.content
    ok("pages directory")

    name = f"QA Page {uuid.uuid4().hex[:6]}"
    r = c.post("/pages", {
        "name": name,
        "industry": "brand",
        "city": "Москва",
        "description": "Тестовая страница QA",
    }, secure=True)
    assert r.status_code in (301, 302)
    page = Company.objects.filter(name=name).first()
    assert page and CompanyAdmin.objects.filter(company=page, social_user=me).exists()
    assert CompanyFollower.objects.filter(company=page, social_user=me).exists()
    ok("create page + admin/fan")

    r = c.get(f"/pages/{page.id}", secure=True)
    assert r.status_code == 200 and name.encode() in r.content
    assert "Стена".encode() in r.content
    ok("page show")

    r = c.post(f"/pages/{page.id}/posts", {"body": "Новость со страницы QA"}, secure=True)
    assert r.status_code in (301, 302)
    post = Post.objects.filter(topic=f"page:{page.id}", body__icontains="Новость со страницы").first()
    assert post
    # must not leak onto personal wall
    wall_ids = {p.id for p in wall_posts_for(me, limit=50, viewer=me)}
    assert post.id not in wall_ids
    ok("page wall post isolated from profile wall")

    feed = news_items(me, limit=60)
    page_stories = [
        i for i in feed
        if i.get("kind") == "page_post" and i.get("post") and i["post"].id == post.id
    ]
    assert page_stories, "fan should see page post in news feed"
    assert page_stories[0]["page"].id == page.id
    r = c.get("/feed", secure=True)
    assert r.status_code == 200 and name.encode() in r.content
    assert "Популярные страницы".encode() in r.content
    ok("page post in news feed + rail")

    r = c.get(f"/profile/{me.id}", secure=True)
    assert r.status_code == 200 and "Страницы".encode() in r.content and name.encode() in r.content
    ok("profile pages box")

    r = c.get(f"/pages/{page.id}/edit", secure=True)
    assert r.status_code == 200 and "Редактировать".encode() in r.content
    ok("page edit")

    r = c.get(f"/search?q={name}&tab=pages", secure=True)
    assert r.status_code == 200 and name.encode() in r.content
    ok("search finds page")

    # cleanup
    Post.objects.filter(topic=f"page:{page.id}").delete()
    CompanyFollower.objects.filter(company=page).delete()
    CompanyAdmin.objects.filter(company=page).delete()
    page.delete()
    ok("cleanup")
    print("ALL pages/apps probes passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL", e)
        raise
