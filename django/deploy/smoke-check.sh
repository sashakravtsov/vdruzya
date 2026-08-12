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
  /sw.js:404 /offline.html:404 /feed:302 /inbox:302 /account:302 /messenger:301 /activity:301 \
  /app:410 /pages:200 /apps:200 /gifts:302 /birthdays:302 \
  /networks:200 /mobile:200 /notes:302 /links:302 /videos:302 /marketplace:302 /blocked:302 \
  /posts/abc:404 /articles/foo:404 /albums/foo:404 /events/foo:404; do
  check_http "${path%%:*}" "${path##*:}"
done
if curl -s "${BASE_URL}/login" | grep -q csrfmiddlewaretoken; then echo "OK   django csrf present"
else echo "FAIL django csrf missing"; FAIL=1; fi
if [[ -d "${ROOT}/app" ]]; then echo "FAIL legacy app/ dir still present"; FAIL=1; else echo "OK   django-only tree"; fi
if [[ -d "${ROOT}/django/public/build" ]]; then echo "FAIL legacy /build assets still present"; FAIL=1; else echo "OK   no legacy /build"; fi
code="$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}/static/css/classic.css")"
if [[ "$code" == "200" ]]; then echo "OK   classic.css http"; else echo "FAIL classic.css (${code})"; FAIL=1; fi
if curl -s "${BASE_URL}/static/css/classic.css" | grep -Eq -- '--tw-|@tailwind|tailwindcss'; then
  echo "FAIL classic.css still Tailwind/Vite"; FAIL=1
else
  echo "OK   classic.css is classic"
fi
if curl -sI "${BASE_URL}/login" | grep -qi 'strict-transport-security'; then echo "OK   HSTS"
else echo "FAIL HSTS missing"; FAIL=1; fi
if grep -RIlE 'Illuminate|laravel-echo|window\.Laravel|broadcaster===.reverb|fb-ref/' \
    "${ROOT}/django/public" "${ROOT}/django/staticfiles" 2>/dev/null \
    | grep -v '\.gz$' | head -5 | grep -q .; then
  echo "FAIL legacy realtime/static leftovers"; FAIL=1
else
  echo "OK   no legacy realtime clients"
fi
H="$(curl -sL "${BASE_URL}/" | grep -oE 'static/css/classic\.[a-f0-9]+\.css' | head -1 || true)"
HN="$(basename "${H:-}")"
if [[ -n "$H" ]] && curl -sL --compressed "${BASE_URL}/${H}" | grep -Eq 'pageheaderbg\.[a-f0-9]+\.png'; then
  echo "OK   Manifest header image"
elif [[ -n "$HN" && -f "${ROOT}/django/staticfiles/css/${HN}" ]] \
  && grep -Eq 'pageheaderbg\.[a-f0-9]+\.png' "${ROOT}/django/staticfiles/css/${HN}"; then
  echo "OK   Manifest header image (staticfiles)"
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
if curl -sL "${BASE_URL}/profile/aleksandr-kravtsov" | grep -Eq 'https://s3\.vdruzya\.ru/avatars/'; then
  echo "OK   profile HTML has S3 avatar"
else
  echo "FAIL profile HTML missing S3 avatar"; FAIL=1
fi
# FB-2006: no live Messenger / PWA / polls surface
if [[ -f "${ROOT}/django/static/js/messenger.js" ]] || [[ -f "${ROOT}/django/apps/social/consumers.py" ]]; then
  echo "FAIL WS messenger leftovers present"; FAIL=1
else
  echo "OK   no WS messenger leftovers"
fi
if [[ -f "${ROOT}/django/public/sw.js" ]] || [[ -f "${ROOT}/django/public/offline.html" ]] || [[ -f "${ROOT}/django/public/site.webmanifest" ]]; then
  echo "FAIL PWA leftovers present"; FAIL=1
else
  echo "OK   no PWA leftovers"
fi
if [[ -f "${ROOT}/django/static/js/app.js" ]]; then
  echo "FAIL empty app.js still present"; FAIL=1
else
  echo "OK   no app.js"
fi
if grep -RIl 'from apps.social.models.feed import Reaction\|models\.feed import Reaction' \
    "${ROOT}/django/apps/social" 2>/dev/null | grep -q .; then
  echo "FAIL Reaction still imported from feed"; FAIL=1
