"""Local click page for the owner's spot check of paraphrased queries (Voyage retrieval bench, #25).

The page shows texts of the owner's story, so the server listens on 127.0.0.1 only, checks Origin and Host, keeps no log
and prints only its address. Verdicts are written to owner-check.json through set_verdict on every click.
Standard library only."""
import argparse
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from memory_bench.paraphrase import MAX_NO, _inside_repo, _summary, set_verdict  # noqa: E402

FILE_NAME = 'owner-check.json'
MAX_BODY = 4096

PAGE = r'''<!doctype html>
<html lang="uk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Перевірка перефразувань</title>
<style>
:root { color-scheme: light dark; --bg:#f6f6f3; --fg:#1d1d1b; --muted:#5d5d58; --card:#fff; --line:#cfcfc8;
  --yes:#1c7a3e; --yesbg:#dff3e5; --no:#a8321f; --nobg:#f9e0db; --focus:#1a56c8; --bar:#ecece6; }
@media (prefers-color-scheme: dark) { :root { --bg:#17181a; --fg:#e8e8e4; --muted:#a4a49d; --card:#222427; --line:#44464b;
  --yes:#6fd694; --yesbg:#1c3a27; --no:#ff9a86; --nobg:#4a2520; --focus:#7fb0ff; --bar:#202225; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.5 system-ui, "Segoe UI", sans-serif; }
header { position:sticky; top:0; background:var(--bar); border-bottom:1px solid var(--line); padding:12px 16px; z-index:1; }
#counter { font-weight:600; }
#threshold { margin-left:12px; padding:2px 8px; border-radius:6px; }
#threshold.ok { background:var(--yesbg); color:var(--yes); }
#threshold.fail { background:var(--nobg); color:var(--no); }
main { max-width:860px; margin:0 auto; padding:16px; }
.hint { color:var(--muted); font-size:14px; margin:0 0 6px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; margin:14px 0; }
.card:focus { outline:3px solid var(--focus); outline-offset:2px; }
.card.current { border-color:var(--focus); }
.label { color:var(--muted); font-size:13px; text-transform:uppercase; letter-spacing:.04em; margin-top:8px; }
.record, .query { margin:2px 0 0; white-space:pre-wrap; }
.query { font-size:18px; font-weight:600; }
.level { font-size:14px; color:var(--muted); }
.buttons { display:flex; gap:10px; margin-top:12px; }
button { font:inherit; padding:8px 18px; border-radius:8px; border:2px solid var(--line); background:transparent; color:var(--fg); cursor:pointer; }
button:focus-visible { outline:3px solid var(--focus); outline-offset:2px; }
button.yes.on { background:var(--yesbg); border-color:var(--yes); color:var(--yes); font-weight:700; }
button.no.on { background:var(--nobg); border-color:var(--no); color:var(--no); font-weight:700; }
.error { color:var(--no); margin-top:8px; font-weight:600; }
.keys { color:var(--muted); font-size:13px; }
</style></head><body>
<header><span id="counter"></span><span id="threshold"></span></header>
<main>
<p class="hint">Чи це справді та сама деталь і чи дотримано правило рівня?</p>
<p class="hint"><b>same</b> — мають бути спільні слова із записом · <b>syn</b> — та сама деталь іншими словами, без слів запису · <b>desc</b> — деталь описано через ознаку чи наслідок</p>
<p class="keys">Клавіші: 1 — «Годиться», 2 — «Ні» для поточної картки (повторне натиснення скасовує), Tab — наступна картка.</p>
<div id="cards"></div>
</main>
<script>
const MAX_NO = __MAX_NO__;
const HINTS = {same:'мають бути спільні слова із записом', syn:'та сама деталь іншими словами, без слів запису', desc:'деталь описано через ознаку чи наслідок'};
let items = [], current = 0;
const cardsEl = document.getElementById('cards');

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function renderSummary() {
  const yes = items.filter(i => i.verdict === 'yes').length, no = items.filter(i => i.verdict === 'no').length;
  document.getElementById('counter').textContent = 'перевірено ' + (yes + no) + ' з ' + items.length + ' · годиться ' + yes + ' · ні ' + no;
  const t = document.getElementById('threshold'), failed = no > MAX_NO;
  t.textContent = failed ? 'понад ' + MAX_NO + ' «ні» — набір буде згенеровано заново' : 'набір проходить';
  t.className = failed ? 'fail' : 'ok';
}

function paint(card, item) {
  card.querySelector('button.yes').classList.toggle('on', item.verdict === 'yes');
  card.querySelector('button.no').classList.toggle('on', item.verdict === 'no');
  card.querySelector('button.yes').setAttribute('aria-pressed', item.verdict === 'yes');
  card.querySelector('button.no').setAttribute('aria-pressed', item.verdict === 'no');
}

async function choose(index, value) {
  const item = items[index], card = cardsEl.children[index];
  const next = item.verdict === value ? null : value;
  const old = card.querySelector('.error');
  if (old) old.remove();
  try {
    const r = await fetch('/verdict', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({index:index, verdict:next})});
    if (!r.ok) throw new Error('status ' + r.status);
    item.verdict = next;
    paint(card, item);
    renderSummary();
  } catch (e) {
    card.appendChild(el('div', 'error', 'Не вдалося зберегти вибір. Спробуйте ще раз.'));
  }
}

function setCurrent(index) {
  current = index;
  Array.from(cardsEl.children).forEach((c, i) => c.classList.toggle('current', i === index));
}

function build() {
  cardsEl.replaceChildren();
  items.forEach((item, index) => {
    const card = el('section', 'card');
    card.tabIndex = 0;
    card.appendChild(el('div', 'label', 'Запис (джерело)'));
    card.appendChild(el('p', 'record', item.record_text));
    card.appendChild(el('div', 'label', 'Рівень'));
    card.appendChild(el('div', 'level', item.level + (HINTS[item.level] ? ' — ' + HINTS[item.level] : '')));
    card.appendChild(el('div', 'label', 'Запит'));
    card.appendChild(el('p', 'query', item.text));
    const row = el('div', 'buttons');
    const yes = el('button', 'yes', 'Годиться'), no = el('button', 'no', 'Ні');
    yes.type = no.type = 'button';
    yes.addEventListener('click', () => { setCurrent(index); choose(index, 'yes'); });
    no.addEventListener('click', () => { setCurrent(index); choose(index, 'no'); });
    row.append(yes, no);
    card.appendChild(row);
    card.addEventListener('focusin', () => setCurrent(index));
    cardsEl.appendChild(card);
    paint(card, item);
  });
  const first = items.findIndex(i => i.verdict === null);
  setCurrent(first < 0 ? 0 : first);
  renderSummary();
}

document.addEventListener('keydown', async e => {
  if (e.ctrlKey || e.metaKey || e.altKey || (e.key !== '1' && e.key !== '2')) return;
  e.preventDefault();
  const index = current, value = e.key === '1' ? 'yes' : 'no';
  if (items[index].verdict !== value && index + 1 < items.length) {
    setCurrent(index + 1);
    cardsEl.children[index + 1].focus();
  }
  await choose(index, value);
});

fetch('/items').then(r => r.ok ? r.json() : Promise.reject(new Error('status ' + r.status))).then(data => {
  items = data.items;
  build();
}).catch(() => {
  cardsEl.replaceChildren(el('div', 'error', 'Не вдалося прочитати файл перевірки.'));
});
</script></body></html>
'''


