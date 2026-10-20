"""Checks the Session Bar: every line is the card's width at every width, and the frame stays closed.

Run: python3 -I ~/.claude/statusline/test_session_bar.py
"""
import importlib.util
import os
import re

spec = importlib.util.spec_from_file_location('session_bar', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'session-bar.py'))
sb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sb)

ANSI = re.compile(r'\x1b\[[\d;]*m|\x1b\]8;;[^\x1b]*\x1b\\')
NOW = 1_800_000_000
FULL = {
    'session_id': 'af9b34f1-c844-4ee6-9df8-79461c5cb209',
    'model': {'id': 'claude-opus-5-5', 'display_name': 'Opus'},
    'workspace': {'current_dir': '/home/u/codewiki', 'project_dir': '/home/u/codewiki'},
    'effort': {'level': 'max'},
    'cost': {'total_cost_usd': 123.456, 'total_duration_ms': 9_360_000},
    'context_window': {'total_input_tokens': 111_000, 'context_window_size': 1_000_000, 'used_percentage': 11.1},
    'rate_limits': {'five_hour': {'used_percentage': 42, 'resets_at': NOW + 9000},
                    'seven_day': {'used_percentage': 97, 'resets_at': NOW + 300_000}},
}
HOST = {'mem': (3.2, 7.5), 'disks': [('/tmp', 12), ('~/.cache', 64)], 'sandbox': False}
SHAPES = [
    FULL,
    {},
    {**FULL, 'rate_limits': None, 'effort': None},
    {**FULL, 'model': {'id': 'some-very-long-custom-model-name-nobody-shortens'}, 'cost': {'total_cost_usd': 1.0}},
]

for d in SHAPES:
    for w in range(30, 241):
        lines = [ANSI.sub('', sb.paint(line)) for line in sb.card(d, w, NOW, HOST)]
        assert [len(line) for line in lines] == [w] * len(lines), (w, d.get('model'), lines)
        assert lines[0][0] == '╭' and lines[0][-1] == '╮' and lines[-1][0] == '╰' and lines[-1][-1] == '╯', lines
        assert all(line[0] == '│' and line[-1] == '│' for line in lines[1:-1]), lines
        assert len(lines) >= 4 and (w < 151 or len(lines) == 4), lines  # narrower, rows wrap onto more lines

wide = [ANSI.sub('', sb.paint(line)) for line in sb.card(FULL, 151, NOW, HOST)]
assert '✻ Opus 5.5 · max' in wide[0] and '$123.46 · ◷ 2h36m' in wide[0], wide[0]
assert 'ctx ▰▱▱▱▱▱▱▱▱▱ 11% 111k/1M · 5h ▰▰▰▰▱▱▱▱▱▱ 43% ↻2h30m · week' in wide[1], wide[1]
assert 'ctx ▰▱▱▱▱▱▱▱▱▱ 11% 111k/1M' in wide[1] and '5h ▰▰▰▰▱▱▱▱▱▱ 43% ↻2h30m' in wide[1] and 'week ▰▰▰▰▰▰▰▰▰▰ 98% ↻3d11h' in wide[1], wide[1]
assert '# af9b34f1' in wide[2] and 'mem 3.2/7.5G' in wide[2] and '/tmp 12%' in wide[2] and 'sandbox' not in wide[2], wide[2]

# 5h and week read about a point under claude.ai (the headers trail the server), so they show 1 more, up to 100
limit_row = lambda p: ANSI.sub('', sb.paint(sb.card({**FULL, 'rate_limits': {'five_hour': {'used_percentage': p, 'resets_at': NOW + 9000}}}, 151, NOW, HOST)[1]))
assert '5h ▰▰▰▰▰▰▰▰▰▰ 100%' in limit_row(99.6) and '5h ▰▰▰▰▰▰▰▰▰▰ 100%' in limit_row(100), limit_row(100)
assert '5h ▱▱▱▱▱▱▱▱▱▱ 1%' in limit_row(0) and '5h ▰▰▰▰▰▰▰▱▱▱ 73%' in limit_row(72.4), limit_row(72.4)

# the card spans the footer: the terminal minus Claude Code's 2 columns of padding on each side, at any context
assert sb.card_width(188) == 184 and sb.card_width(20) == 30
# while Remote Control is on, the card leaves room for Claude Code's /rc pill and the gap before it, so the pill
# sits beside the card's top edge; under 60 columns Claude Code hides the pill, so there is nothing to make room for
assert sb.card_width(188, rc=True) == 180 and sb.card_width(60, rc=True) == 52 and sb.card_width(59, rc=True) == 55
# while Claude Code shows a notice beside the card (an update installed, its idle /clear hint), the card leaves room for
# the widest, 38 columns, and the gap, so the notices and the pill under them sit beside it, as long as the card keeps
# 80 columns; narrower, they go under the card
assert sb.card_width(188, rc=True, notices=True) == 145 and sb.card_width(188, notices=True) == 145
assert sb.card_width(123, notices=True) == 80 and sb.card_width(122, notices=True) == 118 and sb.card_width(122, True, True) == 114
# the card takes the terminal's width from COLUMNS, which Claude Code sets at every run; 120 without a usable one
assert sb.columns({'COLUMNS': '100'}) == 100 and sb.columns({}) == 120
assert sb.columns({'COLUMNS': ''}) == 120 and sb.columns({'COLUMNS': 'x'}) == 120 and sb.columns({'COLUMNS': '-5'}) == 120
src = open(spec.origin).read()
assert 'fcntl' not in src and 'termios' not in src and '/fd/' not in src, 'no Linux-only terminal probe'
assert sb.heat(0) == (0x3F, 0xB9, 0x50) and sb.heat(0.6) == (0xE3, 0xB3, 0x41) and sb.heat(1) == (0xF8, 0x51, 0x49)
assert sb.model_name('claude-opus-5-5', None) == 'Opus 5.5'
assert sb.model_name('claude-sonnet-5-5[1m]', None) == 'Sonnet 5.5 1M'
assert sb.model_name('claude-haiku-4-5-20251001', None) == 'Haiku 4.5'
assert sb.model_name('claude-opus-4-20250514', None) == 'Opus 4'
assert sb.model_name('gpt-x', 'Custom') == 'Custom'
assert sb.duration(59 * 60_000) == '59m' and sb.duration(156 * 60_000) == '2h36m' and sb.duration(50 * 3_600_000) == '2d2h'
assert sb.tokens(111_000) == '111k' and sb.tokens(1_000_000) == '1M' and sb.tokens(1_500_000) == '1.5M' and sb.tokens(800) == '800'


# the footer's states on the bottom edge
def texts(cs):
    return [''.join(p[0] for p in c) for c in cs]


# Claude Code's idle hint, "new task? /clear to save N tokens", as a chip inside the card; offered, not in the default
idle_d = {**FULL, 'context_window': {**FULL['context_window'], 'total_input_tokens': 313_000}}
assert texts([sb.chip('idle', idle_d, {'idle': True}, NOW)]) == ['↺ new task? /clear 313k']
assert sb.chip('idle', idle_d, {'idle': False}, NOW) == [] and 'idle' in sb.CHIPS and 'idle' not in sb.DEFAULT['edge']


assert sb.chips({}, {}, NOW) == []
ALL_D = {**FULL, 'version': '2.1.302', 'remote': {'session_id': 'x'}, 'fast_mode': True, 'vim': {'mode': 'INSERT'},
         'pr': {'number': 12, 'url': 'https://github.com/o/r/pull/12', 'review_state': 'approved'},
         'prompt_cache': {'warm': False, 'caching_observed': True, 'expires_at': None}}
ALL_S = {'rc': 'session_01X', 'busy': True, 'newest': '2.1.303', 'no_transcript': True, 'sandbox': True, 'drafts': 3, 'mode': 'auto'}
CH = sb.chips(ALL_D, ALL_S, NOW)
ORDER = ['◎ cloud', '⇄ rc', '⚠ no transcript', '↑ 2.1.303 restart', '◷ cache cold', '⧈ sandbox', '● working', 'PR #12 ✓', '↯ fast', '-- INSERT --']
assert sb.chips({}, {'drafts': 3}, NOW) == [], 'no drafts chip: Claude Code shows its own N feedback drafts under the card'

# no permission mode on the card: Claude Code's own mode pill sits under it and cannot be hidden
for m in ('auto', 'plan', 'acceptEdits', 'bypassPermissions', 'dontAsk'):
    assert sb.chips({}, {'mode': m}, NOW) == [], m
assert texts(CH) == ORDER, texts(CH)
assert all(p[4] == 'https://claude.ai/code/session_01X' for p in sb.chips({}, {'rc': 'session_01X'}, NOW)[0])
assert sb.chips({}, {'rc': None, 'busy': False, 'no_transcript': False, 'sandbox': False}, NOW) == []

up = lambda new, run='2.1.302': texts(sb.chips({'version': run}, {'newest': new}, NOW))
assert up('2.1.303') == ['↑ 2.1.303 restart'] and up('2.1.302') == [] and up('2.1.299') == [] and up(None) == []
assert up('2.1.10', '2.1.9') == ['↑ 2.1.10 restart'], 'versions compare as numbers'