else
  echo "OK   Reaction quarantined in legacy"
fi
if [[ -f "${ROOT}/django/apps/social/models/polls.py" ]]; then
  echo "FAIL polls module still present"; FAIL=1
else
  echo "OK   no polls module"
fi
if grep -q 'CHANNEL_LAYERS' "${ROOT}/django/config/settings.py" 2>/dev/null; then
  echo "FAIL CHANNEL_LAYERS still configured"; FAIL=1
else
  echo "OK   no CHANNEL_LAYERS"
fi
if grep -q 'Что у вас нового' "${ROOT}/django/templates/social/feed.html" 2>/dev/null; then
  echo "FAIL feed still has status publisher"; FAIL=1
else
  echo "OK   feed has no status publisher"
fi
code="$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}/compose/album-photos")"
if [[ "$code" == "404" ]]; then echo "OK   compose/album-photos 404"
else echo "FAIL compose/album-photos (${code})"; FAIL=1; fi
if grep -q 'type="friend_accept"' "${ROOT}/django/apps/social/friendship.py" 2>/dev/null \
   || grep -q "type='friend_accept'" "${ROOT}/django/apps/social/friendship.py" 2>/dev/null \
   || grep -q 'type="friend_accept"' "${ROOT}/django/apps/social/"*.py 2>/dev/null; then
  echo "FAIL friend_accept notifications still written"; FAIL=1
else
  echo "OK   no friend_accept notify writes"
fi
if grep -q 'compose_album_photos\|compose/album-photos' "${ROOT}/django/apps/social/urls.py" 2>/dev/null; then
  echo "FAIL compose album-photos still routed"; FAIL=1
else
  echo "OK   no compose album-photos route"
fi
if grep -EEq 'page-tabs|wall-media-grid|group-tile|display:\s*flex|display:\s*grid|@media' \
    "${ROOT}/django/static/css/classic.css" 2>/dev/null; then
  echo "FAIL classic.css still has flex/grid/media/page-tabs chrome"; FAIL=1
else
  echo "OK   classic.css float chrome (fixed 760)"
fi
if [[ ! -f "${ROOT}/django/static/img/nophoto.gif" ]]; then
  echo "FAIL nophoto.gif missing"; FAIL=1
else
  echo "OK   nophoto.gif silhouette"
fi
if grep -RIl 'avatar-fallback' "${ROOT}/django/templates" 2>/dev/null | grep -q .; then
  echo "FAIL avatar-fallback still in templates"; FAIL=1
else
  echo "OK   no letter avatar tiles"
fi
if grep -q 'compose-more\|album-pick' "${ROOT}/django/templates/social/_wall_compose.html" 2>/dev/null; then
  echo "FAIL modern wall compose leftovers"; FAIL=1
else
  echo "OK   flat wall compose"
fi
if ! grep -q 'class="group-rail"' "${ROOT}/django/templates/social/group.html" 2>/dev/null \
   || ! awk '/group-rail/{r=NR} /group-main/{m=NR} END{exit !(r && m && r<m)}' "${ROOT}/django/templates/social/group.html"; then
  echo "FAIL group rail not left of main"; FAIL=1
else
  echo "OK   group left rail"
fi
if grep -q 'data:image/svg' "${ROOT}/django/static/css/classic.css" 2>/dev/null; then
  echo "FAIL classic.css still has SVG data icons"; FAIL=1
else
  echo "OK   GIF feed icons"
fi
if grep -q "_wall_post.html" "${ROOT}/django/templates/social/feed.html" 2>/dev/null; then
  echo "FAIL feed still embeds wallpost cards"; FAIL=1
else
  echo "OK   feed news-story rows"
fi
if grep -q 'inbox-list { float: left' "${ROOT}/django/static/css/classic.css" 2>/dev/null; then
  echo "FAIL inbox still split-pane float"; FAIL=1
else
  echo "OK   inbox list/thread full width"
fi
if ! grep -q 'profile.walltowall' "${ROOT}/django/apps/social/urls.py" 2>/dev/null; then
  echo "FAIL wall-to-wall route missing"; FAIL=1
