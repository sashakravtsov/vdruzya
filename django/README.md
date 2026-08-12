# ВДрузья — копия Facebook.com (~2006)

Прод: https://vdruzya.ru → nginx → Daphne `127.0.0.1:18081` (`vdruzya-django.service`).

## Facebook 2006 core
Профиль (Сети → Find Friends: город/школа/работа), Стена, Mini-Feed, Notes (mid-2006), Лента новостей (bare stream + rail), друзья, Find Friends (`/people`, `#tabs`), фото/альбомы, группы (стена + доска), Inbox, подмигивания, глобальный поиск (`/search` — люди|группы), события, Мой аккаунт, Wall-to-Wall. Chrome — float + классические `#tabs` (не flex/grid-«апп»).

Без лайков (2009), без Messenger/WebSocket/групповых чатов, без PYMK, без центра уведомлений (сигналы comment/wall/friend_request не пишут в inbox), без опросов/репостов/стикеров/PWA/manifest, без status-publisher на ленте (статус — в шапке профиля), без `datetime-local` / HTML5 `type=date` (даты — selects / текст). Legacy `Reaction` — только orphan cleanup.

## Стек
- Django 6, Daphne, WhiteNoise, Postgres FTS
- Модели `managed=False` на живой схеме
- `BcryptBackend`, `ModelForm`, `Prefetch`, Redis cache
- Медиа: Beget S3 через `django-storages` (`MEDIA_DISK=s3`)
- Секреты: `.env`

## Команды
```bash
cd /var/www/projects/vdruzya.ru/django
sudo systemctl restart vdruzya-django
sudo -u www-data .venv/bin/python manage.py collectstatic --noinput
bash deploy/smoke-check.sh
```
