#!/usr/bin/env python3
"""Session Bar: Claude Code's status line as a rounded card with segmented, heat-coloured meters.

Claude Code runs it on each update with the session as JSON on stdin and draws what it prints.
No model call, no network and no hook: a few small file reads and one statvfs per disk.
The bottom edge carries the footer's states while they are on: /rc, events that ask for something, steady states.
What each place shows, in what order, comes from session-bar.json beside this script (SESSION_BAR_CONFIG overrides
the path); without it the card is drawn with DEFAULT. Nothing here reaches the model, so no element costs tokens.
Options: --meter N, the meters' longest length in cells (3 to 30), over the settings' "meter".
"""
import json
import os
import re
import stat
import sys
import time

# The card's colours, one set per palette: accent is the model's name; edge the frame, visible on a dark terminal
# and quieter than the text; empty a meter's unfilled segments; green to red the heat; purple, blue, teal the dark
# theme's merged, ide and planMode. "default" is the card as it was first drawn. The themes keep their own colours,
# the nearest one where a theme has none (rose-pine's green and orange); mono, matrix and amber are monochrome.
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
    'catppuccin': {'accent': (203, 166, 247), 'edge': (108, 112, 134), 'empty': (69, 71, 90), 'green': (166, 227, 161),
                   'yellow': (249, 226, 175), 'orange': (250, 179, 135), 'red': (243, 139, 168),
                   'purple': (245, 194, 231), 'blue': (137, 180, 250), 'teal': (148, 226, 213)},
    'rose-pine': {'accent': (235, 188, 186), 'edge': (110, 106, 134), 'empty': (82, 79, 103), 'green': (156, 207, 216),
                  'yellow': (246, 193, 119), 'orange': (235, 188, 186), 'red': (235, 111, 146), 'purple': (196, 167, 231),
                  'blue': (62, 143, 176), 'teal': (156, 207, 216)},
    'solarized': {'accent': (38, 139, 210), 'edge': (88, 110, 117), 'empty': (52, 76, 84), 'green': (133, 153, 0),
                  'yellow': (181, 137, 0), 'orange': (203, 75, 22), 'red': (220, 50, 47), 'purple': (108, 113, 196),
                  'blue': (38, 139, 210), 'teal': (42, 161, 152)},
    'one-dark': {'accent': (97, 175, 239), 'edge': (92, 99, 112), 'empty': (62, 68, 81), 'green': (152, 195, 121),
                 'yellow': (229, 192, 123), 'orange': (209, 154, 102), 'red': (224, 108, 117), 'purple': (198, 120, 221),
                 'blue': (97, 175, 239), 'teal': (86, 182, 194)},
    'everforest': {'accent': (167, 192, 128), 'edge': (122, 132, 120), 'empty': (79, 88, 94), 'green': (167, 192, 128),
                   'yellow': (219, 188, 127), 'orange': (230, 152, 117), 'red': (230, 126, 128),
                   'purple': (214, 153, 182), 'blue': (127, 187, 179), 'teal': (131, 192, 146)},
    'kanagawa': {'accent': (255, 160, 102), 'edge': (114, 113, 105), 'empty': (84, 84, 109), 'green': (152, 187, 108),
                 'yellow': (230, 195, 132), 'orange': (255, 160, 102), 'red': (228, 104, 118), 'purple': (149, 127, 184),
                 'blue': (126, 156, 216), 'teal': (122, 168, 159)},
    'monokai': {'accent': (249, 38, 114), 'edge': (117, 113, 94), 'empty': (73, 72, 62), 'green': (166, 226, 46),
                'yellow': (230, 219, 116), 'orange': (253, 151, 31), 'red': (249, 38, 114), 'purple': (174, 129, 255),
                'blue': (102, 217, 239), 'teal': (102, 217, 239)},
    'ayu': {'accent': (230, 180, 80), 'edge': (108, 115, 128), 'empty': (61, 66, 77), 'green': (170, 217, 76),
            'yellow': (255, 180, 84), 'orange': (255, 143, 64), 'red': (240, 113, 120), 'purple': (210, 166, 255),
            'blue': (57, 186, 230), 'teal': (149, 230, 203)},
    'synthwave': {'accent': (255, 126, 219), 'edge': (132, 139, 189), 'empty': (64, 52, 96), 'green': (114, 241, 184),
                  'yellow': (254, 222, 93), 'orange': (255, 139, 57), 'red': (254, 68, 80), 'purple': (185, 135, 255),
                  'blue': (54, 249, 246), 'teal': (54, 249, 246)},
    'mono': {'accent': (238, 238, 238), 'edge': (92, 92, 92), 'empty': (58, 58, 58), 'green': (140, 140, 140),
             'yellow': (180, 180, 180), 'orange': (215, 215, 215), 'red': (255, 255, 255), 'purple': (200, 200, 200),
             'blue': (170, 170, 170), 'teal': (150, 150, 150)},
    'matrix': {'accent': (80, 255, 120), 'edge': (30, 110, 55), 'empty': (22, 62, 34), 'green': (0, 170, 60),
               'yellow': (60, 210, 90), 'orange': (130, 240, 150), 'red': (210, 255, 215), 'purple': (140, 230, 160),
               'blue': (70, 190, 110), 'teal': (50, 160, 95)},
    'amber': {'accent': (255, 196, 40), 'edge': (130, 85, 20), 'empty': (70, 48, 14), 'green': (180, 110, 10),
              'yellow': (230, 150, 20), 'orange': (255, 190, 60), 'red': (255, 235, 170), 'purple': (240, 170, 60),
              'blue': (210, 140, 40), 'teal': (200, 130, 30)}}


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
MISS_SHOWN = 300  # seconds a prompt cache miss stays on the card
# why the prompt cache missed: Claude Code's causes (RLs in 2.1.303), in short words
MISS_CAUSE = {'system_prompt_changed': 'system prompt', 'tools_changed': 'tools', 'model_changed': 'model',
              'fast_mode_changed': 'fast mode', 'cache_scope_or_ttl_changed': 'cache TTL', 'betas_changed': 'betas',
              'effort_changed': 'effort', 'thinking_mode_changed': 'thinking',
              'thinking_display_changed': 'thinking shown', 'auto_mode_changed': 'auto mode',
              'overage_changed': 'usage limit', 'extra_body_changed': 'request fields',
              'defer_loading_changed': 'deferred tools', 'messages_rewritten': 'earlier messages',
              'ttl_expired_5m': 'idle 5m', 'ttl_expired_1h': 'idle 1h', 'likely_server_side': 'server side'}