else
  echo "OK   wall-to-wall route"
fi
if grep -q 'Поделиться\|Закрепить\|Мне нравится' "${ROOT}/django/templates/social/_wall_post.html" 2>/dev/null \
   || grep -q 'Поделиться\|Закрепить\|Мне нравится' "${ROOT}/django/templates/social/_profile_wall.html" 2>/dev/null; then
  echo "FAIL wall templates have share/pin/like"; FAIL=1
else
  echo "OK   wall has no share/pin/like (FB 2006)"
fi
if ! grep -q 'shared_post' "${ROOT}/django/apps/social/models/defer.py" 2>/dev/null; then
  echo "FAIL shared_post not deferred"; FAIL=1
else
  echo "OK   shared_post deferred (not 2006)"
fi
if grep -q '<details' "${ROOT}/django/templates/social/_comment_thread.html" 2>/dev/null; then
  echo "FAIL comment thread still uses details"; FAIL=1
else
  echo "OK   comment reveal is classic link"
fi
if ! grep -q 'tab=notes' "${ROOT}/django/templates/social/profile.html" 2>/dev/null \
   || ! grep -q 'notes.store' "${ROOT}/django/apps/social/urls.py" 2>/dev/null; then
  echo "FAIL Notes tab/route missing"; FAIL=1
else
  echo "OK   Notes tab (mid-2006)"
fi
if grep -q 'tab=posts\|Записи' "${ROOT}/django/templates/social/search.html" 2>/dev/null; then
  echo "FAIL search still has posts tab"; FAIL=1
elif ! grep -q 'tab=pages' "${ROOT}/django/templates/social/search.html" 2>/dev/null; then
  echo "FAIL search missing pages tab"; FAIL=1
else
  echo "OK   search is people|groups|pages"
fi
if ! grep -q 'name="pages"' "${ROOT}/django/apps/social/urls.py" 2>/dev/null; then
  echo "FAIL Pages routes missing"; FAIL=1
else
  echo "OK   Pages module routes"
fi
if ! grep -q 'name="apps"' "${ROOT}/django/apps/social/urls.py" 2>/dev/null; then
  echo "FAIL Apps catalog route missing"; FAIL=1
else
  echo "OK   Apps catalog route"
fi
if ! grep -q 'Мои страницы' "${ROOT}/django/templates/partials/sidebar.html" 2>/dev/null; then
  echo "FAIL snav missing Pages"; FAIL=1
else
  echo "OK   snav Pages + Apps"
fi
if ! grep -q "url 'videos'" "${ROOT}/django/templates/partials/sidebar.html" 2>/dev/null; then
  echo "FAIL snav missing Videos"; FAIL=1
else
  echo "OK   snav Videos"
fi
if ! grep -q 'photo_tags' "${ROOT}/django/deploy/ensure-classic-modules.py" 2>/dev/null \
  || ! grep -q 'PhotoTag' "${ROOT}/django/apps/social/models/more.py" 2>/dev/null; then
  echo "FAIL Photos of Me / photo_tags missing"; FAIL=1
else
  echo "OK   Photos of Me schema"
fi
if ! grep -q 'events.posts' "${ROOT}/django/apps/social/urls.py" 2>/dev/null \
  || ! grep -q 'tab=photos' "${ROOT}/django/templates/social/event.html" 2>/dev/null; then
  echo "FAIL event wall/photos missing"; FAIL=1
else
  echo "OK   event wall + photos"
fi
if [[ -f "${ROOT}/django/templates/social/videos.html" ]]; then
  echo "FAIL duplicate videos.html still present"; FAIL=1
else
  echo "OK   links/videos share template"
fi
if ! grep -q 'def fb_when' "${ROOT}/django/apps/social/templatetags/vd.py" 2>/dev/null \
   || grep -RIl 'timesince' "${ROOT}/django/templates/social" 2>/dev/null | grep -q .; then
  echo "FAIL relative timesince still in social templates"; FAIL=1
else
  echo "OK   absolute fb_when dates"
fi
if ! grep -q '>Главная<' "${ROOT}/django/templates/layout.html" 2>/dev/null; then
  echo "FAIL gnav missing Главная"; FAIL=1
else
  echo "OK   gnav capitalized"
