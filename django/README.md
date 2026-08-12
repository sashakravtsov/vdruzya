# ВДрузья — копия Facebook.com (~2006)

Прод: https://vdruzya.ru → nginx → Daphne `127.0.0.1:18081` (`vdruzya-django.service`).

## Facebook 2006 core + expansion
Профиль, Стена, Mini-Feed, Notes, Лента, друзья, Find Friends, фото/альбомы, группы, Inbox, подмигивания, поиск (люди|группы|страницы), события, Wall-to-Wall, Мой аккаунт.
**Масштаб под chrome 2006:** Страницы (`/pages`, схема `companies`), каталог Приложений (`/apps`).
Chrome — float + классические `#tabs`. Без лайков/Messenger/WS/PYMK/опросов/PWA.

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
