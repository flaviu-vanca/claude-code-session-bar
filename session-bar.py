#!/usr/bin/env python3
"""Session Bar: Claude Code's status line as a rounded card with segmented, heat-coloured meters.

Claude Code runs it on each update with the session as JSON on stdin and draws what it prints.
No model call, no network and no hook: a few small file reads and one statvfs per disk.
The bottom edge carries the footer's states while they are on: /rc, events that ask for something, steady states.
What each place shows, in what order, comes from session-bar.json beside this script (SESSION_BAR_CONFIG overrides
the path); without it the card is drawn with DEFAULT. Nothing here reaches the model, so no element costs tokens.
Options: --meter N, the meters' longest length in cells (3 to 30), over the settings' "meter".
"""
import fcntl
import json
import os
import re
import struct
import sys
import termios
import time

# The card's colours, one set per palette: accent is the model's name; edge the frame, visible on a dark terminal
# and quieter than the text; empty a meter's unfilled segments; green to red the heat; purple, blue, teal the dark
# theme's merged, ide and planMode. "default" is the card as it was first drawn.
PALETTES = {
    'default': {'accent': (217, 119, 87), 'edge': (92, 92, 92), 'empty': (74, 74, 85), 'green': (63, 185, 80),
                'yellow': (227, 179, 65), 'orange': (240, 136, 62), 'red': (248, 81, 73), 'purple': (175, 135, 255),
                'blue': (71, 130, 200), 'teal': (72, 150, 140)},
    'nord': {'accent': (136, 192, 208), 'edge': (76, 86, 106), 'empty': (59, 66, 82), 'green': (163, 190, 140),
             'yellow': (235, 203, 139), 'orange': (208, 135, 112), 'red': (191, 97, 106), 'purple': (180, 142, 173),
             'blue': (129, 161, 193), 'teal': (143, 188, 187)},
    'dracula': {'accent': (189, 147, 249), 'edge': (98, 114, 164), 'empty': (68, 71, 90), 'green': (80, 250, 123),
                'yellow': (241, 250, 140), 'orange': (255, 184, 108), 'red': (255, 85, 85), 'purple': (255, 121, 198),
                'blue': (139, 233, 253), 'teal': (139, 233, 253)},
    'gruvbox': {'accent': (254, 128, 25), 'edge': (102, 92, 84), 'empty': (60, 56, 54), 'green': (184, 187, 38),
                'yellow': (250, 189, 47), 'orange': (254, 128, 25), 'red': (251, 73, 52), 'purple': (211, 134, 155),
                'blue': (131, 165, 152), 'teal': (142, 192, 124)},
    'tokyo': {'accent': (122, 162, 247), 'edge': (86, 95, 137), 'empty': (59, 66, 97), 'green': (158, 206, 106),
              'yellow': (224, 175, 104), 'orange': (255, 158, 100), 'red': (247, 118, 142), 'purple': (187, 154, 247),
              'blue': (125, 207, 255), 'teal': (115, 218, 202)},
    'mono': {'accent': (238, 238, 238), 'edge': (92, 92, 92), 'empty': (58, 58, 58), 'green': (140, 140, 140),
             'yellow': (180, 180, 180), 'orange': (215, 215, 215), 'red': (255, 255, 255), 'purple': (200, 200, 200),
             'blue': (170, 170, 170), 'teal': (150, 150, 150)}}