fi
if ! grep -q 'id="userprofile"' "${ROOT}/django/templates/social/profile.html" 2>/dev/null \
   || ! grep -q '#userprofile' "${ROOT}/django/static/css/classic.css" 2>/dev/null; then
  echo "FAIL profile missing #userprofile divider shell"; FAIL=1
elif grep -q 'profile-content' "${ROOT}/django/templates/social/profile.html" 2>/dev/null \
   || grep -Eq 'profile-content.*narrowleftbg|narrowleftbg.*profile-content' "${ROOT}/django/static/css/classic.css" 2>/dev/null; then
  echo "FAIL divider still on #content (shifted left)"; FAIL=1
else
  echo "OK   profile #userprofile divider (archive)"
fi
if ! grep -q 'id="tabs"' "${ROOT}/django/templates/social/profile_edit.html" 2>/dev/null \
   || ! grep -q '_editor_fields.html' "${ROOT}/django/templates/social/profile_edit.html" 2>/dev/null \
   || grep -q 'id="editnav"' "${ROOT}/django/templates/social/profile_edit.html" 2>/dev/null \
   || grep -q 'type="date"' "${ROOT}/django/apps/social/forms.py" 2>/dev/null \
   || [[ -f "${ROOT}/django/templates/social/_profile_edit_basic.html" ]] \
   || [[ -f "${ROOT}/django/templates/social/_profile_edit_education.html" ]] \
   || ! grep -q 'row_editors' "${ROOT}/django/apps/social/profile_page.py" 2>/dev/null; then
  echo "FAIL profile edit not archive tabs/field-loop/row_editors"; FAIL=1
else
  echo "OK   profile edit classic (#tabs + field loop + row_editors, no HTML5 date)"
fi
if [[ -f "${ROOT}/django/templates/social/albums_user.html" ]]; then
  echo "FAIL albums_user.html still present"; FAIL=1
else
  echo "OK   albums templates merged"
fi
if grep -q 'news-card' "${ROOT}/django/templates/social/_news_item.html" 2>/dev/null; then
  echo "FAIL news-card still in feed items"; FAIL=1
else
  echo "OK   no news-card wrappers"
fi
if grep -q 'album-card\|empty-panel' "${ROOT}/django/templates/social/"*.html "${ROOT}/django/templates/social/"*.html 2>/dev/null \
   || grep -rq 'album-card\|empty-panel' "${ROOT}/django/templates/social/" 2>/dev/null; then
  echo "FAIL album-card/empty-panel still in templates"; FAIL=1
else
  echo "OK   no album-card/empty-panel"
fi
if grep -q '_ADMIN' "${ROOT}/django/apps/social/group_page.py" 2>/dev/null; then
  echo "FAIL group_page still references _ADMIN"; FAIL=1
else
  echo "OK   group ADMIN_ROLES"
fi
if ! grep -q 'id="tabs"' "${ROOT}/django/templates/social/group.html" 2>/dev/null; then
  echo "FAIL group page missing #tabs"; FAIL=1
else
  echo "OK   group page has #tabs"
fi
echo "== Wall/Groups feature probe =="
if cd "${ROOT}/django" && .venv/bin/python deploy/wall-groups-check.py; then
  echo "OK   wall/groups features"
else
  echo "FAIL wall/groups features"; FAIL=1
fi
echo "== Photos feature probe =="
if grep -q 'max-height: 520px' "${ROOT}/django/static/css/classic.css" 2>/dev/null; then
  echo "FAIL photo viewer still capped at 520px"; FAIL=1
else
  echo "OK   photo viewer uncapped (FB 2006 page)"
fi
if ! grep -q 'полный размер' "${ROOT}/django/templates/social/photo.html" 2>/dev/null; then
  echo "FAIL photo missing full-size link"; FAIL=1
else
  echo "OK   photo full-size link"
fi
if cd "${ROOT}/django" && .venv/bin/python deploy/photos-check.py; then
  echo "OK   photos features"
else
  echo "FAIL photos features"; FAIL=1
fi

if grep -RIl 'album_photos\|album-pick' "${ROOT}/django/apps/social" "${ROOT}/django/templates" "${ROOT}/django/static/css/classic.css" 2>/dev/null | grep -q .; then
  echo "FAIL album-pick leftovers"; FAIL=1
