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
        'prompt_cache': {'warm': True, 'expires_at': NOW + 3000, 'hit_ratio': 0.92}}
RHOST = {**HOST, 'load': (1.2, 8), 'battery': (81, True)}
RS = {**ALL_S, 'mode': 'auto', 'drafts': 3}
for d in (RICH, {}):
    for w in range(30, 241):
        lines = [ANSI.sub('', sb.paint(line)) for line in sb.card(d, w, NOW, RHOST, 10, sb.chips(d, RS, NOW, sb.CHIPS), ALL_CFG)]
        assert [len(line) for line in lines] == [w] * len(lines), (w, lines)
        assert lines[0][0] == '╭' and lines[0][-1] == '╮' and lines[-1][0] == '╰' and lines[-1][-1] == '╯', lines
        assert all(line[0] == '│' and line[-1] == '│' for line in lines[1:-1]), lines
rich = [ANSI.sub('', sb.paint(line)) for line in sb.card(RICH, 240, NOW, RHOST, 10, sb.chips(RICH, RS, NOW, sb.CHIPS), ALL_CFG)]
clock = time.strftime('%H:%M', time.localtime(NOW))
assert '╭─ ✻ Opus 5.5 · max · thinking · style Explanatory · @reviewer · skin work · v2.1.302 ─' in rich[0], rich[0]
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

# the script reads its settings
with tempfile.TemporaryDirectory() as t:
    with open(os.path.join(t, 'c.json'), 'w') as f:
        json.dump({'rows': [['mem']]}, f)
    run = subprocess.run([sys.executable, '-I', '-S', spec.origin], input=json.dumps(FULL).encode(), capture_output=True,
                         env={**env, 'SESSION_BAR_CONFIG': os.path.join(t, 'c.json')})
    assert run.returncode == 0 and run.stdout.decode().count('\n') == 3 and not run.stderr, run

# while Remote Control is on (bridgeSessionId in this session's process file), the script's card is 4 columns
# narrower, from 60 columns up, whatever the terminal's width
with tempfile.TemporaryDirectory() as t:
    os.makedirs(os.path.join(t, '.claude', 'sessions'))

    def first_line_width(rec):
        with open(os.path.join(t, '.claude', 'sessions', f'{os.getpid()}.json'), 'w') as f:
            json.dump({'sessionId': FULL['session_id'], 'pid': os.getpid(), **rec}, f)
        run = subprocess.run([sys.executable, '-I', '-S', spec.origin], input=json.dumps(FULL).encode(),
                             capture_output=True, env={**env, 'HOME': t})
        assert run.returncode == 0 and not run.stderr, run
        return len(ANSI.sub('', run.stdout.decode().split('\n')[0]))

    off, on = first_line_width({}), first_line_width({'bridgeSessionId': 'session_01X'})
    assert off - on == (4 if off >= 56 else 0), (off, on)

F = 'CLAUDE_CODE_SKIP_PROMPT_HISTORY'
assert sb.env_flag(b'A=1\0' + F.encode() + b'=1\0', F) is True and sb.env_flag(F.encode() + b'=true\0', F) is True
assert sb.env_flag(F.encode() + b'=0\0', F) is False and sb.env_flag(b'', F) is False
assert sb.env_flag(b'X_' + F.encode() + b'=1\0', F) is False

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
c = web.clean({'rows': [['ctx', 'bogus', 'rc'], ['repo']], 'edge': ['rc', 'ctx'], 'palette': 'nord', 'meter': 99})
assert c['rows'] == [['ctx'], ['repo']] and c['edge'] == ['rc'] and c['palette'] == 'nord' and c['meter'] == 30, c
d = web.sample({'ctx': 150, '5h': 42.5, 'week': 'x'})
assert d['context_window']['used_percentage'] == 100 and d['rate_limits']['five_hour']['used_percentage'] == 42.5, d
assert d['rate_limits']['seven_day']['used_percentage'] == web.SAMPLE['rate_limits']['seven_day']['used_percentage']
assert web.SAMPLE['context_window']['used_percentage'] != 100  # the sample itself is left as it was
for cols, rc in ((188, True), (188, False), (59, True), (40, False)):
    r = web.render(c, cols, rc, d)
    assert r['width'] == sb.card_width(cols, rc) and all(sum(len(p[0]) for p in l) == r['width'] for l in r['lines']), (cols, rc)
pv = web.previews(c, d)
flat = lambda pieces: ''.join(p[0] for p in pieces)
assert set(pv) == set(sb.TEXT + sb.METERS + sb.CHIPS), set(pv) ^ set(sb.TEXT + sb.METERS + sb.CHIPS)
assert flat(pv['ctx']).startswith('ctx ▰') and flat(pv['repo']).startswith('⎇ ') and flat(pv['rc']).endswith('rc'), pv['rc']
pal = web.palette_rows(c, d)
assert set(pal) == set(sb.PALETTES) and pal['nord'] != pal['dracula'] and flat(pal['nord']).startswith('ctx ▰'), pal['nord']
H = {'127.0.0.1:8790'}
assert web.trusted('127.0.0.1:8790', None, 'GET', H) and web.trusted('127.0.0.1:8790', 'http://127.0.0.1:8790', 'POST', H)
assert not web.trusted('evil.example:8790', None, 'GET', H) and not web.trusted('127.0.0.1:8790', 'http://evil.example', 'POST', H)
life = web.Life(1000)
assert not life.over(1299) and life.over(1301)  # no page yet: five minutes, to open the address by hand
life.ping(1400)
assert not life.over(1549) and life.over(1551)  # silence: 2.5 minutes, past a background tab's once-a-minute timers
life.bye(1560)
assert not life.over(1563) and life.over(1565)  # the page said goodbye: a few seconds, in case it was a reload

import threading
import urllib.error
import urllib.request

with tempfile.TemporaryDirectory() as t:
    web.SAVE = os.path.join(t, 'session-bar.json')
    srv = web.make_server(0, web.Life(time.time()))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{srv.server_address[1]}'
    post = lambda path, body, **h: urllib.request.urlopen(urllib.request.Request(
        base + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', **h}), timeout=5)
    st = json.load(urllib.request.urlopen(base + '/api/state', timeout=5))
    assert st['cfg'] == sb.load_config(web.SAVE) and set(st['palettes']) == set(sb.PALETTES), st['cfg']
    got = json.load(post('/api/render', {'cfg': {'rows': [['week']]}, 'columns': 120, 'rc': True, 'sample': {'week': 91}}))
    assert got['width'] == 112 and flat(got['lines'][1]).startswith('│ week ▰▰▰▰▰▰▰▰▰▱ 92%') and set(got['previews']) == set(pv), got['lines'][1]
    try:
        post('/api/save', {'cfg': c}, Origin='http://evil.example')
        raise AssertionError('a foreign page saved the settings')
    except urllib.error.HTTPError as e:
        assert e.code == 403 and not os.path.exists(web.SAVE), e.code
    json.load(post('/api/save', {'cfg': c}))
    assert sb.load_config(web.SAVE) == c
    srv.shutdown()
    srv.server_close()
print('ok')