def use_palette(name):
    """Paints the card with palette `name` from now on; an unknown name gets the default."""
    global ACCENT, EDGE, EMPTY, GREEN, YELLOW, ORANGE, RED, PURPLE, BLUE, TEAL, HEAT, MODES
    p = PALETTES.get(name, PALETTES['default'])
    ACCENT, EDGE, EMPTY, GREEN, YELLOW, ORANGE, RED, PURPLE, BLUE, TEAL = (
        p[k] for k in ('accent', 'edge', 'empty', 'green', 'yellow', 'orange', 'red', 'purple', 'blue', 'teal'))
    HEAT = [(0.0, GREEN), (0.6, YELLOW), (0.85, ORANGE), (1.0, RED)]
    # the permission modes as the native footer pill words them: glyph, words, colour; the default mode shows none
    MODES = {'auto': ('⏵⏵', 'auto mode', YELLOW), 'acceptEdits': ('⏵⏵', 'accept edits', PURPLE),
             'plan': ('⏸', 'plan mode', TEAL), 'bypassPermissions': ('⏵⏵', 'bypass permissions', RED),
             'dontAsk': ('⏵⏵', "don't ask", RED)}


use_palette('default')
CACHE_SOON = 120  # seconds of prompt cache left under which the card warns
VERSION = re.compile(r'^\d+(\.\d+)+$')
DISKS = ['/tmp', '~/.cache']  # the tmpfs and the scratch disk
FOOTER_PADDING = 2  # columns Claude Code's footer row keeps on each side of the status line (oQe); its notes wrap below
CONFIG = os.environ.get('SESSION_BAR_CONFIG') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'session-bar.json')
# what each place can hold: text on the top edge, anything but chips on a row, chips on the bottom edge
TEXT = ['model', 'effort', 'thinking', 'style', 'agent', 'name', 'version', 'cost', 'time', 'api', 'lines', 'clock',
        'repo', 'cwd', 'session', 'worktree', 'dirs', 'mem', 'disks', 'load', 'battery']
METERS = ['ctx', '5h', 'week', 'spend', 'hits']
CHIPS = ['cloud', 'rc', 'mode', 'no_transcript', 'update', 'cache', 'big', 'drafts', 'sandbox', 'working', 'pr', 'fast', 'vim']
PLACES = {'top_left': TEXT, 'top_right': TEXT, 'rows': TEXT + METERS, 'edge': CHIPS}
DEFAULT = {'top_left': ['model', 'effort'], 'top_right': ['cost', 'time'],
           'rows': [['ctx', '5h', 'week'], ['repo', 'cwd', 'session', 'mem', 'disks']],
           'edge': ['cloud', 'rc', 'no_transcript', 'update', 'cache', 'sandbox', 'working', 'pr', 'fast', 'vim'],
           'meter': 10, 'palette': 'default'}


def heat(t):
    """Green, yellow, orange, red as `t` goes from 0 to 1."""
    x = max(0.0, min(1.0, t))
    i = 1
    while i < len(HEAT) - 1 and x > HEAT[i][0]:
        i += 1
    (a, ca), (b, cb) = HEAT[i - 1], HEAT[i]
    k = (x - a) / (b - a)
    return tuple(round(u + (v - u) * k) for u, v in zip(ca, cb))


# A piece of a row: its text, its look and an optional link. Every glyph used is one cell wide.
def P(t, rgb=None, dim=False, bold=False, link=None):
    return (t, rgb, dim, bold, link)


def cells(row):
    return sum(len(p[0]) for p in row)


def paint(row):
    out = ['\x1b[0m']  # Claude Code wraps each status line in dim; this card sets its own dim and bright
    for t, rgb, dim, bold, link in row:
        code = ('1;' if bold else '') + ('2;' if dim else '') + (f'38;2;{rgb[0]};{rgb[1]};{rgb[2]}' if rgb else '')
        s = f'\x1b[{code.rstrip(";")}m{t}\x1b[0m' if code else t
        out.append(f'\x1b]8;;{link}\x1b\\{s}\x1b]8;;\x1b\\' if link else s)
    return ''.join(out)


def clip(row, n):
    """The first `n` cells of a row."""
    out = []
    for p in row:
        if n <= 0:
            break
        out.append(p if len(p[0]) <= n else (p[0][:n],) + p[1:])
        n -= len(p[0])
    return out


def join(groups):
    """Groups of pieces in one row, a dim dot between them."""
    return [p for i, g in enumerate(groups) for p in ([P(' · ', dim=True)] if i else []) + g]