else
  echo "OK   no album-pick leftovers"
fi
if grep -q 'Хост:' "${ROOT}/django/templates/social/event.html" 2>/dev/null \
   || grep -q 'Email:' "${ROOT}/django/templates/social/_editor_fields.html" 2>/dev/null; then
  echo "FAIL EN/calque labels left"; FAIL=1
else
  echo "OK   RU labels (E-mail / Организатор)"
fi
if ! grep -q 'wall-media-single' "${ROOT}/django/static/css/classic.css" 2>/dev/null; then
  echo "FAIL wall-media-single missing"; FAIL=1
else
  echo "OK   wall media enlarge chrome"
fi

if grep -RIl 'type="email"' "${ROOT}/django/templates" 2>/dev/null | grep -q .; then
  echo "FAIL HTML5 type=email still in templates"; FAIL=1
else
  echo "OK   no type=email (classic text)"
fi
if grep -q 'loading="lazy"\|<figure' "${ROOT}/django/templates/social/album.html" 2>/dev/null; then
  echo "FAIL album still uses figure/lazy"; FAIL=1
else
  echo "OK   album classic gallery markup"
fi
if ! grep -q 'Найти друзей' "${ROOT}/django/templates/partials/sidebar.html" 2>/dev/null; then
  echo "FAIL snav missing Найти друзей"; FAIL=1
else
  echo "OK   snav Find Friends"
fi
if grep -q 'avatar-fallback' "${ROOT}/django/static/css/classic.css" 2>/dev/null; then
  echo "FAIL avatar-fallback CSS leftovers"; FAIL=1
else
  echo "OK   no avatar-fallback CSS"
fi
if grep -q 'image/webp' "${ROOT}/django/apps/social/forms.py" "${ROOT}/django/templates/social/_profile_edit_avatar.html" 2>/dev/null; then
  echo "FAIL webp still accepted"; FAIL=1
else
  echo "OK   JPEG/PNG/GIF only"
fi

if grep -RIlE '\srequired(=|[\s>])|minlength=' "${ROOT}/django/templates/accounts" "${ROOT}/django/templates/social/_comment_compose.html" 2>/dev/null | grep -q .; then
  echo "FAIL HTML5 required/minlength on classic forms"; FAIL=1
else
  echo "OK   no HTML5 required on classic forms"
fi
if grep -q 'album-cover-fallback">·' "${ROOT}/django/templates/social/_profile_left.html" 2>/dev/null; then
  echo "FAIL letter-tile dot fallback on profile rail"; FAIL=1
else
  echo "OK   profile rail uses nophoto"
fi
if ! grep -q 'company_name__icontains' "${ROOT}/django/apps/social/friendship.py" 2>/dev/null; then
  echo "FAIL workplace search ignores Experience"; FAIL=1
else
  echo "OK   workplace Find Friends uses Experience"
fi
if ! grep -q 'NoteForm' "${ROOT}/django/apps/social/views_wall_ops.py" 2>/dev/null; then
  echo "FAIL Notes edit not using NoteForm"; FAIL=1
else
  echo "OK   Notes edit uses NoteForm"
fi
if ! grep -q 'profile-photo-thumbs img {' "${ROOT}/django/static/css/classic.css" 2>/dev/null; then
  echo "FAIL profile photo thumb CSS broken"; FAIL=1
else
  echo "OK   profile photo thumb CSS"
fi
if ! grep -q 'album-index .album-cover img {' "${ROOT}/django/static/css/classic.css" 2>/dev/null; then
  echo "FAIL album cover CSS broken"; FAIL=1
else
  echo "OK   album cover CSS"
fi
if ! grep -q 'def get_absolute_url' "${ROOT}/django/apps/social/models/feed.py" 2>/dev/null; then
  echo "FAIL Post.get_absolute_url missing"; FAIL=1
else
  echo "OK   Post.get_absolute_url"
fi
if grep -qE 'href="\{\{ post\.media_url \}\}"' "${ROOT}/django/templates/social/_post_media.html" 2>/dev/null; then
  echo "FAIL wall media still links raw CDN"; FAIL=1
