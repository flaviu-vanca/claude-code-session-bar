#!/usr/bin/env python3
"""Session Bar settings in the browser: drag elements between the card's places, pick a palette and the bars, and
watch the card change, drawn by session-bar.py itself on a sample session.

Run it in a terminal of its own:
  session-bar [port]    (installed by install.py), or python3 configure.py [port] from this folder
It serves configure-web.html on 127.0.0.1, opens it in the browser, and stops a few seconds after the page is closed
(Ctrl+C stops it at once). Save writes session-bar.json, which the card reads on its next run. Stdlib only, like the
card; nothing here reaches the model.
"""
import hmac
import importlib.util
import json
import os
import queue
import secrets
import shutil
import socketserver
import stat
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('sb', os.path.join(HERE, 'session-bar.py'))
sb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sb)
PAGE = os.path.join(HERE, 'configure-web.html')


def mine(path, kind):
    """Whether `path` is of `kind` itself (no symlink) and, on POSIX, this user's and not writable by everyone: what
    the page saves, another user could otherwise plant in a shared folder. Group-writable stays allowed: with a
    user-private group (umask 002) every file of one's own is."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return kind(st.st_mode) and (os.name == 'nt' or (st.st_uid == os.getuid() and not st.st_mode & 0o002))


def reads_layout(dot):
    """Whether this project's local status line hands the card its layout (install.py --scope project): otherwise a
    committed layout is the team's, not what this user's card draws, and editing it would change nothing on screen."""
    try:  # O_NONBLOCK and fstat, as the card reads a layout: a planted pipe cannot stall the page
        fd = os.open(os.path.join(dot, 'settings.local.json'), os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(fd, 'rb') as f:
            data = f.read(sb.MAX_CONFIG + 1) if stat.S_ISREG(os.fstat(fd).st_mode) else b''
        line = json.loads(data).get('statusLine') if 0 < len(data) <= sb.MAX_CONFIG else None
    except (OSError, ValueError, AttributeError):
        return False
    command = line.get('command') if isinstance(line, dict) else None
    return isinstance(command, str) and 'SESSION_BAR_CONFIG' in command and '/.claude/session-bar.json' in command


def layout_for(cwd, user_layout, home):
    """The layout that applies in `cwd`: the nearest project's .claude/session-bar.json, a regular file, found going
    up to home (home itself is not a project) or, outside home, to the root; else the user's."""
    d, home = os.path.realpath(cwd), os.path.realpath(home)  # macOS: /var is /private/var, and getcwd says the latter
    same = lambda a, b: os.path.normcase(a) == os.path.normcase(b)  # C:\Users\Ana is c:\users\ana on Windows
    under = same(d, home) or os.path.normcase(d).startswith(os.path.normcase(home) + os.sep)
    while not (under and same(d, home)):
        dot = os.path.join(d, '.claude')
        path = os.path.join(dot, 'session-bar.json')
        if mine(dot, stat.S_ISDIR) and mine(path, stat.S_ISREG) and reads_layout(dot):
            return path, 'project'
        if os.path.dirname(d) == d:
            break
        d = os.path.dirname(d)
    return user_layout, 'user'


SAVE, SCOPE = (sb.CONFIG, 'custom') if os.environ.get('SESSION_BAR_CONFIG') else layout_for(
    os.getcwd(), os.path.join(HERE, 'session-bar.json'), os.path.expanduser('~'))
MAX_BODY = 64 * 1024
LOCK = threading.Lock()  # use_palette sets the card's colours for the whole module