VERSION = re.compile(r'^\d+(\.\d+)+$')
DISKS = ['/tmp', '~/.cache']  # the tmpfs and the scratch disk
FOOTER_PADDING = 2  # columns Claude Code's footer row keeps on each side of the status line (oQe); its notes wrap below
RC_PILL = len(' /rc')  # Claude Code's /rc pill and the gap before it (columnGap 1), shown from 60 columns (Tbn)
NOTICE = len('✔ Update installed · Restart to update')  # Claude Code's widest notice; its idle /clear hint is as wide
CONFIG = os.environ.get('SESSION_BAR_CONFIG') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'session-bar.json')
# what each place can hold: text on the top edge, anything but chips on a row, chips on the bottom edge
TEXT = ['model', 'effort', 'thinking', 'style', 'agent', 'name', 'version', 'cost', 'time', 'api', 'lines', 'clock',
        'repo', 'cwd', 'session', 'worktree', 'dirs', 'mem', 'disks', 'load', 'battery']
METERS = ['ctx', '5h', 'week', 'spend', 'hits']
CHIPS = ['cloud', 'rc', 'mode', 'no_transcript', 'update', 'cache', 'miss', 'big', 'drafts', 'sandbox', 'working', 'pr',
         'fast', 'vim']
PLACES = {'top_left': TEXT, 'top_right': TEXT, 'rows': TEXT + METERS, 'edge': CHIPS}
DEFAULT = {'top_left': ['model', 'effort'], 'top_right': ['cost', 'time'],
           'rows': [['ctx', '5h', 'week'], ['repo', 'cwd', 'session', 'mem', 'disks']],
           'edge': ['cloud', 'rc', 'no_transcript', 'update', 'cache', 'miss', 'sandbox', 'working', 'pr', 'fast', 'vim'],
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


CONTROL = re.compile(r'[\x00-\x1f\x7f-\x9f]')  # C0 and C1 controls: a name from disk or the payload never reaches the terminal raw


# A piece of a row: its text, its look and an optional link. Every glyph used is one cell wide.
def P(t, rgb=None, dim=False, bold=False, link=None):
    return (CONTROL.sub('', t), rgb, dim, bold, link and CONTROL.sub('', link))


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


def card_width(columns, rc=False, notices=False):
    """The card's width: the footer's, the terminal less its padding on both sides; 30 at the least. While Remote
    Control is on it also leaves room for the /rc pill, which then sits beside the card's top edge, not under it.
    While Claude Code shows a notice beside the card, it leaves room for the widest notice and the gap before it, the
    pill going under the notices, as long as the card keeps 80 columns; narrower, the notices go under the card."""
    width = columns - 2 * FOOTER_PADDING
    if notices and width - NOTICE - 1 >= 80:
        return width - NOTICE - 1
    return max(30, width - (RC_PILL if rc and columns >= 60 else 0))


def columns(env):
    """The terminal's width: COLUMNS, which Claude Code sets from its own terminal at every run; 120 without it."""
    try:
        n = int(env.get('COLUMNS') or 0)
    except ValueError:
        n = 0
    return n if n > 0 else 120


def head_of(path, n=256):
    """The first `n` characters of a regular file; a pipe, a device or anything else reads as empty, so a hostile
    .git cannot stall the card."""
    if not stat.S_ISREG(os.stat(path).st_mode):
        return ''
    with open(path, errors='replace') as f:
        return f.read(n)


def tail_of(path, n=65536):
    """The last `n` bytes of a regular file, as text; anything else reads as empty, as with head_of."""
    if not stat.S_ISREG(os.stat(path).st_mode):
        return ''
    with open(path, 'rb') as f:
        f.seek(max(0, os.fstat(f.fileno()).st_size - n))
        return f.read().decode(errors='replace')


def git_dir(cwd):
    """The repository's top folder and its git folder, found up from `cwd`; (None, None) outside one."""
    d = cwd
    while d and d != '/':
        dot = os.path.join(d, '.git')
        if os.path.exists(dot):
            try:
                line = head_of(dot).strip() if os.path.isfile(dot) else ''  # a worktree or a submodule: "gitdir: <path>"
            except OSError:
                line = ''
            return d, os.path.join(d, line[8:]) if line.startswith('gitdir: ') else dot
        d = os.path.dirname(d)
    return None, None


def git_info(cwd):
    """The repository's folder name and branch, read from .git without running git."""
    top, gitdir = git_dir(cwd)
    if not top:
        return None, None
    try:
        head = head_of(os.path.join(gitdir, 'HEAD')).strip()
    except OSError:
        head = ''
    return os.path.basename(top), head[16:] if head.startswith('ref: refs/heads/') else head[:7]


def git_sync(cwd, branch):
    """Whether the branch is ahead of origin's (⇡), behind (⇣) or apart (⇅), told without running git: each branch's
    reflog keeps where it stood, and the branch that once stood where the other stands now is the one that moved on."""
    if not branch or '..' in branch or not re.fullmatch(r'[\w./-]+', branch):
        return None
    _, gitdir = git_dir(cwd)
    shared = os.path.join(gitdir, 'commondir')  # a worktree keeps its refs and logs in the main git folder
    common = os.path.join(gitdir, head_of(shared).strip()) if os.path.isfile(shared) else gitdir

    def sha(ref):
        try:
            return head_of(os.path.join(common, ref), 64).strip() or None
        except OSError:
            try:
                packed = head_of(os.path.join(common, 'packed-refs'), 1 << 20)
            except OSError:
                return None
            return next((line.split()[0] for line in packed.splitlines() if line.endswith(' ' + ref)), None)

    def stood(ref):  # where a branch stood, from the end of its reflog
        try:
            log = tail_of(os.path.join(common, 'logs', ref)).splitlines()
        except OSError:
            return set()
        return {line.split()[1] for line in log if len(line.split()) > 1}

    local, there = sha(f'refs/heads/{branch}'), sha(f'refs/remotes/origin/{branch}')
    if not local or not there or local == there:
        return None
    ahead, behind = there in stood(f'refs/heads/{branch}'), local in stood(f'refs/remotes/origin/{branch}')
    return '⇡' if ahead and not behind else '⇣' if behind and not ahead else '⇅'


def claude_dir(env):
    """Claude Code's folder: CLAUDE_CONFIG_DIR, else ~/.claude (read in 2.1.303)."""
    return env.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude')


def versions_dir(env):
    """Where Claude Code downloads its versions, on every system: (XDG_DATA_HOME or ~/.local/share)/claude/versions."""
    return os.path.join(env.get('XDG_DATA_HOME') or os.path.join(os.path.expanduser('~'), '.local', 'share'),
                        'claude', 'versions')


def host(project, env=os.environ):
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
    for path in (os.path.join(claude_dir(env), 'settings.json'), f'{project}/.claude/settings.json',
                 f'{project}/.claude/settings.local.json'):
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
        newest = s.get('newest')
        if update_ready(newest, d.get('version')):
            return [P(f'↑ {newest}', YELLOW, bold=True), P(' restart', dim=True)]
        return []
    if name == 'cache':
        pc = d.get('prompt_cache') or {}
        left = (pc.get('expires_at') or 0) - now
        cold = pc.get('recache_tokens_if_cold')  # what the next request costs once the cache is gone
        cost = [P(f' ({tokens(cold)})', dim=True)] if isinstance(cold, (int, float)) and cold > 0 else []
        if pc.get('warm') and pc.get('expires_at') and 0 < left <= CACHE_SOON:
            return [P(f'◷ cache {int(left)}s' if left < 60 else f'◷ cache {int(left // 60)}m', ORANGE)] + cost
        return [P('◷ cache cold', YELLOW)] + cost if pc and not pc.get('warm') and pc.get('caching_observed') else []
    if name == 'miss':  # the prompt cache missed lately, and why
        pc = d.get('prompt_cache') or {}
        at, causes = pc.get('last_miss_at'), (pc.get('last_miss_cause') or {}).get('causes') or []
        if isinstance(at, (int, float)) and 0 <= now - at <= MISS_SHOWN:
            why = MISS_CAUSE.get(causes[0], str(causes[0])) if causes else 'unknown'
            return [P('✗ cache miss', RED), P(': ' + why + (f' +{len(causes) - 1}' if len(causes) > 1 else ''), dim=True)]
        return []
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
    if name == 'thinking':  # while Claude works out its next step (h, from main); the mode alone is always on in Opus 5.5
        return [P('∴ ', PURPLE), dim('thinking')] if h.get('thinking') and (d.get('thinking') or {}).get('enabled') else []
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
    if name == 'repo':  # linked to the branch on origin; ⇡ ⇣ ⇅ for ahead of it, behind it, apart from it
        if not x['repo']:
            return []
        origin = (d.get('workspace') or {}).get('repo') or {}  # Claude Code's reading of the remote: host, owner, name
        parts, branch = [origin.get(k) for k in ('host', 'owner', 'name')], x['branch']
        url = 'https://' + '/'.join(parts) + (f'/tree/{branch}' if branch and re.fullmatch(r'[\w./-]+', branch) else '') \
            if all(isinstance(v, str) and re.fullmatch(r'[\w.:-]+', v) for v in parts) else None
        return ([P(f"⎇ {x['repo']}", dim=True, link=url)] + ([dim(f' {branch}')] if branch else [])
                + ([P(f" {x['sync']}", YELLOW)] if x['sync'] else []))
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
         'home': os.path.expanduser('~'), 'repo': repo, 'branch': branch,
         'sync': safe(git_sync, cwd, branch) if repo else None}
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
        if name == 'hits':  # hit_ratio is cache read / all input tokens, 0..1 or null (read in 2.1.303)
            r = (d.get('prompt_cache') or {}).get('hit_ratio')
            return gauge('hits', r * 100, m, good_high=True) if isinstance(r, (int, float)) else []
        v = rl.get({'5h': 'five_hour', 'week': 'seven_day', 'spend': 'spend_limit'}[name])
        if not v:
            return []
        p = v.get('used_percentage') or 0
        # the headers trail claude.ai by about a point (seen 2026-10-19), so 5h and week show 1 more, up to 100
        g = gauge(name, p if name == 'spend' else min(100, p + 1), m)
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


