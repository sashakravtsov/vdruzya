# ВДрузья — копия Facebook.com (~2006)

Прод: https://vdruzya.ru → nginx → Daphne `127.0.0.1:18081` (`vdruzya-django.service`).

## Facebook 2006 core
Профиль, Стена, Mini-Feed, Лента новостей, друзья, фото/альбомы, группы (стена + доска), Inbox (сообщения), подмигивания, поиск, события.

Без лайков (2009), без Messenger/WebSocket, без опросов/репостов в UI.

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
