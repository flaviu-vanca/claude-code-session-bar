#!/usr/bin/env python3
"""Session Bar settings in the browser: drag elements between the card's places, pick a palette and the bars, and
watch the card change, drawn by session-bar.py itself on a sample session whose meters you can move.

Run it in a terminal of its own:
  python3 ~/claude-skin/configure-web.py [port]
It serves the page on 127.0.0.1, opens it in the browser, and stops a few seconds after the page is closed (Ctrl+C
stops it at once). Save writes session-bar.json, which the card reads on its next run. Stdlib only, like the card;
nothing here reaches the model.
"""
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('configure', os.path.join(HERE, 'configure.py'))
cf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cf)
sb = cf.sb
PAGE = os.path.join(HERE, 'configure-web.html')
SAVE = sb.CONFIG
MAX_BODY = 64 * 1024
LOCK = threading.Lock()  # use_palette sets the card's colours for the whole module


def clean(raw):
    """Settings from the page, through the card's own loader: unknown or misplaced elements are dropped."""
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(raw if isinstance(raw, dict) else {}, f)
    try:
        return sb.load_config(f.name)
    finally:
        os.unlink(f.name)


def sample(knobs):
    """configure.py's sample session, its clocks moved to now, with the page's ctx, 5h and week (0-100) if given."""
    d = json.loads(json.dumps(cf.SAMPLE))
    shift = time.time() - cf.NOW
    for w in d['rate_limits'].values():
        w['resets_at'] += shift
    d['prompt_cache']['expires_at'] += shift
    knobs = knobs if isinstance(knobs, dict) else {}

    def pct(key, now):
        v = knobs.get(key)
        return max(0, min(100, v)) if isinstance(v, (int, float)) and not isinstance(v, bool) else now

    cw = d['context_window']
    cw['used_percentage'] = pct('ctx', cw['used_percentage'])
    cw['total_input_tokens'] = round(cw['used_percentage'] / 100 * cw['context_window_size'])
    for key, window in (('5h', 'five_hour'), ('week', 'seven_day')):
        d['rate_limits'][window]['used_percentage'] = pct(key, d['rate_limits'][window]['used_percentage'])
    return d


def states(rc):
    return {**cf.STATES, 'rc': cf.STATES['rc'] if rc else None}


def plain(pieces):
    return [[t, rgb, dim, bold] for t, rgb, dim, bold, _ in pieces]


def render(cfg, columns, rc, d):
    """The card for a terminal `columns` wide, as the footer would hold it."""
    with LOCK:
        sb.use_palette(cfg['palette'])
        now, width = time.time(), sb.card_width(columns, rc)
        lines = sb.card(d, width, now, sb.host(HERE), cfg['meter'], sb.chips(d, states(rc), now, cfg['edge']), cfg)
    return {'width': width, 'lines': [plain(line) for line in lines]}


def alone(cfg, names, d, now, h):
    """One row holding `names`, drawn by the card at full length, without its frame."""
    one = {**cfg, 'top_left': [], 'top_right': [], 'rows': [names], 'edge': []}
    return sb.card(d, 240, now, h, cfg['meter'], [], one)[1][1:-2]


def previews(cfg, d):
    """Every element as the card draws it on the sample, for the page's tiles."""
    with LOCK:
        sb.use_palette(cfg['palette'])
        now, h = time.time(), sb.host(HERE)
        out = {name: plain(alone(cfg, [name], d, now, h)) for name in sb.TEXT + sb.METERS}
        for name in sb.CHIPS:
            g = sb.chips(d, states(True), now, [name])
            out[name] = plain(g[0]) if g else []
    return out


def palette_rows(cfg, d):
    """The meters row in each palette, for the palette cards."""
    with LOCK:
        now, h, out = time.time(), sb.host(HERE), {}
        for name in sb.PALETTES:
            sb.use_palette(name)
            out[name] = plain(alone(cfg, ['ctx', '5h', 'week'], d, now, h))
    return out