pc = lambda **k: texts(sb.chips({'prompt_cache': k}, {}, NOW))
assert pc(warm=True, expires_at=NOW + 90) == ['◷ cache 1m'] and pc(warm=True, expires_at=NOW + 45) == ['◷ cache 45s']
assert pc(warm=True, expires_at=NOW + 600) == [] and pc(warm=True, expires_at=None) == []
assert pc(warm=False, caching_observed=True) == ['◷ cache cold'] and pc(warm=False, caching_observed=False) == []
# in brackets, what the next request costs once the cache is gone
assert pc(warm=True, expires_at=NOW + 90, recache_tokens_if_cold=843_000) == ['◷ cache 1m (843k)']
assert pc(warm=False, caching_observed=True, recache_tokens_if_cold=1_200_000) == ['◷ cache cold (1.2M)']
assert pc(warm=True, expires_at=NOW + 90, recache_tokens_if_cold=0) == ['◷ cache 1m']
# a cache miss shows for 5 minutes, with its first cause in short words and how many more there were
miss = lambda ago, *causes: pc(last_miss_at=NOW - ago, last_miss_cause={'causes': list(causes)})
assert miss(120, 'ttl_expired_5m') == ['✗ cache miss: idle 5m'] and miss(301, 'ttl_expired_5m') == [] and miss(-5) == []
assert miss(0, 'tools_changed', 'system_prompt_changed') == ['✗ cache miss: tools +1'] and miss(10) == ['✗ cache miss: unknown']
assert miss(10, 'a_new_cause') == ['✗ cache miss: a_new_cause']


def pr(state=None, kind=None):
    p = {'number': 7, 'url': 'https://x/7', **({'review_state': state} if state else {}), **({'kind': kind} if kind else {})}
    return sb.chips({'pr': p}, {}, NOW)[0]


assert texts([pr('approved')]) == ['PR #7 ✓'] and pr('approved')[0][1] == sb.GREEN
assert texts([pr('changes_requested')]) == ['PR #7 ±'] and pr('changes_requested')[0][1] == sb.RED
assert texts([pr('pending')]) == ['PR #7'] and pr('pending')[0][1] == sb.YELLOW
assert texts([pr('merged')]) == ['PR #7 ✓'] and pr('merged')[0][1] == sb.PURPLE
assert texts([pr()]) == ['PR #7'] and pr()[0][1] is None and texts([pr(None, 'mr')]) == ['MR !7']
assert all(p[4] == 'https://x/7' for p in pr())
assert sb.chips({'vim': {'mode': 'NORMAL'}}, {}, NOW) == [] and sb.chips({'fast_mode': False}, {}, NOW) == []

# the bottom edge keeps the first chips that fit and drops the rest from the right
for w in range(30, 241):
    lines = [ANSI.sub('', sb.paint(line)) for line in sb.card(FULL, w, NOW, HOST, chips=CH)]
    assert [len(line) for line in lines] == [w] * len(lines), (w, lines)
    edge = lines[-1]
    assert edge[0] == '╰' and edge[-1] == '╯', edge
    fits = [k for k in range(len(ORDER) + 1) if len(' · '.join(ORDER[:k])) <= w - 6]
    want = ' · '.join(ORDER[:max(fits)])
    assert edge == ('╰─ ' + want + ' ' + '─' * (w - 5 - len(want)) + '╯' if want else '╰' + '─' * (w - 2) + '╯'), (w, edge)
assert ANSI.sub('', sb.paint(sb.card(FULL, 80, NOW, HOST)[-1])) == '╰' + '─' * 78 + '╯'

# the meters' length
m15 = ANSI.sub('', sb.paint(sb.card(FULL, 200, NOW, HOST, meter=15)[1]))
assert 'ctx ▰▰▱▱▱▱▱▱▱▱▱▱▱▱▱ 11%' in m15, m15
assert sb.meter_arg(['x']) == 10 and sb.meter_arg(['x', '--meter', '15']) == 15 and sb.meter_arg(['x', '--meter', 'abc']) == 10
assert sb.meter_arg(['x', '--meter', '99']) == 30 and sb.meter_arg(['x', '--meter', '1']) == 3 and sb.meter_arg(['x', '--meter']) == 10

# the readers: this session's record among the live ones, the newest downloaded version, a launch-time env flag
import json
import tempfile
import time

# Claude Code's folder moves with CLAUDE_CONFIG_DIR, its downloads with XDG_DATA_HOME; empty means unset
home = os.path.expanduser('~')
assert sb.claude_dir({'CLAUDE_CONFIG_DIR': '/c'}) == '/c' and sb.claude_dir({'CLAUDE_CONFIG_DIR': ''}) == os.path.join(home, '.claude')
assert sb.versions_dir({'XDG_DATA_HOME': '/d'}) == os.path.join('/d', 'claude', 'versions')
assert sb.versions_dir({}) == os.path.join(home, '.local', 'share', 'claude', 'versions')

# a process is alive without /proc: os.kill(pid, 0) on POSIX, OpenProcess on Windows (never kill there: 0 is Ctrl+C)
import subprocess
import sys

dead = subprocess.Popen([sys.executable, '-c', ''])
dead.wait()
assert sb.alive(os.getpid()) is True and sb.alive(dead.pid) is False and sb.alive('x') is False and sb.alive(None) is False
assert '/proc/{' not in open(spec.origin).read().split('def session_record')[1].split('\ndef ')[0]
# a system without a load average (Windows) loses that element, never the card
saved = os.getloadavg
del os.getloadavg
try:
    assert 'load' not in sb.host('/nonexistent')
finally:
    os.getloadavg = saved

# names from disk or the payload cannot drive the terminal, and a hostile .git cannot stall the card
import signal

assert sb.P('a\x1b]52;c;eA==\x07b\x9bc')[0] == 'a]52;c;eA==bc' and sb.P('x', link='https://x/\x1b\\y')[4] == 'https://x/\\y'
assert sb.P('x')[4] is None


def stuck(*_):
    raise RuntimeError('git_info blocked')  # not an OSError, which git_info catches


with tempfile.TemporaryDirectory() as t:
    os.mkdir(os.path.join(t, '.git'))
    head = os.path.join(t, '.git', 'HEAD')
    os.mkfifo(head)
    signal.signal(signal.SIGALRM, stuck)
    signal.alarm(2)
    try:
        assert sb.git_info(t) == (os.path.basename(t), ''), 'a pipe for HEAD reads as nothing'
    finally:
        signal.alarm(0)
    os.remove(head)
    with open(head, 'w') as f:
        f.write('ref: refs/heads/' + 'b' * 100_000)
    assert 0 < len(sb.git_info(t)[1]) <= 256, 'only the start of HEAD is read'
    os.remove(head)
    os.symlink('/dev/zero', head)
    signal.alarm(2)
    try:
        assert sb.git_info(t) == (os.path.basename(t), ''), 'a symlink to a device reads as nothing'
    finally:
        signal.alarm(0)
    os.remove(head)
    with open(head, 'w') as f:
        f.write('ref: refs/heads/main\n')
    with open(os.path.join(t, '.git', 'packed-refs'), 'w') as f:
        f.write(('0' * 40 + ' refs/tags/x\n') * 40_000)  # 2 MB
    assert sb.git_sync(t, 'main') in (None, '⇡', '⇣', '⇅'), 'a huge packed-refs is read only in part'

# outside a repository, the search for .git ends at a Windows root too (dirname('C:\\') is 'C:\\'), simulated here
import ntpath
import types

saved = sb.os
sb.os = types.SimpleNamespace(path=ntpath)
signal.alarm(2)
try:
    assert sb.git_dir('C:\\work\\app') == (None, None) and sb.git_dir('\\\\server\\share\\x') == (None, None)
finally:
    signal.alarm(0)
    sb.os = saved

# links are https only: a file://, javascript: or ssh:// link would open on a click
assert sb.P('x', link='file:///etc/passwd')[4] is None and sb.P('x', link='javascript:x')[4] is None
assert sb.P('x', link='ssh://h/x')[4] is None and sb.P('x', link='https://github.com/o/r')[4] == 'https://github.com/o/r'

# session files of another shape are skipped
with tempfile.TemporaryDirectory() as t:
    for i, raw in enumerate([b'[]', b'null', b'{"pid": "x", "sessionId": "s"}', b'\xff\xfe']):
        with open(os.path.join(t, f'{i + 1}.json'), 'wb') as f:
            f.write(raw)
    assert sb.session_record('s', t) == {}

# a layout over 64 KiB is not read: it would cost every run
with tempfile.TemporaryDirectory() as t:
    path = os.path.join(t, 'big.json')
    with open(path, 'w') as f:
        f.write('{"meter": 7' + ' ' * 70_000 + '}')
    assert sb.load_config(path) == sb.load_config('/nonexistent') and sb.MAX_CONFIG == 64 * 1024
    # a layout of the wrong shape keeps the defaults it gets wrong, never stops the card; a pipe is not read
    for raw in ({'palette': []}, {'palette': {}}, {'rows': 5}, {'rows': [5, 'x']}, {'top_left': {'a': 1}},
                {'meter': []}, {'edge': 'x'}, {'meters': 5}):
        with open(path, 'w') as f:
            json.dump(raw, f)
        assert sb.load_config(path)['palette'] == 'default', raw
    with open(path, 'w') as f:
        json.dump({'palette': []}, f)
    run = subprocess.run([sys.executable, '-I', '-S', spec.origin], input=b'{}', capture_output=True,
                         env={**os.environ, 'SESSION_BAR_CONFIG': path})
    assert run.returncode == 0 and not run.stderr, run
    os.remove(path)
    os.mkfifo(path)
    signal.alarm(2)
    try:
        assert sb.load_config(path) == sb.load_config('/nonexistent'), 'a pipe for a layout reads as none'
    finally:
        signal.alarm(0)

# the branch ahead of origin's (⇡), behind (⇣) or apart (⇅), told by the reflogs: the branch that once stood where
# the other stands now is the one that moved on
A, B, C = 'a' * 40, 'b' * 40, 'c' * 40


