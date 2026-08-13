# ВДрузья — копия Facebook.com (~2006 chrome)

Прод: https://vdruzya.ru → nginx → Daphne `127.0.0.1:18081` (`vdruzya-django.service`).

## Facebook 2006 core + era expansion
Профиль, Стена, Mini-Feed, Notes, Лента, друзья, Find Friends, фото/альбомы, группы, Inbox, подмигивания, поиск (люди|группы|страницы), события, Wall-to-Wall, Мой аккаунт.

**Под chrome 2006 (float / `#tabs` / formtable):** Страницы, App Center, Likes, Places, Questions, classic Polls, Share, Open Graph, Timeline milestones, Collections, Graph Search, Hashtags, Nearby Friends, Trending, Save, Safety Check. Inbox — классический Message Center (ответы/стикеры), без live Messenger.

**Soft bans (не возвращать):** WebSocket Messenger / `static/js/messenger.js` (чат остаётся классическим Message Center; Channels для Messenger — нельзя), PYMK, Ads/Flyers/Beacon/Connect, **third-party hosted canvas/iframe** (чужой код во frame — нельзя; кабинет `/developers` + OAuth-lite / signed_request / `/api/app/*` + редирект на сайт вроде somneniya.ru — можно; first-party canvas на ВДрузья — можно), отдельный video-CDN продукт (видео — на том же медиа-диске/S3, что и фото), Facebook Home, blue Timeline redesign (`page-tabs` / flex-hero), `models/polls.py` (использовать только `ClassicPoll`), современный photo theater/lightbox (можно только 2006 `FBDialog`: фото слева / комментарии справа).


**Разрешено (LIVE apps):** Django Channels + Redis channel layer + `apps/social/live/` + `apps/social/poker/consumers.py` + `static/js/live-client.js` / `poker-realtime.js` / `farm-live.js` / `dating-live.js` для realtime first-party canvas (покер, ферма, знакомства, шахматы). Messenger WS — нельзя.

## Стек
- Django 6, Daphne (HTTP + WebSocket), Channels, WhiteNoise, Postgres FTS
- Модели `managed=False` на живой схеме; `deploy/ensure-*-modules.py` для новых таблиц
- `BcryptBackend`, `ModelForm`, `Prefetch`, Redis cache + Channels layer (DB `/2`)
- Медиа: Beget S3 через `django-storages` (`MEDIA_DISK=s3`)
- Секреты: `.env`

## Команды
```bash
cd /var/www/projects/vdruzya.ru/django
sudo systemctl restart vdruzya-django
sudo -u www-data .venv/bin/python manage.py collectstatic --noinput
bash deploy/smoke-check.sh
```
