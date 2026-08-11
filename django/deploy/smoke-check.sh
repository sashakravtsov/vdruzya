#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${SMOKE_BASE_URL:-https://vdruzya.ru}"
ROOT=/var/www/projects/vdruzya.ru
FAIL=0
check_http() {
  local path="$1" expected="$2" code
  code="$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}${path}")"
  if [[ "$code" != "$expected" ]]; then echo "FAIL ${code} (expected ${expected}) ${path}"; FAIL=1
  else echo "OK   ${code} ${path}"; fi
}
echo "== HTTP smoke (${BASE_URL}) =="
for path in \
  /up:200 /:200 /login:200 /register:200 /terms:200 /privacy:200 \
  /contacts:200 /security:200 \
  /apple-touch-icon.png:200 /favicon-32x32.png:200 \
  /password-reset:200 \
  /sitemap.xml:200 /robots.txt:200 \
  /sw.js:200 /offline.html:200 /feed:302 /messenger:302 \
  /app:410 \
  /posts/abc:404 /articles/foo:404 /albums/foo:404 /events/foo:404; do
  check_http "${path%%:*}" "${path##*:}"
done
if curl -s "${BASE_URL}/login" | grep -q csrfmiddlewaretoken; then echo "OK   django csrf present"
else echo "FAIL django csrf missing"; FAIL=1; fi
if [[ -d "${ROOT}/app" ]]; then echo "FAIL legacy app/ dir still present"; FAIL=1; else echo "OK   django-only tree"; fi
if [[ -d "${ROOT}/django/public/build" ]]; then echo "FAIL legacy /build assets still present"; FAIL=1; else echo "OK   no legacy /build"; fi
code="$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}/static/css/classic.css")"
if [[ "$code" == "200" ]]; then echo "OK   classic.css http"; else echo "FAIL classic.css (${code})"; FAIL=1; fi
if curl -s "${BASE_URL}/static/css/classic.css" | rg -q -- '--tw-|@tailwind|tailwindcss'; then
  echo "FAIL classic.css still Tailwind/Vite"; FAIL=1
else
  echo "OK   classic.css is classic"
fi
if curl -sI "${BASE_URL}/login" | rg -qi 'strict-transport-security'; then echo "OK   HSTS"
else echo "FAIL HSTS missing"; FAIL=1; fi
if rg -l 'Illuminate|laravel-echo|window\.Laravel|broadcaster===.reverb|fb-ref/' "${ROOT}/django/public" "${ROOT}/django/staticfiles" -g '!*.gz' 2>/dev/null | head -5 | grep -q .; then
  echo "FAIL legacy realtime/static leftovers"; FAIL=1
else
  echo "OK   no legacy realtime clients"
fi
H="$(curl -sL "${BASE_URL}/" | rg -o 'static/css/classic\.[a-f0-9]+\.css' | head -1 || true)"
if [[ -n "$H" ]] && curl -s "${BASE_URL}/${H}" | rg -q 'pageheaderbg\.[a-f0-9]+\.png'; then
  echo "OK   Manifest header image"
else
  echo "FAIL Manifest header image (${H:-none})"; FAIL=1
fi
cd "${ROOT}/django" && .venv/bin/python - <<'PY' || FAIL=1
import os,django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.db import connection
bad={'jobs','failed_jobs','job_batches','sessions','cache','migrations','password_reset_tokens'}
with connection.cursor() as c:
    c.execute("select tablename from pg_tables where schemaname='public'")
    have={r[0] for r in c.fetchall()}
left=sorted(bad & have)
if left:
    print('FAIL legacy tables still present:', ', '.join(left)); raise SystemExit(1)
print('OK   legacy infra tables dropped')
PY
cd "${ROOT}/django" && .venv/bin/python manage.py health >/dev/null && echo "OK   manage.py health" || { echo "FAIL manage.py health"; FAIL=1; }
cd "${ROOT}/django" && .venv/bin/python - <<'PY' || FAIL=1
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.conf import settings
from django.core.files.storage import default_storage
from apps.social.models import SocialProfile
name = default_storage.__class__.__name__
if "S3" not in name:
    print("FAIL storage backend is", name); raise SystemExit(1)
print("OK   S3Storage active")
p = SocialProfile.objects.exclude(avatar_path__isnull=True).exclude(avatar_path="").first()
url = p.avatar_url if p else None
if not url or not str(url).startswith("https://s3.vdruzya.ru/"):
    print("FAIL avatar CDN url:", url); raise SystemExit(1)
print("OK   avatar CDN", url)
import urllib.request
code = urllib.request.urlopen(url, timeout=10).status
if code != 200:
    print("FAIL avatar HTTP", code); raise SystemExit(1)
print("OK   avatar HTTP 200")
if not (settings.MEDIA_URL or "").startswith("https://s3.vdruzya.ru"):
    print("FAIL MEDIA_URL", settings.MEDIA_URL); raise SystemExit(1)
print("OK   MEDIA_URL CDN")
PY
if curl -sL "${BASE_URL}/profile/aleksandr-kravtsov" | rg -q 'https://s3\.vdruzya\.ru/avatars/'; then
  echo "OK   profile HTML has S3 avatar"
else
  echo "FAIL profile HTML missing S3 avatar"; FAIL=1
fi
echo "== Wall/Groups feature probe =="
if cd "${ROOT}/django" && .venv/bin/python deploy/wall-groups-check.py; then
  echo "OK   wall/groups features"
else
  echo "FAIL wall/groups features"; FAIL=1
fi
echo "== Photos feature probe =="
if cd "${ROOT}/django" && .venv/bin/python deploy/photos-check.py; then
  echo "OK   photos features"
else
  echo "FAIL photos features"; FAIL=1
fi
echo "== Friends feature probe =="
if cd "${ROOT}/django" && .venv/bin/python deploy/friends-check.py; then
  echo "OK   friends features"
else
  echo "FAIL friends features"; FAIL=1
fi
exit "$FAIL"