WHAT = {
    'model': "the model's name", 'effort': 'the effort level',
    'thinking': '"∴ thinking" while Claude works out its next step: thinks, then writes it',
    'style': 'the output style, when it is not the default', 'agent': 'the agent the session runs as (--agent)',
    'name': 'the session name set with /rename', 'version': "Claude Code's version", 'cost': "the session's cost",
    'time': "the session's wall time", 'api': 'the time spent waiting on the API', 'lines': 'lines added and removed',
    'clock': 'the time of day', 'cwd': 'the current folder',
    'repo': 'the repository and branch, a link to the branch on origin; ⇡ ahead of origin, ⇣ behind, ⇅ apart',
    'session': 'the session id', 'worktree': 'the worktree the session runs in', 'dirs': 'folders added with /add-dir',
    'mem': 'memory in use', 'disks': 'how full /tmp and ~/.cache are', 'load': 'the 1-minute load, coloured by CPU count',
    'battery': 'the battery charge, + while charging',
    'ctx': 'the context used, of the window', '5h': 'the 5-hour limit and when it resets',
    'week': 'the weekly limit and when it resets', 'spend': 'the spend limit (on a gateway only)',
    'hits': 'the prompt cache hit ratio: green is good',
    'cloud': 'this CLI drives a cloud or remote session', 'rc': 'Remote Control is on, as a link',
    'mode': 'the permission mode (Claude Code shows it under the card too)',
    'no_transcript': 'started with transcript saving off', 'update': 'a newer Claude Code is downloaded: restart',
    'cache': 'the prompt cache is about to expire, or is cold; in brackets what the next request costs then',
    'miss': 'the prompt cache missed in the last 5 minutes, and why', 'big': 'the context is past 200k tokens',
    'idle': 'Claude Code\'s "new task? /clear" hint: idle 75 minutes with 100k tokens or more; set '
            'CLAUDE_CODE_IDLE_TOKEN_THRESHOLD high where claude starts to keep only this one',
    'drafts': 'feedback drafts waiting (Claude Code shows them under the card too)', 'sandbox': 'the sandbox is on',
    'working': 'a turn is running', 'pr': "the branch's pull request and its review", 'fast': 'fast mode is on',
    'vim': 'the vim mode, when not NORMAL'}
NOW = time.time()
# a session where every element has something to show
SAMPLE = {'session_id': '804d5fae-3e29', 'session_name': 'skin work', 'version': '2.1.302',
          'model': {'id': 'claude-opus-5-5'}, 'effort': {'level': 'xhigh'}, 'thinking': {'enabled': True},
          'output_style': {'name': 'Explanatory'}, 'agent': {'name': 'reviewer'}, 'remote': {'session_id': 'x'},
          'workspace': {'current_dir': HERE, 'added_dirs': ['/srv/data']}, 'worktree': {'name': 'feat-ui'},
          'cost': {'total_cost_usd': 73.50, 'total_duration_ms': 24_120_000, 'total_api_duration_ms': 5_400_000,
                   'total_lines_added': 412, 'total_lines_removed': 96},
          'context_window': {'total_input_tokens': 383_000, 'context_window_size': 1_000_000, 'used_percentage': 38},
          'exceeds_200k_tokens': True, 'fast_mode': True, 'vim': {'mode': 'INSERT'},
          'rate_limits': {'five_hour': {'used_percentage': 19, 'resets_at': NOW + 5640},
                          'seven_day': {'used_percentage': 68, 'resets_at': NOW + 439_000},
                          'spend_limit': {'used_percentage': 30, 'resets_at': NOW + 86_400, 'used_usd': 15, 'limit_usd': 50}},
          'prompt_cache': {'warm': True, 'expires_at': NOW + 75, 'hit_ratio': 0.92, 'recache_tokens_if_cold': 383_000,
                           'last_miss_at': NOW - 60, 'last_miss_cause': {'causes': ['ttl_expired_5m']}},
          'pr': {'number': 12, 'url': 'https://github.com/o/r/pull/12', 'review_state': 'approved'}}
STATES = {'rc': 'session_01X', 'busy': True, 'newest': '2.1.303', 'no_transcript': True, 'sandbox': True,
          'mode': 'auto', 'drafts': 3, 'idle': True}