def repo_at(t, local, there, local_log, there_log, packed=False):
    files = {'HEAD': 'ref: refs/heads/main\n',
             'logs/refs/heads/main': ''.join(f'{"0" * 40} {s} u <u> 1 +0000\tx\n' for s in local_log),
             'logs/refs/remotes/origin/main': ''.join(f'{"0" * 40} {s} u <u> 1 +0000\tx\n' for s in there_log)}
    if packed:
        files['packed-refs'] = f'# pack-refs with: peeled\n{local} refs/heads/main\n{there} refs/remotes/origin/main\n'
    else:
        files['refs/heads/main'], files['refs/remotes/origin/main'] = local + '\n', there + '\n'
    for path, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(t, '.git', path)), exist_ok=True)
        with open(os.path.join(t, '.git', path), 'w') as f:
            f.write(text)
    return sb.git_sync(t, 'main')


for packed in (False, True):
    for local, there, local_log, there_log, sync in ((B, A, [A, B], [A], '⇡'), (A, B, [A], [A, B], '⇣'),
                                                       (B, C, [A, B], [A, C], '⇅'), (A, A, [A], [A], None)):
        with tempfile.TemporaryDirectory() as t:
            assert repo_at(t, local, there, local_log, there_log, packed) == sync, sync
# the repository's name links to the branch on origin, from the payload's workspace.repo: Claude Code reads the
# remote itself, credentials dropped and remotes on disk left out
with tempfile.TemporaryDirectory() as t:
    repo_at(t, B, A, [A, B], [A])
    sub = os.path.join(t, 'src')
    os.mkdir(sub)
    repo_line = lambda ws: sb.card({**FULL, 'workspace': {'current_dir': sub, **ws}}, 120, NOW, HOST, 10, (),
                                   {**sb.DEFAULT, 'rows': [['repo']]})[1]
    line = repo_line({'repo': {'host': 'github.com', 'owner': 'o', 'name': 'r'}})
    assert ''.join(p[0] for p in line).startswith(f'│ ⎇ {os.path.basename(t)} main ⇡ '), line
    assert [p[4] for p in line if p[4]] == ['https://github.com/o/r/tree/main'], line
    assert not any(p[4] for p in repo_line({})) and not any(p[4] for p in repo_line({'repo': {'host': 'a b', 'owner': 'o', 'name': 'r'}}))


with tempfile.TemporaryDirectory() as t:
    sess = os.path.join(t, 'sessions')
    os.mkdir(sess)

    def put(name, **k):
        with open(os.path.join(sess, name), 'w') as f:
            json.dump(k, f)

    put(f'{os.getpid()}.json', pid=os.getpid(), sessionId='abc', status='busy', bridgeSessionId='session_01X', updatedAt=2)
    put('999999999.json', pid=999_999_999, sessionId='abc', status='idle', bridgeSessionId=None, updatedAt=3)  # gone
    put(f'{os.getppid()}.json', pid=os.getppid(), sessionId='other', status='idle', updatedAt=4)
    with open(os.path.join(sess, 'broken.json'), 'w') as f:
        f.write('{')
    rec = sb.session_record('abc', sess)
    assert rec.get('pid') == os.getpid() and rec.get('bridgeSessionId') == 'session_01X', rec
    assert sb.session_record('nope', sess) == {} and sb.session_record('', sess) == {}
    assert sb.session_record('abc', os.path.join(t, 'missing')) == {}

    vers = os.path.join(t, 'versions')
    os.mkdir(vers)
    for v in ('2.1.299', '2.1.302', '2.1.10', 'tmp-download', '2.1.302.partial'):
        open(os.path.join(vers, v), 'w').close()
    assert sb.newest_version(vers) == '2.1.302', sb.newest_version(vers)
    assert sb.newest_version(os.path.join(t, 'missing')) is None

    drafts = os.path.join(t, 'drafts')
    os.mkdir(drafts)
    for n in ('a.json', 'b.json', 'c.tmp'):
        open(os.path.join(drafts, n), 'w').close()
    assert sb.count_json(drafts) == 2 and sb.count_json(os.path.join(t, 'missing')) == 0

    # the transcript's last permission-mode entry, looked for in the file's tail only
    tr = os.path.join(t, 's.jsonl')
    with open(tr, 'w') as f:
        f.write('{"type":"permission-mode","permissionMode":"plan","sessionId":"abc"}\n')
        f.write('{"type":"user","message":"x"}\n' * 50)
        f.write('{"type":"permission-mode","permissionMode":"auto","sessionId":"abc"}\n')
        f.write('{"type":"assistant","message":"' + 'y' * 300 + '"}\n')
    assert sb.last_permission_mode(tr) == 'auto'
    assert sb.last_permission_mode(tr, tail=200) is None, 'the entry sits before the tail'
    assert sb.last_permission_mode(os.path.join(t, 'missing.jsonl')) is None and sb.last_permission_mode(None) is None

    # the battery, from the kernel's power-supply folder
    bat = os.path.join(t, 'power', 'BAT0')
    os.makedirs(bat)
    with open(os.path.join(bat, 'capacity'), 'w') as f:
        f.write('81\n')
    with open(os.path.join(bat, 'status'), 'w') as f:
        f.write('Charging\n')
    assert sb.battery(os.path.join(t, 'power')) == (81, True) and sb.battery(os.path.join(t, 'missing')) is None

    # settings: each place's elements in order; what is missing, misspelt or of another type keeps its default
    cfgp = os.path.join(t, 'session-bar.json')
    assert sb.load_config(cfgp) == sb.DEFAULT
    for raw in ('{', '["x"]', json.dumps({'meter': True})):
        with open(cfgp, 'w') as f:
            f.write(raw)
        assert sb.load_config(cfgp) == sb.DEFAULT, raw
    with open(cfgp, 'w') as f:
        json.dump({'rows': [['mem', 'nope', 'ctx', 'mem'], 'x', ['repo']], 'edge': 'x', 'meter': 99, 'top_left': ['model'],
                   'palette': 'nord'}, f)
    c = sb.load_config(cfgp)
    assert c == {**sb.DEFAULT, 'rows': [['mem', 'ctx'], ['repo']], 'meter': 30, 'top_left': ['model'], 'palette': 'nord'}, c
    with open(cfgp, 'w') as f:
        json.dump({'meters': ['ctx'], 'info': ['mem'], 'palette': 'nope'}, f)  # the first settings: two fixed rows
    assert sb.load_config(cfgp) == {**sb.DEFAULT, 'rows': [['ctx'], ['mem']]}, sb.load_config(cfgp)

# every element on at once, on a payload that has them all: each line is the card's width at every width
ALL_CFG = {'top_left': ['model', 'effort', 'thinking', 'style', 'agent', 'name', 'version'],
           'top_right': ['cost', 'time', 'api', 'lines', 'clock'], 'edge': sb.CHIPS, 'meter': 10,
           'rows': [sb.METERS, ['repo', 'cwd', 'session', 'worktree', 'dirs', 'mem', 'disks', 'load', 'battery']]}
assert set(sb.TEXT) == set(ALL_CFG['top_left'] + ALL_CFG['top_right'] + ALL_CFG['rows'][1]), 'the test covers every text element'
RICH = {**ALL_D, 'session_name': 'skin work', 'output_style': {'name': 'Explanatory'}, 'thinking': {'enabled': True},
        'agent': {'name': 'reviewer'}, 'exceeds_200k_tokens': True,
        'cost': {**FULL['cost'], 'total_api_duration_ms': 3_600_000, 'total_lines_added': 120, 'total_lines_removed': 30},
        'workspace': {**FULL['workspace'], 'added_dirs': ['/a', '/b']}, 'worktree': {'name': 'feat', 'branch': 'feat'},
        'rate_limits': {**FULL['rate_limits'], 'spend_limit': {'used_percentage': 30, 'resets_at': NOW + 86_400, 'used_usd': 15, 'limit_usd': 50}},
        'prompt_cache': {'warm': True, 'expires_at': NOW + 3000, 'hit_ratio': 0.92, 'last_miss_at': NOW - 60,
                         'last_miss_cause': {'causes': ['tools_changed']}}}
RHOST = {**HOST, 'load': (1.2, 8), 'battery': (81, True), 'thinking': True}
RS = {**ALL_S, 'mode': 'auto', 'drafts': 3}
for d in (RICH, {}):
    for w in range(30, 241):
        lines = [ANSI.sub('', sb.paint(line)) for line in sb.card(d, w, NOW, RHOST, 10, sb.chips(d, RS, NOW, sb.CHIPS), ALL_CFG)]
        assert [len(line) for line in lines] == [w] * len(lines), (w, lines)
        assert lines[0][0] == '╭' and lines[0][-1] == '╮' and lines[-1][0] == '╰' and lines[-1][-1] == '╯', lines
        assert all(line[0] == '│' and line[-1] == '│' for line in lines[1:-1]), lines
rich = [ANSI.sub('', sb.paint(line)) for line in sb.card(RICH, 240, NOW, RHOST, 10, sb.chips(RICH, RS, NOW, sb.CHIPS), ALL_CFG)]
clock = time.strftime('%H:%M', time.localtime(NOW))
assert '╭─ ✻ Opus 5.5 · max · ∴ thinking · style Explanatory · @reviewer · skin work · v2.1.302 ─' in rich[0], rich[0]
# "thinking" shows while Claude works out its next step (the host's live flag, set by main), and only in thinking
# mode: the mode alone says nothing, Opus 5.5 cannot turn it off
top = lambda d, h: ANSI.sub('', sb.paint(sb.card(d, 240, NOW, h, 10, (), {**sb.DEFAULT, 'top_left': ['model', 'thinking']})[0]))
assert '✻ Opus 5.5 · ∴ thinking ─' in top(RICH, RHOST) and 'thinking' not in top(RICH, HOST), top(RICH, RHOST)
assert 'thinking' not in top({**RICH, 'thinking': {'enabled': False}}, RHOST)
assert f'─ $123.46 · ◷ 2h36m · api 1h0m · +120 -30 · {clock} ─╮' in rich[0], rich[0]
assert 'spend ▰▰▰▱▱▱▱▱▱▱ 30% $15/$50 ↻24h0m' in rich[1] and 'hits ▰▰▰▰▰▰▰▰▰▱ 92%' in rich[1], rich[1]
assert '│ ⌂ /home/u/codewiki · # af9b34f1 · wt feat · +2 dirs · mem 3.2/7.5G · /tmp 12% · ~/.cache 64% · load 1.2 · bat 81%+ ' in rich[2], rich[2]
assert '⏵⏵ auto mode on' in rich[3] and '▲ 200k+' in rich[3] and '✎ 3 drafts' in rich[3], rich[3]
assert texts(sb.chips({}, {'drafts': 1}, NOW, ['drafts'])) == ['✎ 1 draft'] and texts(sb.chips({}, {'mode': 'plan'}, NOW, ['mode'])) == ['⏸ plan mode on']