def trusted(host, origin, method, hosts):
    """Only this machine's page: the Host header (against DNS rebinding) and, on a POST, the Origin."""
    return host in hosts and (method == 'GET' or origin in (None, f'http://{host}'))


class Life:
    """Whether the page is gone: no ping for 2.5 min once it has pinged (a background tab's timers run once a minute),
    5 min before it first does (time to open the address by hand), and a few seconds after it says goodbye, so a
    reload keeps the server."""

    def __init__(self, now, quiet=150, first=300, grace=4):
        self.last, self.quiet, self.first, self.grace, self.seen = now, quiet, first, grace, False

    def ping(self, now):
        self.last, self.seen = now, True

    def bye(self, now):
        self.last, self.seen = now - self.quiet + self.grace, True

    def over(self, now):
        return now - self.last > (self.quiet if self.seen else self.first)


class Handler(BaseHTTPRequestHandler):
    hosts, life = set(), None

    def send(self, code, body, kind='application/json'):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def ok(self):
        return trusted(self.headers.get('Host', ''), self.headers.get('Origin'), self.command, self.hosts)

    def do_GET(self):
        if not self.ok():
            return self.send(403, {'error': 'forbidden'})
        if self.path == '/':
            with open(PAGE, 'rb') as f:
                return self.send(200, f.read(), 'text/html; charset=utf-8')
        if self.path == '/api/state':
            return self.send(200, {'cfg': sb.load_config(SAVE), 'default': clean(sb.DEFAULT), 'saveTo': SAVE,
                                   'kinds': {'text': sb.TEXT, 'meter': sb.METERS, 'chip': sb.CHIPS},
                                   'places': sb.PLACES, 'what': cf.WHAT, 'palettes': sb.PALETTES,
                                   'columns': sb.terminal_columns() or 160})
        self.send(404, {'error': 'not found'})

    def do_POST(self):
        if not self.ok():
            return self.send(403, {'error': 'forbidden'})
        if self.path == '/api/bye':  # sendBeacon, as the page closes: text/plain, no body worth reading
            self.life.bye(time.time())
            return self.send(200, {})
        size = int(self.headers.get('Content-Length') or 0)
        if self.headers.get('Content-Type') != 'application/json' or not 0 < size <= MAX_BODY:
            return self.send(400, {'error': 'bad request'})
        try:
            body = json.loads(self.rfile.read(size))
        except ValueError:
            return self.send(400, {'error': 'bad json'})
        body = body if isinstance(body, dict) else {}
        self.life.ping(time.time())
        if self.path == '/api/ping':
            return self.send(200, {})
        cfg = clean(body.get('cfg'))
        if self.path == '/api/render':
            columns = body.get('columns')
            columns = max(30, min(300, columns)) if isinstance(columns, int) and not isinstance(columns, bool) else 160
            d = sample(body.get('sample'))
            return self.send(200, {'cfg': cfg, **render(cfg, columns, body.get('rc') is True, d),
                                   'previews': previews(cfg, d), 'palettes': palette_rows(cfg, d)})
        if self.path == '/api/save':
            cf.save(cfg, SAVE)
            return self.send(200, {'cfg': cfg, 'path': SAVE})
        self.send(404, {'error': 'not found'})

    def log_message(self, *a):
        pass


def make_server(port, life):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    port = server.server_address[1]
    Handler.hosts, Handler.life = {f'127.0.0.1:{port}', f'localhost:{port}'}, life
    return server


def main():
    life = Life(time.time())
    server = make_server(int(sys.argv[1]) if len(sys.argv) > 1 else 0, life)
    url = f'http://127.0.0.1:{server.server_address[1]}/'

    def watch():
        while not life.over(time.time()):
            time.sleep(1)
        server.shutdown()

    threading.Thread(target=watch, daemon=True).start()
    print(f'Session Bar settings: {url}\nIt stops a few seconds after the page closes; Ctrl+C stops it now.', flush=True)
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