def make_server(path: Path, port: int) -> ThreadingHTTPServer:
    path = Path(path)
    lock = threading.Lock()  # set_verdict is read-modify-write; fast clicks must not lose updates

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # no request logging
            pass

        def _send(self, status: int, body: bytes, content_type: str = 'application/json; charset=utf-8') -> None:
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode('utf-8'))

        def _allowed(self) -> bool:
            actual = self.server.server_address[1]
            origin = self.headers.get('Origin')
            if origin is not None and origin != f'http://127.0.0.1:{actual}':
                return False
            return self.headers.get('Host') in (None, f'127.0.0.1:{actual}', f'localhost:{actual}')

        def do_GET(self):
            if not self._allowed():
                return self._json(403, {'error': 'forbidden'})
            route = self.path.split('?', 1)[0]
            if route == '/':
                return self._send(200, PAGE.replace('__MAX_NO__', str(MAX_NO)).encode('utf-8'), 'text/html; charset=utf-8')
            if route == '/items':
                try:
                    data = json.loads(path.read_text(encoding='utf-8'))
                    raw = data['items']
                    items = [{'index': n, 'level': i['level'], 'record_text': i['record_text'], 'text': i['text'],
                              'verdict': i.get('verdict')} for n, i in enumerate(raw)]
                    summary = _summary(raw)
                except (OSError, ValueError, KeyError, TypeError, AttributeError):
                    return self._json(500, {'error': 'owner_check_missing'})
                return self._json(200, {'items': items, 'summary': summary})
            self._json(404, {'error': 'not_found'})

        def do_POST(self):
            try:  # drain the body first so early refusals do not reset the connection
                length = int(self.headers.get('Content-Length') or 0)
            except ValueError:
                length = -1
            raw = self.rfile.read(length) if 0 < length <= MAX_BODY else b''
            if not self._allowed():
                return self._json(403, {'error': 'forbidden'})
            if self.path.split('?', 1)[0] != '/verdict':
                return self._json(404, {'error': 'not_found'})
            try:
                body = json.loads(raw.decode('utf-8'))
                with lock:
                    summary = set_verdict(path, body['index'], body['verdict'])
            except (ValueError, KeyError, TypeError, OSError):
                return self._json(400, {'error': 'bad_verdict'})
            self._json(200, summary)

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dir', required=True, type=Path)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args(argv)
    path = args.dir / FILE_NAME
    if _inside_repo(path):
        print(json.dumps({'error': 'inside_repo'}))
        return 1
    try:
        json.loads(path.read_text(encoding='utf-8'))['items']
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({'error': 'owner_check_missing'}))
        return 1
    server = make_server(path, args.port)
    url = f'http://127.0.0.1:{server.server_address[1]}/'
    print(url, flush=True)
    if not args.no_browser:
        threading.Timer(0.3, webbrowser.open, (url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
