/* Classic Facebook messages thread */
(() => {
  const log = document.getElementById('chat-log');
  const form = document.getElementById('chat-form');
  if (!log || !form) return;

  const me = String(log.dataset.me || '');
  const cid = log.dataset.cid;
  const csrf = (form.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';
  const replyInput = form.querySelector('[name=reply_to]');
  const replyBanner = document.getElementById('reply-banner');
  const olderBtn = document.getElementById('chat-older');
  const friendsEl = document.getElementById('msg-friends');
  const friends = friendsEl ? JSON.parse(friendsEl.textContent || '[]') : [];
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/ws/messenger/${cid}`);

  const setReply = (id, name, body) => {
    if (!replyInput) return;
    replyInput.value = id || '';
    if (replyBanner) {
      replyBanner.style.display = id ? '' : 'none';
      if (id) replyBanner.firstChild.textContent = 'Ответ ' + (name || '') + ': ' + (body || '') + ' ';
    }
  };

  const bindReply = (root) => {
    root.querySelectorAll('.msg-reply').forEach((a) => {
      a.addEventListener('click', (e) => {
        e.preventDefault();
        setReply(a.dataset.reply, a.dataset.name, a.dataset.body);
        form.querySelector('textarea')?.focus();
      });
    });
  };

  const bindDel = (root) => {
    root.querySelectorAll('.msg-del').forEach((sf) => {
      sf.addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = sf.closest('[data-id]')?.dataset.id;
        const d = await postAjax(sf.action, new FormData(sf));
        if (d && id) removeLine(id); else sf.submit();
      });
    });
  };

  const bindFwd = (root) => {
    root.querySelectorAll('.msg-fwd-toggle').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const box = btn.parentElement?.querySelector('.msg-fwd-box');
        if (box) box.style.display = box.style.display === 'none' ? '' : 'none';
      });
    });
  };

  const fwdBox = (messageId) => {
    const wrap = document.createElement('div');
    wrap.className = 'msg-fwd-box';
    wrap.style.display = 'none';
    const sf = document.createElement('form');
    sf.method = 'post';
    sf.action = '/messages/' + messageId + '/forward';
    sf.className = 'inline';
    const tok = document.createElement('input');
    tok.type = 'hidden';
    tok.name = 'csrfmiddlewaretoken';
    tok.value = csrf;
    sf.appendChild(tok);
    const next = document.createElement('input');
    next.type = 'hidden';
    next.name = 'next';
    next.value = '/messenger?c=' + cid;
    sf.appendChild(next);
    const sel = document.createElement('select');
    sel.name = 'to';
    sel.className = 'inputtext';
    sel.required = true;
    const ph = document.createElement('option');
    ph.value = '';
    ph.textContent = 'Другу…';
    sel.appendChild(ph);
    friends.forEach((f) => {
      const o = document.createElement('option');
      o.value = f.id;
      o.textContent = f.name;
      sel.appendChild(o);
    });
    sf.appendChild(sel);
    const go = document.createElement('input');
    go.type = 'submit';
    go.className = 'inputbutton';
    go.value = 'OK';
    sf.appendChild(go);
    wrap.appendChild(sf);
    return wrap;
  };

  const lineEl = (d, actions) => {
    const line = document.createElement('div');
    line.className = 'chat-line' + (String(d.user_id) === me ? ' is-mine' : '');
    line.dataset.id = d.id;
    const a = document.createElement('a');
    a.href = '/profile/' + d.user_id;
    const b = document.createElement('b');
    b.textContent = d.name || '';
    a.appendChild(b);
    line.appendChild(a);
    if (d.created_at) {
      const t = document.createElement('span');
      t.className = 'muted chat-time';
      t.textContent = ' · ' + d.created_at;
      line.appendChild(t);
    }
    if (actions) {
      const reply = document.createElement('a');
      reply.href = '#chat-form';
      reply.className = 'linkish muted msg-reply';
      reply.dataset.reply = String(d.id);
      reply.dataset.name = d.name || '';
      reply.dataset.body = (d.body || '').slice(0, 60);
      reply.textContent = 'ответить';
      line.appendChild(reply);
      const fwd = document.createElement('a');
      fwd.href = '#';
      fwd.className = 'linkish muted msg-fwd-toggle';
      fwd.textContent = 'переслать';
      line.appendChild(fwd);
      if (String(d.user_id) === me) {
        const df = document.createElement('form');
        df.method = 'post';
        df.action = '/messages/' + d.id + '/delete';
        df.className = 'inline msg-del';
        const tok = document.createElement('input');
        tok.type = 'hidden';
        tok.name = 'csrfmiddlewaretoken';
        tok.value = csrf;
        df.appendChild(tok);
        const btn = document.createElement('button');
        btn.type = 'submit';
        btn.className = 'linkish muted';
        btn.title = 'Удалить';
        btn.textContent = '×';
        df.appendChild(btn);
        line.appendChild(df);
      }
      line.appendChild(fwdBox(d.id));
    }
    if (d.reply_to_id) {
      const q = document.createElement('div');
      q.className = 'chat-quote muted';
      q.textContent = (d.reply_name || '') + ': ' + (d.reply_body || '');
      line.appendChild(q);
    }
    const body = document.createElement('div');
    body.className = 'chat-body';
    if (d.body && d.body !== '[фото]') {
      body.appendChild(document.createTextNode(d.body || ''));
    }
    if (d.attachment_url) {
      const img = document.createElement('img');
      img.src = d.attachment_url;
      img.className = 'chat-photo';
      img.alt = '';
      const p = document.createElement('p');
      p.appendChild(img);
      body.appendChild(p);
    }
    line.appendChild(body);
    if (String(d.user_id) === me && d.read_at) {
      const seen = document.createElement('div');
      seen.className = 'muted chat-seen';
      seen.textContent = 'прочитано';
      line.appendChild(seen);
    }
    return line;
  };

  const wire = (el) => {
    bindReply(el);
    bindDel(el);
    bindFwd(el);
  };

  const append = (d) => {
    if (!d || !d.id || d.event === 'delete') return;
    if (log.querySelector('[data-id="' + d.id + '"]')) return;
    document.getElementById('chat-empty')?.remove();
    const el = lineEl(d, true);
    log.appendChild(el);
    wire(el);
    log.scrollTop = log.scrollHeight;
  };

  const prepend = (rows) => {
    if (!rows || !rows.length) return;
    const first = log.firstChild;
    const keep = log.scrollHeight;
    rows.forEach((d) => {
      if (!d || !d.id || log.querySelector('[data-id="' + d.id + '"]')) return;
      const el = lineEl(d, true);
      log.insertBefore(el, first);
      wire(el);
    });
    log.scrollTop = log.scrollHeight - keep;
  };

  const removeLine = (id) => log.querySelector('[data-id="' + id + '"]')?.remove();

  ws.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data);
      if (d.event === 'delete') removeLine(d.id);
      else append(d);
    } catch (_) {}
  };

  const postAjax = async (action, fd) => {
    if (!fd.has('csrfmiddlewaretoken')) fd.append('csrfmiddlewaretoken', csrf);
    const r = await fetch(action, {
      method: 'POST', body: fd,
      headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
    });
    if (!r.ok) return null;
    return r.json();
  };

  document.getElementById('reply-clear')?.addEventListener('click', () => setReply(''));
  wire(document);

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const body = (fd.get('body') || '').toString().trim();
    const hasPhoto = form.querySelector('[name=photo]')?.files?.length;
    if (!body && !hasPhoto) return;
    const d = await postAjax(form.action, fd);
    if (d) {
      append(d);
      const ta = form.querySelector('textarea');
      if (ta) ta.value = '';
      const file = form.querySelector('[name=photo]');
      if (file) file.value = '';
      setReply('');
    } else form.submit();
  });

  form.querySelector('textarea')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  olderBtn?.addEventListener('click', async (e) => {
    e.preventDefault();
    const before = log.querySelector('.chat-line')?.dataset.id;
    if (!before) return;
    const tq = encodeURIComponent(log.dataset.tq || olderBtn.dataset.tq || '');
    const r = await fetch(`/messenger/${cid}/older?before=${before}${tq ? '&tq=' + tq : ''}`, {
      headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
    });
    if (!r.ok) return;
    const d = await r.json();
    prepend(d.messages || []);
    if (!d.has_older) olderBtn.remove();
  });

  log.scrollTop = log.scrollHeight;
})();