def safe(f, *a):
    """f(*a), or no pieces when a payload field of another shape breaks it: it costs that element, not the card."""
    try:
        return f(*a)
    except (TypeError, AttributeError, ValueError, KeyError, IndexError):
        return []


def first_fit(rows, n):
    """The first of `rows` at most `n` cells wide, else the last one cut to `n`."""
    row = []
    for row in rows:
        if cells(row) <= n:
            return row
    return clip(row, n)


def model_name(mid, display):
    """claude-opus-5-5 as people say it: Opus 5.5."""
    m = re.match(r'^claude-([a-z]+)-(\d+)(?:-(\d{1,2}))?(?:-\d{8})?(\[1m\])?$', mid or '', re.I)
    if m:
        return f"{m[1][0].upper()}{m[1][1:]} {m[2]}{'.' + m[3] if m[3] else ''}{' 1M' if m[4] else ''}"
    return display or mid or '?'


def tokens(n):
    if n >= 1_000_000:
        return f'{n / 1_000_000:.1f}'.rstrip('0').rstrip('.') + 'M'
    return f'{round(n / 1000)}k' if n >= 1000 else str(n)


def duration(ms):
    m = max(0, int(ms // 60000))
    if m < 60:
        return f'{m}m'
    h = m // 60
    return f'{h}h{m % 60}m' if h < 48 else f'{h // 24}d{h % 24}h'


def tilde(path, home):
    return '~' + path[len(home):] if home and (path == home or path.startswith(home + '/')) else path


def card_width(columns):
    """The card's width: the footer's, the terminal less its padding on both sides; 30 at the least."""
    return max(30, columns - 2 * FOOTER_PADDING)


def terminal_columns():
    """The terminal's width: Claude Code's own terminal, found up the process tree (this has none)."""
    pid = os.getppid()
    for _ in range(8):
        for fd in (0, 1, 2):
            try:
                path = os.readlink(f'/proc/{pid}/fd/{fd}')
            except OSError:
                continue
            if path.startswith('/dev/pts/') or path.startswith('/dev/tty'):
                try:
                    tty = os.open(path, os.O_RDONLY | os.O_NOCTTY)
                    try:
                        return struct.unpack('HHHH', fcntl.ioctl(tty, termios.TIOCGWINSZ, b'\0' * 8))[1]
                    finally:
                        os.close(tty)
                except OSError:
                    pass
        try:
            with open(f'/proc/{pid}/stat') as f:
                pid = int(f.read().rsplit(')', 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
        if pid <= 1:
            break
    return int(os.environ.get('COLUMNS') or 120)


def git_info(cwd):
    """The repository's folder name and branch, read from .git without running git."""
    d = cwd
    while d and d != '/':
        dot = os.path.join(d, '.git')
        if os.path.exists(dot):
            try:
                gitdir = dot
                if os.path.isfile(dot):  # a worktree or a submodule: "gitdir: <path>"
                    with open(dot) as f:
                        line = f.read().strip()
                    gitdir = os.path.join(d, line[8:]) if line.startswith('gitdir: ') else dot
                with open(os.path.join(gitdir, 'HEAD')) as f:
                    head = f.read().strip()
            except OSError:
                head = ''
            return os.path.basename(d), head[16:] if head.startswith('ref: refs/heads/') else head[:7]
        d = os.path.dirname(d)
    return None, None


def host(project):
    info = {'disks': [], 'sandbox': False}
    try:
        mem = {}
        with open('/proc/meminfo') as f:
            for line in f:
                k, v = line.split(':', 1)
                mem[k] = int(v.split()[0])
        info['mem'] = ((mem['MemTotal'] - mem['MemAvailable']) / 2**20, mem['MemTotal'] / 2**20)
    except (OSError, KeyError, ValueError):
        pass
    for mount in DISKS:
        try:
            s = os.statvfs(os.path.expanduser(mount))
            used = s.f_blocks - s.f_bfree
            info['disks'].append((mount, round(100 * used / max(1, used + s.f_bavail))))
        except OSError:
            pass
    try:
        info['load'] = (os.getloadavg()[0], os.cpu_count() or 1)
    except OSError:
        pass
    info['battery'] = battery()
    # the sandbox setting as Claude Code layers it: the user's, the project's, the project's local one
    for path in ('~/.claude/settings.json', f'{project}/.claude/settings.json', f'{project}/.claude/settings.local.json'):
        try:
            with open(os.path.expanduser(path)) as f:
                enabled = (json.load(f).get('sandbox') or {}).get('enabled')
        except (OSError, ValueError, AttributeError):
            continue
        if enabled is not None:
            info['sandbox'] = bool(enabled)
    return info


def battery(root='/sys/class/power_supply'):
    """The first battery's charge in percent and whether it is charging; None on a machine without one."""
    try:
        name = min(n for n in os.listdir(root) if n.startswith('BAT'))
        with open(os.path.join(root, name, 'capacity')) as f:
            pct = int(f.read())
        with open(os.path.join(root, name, 'status')) as f:
            return pct, f.read().strip() == 'Charging'
    except (OSError, ValueError):
        return None


def load_config(path):
    """The card's settings from `path`: the edges' elements, the rows' elements, each in order, the meters' length
    and the palette. A setting missing, misspelt or of another type keeps its default; an unknown element is
    skipped, a repeated one kept once in its place."""
    try:
        with open(path) as f:
            raw = json.load(f)
    except (OSError, ValueError):
        raw = {}
    raw = raw if isinstance(raw, dict) else {}
    keep = lambda names, known: list(dict.fromkeys(x for x in names if x in known))
    cfg = {'top_left': list(DEFAULT['top_left']), 'top_right': list(DEFAULT['top_right']),
           'rows': [list(r) for r in DEFAULT['rows']], 'edge': list(DEFAULT['edge'])}
    for place in ('top_left', 'top_right', 'edge'):
        if isinstance(raw.get(place), list):
            cfg[place] = keep(raw[place], PLACES[place])
    rows = raw.get('rows')
    if rows is None and ('meters' in raw or 'info' in raw):  # the first settings had two fixed rows
        rows = [raw.get('meters', DEFAULT['rows'][0]), raw.get('info', DEFAULT['rows'][1])]
    if isinstance(rows, list):
        cfg['rows'] = [keep(r, PLACES['rows']) for r in rows if isinstance(r, list)]
    m = raw.get('meter')
    cfg['meter'] = max(3, min(30, m)) if isinstance(m, int) and not isinstance(m, bool) else DEFAULT['meter']
    cfg['palette'] = raw['palette'] if raw.get('palette') in PALETTES else DEFAULT['palette']
    return cfg


def version_key(v):
    return tuple(int(x) for x in v.split('.'))


def chip(name, d, s, now):
    """One footer state's pieces for the bottom edge, or [] while it is off. `s` holds what the payload lacks:
    rc (the Remote Control session id), mode (permission mode), busy, newest (downloaded version), no_transcript,
    sandbox, drafts (feedback drafts waiting for review)."""
    if name == 'cloud':
        return [P('◎ cloud', BLUE)] if d.get('remote') else []
    if name == 'rc':
        return [P('⇄ rc', GREEN, bold=True, link=f"https://claude.ai/code/{s['rc']}")] if s.get('rc') else []
    if name == 'mode':
        if s.get('mode') not in MODES:
            return []
        glyph, words, rgb = MODES[s['mode']]
        return [P(f'{glyph} {words} on', rgb)]
    if name == 'no_transcript':
        return [P('⚠ no transcript', RED, bold=True)] if s.get('no_transcript') else []
    if name == 'update':
        newest, running = s.get('newest'), d.get('version') or ''
        if newest and VERSION.match(running) and version_key(newest) > version_key(running):
            return [P(f'↑ {newest}', YELLOW, bold=True), P(' restart', dim=True)]
        return []
    if name == 'cache':
        pc = d.get('prompt_cache') or {}
        left = (pc.get('expires_at') or 0) - now
        if pc.get('warm') and pc.get('expires_at') and 0 < left <= CACHE_SOON:
            return [P(f'◷ cache {int(left)}s' if left < 60 else f'◷ cache {int(left // 60)}m', ORANGE)]
        return [P('◷ cache cold', YELLOW)] if pc and not pc.get('warm') and pc.get('caching_observed') else []
    if name == 'big':  # past 200k tokens of context, where the long-context price applies
        return [P('▲ 200k+', ORANGE)] if d.get('exceeds_200k_tokens') else []
    if name == 'drafts':
        n = s.get('drafts')
        return [P('✎ ', YELLOW), P(f"{n} draft{'s' if n > 1 else ''}", dim=True)] if n else []
    if name == 'sandbox':
        return [P('⧈ sandbox', GREEN)] if s.get('sandbox') else []
    if name == 'working':
        return [P('● ', YELLOW), P('working', dim=True)] if s.get('busy') else []
    if name == 'pr':
        pr = d.get('pr') or {}
        if pr.get('number') is None:
            return []
        # the native badge's colours by review state
        rgb, mark = {'approved': (GREEN, ' ✓'), 'changes_requested': (RED, ' ±'), 'pending': (YELLOW, ''),
                     'merged': (PURPLE, ' ✓')}.get(pr.get('review_state'), (None, ''))
        label = f"MR !{pr['number']}" if pr.get('kind') == 'mr' else f"PR #{pr['number']}"
        return [P(label, rgb, link=pr.get('url'))] + ([P(mark, rgb, bold=True, link=pr.get('url'))] if mark else [])
    if name == 'fast':
        return [P('↯ fast', ORANGE)] if d.get('fast_mode') else []
    if name == 'vim':
        vim = (d.get('vim') or {}).get('mode')
        return [P(f'-- {vim} --', dim=True)] if vim and vim != 'NORMAL' else []
    return []


def chips(d, s, now, order=None):
    """The footer states that are on, as pieces for the bottom edge, in `order`: the settings' bottom edge, by
    default the order a narrow card keeps them (the connection, the events that ask something of you, the steady
    states)."""
    return [c for c in (safe(chip, name, d, s, now) for name in (DEFAULT['edge'] if order is None else order)) if c]


def element(name, x):
    """One text element's pieces, or [] when it has nothing to show. `x` holds the payload `d`, the host `h`,
    `now`, and what the card worked out once: the model's name, the folder, home, the repository and branch."""
    d, h = x['d'], x['h']
    dim = lambda t: P(t, dim=True)
    cost = d.get('cost') or {}
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    if name == 'model':
        return [P(f"✻ {x['model']}", ACCENT, bold=True)]
    if name == 'effort':
        level = (d.get('effort') or {}).get('level')
        return [dim(level)] if level else []
    if name == 'thinking':
        return [dim('thinking')] if (d.get('thinking') or {}).get('enabled') else []
    if name == 'style':
        style = (d.get('output_style') or {}).get('name')
        return [dim(f'style {style}')] if style and style.lower() != 'default' else []
    if name == 'agent':
        agent = (d.get('agent') or {}).get('name')
        return [P(f'@{agent}', BLUE)] if agent else []
    if name == 'name':
        return [P(d['session_name'])] if d.get('session_name') else []
    if name == 'version':
        return [dim(f"v{d['version']}")] if d.get('version') else []
    if name == 'cost':
        return [P(f"${cost['total_cost_usd']:.2f}")] if num(cost.get('total_cost_usd')) else []
    if name == 'time':
        return [P(f"◷ {duration(cost['total_duration_ms'])}")] if num(cost.get('total_duration_ms')) else []
    if name == 'api':
        return [dim('api '), P(duration(cost['total_api_duration_ms']))] if num(cost.get('total_api_duration_ms')) else []
    if name == 'lines':
        added, removed = cost.get('total_lines_added') or 0, cost.get('total_lines_removed') or 0
        return [P(f'+{added}', GREEN), P(f' -{removed}', RED)] if added or removed else []
    if name == 'clock':
        return [P(time.strftime('%H:%M', time.localtime(x['now'])))]
    if name == 'repo':
        return [dim(f"⎇ {x['repo']}")] + ([dim(f" {x['branch']}")] if x['branch'] else []) if x['repo'] else []
    if name == 'cwd':
        return [dim(f"⌂ {tilde(x['cwd'], x['home'])}")]
    if name == 'session':
        sid = (d.get('session_id') or '')[:8]
        return [dim(f'# {sid}')] if sid else []
    if name == 'worktree':
        wt = (d.get('worktree') or {}).get('name')
        return [dim(f'wt {wt}')] if wt else []
    if name == 'dirs':
        n = len((d.get('workspace') or {}).get('added_dirs') or [])
        return [dim(f"+{n} dir{'s' if n > 1 else ''}")] if n else []
    if name == 'mem' and 'mem' in h:
        used, total = h['mem']
        return [dim('mem '), P(f'{used:.1f}/{total:.1f}G', heat(used / max(total, 0.1)))]
    if name == 'disks':
        return join([[dim(f'{mount} '), P(f'{p}%', heat(p / 100))] for mount, p in h.get('disks', [])])
    if name == 'load' and 'load' in h:
        now_load, cpus = h['load']
        return [dim('load '), P(f'{now_load:.1f}', heat(now_load / max(cpus, 1)))]
    if name == 'battery' and h.get('battery'):
        pct, charging = h['battery']
        return [dim('bat '), P(f'{pct}%', heat(1 - pct / 100))] + ([P('+', GREEN)] if charging else [])
    return []


def card(d, width, now, h, meter=10, chips=(), cfg=None):
    """The card's lines for `width` cells, laid out by `cfg` (DEFAULT when None): a top edge with its left and
    right elements; its rows; the bottom edge, holding `chips`. Narrower, a row's meters shrink to half their
    length, then the row wraps onto more lines; the edges drop elements from the end of their lists."""
    cfg = cfg or DEFAULT
    dim = lambda t: P(t, dim=True)
    edge = lambda t: P(t, EDGE)
    inner = width - 4
    m_ = d.get('model') if isinstance(d.get('model'), dict) else {}
    ws = d.get('workspace') if isinstance(d.get('workspace'), dict) else {}
    cwd = ws.get('current_dir') or d.get('cwd') or os.getcwd()
    texts = cfg['top_left'] + cfg['top_right'] + [n for r in cfg['rows'] for n in r]
    repo, branch = git_info(cwd) if 'repo' in texts else (None, None)
    x = {'d': d, 'h': h, 'now': now, 'model': model_name(m_.get('id'), m_.get('display_name')), 'cwd': cwd,
         'home': os.path.expanduser('~'), 'repo': repo, 'branch': branch}
    pieces = lambda place: [g for g in (safe(element, n, x) for n in cfg[place]) if g]

    # the top edge: drops its right elements from the end, then its left ones but the first, then cuts that one
    lefts, rights = pieces('top_left'), pieces('top_right')
    for nl, nr in [(len(lefts), k) for k in range(len(rights), -1, -1)] + [(k, 0) for k in range(len(lefts) - 1, 0, -1)]:
        left = [edge('╭─ ')] + join(lefts[:nl]) + [P(' ')]
        right = [P(' ')] + join(rights[:nr]) + [edge(' ─╮')] if nr else [edge('╮')]
        if cells(left) + cells(right) < width:
            break
    left = clip(left, width - cells(right) - 1)
    top = left + [edge('─' * (width - cells(left) - cells(right)))] + right

    # the rows: meters and text, a dim dot between them
    ctx = d.get('context_window') or {}
    rl = d.get('rate_limits') or {}

    def gauge(label, p, m, good_high=False):
        full = max(0, min(m, round(p / 100 * m)))
        tone = (lambda i: heat(1 - p / 100)) if good_high else (lambda i: heat((i + 0.5) / m))
        bar = [P('▰', tone(i)) for i in range(full)] + [P('▱' * (m - full) + ' ', EMPTY)] if m else []
        return [dim(f'{label} ')] + bar + [P(f'{round(p)}%', heat(1 - p / 100 if good_high else p / 100), bold=True)]

    def meter_group(name, m, gone):
        if name == 'ctx':
            if ctx.get('used_percentage') is None:
                return []
            g = gauge('ctx', ctx['used_percentage'], m)
            if 'tokens' not in gone and ctx.get('context_window_size'):
                g.append(P(f" {tokens(ctx.get('total_input_tokens') or 0)}/{tokens(ctx['context_window_size'])}"))
            return g
        if name == 'hits':  # shortcut: hit_ratio read as a fraction up to 1; check it against a real payload
            r = (d.get('prompt_cache') or {}).get('hit_ratio')
            return gauge('hits', r * 100 if r <= 1 else r, m, good_high=True) if isinstance(r, (int, float)) else []
        v = rl.get({'5h': 'five_hour', 'week': 'seven_day', 'spend': 'spend_limit'}[name])
        if not v:
            return []
        g = gauge(name, v.get('used_percentage') or 0, m)
        if name == 'spend' and 'tokens' not in gone and v.get('limit_usd'):
            g.append(P(f" ${v.get('used_usd') or 0:.0f}/${v['limit_usd']:.0f}"))
        if 'resets' not in gone and v.get('resets_at'):
            g.append(P(f" ↻{duration(v['resets_at'] * 1000 - now * 1000)}"))
        return g

    def group(name, m, gone):
        return meter_group(name, m, gone) if name in METERS else element(name, x)

    tries = [(m, ()) for m in range(meter, 2, -1)] + [(0, ()), (0, ('resets',)), (0, ('resets', 'tokens'))]

    def lay(names):
        """A row's lines: one, with the meters shrunk to half their length at most; else wrapped at full length,
        each element alone on its line shrinking further (then losing resets and tokens) only if it must."""
        for m in range(meter, max(3, meter // 2) - 1, -1):
            line = join([g for g in (safe(group, n, m, ()) for n in names) if g])
            if cells(line) <= inner:
                return [line]
        lines, line = [], []
        for n in names:
            g = first_fit((safe(group, n, m, gone) for m, gone in tries), inner)
            if not g:
                continue
            if line and cells(line) + 3 + cells(g) > inner:
                lines.append(line)
                line = []
            line = line + [dim(' · ')] + g if line else g
        return lines + [line] if line or not lines else lines

    rows = [line for names in cfg['rows'] for line in lay(names)]

    framed = [[edge('│ ')] + r + [P(' ' * (inner - cells(r))), edge(' │')] for r in rows]

    # the bottom edge: as many chips as fit, dropped from the right
    for k in range(len(chips), -1, -1):
        row = join(chips[:k])
        if cells(row) <= width - 6:
            break
    bottom = [edge('╰─ ')] + row + [edge(' ' + '─' * (width - 5 - cells(row)) + '╯')] if row else [edge('╰' + '─' * (width - 2) + '╯')]
    return [top] + framed + [bottom]


def session_record(sid, sessions_dir):
    """This session's entry among Claude Code's per-process files (<pid>.json), from a process still alive."""
    best = {}
    try:
        names = os.listdir(sessions_dir) if sid else []
    except OSError:
        return best
    for name in names:
        if not name.endswith('.json'):
            continue
        try:
            with open(os.path.join(sessions_dir, name)) as f:
                rec = json.load(f)
        except (OSError, ValueError):
            continue
        if (isinstance(rec, dict) and rec.get('sessionId') == sid and os.path.exists(f"/proc/{rec.get('pid')}")
                and (rec.get('updatedAt') or 0) >= (best.get('updatedAt') or 0)):
            best = rec
    return best


def newest_version(versions_dir):
    """The newest Claude Code the installer has downloaded, by version number."""
    try:
        return max((n for n in os.listdir(versions_dir) if VERSION.match(n)), key=version_key, default=None)
    except OSError:
        return None


def last_permission_mode(transcript, tail=262144):
    """The permission mode in the transcript's last permission-mode entry, read from its tail only.
    shortcut: Claude Code writes the entry at its next metadata write, not on shift+tab, so it can trail the
    native pill until the next message; upgrade if the status line payload ever carries permission_mode."""
    try:
        with open(transcript, 'rb') as f:
            f.seek(max(0, os.fstat(f.fileno()).st_size - tail))
            lines = f.read().split(b'\n')
    except (OSError, TypeError):
        return None
    for line in reversed(lines):
        if b'"type":"permission-mode"' in line:
            try:
                return json.loads(line).get('permissionMode')
            except ValueError:
                continue
    return None


def count_json(folder):
    """How many .json files a folder holds: the feedback drafts waiting for review."""
    try:
        return sum(n.endswith('.json') for n in os.listdir(folder))
    except OSError:
        return 0


def env_flag(raw, name):
    """Whether `name` is on in a NUL-separated environment, read as Claude Code reads a boolean: 1, true, yes, on."""
    for item in raw.split(b'\0'):
        key, _, value = item.partition(b'=')
        if key == name.encode():
            return value.strip().lower() in (b'1', b'true', b'yes', b'on')
    return False


def launch_env(pid):
    """The environment a process was started with."""
    try:
        with open(f'/proc/{int(pid)}/environ', 'rb') as f:
            return f.read()
    except (OSError, TypeError, ValueError):
        return b''


def meter_arg(argv):
    """--meter N: the meters' longest length in cells, 3 to 30; 10 when absent or not a number."""
    try:
        return max(3, min(30, int(argv[argv.index('--meter') + 1])))
    except (ValueError, IndexError):
        return 10


def main():
    try:
        d = json.loads(sys.stdin.read() or '{}')
    except ValueError:
        d = {}
    width = card_width(terminal_columns())
    ws = d.get('workspace') or {}
    project = ws.get('project_dir') or ws.get('current_dir') or d.get('cwd') or os.getcwd()
    h, now, home = host(project), time.time(), os.path.expanduser('~')
    cfg = load_config(CONFIG)
    use_palette(cfg['palette'])
    try:
        rec = session_record(d.get('session_id'), os.path.join(home, '.claude', 'sessions'))
        edge = cfg['edge']
        s = {'rc': rec.get('bridgeSessionId'), 'busy': rec.get('status') == 'busy', 'sandbox': h.get('sandbox'),
             'newest': newest_version(os.path.join(home, '.local', 'share', 'claude', 'versions')),
             'no_transcript': env_flag(launch_env(rec.get('pid')), 'CLAUDE_CODE_SKIP_PROMPT_HISTORY'),
             'mode': last_permission_mode(d.get('transcript_path')) if 'mode' in edge else None,
             'drafts': count_json(os.path.join(home, '.claude', 'feedback', 'drafts')) if 'drafts' in edge else 0}
        cs = chips(d, s, now, edge)
    except (TypeError, ValueError, AttributeError):  # a payload or session file of another shape costs the chips, not the card
        cs = []
    meter = meter_arg(sys.argv) if '--meter' in sys.argv else cfg['meter']
    lines = card(d, width, now, h, meter, cs, cfg)
    sys.stdout.buffer.write(''.join(paint(line) + '\n' for line in lines).encode())


if __name__ == '__main__':
    main()