# a row's order is the card's order; a row too long shrinks its meters to half, then wraps onto more lines
row = lambda cfg, w=151: [ANSI.sub('', sb.paint(line)) for line in sb.card(RICH, w, NOW, RHOST, 10, (), {**sb.DEFAULT, **cfg})]
assert row({'rows': [['mem', 'cwd']]})[1].startswith('│ mem 3.2/7.5G · ⌂ /home/u/codewiki '), row({'rows': [['mem', 'cwd']]})[1]
wrapped = row({'rows': [['cwd', 'session', 'mem', 'disks', 'load']]}, 70)
assert wrapped[1].startswith('│ ⌂ /home/u/codewiki · # af9b34f1 · mem 3.2/7.5G ') and wrapped[2].startswith('│ /tmp 12% · ~/.cache 64% · load 1.2 '), wrapped
m77 = row({}, 77)
assert 'ctx ▰▱▱▱▱▱▱ 11% 111k/1M · 5h' in m77[1] and m77[2].startswith('│ ⌂'), m77
m50 = row({}, 50)
assert m50[1].startswith('│ ctx ▰▱▱▱▱▱▱▱▱▱ 11% 111k/1M') and m50[2].startswith('│ 5h ▰▰▰▰▱▱▱▱▱▱ 43%') and m50[3].startswith('│ week ▰▰▰▰▰▰▰▰▰▰ 98%'), m50
assert len(row({'rows': []})) == 2 and len(row({'rows': [['mem']]})) == 3 and len(row({'rows': [['mem'], [], ['ctx']]})) == 5
narrow_top = row({'top_right': ['cost', 'time', 'clock']}, 40)[0]
assert '$123.46' in narrow_top and clock not in narrow_top, narrow_top

# colour palettes: every one has the same colours, an unknown name gets the default
assert all(set(pal) == set(sb.PALETTES['default']) for pal in sb.PALETTES.values())
# the looks, the monochrome ones last: every colour an (r, g, b), a meter's empty segments darker than the frame
assert list(sb.PALETTES) == ['default', 'nord', 'dracula', 'gruvbox', 'tokyo', 'catppuccin', 'rose-pine', 'solarized',
                             'one-dark', 'everforest', 'kanagawa', 'monokai', 'ayu', 'synthwave', 'mono', 'matrix', 'amber']
luma = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
for name, pal in sb.PALETTES.items():
    assert all(len(c) == 3 and all(isinstance(v, int) and 0 <= v <= 255 for v in c) for c in pal.values()), name
    assert luma(pal['empty']) < luma(pal['edge']), name
sb.use_palette('dracula')
dr = sb.PALETTES['dracula']
assert sb.ACCENT == dr['accent'] and sb.heat(0) == dr['green'] and sb.MODES['auto'][2] == dr['yellow']
assert sb.card(FULL, 100, NOW, HOST)[0][0][1] == dr['edge']
sb.use_palette('nope')
assert sb.ACCENT == sb.PALETTES['default']['accent'] and sb.heat(1) == sb.PALETTES['default']['red']


# a payload of unexpected shape loses its chips, never the card
import subprocess
import sys

bad = json.dumps({**FULL, 'prompt_cache': 'x', 'pr': 'x', 'vim': 'x', 'version': 5})
env = {**os.environ, 'SESSION_BAR_CONFIG': '/nonexistent/session-bar.json'}
run = subprocess.run([sys.executable, '-I', '-S', spec.origin], input=bad.encode(), capture_output=True, env=env)
assert run.returncode == 0 and run.stdout.decode().count('\n') == 4 and not run.stderr, run
odd = json.dumps({**FULL, 'context_window': {**FULL['context_window'], 'used_percentage': float('nan')},
                  'rate_limits': {'five_hour': {'used_percentage': float('inf'), 'resets_at': NOW}},
                  'prompt_cache': {'hit_ratio': float('inf')}})  # NaN and Infinity, not JSON
with tempfile.TemporaryDirectory() as t:
    with open(os.path.join(t, 'c.json'), 'w') as f:
        json.dump({'rows': [['ctx', '5h', 'week', 'hits']]}, f)
    run = subprocess.run([sys.executable, '-I', '-S', spec.origin], input=odd.encode(), capture_output=True,
                         env={**env, 'SESSION_BAR_CONFIG': os.path.join(t, 'c.json')})
    assert run.returncode == 0 and run.stdout.decode().count('\n') == 3 and not run.stderr, run
with tempfile.TemporaryDirectory() as t:  # an empty home: no session file, no newer version, no notice
    for cols, width in (('100', 96), ('x', 116)):
        run = subprocess.run([sys.executable, '-I', '-S', spec.origin], input=json.dumps(FULL).encode(),
                             capture_output=True, env={**env, 'HOME': t, 'COLUMNS': cols})
        assert {len(ANSI.sub('', l)) for l in run.stdout.decode().splitlines()} == {width}, (cols, run)

# the script reads its settings
with tempfile.TemporaryDirectory() as t:
    with open(os.path.join(t, 'c.json'), 'w') as f:
        json.dump({'rows': [['mem']]}, f)
    run = subprocess.run([sys.executable, '-I', '-S', spec.origin], input=json.dumps(FULL).encode(), capture_output=True,
                         env={**env, 'SESSION_BAR_CONFIG': os.path.join(t, 'c.json')})
    assert run.returncode == 0 and run.stdout.decode().count('\n') == 3 and not run.stderr, run

# while Remote Control is on (bridgeSessionId in this session's process file), the script's card is 4 columns
# narrower, from 60 columns up, whatever the terminal's width; while a notice of Claude Code's sits beside it, 39
with tempfile.TemporaryDirectory() as t:
    os.makedirs(os.path.join(t, '.claude', 'sessions'))

    def first_line_width(rec, d=FULL):
        with open(os.path.join(t, '.claude', 'sessions', f'{os.getpid()}.json'), 'w') as f:
            json.dump({'sessionId': FULL['session_id'], 'pid': os.getpid(), **rec}, f)
        run = subprocess.run([sys.executable, '-I', '-S', spec.origin], input=json.dumps(d).encode(),
                             capture_output=True, env={**env, 'HOME': t, 'COLUMNS': '188'})
        assert run.returncode == 0 and not run.stderr, run
        return len(ANSI.sub('', run.stdout.decode().split('\n')[0]))

    off, on = first_line_width({}), first_line_width({'bridgeSessionId': 'session_01X'})
    assert off - on == (4 if off >= 56 else 0), (off, on)
    beside = first_line_width({'status': 'idle', 'statusUpdatedAt': (time.time() - 80 * 60) * 1000})
    assert off - beside == (39 if off >= 119 else 0), (off, beside)
    os.makedirs(os.path.join(t, '.local', 'share', 'claude', 'versions', '9.9.9'))
    assert first_line_width({}, {**FULL, 'version': '2.1.302'}) == beside, 'an update installed makes the same room'

# the idle chip keeps its own thresholds (75 minutes, 100k): set CLAUDE_CODE_IDLE_TOKEN_THRESHOLD high where claude
# starts and Claude Code's own hint is gone, the card's shows, and the card takes back the room it kept for the hint
with tempfile.TemporaryDirectory() as t:
    os.makedirs(os.path.join(t, '.claude', 'sessions'))
    with open(os.path.join(t, '.claude', 'sessions', f'{os.getpid()}.json'), 'w') as f:
        json.dump({'sessionId': FULL['session_id'], 'pid': os.getpid(), 'status': 'idle',
                   'statusUpdatedAt': (time.time() - 80 * 60) * 1000}, f)
    with open(os.path.join(t, 'c.json'), 'w') as f:
        json.dump({'edge': ['idle']}, f)
    run = subprocess.run([sys.executable, '-I', '-S', spec.origin], input=json.dumps(FULL).encode(), capture_output=True,
                         env={**env, 'HOME': t, 'COLUMNS': '188', 'SESSION_BAR_CONFIG': os.path.join(t, 'c.json'),
                              'CLAUDE_CODE_IDLE_TOKEN_THRESHOLD': '999999999'})
    lines = [ANSI.sub('', l) for l in run.stdout.decode().splitlines()]
    assert '↺ new task? /clear' in lines[-1] and {len(l) for l in lines} == {184}, lines

# the script finds the session file and the downloads where CLAUDE_CONFIG_DIR and XDG_DATA_HOME put them
with tempfile.TemporaryDirectory() as t:
    cfg_dir, data = os.path.join(t, 'cfg'), os.path.join(t, 'data')
    os.makedirs(os.path.join(cfg_dir, 'sessions'))
    with open(os.path.join(cfg_dir, 'sessions', f'{os.getpid()}.json'), 'w') as f:
        json.dump({'sessionId': FULL['session_id'], 'pid': os.getpid(), 'bridgeSessionId': 'session_01X'}, f)
    os.makedirs(os.path.join(data, 'claude', 'versions', '9.9.9'))
    run = subprocess.run([sys.executable, '-I', '-S', spec.origin], input=json.dumps({**FULL, 'version': '2.1.302'}).encode(),
                         capture_output=True, env={**env, 'HOME': t, 'COLUMNS': '188', 'CLAUDE_CONFIG_DIR': cfg_dir, 'XDG_DATA_HOME': data})
    bottom = ANSI.sub('', run.stdout.decode().splitlines()[-1])
    assert '⇄ rc' in bottom and '↑ 9.9.9' in bottom, bottom