def last_speaker(transcript, tail=262144):
    """Who spoke last in the transcript, 'user' (a prompt or a tool's result) or 'assistant', read from its tail;
    other entries and side chains do not count. Claude Code writes a message once it is whole, so while the user
    spoke last, Claude is at work on its next step: thinking, then writing it."""
    try:
        with open(transcript, 'rb') as f:
            f.seek(max(0, os.fstat(f.fileno()).st_size - tail))
            lines = f.read().split(b'\n')
    except (OSError, TypeError):
        return None
    for line in reversed(lines):
        if b'"type":"user"' not in line and b'"type":"assistant"' not in line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict) and e.get('type') in ('user', 'assistant') and not e.get('isSidechain'):
            return e['type']
    return None


def count_json(folder):
    """How many .json files a folder holds: the feedback drafts waiting for review."""
    try:
        return sum(n.endswith('.json') for n in os.listdir(folder))
    except OSError:
        return 0


def env_flag(env, name):
    """Whether `name` is on in an environment, read as Claude Code reads a boolean: 1, true, yes, on."""
    return (env.get(name) or '').strip().lower() in ('1', 'true', 'yes', 'on')


def update_ready(newest, running):
    """Whether a newer Claude Code than the running one is installed: the update chip, and the "Update installed ·
    Restart to update" notice Claude Code shows until it restarts."""
    return bool(newest and VERSION.match(running or '') and version_key(newest) > version_key(running))