else
  echo "OK   wall media uses page href"
fi
if grep -q 'object-fit' "${ROOT}/django/static/css/classic.css" 2>/dev/null; then
  echo "FAIL classic.css still has object-fit"; FAIL=1
else
  echo "OK   no object-fit in classic.css"
fi
if grep -q '("everyone"' "${ROOT}/django/apps/social/forms.py" 2>/dev/null; then
  echo "FAIL posting_policy everyone still in GroupForm"; FAIL=1
else
  echo "OK   no everyone posting_policy"
fi
if ! grep -q 'use_required_attribute = False' "${ROOT}/django/apps/social/forms.py" 2>/dev/null; then
  echo "FAIL ClassicForm missing use_required_attribute"; FAIL=1
else
  echo "OK   ClassicForm disables HTML5 required"
fi
if ! grep -q 'TextInput' "${ROOT}/django/apps/accounts/forms.py" 2>/dev/null; then
  echo "FAIL PasswordResetForm not using TextInput"; FAIL=1
else
  echo "OK   password reset TextInput"
fi
if ! grep -q 'border-top: solid 1px #3B5998' "${ROOT}/django/static/css/classic.css" 2>/dev/null \
  || ! grep -q 'wallpost td.image img {' "${ROOT}/django/static/css/classic.css" 2>/dev/null; then
  echo "FAIL wallpost avatar/info CSS not split"; FAIL=1
else
  echo "OK   wallpost avatar CSS split"
fi
cd "${ROOT}/django" && .venv/bin/python - <<'PY' || FAIL=1
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from apps.social.forms import CommentForm, NoteForm, EventForm, PasswordForm
from apps.accounts.forms import PasswordResetForm
for label, html in (
    ("comment", CommentForm().as_p()),
    ("note", NoteForm().as_p()),
    ("event", EventForm().as_p()),
    ("password", PasswordForm().as_p()),
    ("reset", str(PasswordResetForm()["email"])),
):
    bad = [x for x in ("required", "minlength", 'type="email"') if x in html]
    # "required=False" won't appear; bare required attr would
    bad = []
    if " required" in html or 'required="' in html or "required='" in html:
        bad.append("required")
    if "minlength" in html:
        bad.append("minlength")
    if 'type="email"' in html:
        bad.append("type=email")
    if bad:
        raise SystemExit(f"FAIL rendered {label} has {', '.join(bad)}")
print("OK   rendered forms have no HTML5 required/email/minlength")
PY
echo "== Friends feature probe =="
if cd "${ROOT}/django" && .venv/bin/python deploy/friends-check.py; then
  echo "OK   friends features"
else
  echo "FAIL friends features"; FAIL=1
fi
echo "== Profile feature probe =="
if cd "${ROOT}/django" && .venv/bin/python deploy/profile-check.py; then
  echo "OK   profile features"
else
  echo "FAIL profile features"; FAIL=1
fi
echo "== Events feature probe =="
if cd "${ROOT}/django" && .venv/bin/python deploy/events-check.py; then
  echo "OK   events features"
else
  echo "FAIL events features"; FAIL=1
fi
echo "== Pages/Apps feature probe =="
if cd "${ROOT}/django" && .venv/bin/python deploy/pages-check.py; then
  echo "OK   pages/apps features"
else
  echo "FAIL pages/apps features"; FAIL=1
fi
echo "== Gifts/Page-events feature probe =="
if cd "${ROOT}/django" && .venv/bin/python deploy/gifts-check.py; then
  echo "OK   gifts/page-events features"
else
  echo "FAIL gifts/page-events features"; FAIL=1
fi
echo "== Inbox/Flash/Birthdays feature probe =="
if cd "${ROOT}/django" && .venv/bin/python deploy/inbox-check.py; then
  echo "OK   inbox/flash/birthdays features"
else
  echo "FAIL inbox/flash/birthdays features"; FAIL=1
fi
echo "== Classic 2006-09 modules probe =="
if cd "${ROOT}/django" && .venv/bin/python deploy/ensure-classic-modules.py \
  && .venv/bin/python deploy/classic-check.py; then
  echo "OK   classic modules features"
else
  echo "FAIL classic modules features"; FAIL=1
fi
exit "$FAIL"