# who spoke last in a transcript, read from its tail: Claude Code writes a message once it is whole, so while the user
# or a tool's result spoke last, Claude is at work on its next step; other entries and side chains do not count
PROMPT, RESULT = {'type': 'user', 'message': {'content': 'hi'}}, {'type': 'user', 'message': {'content': [{'type': 'tool_result'}]}}
THOUGHT, CALL = [{'type': 'assistant', 'message': {'content': [{'type': k}]}} for k in ('thinking', 'tool_use')]
line = lambda e: json.dumps(e, separators=(',', ':')) + '\n'  # as Claude Code writes them
with tempfile.TemporaryDirectory() as t:
    path = os.path.join(t, 's.jsonl')
    for entries, tail, who in (([PROMPT, THOUGHT, RESULT], '', 'user'), ([PROMPT, THOUGHT], '', 'assistant'),
                               ([THOUGHT, RESULT, {'type': 'system'}, {**CALL, 'isSidechain': True}], '{"type":"assist', 'user')):
        with open(path, 'w') as f:
            f.write(''.join(map(line, entries)) + tail)
        assert sb.last_speaker(path) == who, (entries, who)
    assert sb.last_speaker(os.path.join(t, 'none.jsonl')) is None and sb.last_speaker(None) is None

# the script shows "∴ thinking" while the session is busy and the user or a tool spoke last
with tempfile.TemporaryDirectory() as t:
    os.makedirs(os.path.join(t, '.claude', 'sessions'))
    conf, path = os.path.join(t, 'c.json'), os.path.join(t, 's.jsonl')
    with open(conf, 'w') as f:
        json.dump({'top_left': ['model', 'thinking']}, f)

    def top_line(status, last):
        with open(os.path.join(t, '.claude', 'sessions', f'{os.getpid()}.json'), 'w') as f:
            json.dump({'sessionId': FULL['session_id'], 'pid': os.getpid(), 'status': status}, f)
        with open(path, 'w') as f:
            f.write(line(PROMPT) + line(last))
        d = {**FULL, 'thinking': {'enabled': True}, 'transcript_path': path}
        run = subprocess.run([sys.executable, '-I', '-S', spec.origin], input=json.dumps(d).encode(), capture_output=True,
                             env={**env, 'HOME': t, 'SESSION_BAR_CONFIG': conf})
        assert run.returncode == 0 and not run.stderr, run
        return ANSI.sub('', run.stdout.decode().split('\n')[0])

    assert '∴ thinking' in top_line('busy', RESULT), top_line('busy', RESULT)
    assert 'thinking' not in top_line('busy', CALL) and 'thinking' not in top_line('idle', RESULT)

F = 'CLAUDE_CODE_SKIP_PROMPT_HISTORY'
assert sb.env_flag({'A': '1', F: '1'}, F) is True and sb.env_flag({F: 'true'}, F) is True
assert sb.env_flag({F: '0'}, F) is False and sb.env_flag({}, F) is False
assert sb.env_flag({'X_' + F: '1'}, F) is False

# the card reads named variables from its own environment only: never another process's, which holds every key
assert '/environ' not in open(spec.origin).read()
run = subprocess.run([sys.executable, '-I', '-S', spec.origin], input=json.dumps(FULL).encode(), capture_output=True,
                     env={**env, F: '1'})
assert '⚠ no transcript' in run.stdout.decode(), run

# Claude Code's idle hint shows once the session has been idle 75 minutes since its turn ended, with 100k tokens or
# more; its environment can move both thresholds
idle = lambda minutes, tokens=200_000, env={}, status='idle': sb.idle_hint(
    {'status': status, 'statusUpdatedAt': (NOW - minutes * 60) * 1000}, {'context_window': {'total_input_tokens': tokens}}, env, NOW)
assert idle(76) and not idle(74) and not idle(76, tokens=99_000) and not idle(76, status='busy')
assert idle(11, env={'CLAUDE_CODE_IDLE_THRESHOLD_MINUTES': '10'}) and idle(76, 60_000, {'CLAUDE_CODE_IDLE_TOKEN_THRESHOLD': '50000'})
assert idle(76, env={'CLAUDE_CODE_IDLE_THRESHOLD_MINUTES': 'x'}) and not sb.idle_hint({'status': 'idle'}, FULL, {}, NOW)
assert sb.update_ready('2.1.303', '2.1.302') and not sb.update_ready('2.1.302', '2.1.302')
assert not sb.update_ready(None, '2.1.302') and not sb.update_ready('2.1.303', None)

# the settings page (configure.py): its cleaning, its sample, the card it draws, the previews, guards, lifetime
wspec = importlib.util.spec_from_file_location('web', os.path.join(os.path.dirname(spec.origin), 'configure.py'))
web = importlib.util.module_from_spec(wspec)
wspec.loader.exec_module(web)
assert set(web.WHAT) == set(sb.TEXT + sb.METERS + sb.CHIPS), 'every element says what it shows'
with tempfile.TemporaryDirectory() as t:  # saved whole, through a temporary file that does not stay behind
    path = os.path.join(t, 'session-bar.json')
    cfg = {**sb.DEFAULT, 'rows': [['load', 'battery'], ['ctx']], 'meter': 7, 'palette': 'gruvbox'}
    web.save(cfg, path)
    assert sb.load_config(path) == cfg and os.listdir(t) == ['session-bar.json'], os.listdir(t)
    assert os.stat(path).st_mode & 0o777 == 0o644
c = web.clean({'rows': [['ctx', 'bogus', 'rc'], ['repo']], 'edge': ['rc', 'ctx'], 'palette': 'nord', 'meter': 99})
assert c['rows'] == [['ctx'], ['repo']] and c['edge'] == ['rc'] and c['palette'] == 'nord' and c['meter'] == 30, c
before = json.dumps(web.SAMPLE)
d = web.sample()  # the sample with its clocks moved to now, so its resets stay as far off as written
far = web.SAMPLE['rate_limits']['five_hour']['resets_at'] - web.NOW
assert abs(d['rate_limits']['five_hour']['resets_at'] - time.time() - far) < 5 and json.dumps(web.SAMPLE) == before
for cols, rc in ((188, True), (188, False), (59, True), (40, False)):
    r = web.render(c, cols, rc, d)
    assert r['width'] == sb.card_width(cols, rc) and all(sum(len(p[0]) for p in l) == r['width'] for l in r['lines']), (cols, rc)
pv = web.previews(c, d)
flat = lambda pieces: ''.join(p[0] for p in pieces)
assert set(pv) == set(sb.TEXT + sb.METERS + sb.CHIPS), set(pv) ^ set(sb.TEXT + sb.METERS + sb.CHIPS)
assert flat(pv['ctx']).startswith('ctx ▰') and flat(pv['repo']).startswith('⎇ ') and flat(pv['rc']).endswith('rc'), pv['rc']
assert flat(pv['thinking']) == '∴ thinking', pv['thinking']  # the sample session is mid-step
H = {'127.0.0.1:8790'}
assert web.trusted('127.0.0.1:8790', None, 'GET', H) and web.trusted('127.0.0.1:8790', 'http://127.0.0.1:8790', 'POST', H)
assert not web.trusted('evil.example:8790', None, 'GET', H) and not web.trusted('127.0.0.1:8790', 'http://evil.example', 'POST', H)
life = web.Life(1000)
assert not life.over(1299) and life.over(1301)  # no page yet: five minutes, to open the address by hand
life.ping(1400)
assert not life.over(1549) and life.over(1551)  # silence: 2.5 minutes, past a background tab's once-a-minute timers
life.bye(1560)
assert not life.over(1563) and life.over(1565)  # the page said goodbye: a few seconds, in case it was a reload

import socket
import threading
import urllib.error
import urllib.request

def opened(base, token):
    """The page's first act: its address's one-time token, from #t=, swapped for the session it sends as X-Session."""
    r = urllib.request.urlopen(urllib.request.Request(base + '/api/open', data=json.dumps({'t': token}).encode(),
                                                      headers={'Content-Type': 'application/json'}), timeout=5)
    return {'X-Session': json.load(r)['session']}