def idle_hint(rec, d, env, now):
    """Whether Claude Code shows its idle hint, "new task? /clear to save … tokens": the session idle since its last
    turn for CLAUDE_CODE_IDLE_THRESHOLD_MINUTES (75), with CLAUDE_CODE_IDLE_TOKEN_THRESHOLD (100k) tokens or more.
    shortcut: the hint counts the conversation's tokens and this the context's, a few percent apart; near the
    threshold they can disagree."""
    def number(name, default):
        try:
            return float(env.get(name))
        except (TypeError, ValueError):
            return default

    since = rec.get('statusUpdatedAt')
    tokens = (d.get('context_window') or {}).get('total_input_tokens') or 0
    return (rec.get('status') == 'idle' and isinstance(since, (int, float)) and not isinstance(since, bool)
            and tokens >= number('CLAUDE_CODE_IDLE_TOKEN_THRESHOLD', 1e5)
            and now - since / 1000 >= number('CLAUDE_CODE_IDLE_THRESHOLD_MINUTES', 75) * 60)


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
    ws = d.get('workspace') or {}
    project = ws.get('project_dir') or ws.get('current_dir') or d.get('cwd') or os.getcwd()
    h, now = host(project), time.time()
    cfg = load_config(CONFIG)
    use_palette(cfg['palette'])
    rc, notices = None, False  # Remote Control's session, while it is on; whether a notice sits beside the card
    try:
        rec = session_record(d.get('session_id'), os.path.join(claude_dir(os.environ), 'sessions'))
        edge = cfg['edge']
        rc = rec.get('bridgeSessionId')
        env = os.environ  # Claude Code hands its own environment to the command; only named variables are read
        s = {'rc': rc, 'busy': rec.get('status') == 'busy', 'sandbox': h.get('sandbox'),
             'newest': newest_version(versions_dir(os.environ)),
             'no_transcript': env_flag(env, 'CLAUDE_CODE_SKIP_PROMPT_HISTORY'),
             'mode': last_permission_mode(d.get('transcript_path')) if 'mode' in edge else None,
             'drafts': count_json(os.path.join(claude_dir(os.environ), 'feedback', 'drafts')) if 'drafts' in edge else 0}
        notices = update_ready(s['newest'], d.get('version')) or idle_hint(rec, d, env, now)
        if 'thinking' in cfg['top_left'] + cfg['top_right'] + [n for r in cfg['rows'] for n in r]:
            h['thinking'] = s['busy'] and last_speaker(d.get('transcript_path')) == 'user'
        cs = chips(d, s, now, edge)
    except (TypeError, ValueError, AttributeError):  # a payload or session file of another shape costs the chips, not the card
        cs = []
    meter = meter_arg(sys.argv) if '--meter' in sys.argv else cfg['meter']
    lines = card(d, card_width(columns(os.environ), bool(rc), notices), now, h, meter, cs, cfg)
    sys.stdout.buffer.write(''.join(paint(line) + '\n' for line in lines).encode())


if __name__ == '__main__':
    main()
