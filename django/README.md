# ВДрузья — копия Facebook.com (classic 2005 UI)

Прод: https://vdruzya.ru → nginx → Daphne `127.0.0.1:18081` (`vdruzya-django.service`).
WebSocket: `/ws/messenger/<id>`.

## Facebook-core
Лента, профиль, друзья, фото/альбомы, группы, мессенджер, уведомления, поиск, события, стена (лайки/комменты/репосты/опросы).

## Стек
- Django 6, Channels, Daphne, WhiteNoise, Postgres FTS
- Модели `managed=False` на живой схеме
- `BcryptBackend`, `ModelForm`, `Prefetch`, Redis cache + channel layer
- Медиа: Beget S3 через `django-storages` (`MEDIA_DISK=s3`)
- Секреты: `.env`

## Команды
```bash
cd /var/www/projects/vdruzya.ru/django
sudo systemctl restart vdruzya-django
sudo -u www-data .venv/bin/python manage.py collectstatic --noinput
bash deploy/smoke-check.sh
```