def save(cfg, path):
    """Writes the settings whole: a temporary file renamed over the old, so the card never reads half of one. The
    temporary file gets a fresh name (mkstemp), so one planted in a project's .claude is never written through, and
    the folder is checked again now: one swapped for a symlink since the page opened is refused.
    shortcut: a check, then a write; a writer racing in between needs write access to the project folder already,
    upgrade to dir_fd writes if that ever matters."""
    folder = os.path.dirname(path) or '.'
    if not mine(folder, stat.S_ISDIR) or (os.path.lexists(path) and not mine(path, stat.S_ISREG)):
        raise ValueError(f'{path} is not a layout of this user\'s in a folder of their own; not saved')
    fd, tmp = tempfile.mkstemp(dir=folder, prefix='.session-bar-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump({k: cfg[k] for k in sb.DEFAULT}, f, indent=2)
            f.write('\n')
            if hasattr(os, 'fchmod'):  # on the open file, not by name: no symlink can be slipped in between
                os.fchmod(f.fileno(), 0o644)
            else:
                os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def clean(raw):
    """Settings from the page, through the card's own loader: unknown or misplaced elements are dropped."""
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(raw if isinstance(raw, dict) else {}, f)
    try:
        return sb.load_config(f.name)
    finally:
        os.unlink(f.name)


def sample():
    """The sample session, its clocks moved to now."""
    d = json.loads(json.dumps(SAMPLE))
    shift = time.time() - NOW
    for w in d['rate_limits'].values():
        w['resets_at'] += shift
    d['prompt_cache']['expires_at'] += shift
    d['prompt_cache']['last_miss_at'] += shift
    return d


def states(rc):
    return {**STATES, 'rc': STATES['rc'] if rc else None}


def host():
    """This machine, for the sample session, which is mid-step: Claude works out its next one, so "thinking" shows."""
    return {**sb.host(HERE), 'thinking': True}


def plain(pieces):
    return [[t, rgb, dim, bold] for t, rgb, dim, bold, _ in pieces]


def render(cfg, columns, rc, d):
    """The card for a terminal `columns` wide, as the footer would hold it."""
    with LOCK:
        sb.use_palette(cfg['palette'])
        now, width = time.time(), sb.card_width(columns, rc)
        lines = sb.card(d, width, now, host(), cfg['meter'], sb.chips(d, states(rc), now, cfg['edge']), cfg)
    return {'width': width, 'lines': [plain(line) for line in lines]}


def alone(cfg, names, d, now, h):
    """One row holding `names`, drawn by the card at full length, without its frame."""
    one = {**cfg, 'top_left': [], 'top_right': [], 'rows': [names], 'edge': []}
    return sb.card(d, 240, now, h, cfg['meter'], [], one)[1][1:-2]


def previews(cfg, d):
    """Every element as the card draws it on the sample, for the page's tiles."""
    with LOCK:
        sb.use_palette(cfg['palette'])
        now, h = time.time(), host()
        out = {name: plain(alone(cfg, [name], d, now, h)) for name in sb.TEXT + sb.METERS}
        for name in sb.CHIPS:
            g = sb.chips(d, states(True), now, [name])
            out[name] = plain(g[0]) if g else []
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
        return self.ended or now - self.last > (self.quiet if self.seen else self.first)

    def end(self):
        """For good: no ping or goodbye undoes it, and the session is void at once."""
        self.ended = True
        Handler.session = ''

    ended = False


def peer_uid(client_port, server_port, table='/proc/net/tcp'):
    """The user owning the client end of a loopback connection, from /proc/net/tcp (Linux): the one row whose local
    end is 127.0.0.1:client_port and remote end 127.0.0.1:server_port, or None (none, several, unreadable)."""
    want = f'0100007F:{client_port:04X}', f'0100007F:{server_port:04X}'  # 127.0.0.1, as the kernel prints it
    try:
        with open(table) as f:
            rows = [line.split() for line in f.readlines()[1:]]
        found = [int(r[7]) for r in rows if len(r) > 7 and (r[1], r[2]) == want]
    except (OSError, ValueError):
        return None
    return found[0] if len(found) == 1 else None


OPENING = threading.Lock()  # the token is checked and spent in one step: two requests cannot both spend it


class Handler(BaseHTTPRequestHandler):
    # token: in the address's fragment (#t=), which the page spends once on /api/open for the session it then sends
    # as X-Session. Another user of the machine can reach 127.0.0.1 and read the browser's command line (ps): on
    # Linux the token is taken only from this user's connections, and a second use anywhere ends the server. A
    # header, unlike a cookie, never goes to another port of 127.0.0.1.
    hosts, life, token, session, spent = set(), None, '', '', ''

    def send(self, code, body, kind='application/json', headers=()):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def here(self):
        """This machine's page: the Host (against DNS rebinding) and, on a POST, the Origin. Sets self.route."""
        self.route = self.path.partition('?')[0]
        return trusted(self.headers.get('Host', ''), self.headers.get('Origin'), self.command, self.hosts)

    def authed(self):
        held = self.headers.get('X-Session', '')
        return bool(self.session) and hmac.compare_digest(held.encode(), self.session.encode())

    def open_page(self, body):
        """The page's first request: the address's token, spent once, for the session."""
        given = body.get('t') if isinstance(body.get('t'), str) else ''
        if sys.platform.startswith('linux') and peer_uid(self.client_address[1], self.server.server_address[1]) != os.getuid():
            return self.send(403, {'error': 'forbidden'})
        with OPENING:
            if Handler.token and hmac.compare_digest(given.encode(), Handler.token.encode()):
                Handler.spent, Handler.token = Handler.token, ''
                return self.send(200, {'session': Handler.session})
            if Handler.spent and hmac.compare_digest(given.encode(), Handler.spent.encode()):
                self.life.end()  # someone else spent it first: their session ends with the server
                return self.send(409, {'error': 'This address was opened somewhere else first, so the settings '
                                                'server stopped. Run session-bar again.'})
        return self.send(403, {'error': 'forbidden'})

    def do_GET(self):
        if not self.here():
            return self.send(403, {'error': 'forbidden'})
        if self.route == '/':  # the page holds no secret: its session comes from /api/open
            with open(PAGE, 'rb') as f:
                return self.send(200, f.read(), 'text/html; charset=utf-8')
        if not self.authed():
            return self.send(403, {'error': 'forbidden'})
        if self.route == '/api/state':
            return self.send(200, {'cfg': sb.load_config(SAVE), 'places': sb.PLACES, 'what': WHAT,
                                   'kinds': {'text': sb.TEXT, 'meter': sb.METERS, 'chip': sb.CHIPS},
                                   'palettes': sb.PALETTES, 'columns': shutil.get_terminal_size((160, 24)).columns,
                                   'file': SAVE, 'scope': SCOPE})
        self.send(404, {'error': 'not found'})

    def do_POST(self):
        if not self.here() or (self.route != '/api/open' and not self.authed()):
            return self.send(403, {'error': 'forbidden'})
        if self.route == '/api/bye':  # as the page closes: no body worth reading
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
        if self.route == '/api/open':
            return self.open_page(body)
        self.life.ping(time.time())
        if self.route == '/api/ping':
            return self.send(200, {})
        cfg = clean(body.get('cfg'))
        if self.route == '/api/render':
            columns = body.get('columns')
            columns = max(30, min(300, columns)) if isinstance(columns, int) and not isinstance(columns, bool) else 160
            d = sample()
            return self.send(200, {'cfg': cfg, **render(cfg, columns, body.get('rc') is True, d),
                                   'previews': previews(cfg, d)})
        if self.route == '/api/save':
            try:
                save(cfg, SAVE)
            except (OSError, ValueError) as e:
                return self.send(500, {'error': str(e)})
            return self.send(200, {'cfg': cfg, 'path': SAVE})
        self.send(404, {'error': 'not found'})

    def log_message(self, *a):
        pass


class Server(ThreadingHTTPServer):
    def server_bind(self):
        """HTTPServer's own, without its socket.getfqdn(): a reverse DNS lookup that can take seconds on macOS,
        longer than the launcher waits for the server to say it listens."""
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


def make_server(port, life):
    server = Server(('127.0.0.1', port), Handler)
    port = server.server_address[1]
    Handler.hosts, Handler.life = {f'127.0.0.1:{port}', f'localhost:{port}'}, life
    Handler.token, Handler.session, Handler.spent = secrets.token_urlsafe(24), secrets.token_urlsafe(24), ''
    return server


# what the server keeps of its environment, whatever launcher started it (install.PAGE_ENV, the same; a test checks)
PAGE_ENV = ['HOME', 'USERPROFILE', 'SYSTEMROOT', 'COLUMNS', 'CLAUDE_CONFIG_DIR', 'XDG_DATA_HOME',
            'CLAUDE_CODE_SKIP_PROMPT_HISTORY', 'CLAUDE_CODE_IDLE_THRESHOLD_MINUTES', 'CLAUDE_CODE_IDLE_TOKEN_THRESHOLD',
            'PATH', 'DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'XDG_RUNTIME_DIR', 'XDG_CURRENT_DESKTOP',
            'DBUS_SESSION_BUS_ADDRESS', 'BROWSER', 'TMPDIR', 'TEMP', 'TMP']


BROWSER_WAIT = 5  # seconds the launcher waits for the browser to say it opened, before it prints the address


def detach(port):
    """Starts the server in a process of its own and returns. The server says first that it listens (its address),
    then whether a browser opened; the address is printed unless one did, so `! session-bar` in Claude Code adds next
    to nothing to the conversation. A browser slow to answer (osascript on a busy Mac, a console browser) gets
    BROWSER_WAIT seconds, then the address is printed anyway."""
    kw = {'creationflags': 0x8 | 0x200} if os.name == 'nt' else {'start_new_session': True}  # DETACHED, NEW_GROUP
    env = {k: v for k, v in os.environ.items() if k in PAGE_ENV}  # a .cmd launcher has no env -i: keys stop here
    child = subprocess.Popen([sys.executable, '-I', '-S', os.path.abspath(__file__), '--serve', str(port)],
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, **kw)
    said, errors = queue.Queue(), []

    def hear():
        for line in child.stdout:
            said.put(line.decode(errors='replace').strip())
        said.put(None)  # the end: the server is gone

    threading.Thread(target=hear, daemon=True).start()
    reading = threading.Thread(target=lambda: errors.extend(child.stderr.read().decode(errors='replace').splitlines()),
                               daemon=True)  # the server sends its errors here until it listens, then to devnull
    reading.start()
    try:
        listening = said.get(timeout=10)
    except queue.Empty:
        listening = ''
    if not listening:
        try:
            code = child.wait(timeout=1)
        except subprocess.TimeoutExpired:
            print('The settings page did not answer within 10 s.')
            return 1
        reading.join(1)
        print(f'The settings page did not start (exit {code}): {errors[-1] if errors else "no message"}')
        return 1
    try:
        browsed = said.get(timeout=BROWSER_WAIT)
    except queue.Empty:
        browsed = ''
    if browsed != 'opened':
        print(listening)
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[0] if argv and argv[0] in ('--detach', '--serve') else None
    rest = argv[1:] if mode else argv
    port = int(rest[0]) if rest else 0
    if mode == '--detach':
        return detach(port)
    life = Life(time.time())
    server = make_server(port, life)
    url = f'http://127.0.0.1:{server.server_address[1]}/#t={Handler.token}'

    def watch():
        while not life.over(time.time()):
            time.sleep(1)
        server.shutdown()

    threading.Thread(target=watch, daemon=True).start()
    serving = threading.Thread(target=server.serve_forever, daemon=True)  # before the browser: a console one blocks
    serving.start()
    if mode == '--serve':  # two lines to the launcher, then nothing: a browser it starts writes to devnull, not to it
        out, devnull = os.dup(1), os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 1)
        os.write(out, f'Session Bar settings ({SCOPE}: {SAVE}): {url}\n'.encode())
        os.dup2(devnull, 2)  # listening: errors from here on would land in a pipe no one reads
        browsed = 'opened' if webbrowser.open(url) else 'no browser'
        try:
            os.write(out, f'{browsed}\n'.encode())
        except OSError:  # the launcher stopped waiting
            pass
        os.close(out)
    else:
        print(f'Session Bar settings: {url}\nIt stops a few seconds after the page closes; Ctrl+C stops it now.', flush=True)
        webbrowser.open(url)
    try:
        while serving.is_alive():  # join() with a timeout, so Ctrl+C reaches this thread
            serving.join(0.5)
    except KeyboardInterrupt:
        server.shutdown()
    finally:
        server.server_close()


if __name__ == '__main__':
    sys.exit(main())