with tempfile.TemporaryDirectory() as t:
    web.SAVE = os.path.join(t, 'session-bar.json')
    life = web.Life(time.time())
    srv = web.make_server(0, life)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base, token = f'http://127.0.0.1:{srv.server_address[1]}', web.Handler.token

    def refused(req, code=403):
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError(f'answered: {req}')
        except urllib.error.HTTPError as e:
            assert e.code == code, e.code

    # the page holds no secret and loads for anyone on this machine; its API answers only with the session that the
    # address's one-time token buys. The token never rides a command line (ps shows those to every user), and a
    # session in a header, unlike a cookie, never reaches another port of 127.0.0.1
    assert urllib.request.urlopen(base + '/', timeout=5).status == 200 and len(token) >= 20
    refused(base + '/api/state')
    refused(urllib.request.Request(base + '/api/state', headers={'X-Session': 'wrong'}))
    refused(urllib.request.Request(base + '/api/open', data=b'{"t": "wrong"}', headers={'Content-Type': 'application/json'}))
    refused(urllib.request.Request(base + '/api/save', data=b'{}', headers={'Content-Type': 'application/json'}))
    C = opened(base, token)
    post = lambda path, body, **h: urllib.request.urlopen(urllib.request.Request(
        base + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', **C, **h}), timeout=5)
    st = json.load(urllib.request.urlopen(urllib.request.Request(base + '/api/state', headers=C), timeout=5))
    assert st['cfg'] == sb.load_config(web.SAVE) and set(st['palettes']) == set(sb.PALETTES), st['cfg']
    assert set(st) == {'cfg', 'kinds', 'places', 'what', 'palettes', 'columns', 'file', 'scope'}, set(st)  # what the page reads
    assert st['file'] == web.SAVE, st['file']
    with open(web.PAGE) as f:  # the page says which layout it edits, as text, never as markup
        assert "$('#which').textContent = `${S.scope} layout · ${S.file}`" in f.read()
    got = json.load(post('/api/render', {'cfg': {'rows': [['week']]}, 'columns': 120, 'rc': True}))
    assert got['width'] == 112 and flat(got['lines'][1]).startswith('│ week ▰▰▰▰▰▰▰▱▱▱ 69%') and set(got['previews']) == set(pv), got['lines'][1]
    assert set(got) == {'cfg', 'width', 'lines', 'previews'}, set(got)
    try:
        post('/api/save', {'cfg': c}, Origin='http://evil.example')
        raise AssertionError('a foreign page saved the settings')
    except urllib.error.HTTPError as e:
        assert e.code == 403 and not os.path.exists(web.SAVE), e.code
    json.load(post('/api/save', {'cfg': c}))
    assert sb.load_config(web.SAVE) == c
    # on Linux the token is taken only from a connection of this user's (/proc/net/tcp says whose a socket is): one
    # who read it in ps under another account gets nothing
    if sys.platform.startswith('linux'):
        with socket.create_connection(('127.0.0.1', srv.server_address[1])) as probe:
            assert web.peer_uid(probe.getsockname()[1], srv.server_address[1]) == os.getuid()
        saved, web.peer_uid = web.peer_uid, lambda *a: os.getuid() + 1
        try:  # the spent token, replayed by another user, cannot even end the server
            refused(urllib.request.Request(base + '/api/open', data=json.dumps({'t': token}).encode(),
                                           headers={'Content-Type': 'application/json'}))
        finally:
            web.peer_uid = saved
    # the token buys one session; spent again, it means someone else opened the page first: the server ends, and
    # whatever session they got ends with it
    assert not life.over(time.time())
    refused(urllib.request.Request(base + '/api/open', data=json.dumps({'t': token}).encode(),
                                   headers={'Content-Type': 'application/json'}), 409)
    assert life.over(time.time())
    srv.shutdown()
    srv.server_close()

# the server's guards: a body too big, not JSON or of another type, and paths that try to leave the page, all
# answered without touching the layout
import http.client

with tempfile.TemporaryDirectory() as t:
    web.SAVE = os.path.join(t, 'guarded.json')
    srv = web.make_server(0, web.Life(time.time()))
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def status(method, path, body=b'', **headers):
        conn = http.client.HTTPConnection('127.0.0.1', srv.server_address[1], timeout=5)
        conn.request(method, path, body=body or None, headers=headers)
        r = conn.getresponse()
        r.read()
        conn.close()
        return r.status

    if sys.platform.startswith('linux'):  # a fresh token, offered by another user: refused, and still good for ours
        saved, web.peer_uid = web.peer_uid, lambda *a: os.getuid() + 1
        try:
            assert status('POST', '/api/open', json.dumps({'t': web.Handler.token}).encode(), **{'Content-Type': 'application/json'}) == 403
        finally:
            web.peer_uid = saved
    J = {'Content-Type': 'application/json', **opened(f'http://127.0.0.1:{srv.server_address[1]}', web.Handler.token)}
    assert status('POST', '/api/save', b'{}', **J, **{'Content-Length': str(web.MAX_BODY + 1)}) == 400
    assert status('POST', '/api/save', b'{oops', **J) == 400 and status('POST', '/api/save', b'{}', **{**J, 'Content-Type': 'text/plain'}) == 400
    assert {status('GET', p, **{'X-Session': J['X-Session']}) for p in ('/../session-bar.py', '/%2e%2e/session-bar.json', '/configure.py')} == {404}
    assert not os.path.exists(web.SAVE)
    # checked again at save time: a folder swapped for a symlink after the page opened is not written into
    os.makedirs(os.path.join(t, 'elsewhere'))
    os.symlink(os.path.join(t, 'elsewhere'), os.path.join(t, 'via'))
    web.SAVE = os.path.join(t, 'via', 'session-bar.json')
    assert status('POST', '/api/save', json.dumps({'cfg': {}}).encode(), **J) == 500 and os.listdir(os.path.join(t, 'elsewhere')) == []
    srv.shutdown()
    srv.server_close()

# the launcher edits the layout that applies here: the nearest project's, else the user's; never one above home
with tempfile.TemporaryDirectory() as t:
    home, user = os.path.join(t, 'h'), os.path.join(t, 'h', '.claude', 'session-bar', 'session-bar.json')
    proj = os.path.join(home, 'work', 'app')
    os.makedirs(os.path.join(proj, '.claude'))
    os.makedirs(os.path.join(proj, 'src', 'deep'))
    os.makedirs(os.path.join(t, '.claude'))
    open(os.path.join(t, '.claude', 'session-bar.json'), 'w').close()  # above home: never used
    assert web.layout_for(os.path.join(home, 'work'), user, home) == (user, 'user')
    assert web.layout_for(home, user, home) == (user, 'user'), 'from home itself, the layout above home is not taken'
    layout = os.path.join(proj, '.claude', 'session-bar.json')
    with open(layout, 'w') as f:  # a hostile project layout: unknown elements, wrong types, past the 64 KiB cap
        f.write('{"rows": [["nope", 5]], "meter": "x"' + ' ' * 70_000 + '}')
    # a project's layout is the page's only where the card reads it: that project's local status line points at it
    assert web.layout_for(os.path.join(proj, 'src', 'deep'), user, home) == (user, 'user'), 'no project install yet'
    with open(os.path.join(proj, '.claude', 'settings.local.json'), 'w') as f:
        json.dump({'statusLine': {'type': 'command', 'command': 'npx ccstatusline'}}, f)
    assert web.layout_for(os.path.join(proj, 'src', 'deep'), user, home) == (user, 'user'), 'another tool draws here'
    reads = json.dumps({'statusLine': {'type': 'command', 'command':
                        'env -i SESSION_BAR_CONFIG="$CLAUDE_PROJECT_DIR/.claude/session-bar.json" python3 -I -S card.py'}})

    def installed(folder):
        with open(os.path.join(folder, '.claude', 'settings.local.json'), 'w') as f:
            f.write(reads)

    installed(proj)
    assert web.layout_for(os.path.join(proj, 'src', 'deep'), user, home) == (layout, 'project')
    # a layout the page would save is only one of this user's that no one else can write, in a real .claude folder;
    # and a save never writes through a planted temporary file
    shared = os.path.join(home, 'shared')
    os.makedirs(os.path.join(shared, '.claude'))
    open(os.path.join(shared, '.claude', 'session-bar.json'), 'w').close()
    installed(shared)
    os.chmod(os.path.join(shared, '.claude'), 0o777)
    linked = os.path.join(home, 'linked')
    os.makedirs(linked)
    os.symlink(os.path.join(proj, '.claude'), os.path.join(linked, '.claude'))
    loose = os.path.join(home, 'loose')
    os.makedirs(os.path.join(loose, '.claude'))
    open(os.path.join(loose, '.claude', 'session-bar.json'), 'w').close()
    installed(loose)
    os.chmod(os.path.join(loose, '.claude', 'session-bar.json'), 0o666)
    assert [web.layout_for(p, user, home)[1] for p in (shared, linked, loose)] == ['user'] * 3
    try:
        web.save(sb.DEFAULT, os.path.join(shared, '.claude', 'session-bar.json'))
        raise AssertionError('saved into a folder anyone can write')
    except ValueError:
        pass
    os.symlink(os.path.join(t, 'victim'), layout + '.tmp')
    web.save(sb.DEFAULT, layout)
    assert not os.path.exists(os.path.join(t, 'victim')) and sb.load_config(layout) == sb.DEFAULT
    os.remove(layout + '.tmp')
    with open(layout, 'w') as f:  # hostile again, for the detached run below
        f.write('{"rows": [["nope", 5]], "meter": "x"' + ' ' * 70_000 + '}')
    # started detached, the page's server answers for the project's layout; with no browser to open, the address is
    # printed; with one, nothing is (so `! session-bar` adds next to nothing to the conversation)
    bare = {k: v for k, v in os.environ.items() if k not in ('DISPLAY', 'WAYLAND_DISPLAY', 'BROWSER', 'SESSION_BAR_CONFIG')}
    began = time.time()
    run = subprocess.run([sys.executable, '-I', '-S', wspec.origin, '--detach', '0'], cwd=os.path.join(proj, 'src'),
                         env={**bare, 'HOME': home, 'PATH': '/nonexistent'}, capture_output=True, text=True, timeout=15)
    assert run.returncode == 0 and time.time() - began < 5 and run.stdout.count('\n') == 1 and 'http://127.0.0.1:' in run.stdout, run
    url = run.stdout.strip().rsplit(' ', 1)[1]

    def session(url):  # what the page does with its address: spend the token in #t= for a session
        root, token = url.split('/#t=')
        return root, opened(root, token)

    root, C = session(url)
    st = json.load(urllib.request.urlopen(urllib.request.Request(f'{root}/api/state', headers=C), timeout=5))
    assert st['scope'] == 'project' and st['file'] == layout and st['cfg'] == sb.load_config('/nonexistent'), st
    urllib.request.urlopen(urllib.request.Request(f'{root}/api/bye', data=b'', headers=C), timeout=5)
    import socket

    def browser(name, body):  # a stand-in browser: BROWSER runs it with the page's address
        path = os.path.join(t, name)
        with open(path, 'w') as f:
            f.write('#!/bin/sh\n' + body + '\n')
        os.chmod(path, 0o755)
        return path

    def free_port():
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]

    seen = os.path.join(t, 'opened.txt')
    run = subprocess.run([sys.executable, '-I', '-S', wspec.origin, '--detach', str(free_port())], cwd=proj, capture_output=True, text=True,
                         env={**bare, 'HOME': home, 'BROWSER': browser('record', f'echo "$1" > {seen}'), 'PATH': '/usr/bin:/bin'}, timeout=15)
    assert run.returncode == 0 and run.stdout == '', run
    with open(seen) as f:
        given = f.read().strip()
    assert '/#t=' in given and '?' not in given, given  # in the fragment: never in a request line, a log or a Referer
    root, C = session(given)
    urllib.request.urlopen(urllib.request.Request(f'{root}/api/bye', data=b'', headers=C), timeout=5)
    # the server answers while a browser that blocks (a console one) still runs
    port = free_port()
    slow = subprocess.Popen([sys.executable, '-I', '-S', wspec.origin, '--serve', str(port)], cwd=proj, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, env={**bare, 'HOME': home, 'BROWSER': browser('block', 'sleep 5'), 'PATH': '/usr/bin:/bin'})
    try:
        for _ in range(40):
            try:
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
                conn.request('GET', '/api/state')
                assert conn.getresponse().status == 403
                break
            except ConnectionRefusedError:
                time.sleep(0.05)
        else:
            raise AssertionError('the server never listened')
    finally:
        slow.kill()
        slow.wait()

# the installer (install.py): the status line command starts Python with an empty environment and a short list, so
# no key Claude Code was started with reaches the card; paths with a space or a quote still run
import stat

ispec = importlib.util.spec_from_file_location('install', os.path.join(os.path.dirname(spec.origin), 'install.py'))
inst = importlib.util.module_from_spec(ispec)
ispec.loader.exec_module(inst)
with tempfile.TemporaryDirectory() as t:
    folder = os.path.join(t, "a b'c")
    os.mkdir(folder)
    stub = os.path.join(folder, 'stub.py')
    with open(stub, 'w') as f:
        f.write('import json, os, sys; json.dump(dict(os.environ), sys.stdout)')
    outer = {**os.environ, 'FAKE_SECRET': 'k', 'ANTHROPIC_API_KEY': 'k', 'COLUMNS': '90', 'CLAUDE_PROJECT_DIR': '/p'}
    for project in (False, True):
        run = subprocess.run(['sh', '-c', inst.card_command(sys.executable, stub, project)], capture_output=True, env=outer)
        seen = json.loads(run.stdout)
        assert 'FAKE_SECRET' not in seen and 'ANTHROPIC_API_KEY' not in seen and seen['COLUMNS'] == '90', seen
        assert set(seen) - {'LC_CTYPE', 'SESSION_BAR_CONFIG'} <= set(inst.CARD_ENV), set(seen)  # PEP 538 may add LC_CTYPE
        assert seen.get('SESSION_BAR_CONFIG') == ('/p/.claude/session-bar.json' if project else None), seen
assert "'C:/Py/python.exe'" in inst.card_command('C:\\Py\\python.exe', 'C:\\x\\s.py', windows=True)
# backslashes become / only for Windows (Git Bash drops them); on POSIX a backslash is a character of the name
assert inst.sh_word('/a\\b', windows=False) == "'/a\\b'" and inst.sh_word('C:\\Py', windows=True) == "'C:/Py'"
assert inst.ps_word("C:/o’neil/‘x’") == "'C:/o’’neil/‘‘x’’'", inst.ps_word("C:/o’neil/‘x’")  # PowerShell reads ‘ ’ as '
ps = inst.card_command('C:/Py/python.exe', 'C:/x/s.py', project=True, shell='powershell')
assert 'env -i' not in ps and ps.startswith('$env:SESSION_BAR_CONFIG') and "& 'C:/Py/python.exe'" in ps, ps

# the settings file: never written when it cannot be read; written whole, through its symlink, keeping its mode and
# its non-ASCII text, after a backup of the old bytes
with tempfile.TemporaryDirectory() as t:
    assert inst.read_settings(os.path.join(t, 'none.json')) == {}
    bad = os.path.join(t, 'bad.json')
    for text in ('{oops', '[]'):
        with open(bad, 'w') as f:
            f.write(text)
        try:
            inst.read_settings(bad)
            raise AssertionError(text)
        except inst.SettingsError:
            pass
    if os.geteuid() != 0:
        os.chmod(bad, 0)
        try:
            inst.read_settings(bad)
            raise AssertionError('unreadable')
        except inst.SettingsError:
            pass
    old = {'name': 'Ștefan', 'theme': 'dark', 'permissions': {'allow': ['Bash(ls)']}}
    real, link = os.path.join(t, 'real.json'), os.path.join(t, 'settings.json')
    with open(real, 'w', encoding='utf-8') as f:
        f.write(json.dumps(old, indent=2) + '\n')  # as Claude Code writes it
    os.chmod(real, 0o600)
    os.symlink(real, link)
    with open(real, 'rb') as f:
        before = f.read()
    sl = inst.status_line('x')
    assert sl == {'type': 'command', 'command': 'x', 'padding': 0, 'refreshInterval': 1}
    backup = inst.write_settings(link, {**old, 'statusLine': sl}, '2026-10-20')
    with open(real, encoding='utf-8') as f:
        text = f.read()
    assert os.path.islink(link) and json.loads(text) == {**old, 'statusLine': sl} and 'Ștefan' in text
    assert stat.S_IMODE(os.stat(real).st_mode) == 0o600 and sorted(os.listdir(t)) == sorted(
        ['bad.json', 'real.json', 'settings.json', 'real.json.bak-2026-10-20-session-bar']), os.listdir(t)
    with open(backup, 'rb') as f:
        assert backup == real + '.bak-2026-10-20-session-bar' and f.read() == before
    assert inst.write_settings(link, old, '2026-10-20') == real + '.bak-2026-10-20-session-bar-2'
    assert inst.write_settings(os.path.join(t, 'new.json'), old, '2026-10-20') is None
    diff = inst.settings_diff(old, {**old, 'statusLine': sl}, link)
    assert '+  "statusLine": {' in diff and not any(l[:1] in '+-' and 'theme' in l for l in diff.splitlines()), diff
    # the diff never shows what an env block holds: the installer's output can land in a conversation
    secret = {'theme': 'dark', 'env': {'ANTHROPIC_API_KEY': 'sk-ant-SECRET'}}
    assert 'SECRET' not in inst.settings_diff(secret, {**secret, 'statusLine': sl}, link)
    assert 'SECRET' not in inst.settings_diff({**secret, 'statusLine': sl}, secret, link)
script = '/x/session-bar/session-bar.py'
assert inst.is_ours(inst.status_line(inst.card_command(sys.executable, script)), script)

# the page's server starts with the page's names only, whatever launcher started it (a .cmd has no env -i)
import io

seen = {}


class Started:
    stdout = io.BytesIO(b'opened http://127.0.0.1:1/\n')


def popen(cmd, **kw):
    seen.update(kw)
    return Started()


saved, os.environ['FAKE_SECRET'] = subprocess.Popen, 'k'
subprocess.Popen = popen
try:
    assert web.detach(0) == 0
finally:
    subprocess.Popen = saved
    del os.environ['FAKE_SECRET']
assert 'FAKE_SECRET' not in seen['env'] and set(seen['env']) <= set(web.PAGE_ENV) and web.PAGE_ENV == inst.PAGE_ENV
assert {'XAUTHORITY', 'XDG_CURRENT_DESKTOP'} <= set(web.PAGE_ENV), 'what a desktop browser needs under X11'

# launchers for a home with Ș in its name, on Windows: the .cmd stays ASCII through %USERPROFILE%, a % is doubled;
# Git Bash finds bash where Claude Code would
with tempfile.TemporaryDirectory() as t:
    home, saved = os.path.join(t, 'Ștefan'), os.environ['HOME']
    os.environ['HOME'] = home
    try:
        paths = inst.write_launcher(os.path.join(home, '.local', 'bin'), os.path.join(home, 'Py', 'python.exe'),
                                    os.path.join(home, '50%', 'configure.py'), True)
    finally:
        os.environ['HOME'] = saved
    with open(paths[1], 'rb') as f:
        cmd = f.read().decode('ascii')
    assert '%USERPROFILE%' in cmd and '50%%' in cmd and 'Ștefan' not in cmd, cmd
    with open(paths[0], encoding='utf-8') as f:
        assert 'Ștefan' in f.read()
    fake = os.path.join(t, 'bash.exe')
    open(fake, 'w').close()
    other = os.path.join(t, 'other.exe')
    open(other, 'w').close()
    assert inst.git_bash({'CLAUDE_CODE_GIT_BASH_PATH': fake}) == fake and inst.git_bash({'CLAUDE_CODE_GIT_BASH_PATH': other}) != other
    # a session-bar of someone else's in ~/.local/bin is left alone
    mine = os.path.join(t, '.local', 'bin', 'session-bar')
    os.makedirs(os.path.dirname(mine))
    with open(mine, 'w') as f:
        f.write('echo mine\n')
    run = subprocess.run([sys.executable, '-I', ispec.origin, '--yes'], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                         env={**os.environ, 'HOME': t, 'CLAUDE_CONFIG_DIR': os.path.join(t, 'c')})
    with open(mine) as f:
        assert run.returncode == 0 and f.read() == 'echo mine\n' and 'left as it is' in run.stdout, run
    # a console that cannot print Ș (cp1252 in mintty, here ascii) costs a character, not the install
    run = subprocess.run([sys.executable, '-X', 'utf8=0', ispec.origin, '--dry-run'], capture_output=True, stdin=subprocess.DEVNULL,
                         env={**os.environ, 'HOME': home, 'CLAUDE_CONFIG_DIR': os.path.join(home, 'c'), 'PYTHONIOENCODING': 'ascii'})
    assert run.returncode == 0, run
assert not inst.is_ours({'type': 'command', 'command': 'npx ccstatusline'}, script) and not inst.is_ours(None, script)

# installing and uninstalling, for the user and for a project: a layout is never lost, a settings file it cannot read
# or a status line that is not its own is never overwritten unasked
with tempfile.TemporaryDirectory() as t:
    c, proj = os.path.join(t, 'c'), os.path.join(t, 'p')
    os.makedirs(proj)
    today = time.strftime('%Y-%m-%d')

    def installer(*args, cfg=c):
        return subprocess.run([sys.executable, '-I', ispec.origin, *args], capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, env={**os.environ, 'HOME': t, 'CLAUDE_CONFIG_DIR': cfg})

    def settings(path=os.path.join(c, 'settings.json')):
        with open(path, encoding='utf-8') as f:
            return json.load(f)

    code, layout, launcher = os.path.join(c, 'session-bar'), os.path.join(c, 'session-bar', 'session-bar.json'), os.path.join(t, '.local', 'bin', 'session-bar')
    run = installer('--scope', 'user', '--yes')
    assert run.returncode == 0, run
    assert all(os.path.isfile(os.path.join(code, n)) for n in inst.CODE) and sb.load_config(layout) == sb.load_config('/nonexistent')
    card = os.path.join(code, 'session-bar.py')
    line = settings()['statusLine']
    assert inst.is_ours(line, card) and 'env -i' in line['command'], line
    with open(launcher) as f:
        assert os.access(launcher, os.X_OK) and inst.MARKER in f.read()
    # the installed command draws the card, with no key in reach and every line the card's width
    run = subprocess.run(['sh', '-c', line['command']], input=json.dumps(FULL).encode(), capture_output=True,
                         env={**os.environ, 'HOME': t, 'CLAUDE_CONFIG_DIR': c, 'COLUMNS': '100', 'FAKE_SECRET': 'k'})
    assert run.returncode == 0 and {len(ANSI.sub('', l)) for l in run.stdout.decode().splitlines()} == {96}, run
    # a second install keeps an edited layout and backs the settings up
    with open(layout, 'w') as f:
        json.dump({'meter': 7}, f)
    assert installer('--yes').returncode == 0 and sb.load_config(layout)['meter'] == 7
    user_backups = os.path.join(c, 'session-bar', 'backups', 'user')  # not beside a symlink's target: a dotfiles repo
    assert os.path.isfile(os.path.join(user_backups, f'settings.json.bak-{today}-session-bar')), os.listdir(c)
    assert not [n for n in os.listdir(c) if '.bak-' in n], os.listdir(c)
    # uninstall: the status line, the code and the launcher go; the layout stays, named
    run = installer('--uninstall')
    assert run.returncode == 0 and 'statusLine' not in settings() and layout in run.stdout, run
    assert not any(os.path.exists(os.path.join(code, n)) for n in inst.CODE) and not os.path.exists(launcher)
    assert os.path.isfile(layout)
    # a status line the user changed is not theirs to remove
    installer('--yes')
    s = settings()
    s['statusLine']['command'] = 'echo mine'
    inst.write_settings(os.path.join(c, 'settings.json'), s, today)
    run = installer('--uninstall')
    assert run.returncode == 0 and settings()['statusLine']['command'] == 'echo mine' and 'left as it is' in run.stdout, run
    # a settings file it cannot read, or a status line of another tool, is not overwritten unasked
    with open(os.path.join(c, 'settings.json'), 'w') as f:
        f.write('{oops')
    run = installer('--yes')
    with open(os.path.join(c, 'settings.json')) as f:
        assert run.returncode == 1 and f.read() == '{oops', run
    inst.write_settings(os.path.join(c, 'settings.json'), {'statusLine': {'type': 'command', 'command': 'npx ccstatusline'}}, today)
    run = installer()
    assert run.returncode == 1 and settings()['statusLine']['command'] == 'npx ccstatusline', run
    assert installer('--yes').returncode == 0 and inst.is_ours(settings()['statusLine'], card)
    backups = sorted((n for n in os.listdir(user_backups) if n.startswith('settings.json.bak-')),
                     key=lambda n: int(n.rsplit('-', 1)[1]) if n.rsplit('-', 1)[1].isdigit() else 1)
    with open(os.path.join(user_backups, backups[-1])) as f:
        assert 'npx ccstatusline' in f.read(), backups
    # a project: its layout for the team to commit, the command in the local settings, the code from the user's folder
    fresh = os.path.join(t, 'c2')
    run = installer('--scope', 'project', '--project', proj, '--yes', cfg=fresh)
    assert run.returncode == 0, run
    assert sb.load_config(os.path.join(proj, '.claude', 'session-bar.json')) == sb.load_config('/nonexistent')
    local = settings(os.path.join(proj, '.claude', 'settings.local.json'))['statusLine']['command']
    assert 'SESSION_BAR_CONFIG="$CLAUDE_PROJECT_DIR/' in local and os.path.isfile(os.path.join(fresh, 'session-bar', 'session-bar.py'))
    assert not os.path.exists(os.path.join(fresh, 'settings.json'))
    # the user's uninstall would take the code a project's status line still runs: it says so and stops, unless --yes
    run = installer('--uninstall', cfg=fresh)
    assert run.returncode == 1 and proj in run.stdout and os.path.isfile(os.path.join(fresh, 'session-bar', 'session-bar.py')), run
    assert installer('--uninstall', '--scope', 'project', '--project', proj, cfg=fresh).returncode == 0
    run = installer('--uninstall', cfg=fresh)
    assert run.returncode == 0 and not os.path.exists(os.path.join(fresh, 'session-bar', 'session-bar.py')), run
    # a settings file not in Claude Code's own layout is rewritten whole, and the installer says so
    loose_cfg = os.path.join(t, 'c4')
    os.makedirs(loose_cfg)
    with open(os.path.join(loose_cfg, 'settings.json'), 'w') as f:
        f.write(json.dumps({'theme': 'dark'}, indent=4) + '\n')
    assert 'rewritten whole' in installer('--dry-run', cfg=loose_cfg).stdout
    inst.write_settings(os.path.join(loose_cfg, 'settings.json'), {'theme': 'dark'}, today)
    assert 'rewritten whole' not in installer('--dry-run', cfg=loose_cfg).stdout
    # a dry run shows the diff and writes nothing
    dry = os.path.join(t, 'c3')
    run = installer('--dry-run', cfg=dry)
    assert run.returncode == 0 and '"statusLine"' in run.stdout and not os.path.exists(dry), run
    # a symlink planted where the installer writes is never written through: the backup's name, a project's local
    # settings leading out of the project (a cloned repository controls its .claude folder), a project's layout
    s_path = os.path.join(c, 'settings.json')
    os.symlink(os.path.join(t, 'victim'), os.path.join(c, f'settings.json.bak-{today}-session-bar-9'))
    for n in range(2, 9):
        open(os.path.join(c, f'settings.json.bak-{today}-session-bar-{n}'), 'w').close()
    inst.write_settings(s_path, settings(), today)
    assert not os.path.exists(os.path.join(t, 'victim')) and os.path.isfile(os.path.join(c, f'settings.json.bak-{today}-session-bar-10'))
    evil = os.path.join(t, 'evil')
    os.makedirs(os.path.join(evil, '.claude'))
    with open(os.path.join(t, 'outside.json'), 'w') as f:
        f.write('{}')
    os.symlink(os.path.join(t, 'outside.json'), os.path.join(evil, '.claude', 'settings.local.json'))
    run = installer('--scope', 'project', '--project', evil, '--yes')
    with open(os.path.join(t, 'outside.json')) as f:
        assert run.returncode == 1 and f.read() == '{}' and 'outside' in run.stdout, run
    os.remove(os.path.join(evil, '.claude', 'settings.local.json'))
    os.symlink(os.path.join(t, 'victim2'), os.path.join(evil, '.claude', 'session-bar.json'))
    run = installer('--scope', 'project', '--project', evil, '--yes')
    assert run.returncode == 1 and not os.path.exists(os.path.join(t, 'victim2')), run
    # what the installer prints from a repository's files cannot drive the terminal, and a project's old settings
    # are backed up in the user's folder, never beside them, where git would see them
    hostile = os.path.join(t, 'hostile')
    os.makedirs(os.path.join(hostile, '.claude'))
    with open(os.path.join(hostile, '.claude', 'settings.local.json'), 'w', encoding='utf-8') as f:
        json.dump({'statusLine': {'type': 'command', 'command': 'x\x1b]0;pwned\x07\x9b31m'}, 'env': {'KEY': 'k'}}, f, ensure_ascii=False)
    for args in ((), ('--yes',)):
        run = installer('--scope', 'project', '--project', hostile, *args)
        assert not set(run.stdout) & {'\x1b', '\x07', '\x9b'}, repr(run.stdout)
    assert not [n for n in os.listdir(os.path.join(hostile, '.claude')) if '.bak-' in n], os.listdir(os.path.join(hostile, '.claude'))
    kept = [os.path.join(r, n) for r, _, ns in os.walk(os.path.join(c, 'session-bar', 'backups')) for n in ns
            if os.path.basename(r).startswith('hostile-')]
    assert len(kept) == 1 and kept[0] in run.stdout and 'pwned' in open(kept[0], encoding='utf-8').read(), (kept, run.stdout)
print('ok')
