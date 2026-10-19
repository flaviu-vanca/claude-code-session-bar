#!/usr/bin/env python3
"""Session Bar settings: pick what each place of the card shows and in what order, and watch the card change.

Run it in a terminal of its own (not through `!`, which is not interactive):
  python3 ~/claude-skin/configure.py
Keys: left and right pick a place (the top edge's two sides, each row, the bottom edge), up and down an element
(or h j k l); space turns it on or off; [ and ] move it up or down its place; a adds a row, x deletes the row
under the cursor; + and - set the meters' length in bars; p cycles the colour palettes; s saves to
session-bar.json, which the card reads on its next run; q or esc quits. Stdlib only, like the card. Nothing here
reaches the model.
"""
import importlib.util
import json
import os
import shutil
import sys
import termios
import time
import tty

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('sb', os.path.join(HERE, 'session-bar.py'))
sb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sb)
P = sb.P
dim = lambda t: P(t, dim=True)

TITLES = {'top_left': 'Top edge, left', 'top_right': 'Top edge, right', 'edge': 'Bottom edge'}
WHAT = {
    'model': "the model's name", 'effort': 'the effort level', 'thinking': '"thinking" while extended thinking is on',
    'style': 'the output style, when it is not the default', 'agent': 'the agent the session runs as (--agent)',
    'name': 'the session name set with /rename', 'version': "Claude Code's version", 'cost': "the session's cost",
    'time': "the session's wall time", 'api': 'the time spent waiting on the API', 'lines': 'lines added and removed',
    'clock': 'the time of day', 'repo': 'the repository and branch', 'cwd': 'the current folder',
    'session': 'the session id', 'worktree': 'the worktree the session runs in', 'dirs': 'folders added with /add-dir',
    'mem': 'memory in use', 'disks': 'how full /tmp and ~/.cache are', 'load': 'the 1-minute load, coloured by CPU count',
    'battery': 'the battery charge, + while charging',
    'ctx': 'the context used, of the window', '5h': 'the 5-hour limit and when it resets',
    'week': 'the weekly limit and when it resets', 'spend': 'the spend limit (on a gateway only)',
    'hits': 'the prompt cache hit ratio: green is good',
    'cloud': 'this CLI drives a cloud or remote session', 'rc': 'Remote Control is on, as a link',
    'mode': 'the permission mode (Claude Code shows it under the card too)',
    'no_transcript': 'started with transcript saving off', 'update': 'a newer Claude Code is downloaded: restart',
    'cache': 'the prompt cache is about to expire, or is cold', 'big': 'the context is past 200k tokens',
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
          'prompt_cache': {'warm': True, 'expires_at': NOW + 75, 'hit_ratio': 0.92},
          'pr': {'number': 12, 'url': 'https://github.com/o/r/pull/12', 'review_state': 'approved'}}
STATES = {'rc': 'session_01X', 'busy': True, 'newest': '2.1.303', 'no_transcript': True, 'sandbox': True,
          'mode': 'auto', 'drafts': 3}
KEYS = {b'\x1b[A': 'up', b'\x1b[B': 'down', b'\x1b[C': 'right', b'\x1b[D': 'left',
        b'k': 'up', b'j': 'down', b'h': 'left', b'l': 'right'}


class State:
    """The settings being edited, the cursor (a place, and a row in its list), and whether they are saved."""

    def __init__(self, cfg, place=0, row=0, saved=False):
        self.cfg = {k: [list(r) for r in v] if k == 'rows' else list(v) if isinstance(v, list) else v
                    for k, v in cfg.items()}
        self.place, self.row, self.saved = place, row, saved


def places(cfg):
    """The places in the order the cursor walks them: (key, row index or None)."""
    return [('top_left', None), ('top_right', None)] + [('rows', i) for i in range(len(cfg['rows']))] + [('edge', None)]


def chosen(cfg, place):
    key, i = place
    return cfg['rows'][i] if key == 'rows' else cfg[key]


def items(cfg, place):
    """A place's list: the elements on, in the card's order, then the others, in the registry's order."""
    on = chosen(cfg, place)
    return [(n, True) for n in on] + [(n, False) for n in sb.PLACES[place[0]] if n not in on]


def step(st, key):
    """The state after one key; the state handed in is left as it was."""
    st = State(st.cfg, st.place, st.row, st.saved)
    place = places(st.cfg)[st.place]
    rows = items(st.cfg, place)
    name, on = rows[st.row]
    if key in ('up', 'down'):
        st.row = max(0, min(len(rows) - 1, st.row + (1 if key == 'down' else -1)))
    elif key in ('left', 'right'):
        st.place = max(0, min(len(places(st.cfg)) - 1, st.place + (1 if key == 'right' else -1)))
        st.row = min(st.row, len(items(st.cfg, places(st.cfg)[st.place])) - 1)
        return st
    elif key == ' ':
        chosen(st.cfg, place).remove(name) if on else chosen(st.cfg, place).append(name)
    elif key in ('[', ']') and on:
        lst = chosen(st.cfg, place)
        i = lst.index(name)
        j = i + (1 if key == ']' else -1)
        if not 0 <= j < len(lst):
            return st
        lst[i], lst[j] = lst[j], lst[i]
        st.row = j
    elif key == 'a':
        st.cfg['rows'].append([])
        st.place, st.row = 1 + len(st.cfg['rows']), 0
    elif key == 'x' and place[0] == 'rows':
        del st.cfg['rows'][place[1]]
        st.place, st.row = st.place - 1, 0
    elif key == 'p':
        names = list(sb.PALETTES)
        st.cfg['palette'] = names[(names.index(st.cfg['palette']) + 1) % len(names)]
    elif key in ('+', '-'):
        st.cfg['meter'] = max(3, min(30, st.cfg['meter'] + (1 if key == '+' else -1)))
    else:
        return st
    st.saved = False
    return st


def render(st, w, h, now, host):
    """The screen for a terminal `w` columns by `h` rows: the places on the left, the chosen place's elements on
    the right, the element under the cursor explained, the keys, and the card drawn live from the settings."""
    sb.use_palette(st.cfg['palette'])
    preview = sb.card(SAMPLE, max(30, w - 2), now, host, st.cfg['meter'],
                      sb.chips(SAMPLE, STATES, now, st.cfg['edge']), st.cfg)
    title = [P('Session Bar · settings', sb.ACCENT, bold=True), dim(f'  {sb.CONFIG}'),
             P('  saved' if st.saved else '', sb.GREEN)]
    out = [sb.paint(sb.clip(title, w)), '']
    ps = places(st.cfg)
    left_w = min(22, w // 3)
    lefts = []
    for k, (key, i) in enumerate(ps):
        here = k == st.place
        label = f'Row {i + 1}' if key == 'rows' else TITLES[key]
        lefts.append([P('❯ ' if here else '  ', sb.ACCENT), P(label, sb.ACCENT if here else None, bold=here),
                      dim(f' {len(chosen(st.cfg, (key, i)))}')])
    rows = items(st.cfg, ps[st.place])
    room = max(5, h - len(preview) - 8)  # the list scrolls with the cursor
    first = max(0, st.row - room + 1)
    rights = []
    for r in range(first, min(len(rows), first + room)):
        name, on = rows[r]
        here = r == st.row
        rights.append([P('❯ ' if here else '  ', sb.ACCENT), P('[x] ' if on else '[ ] ', sb.GREEN if on else None, dim=not on),
                       P(name, sb.ACCENT if here else None, dim=not on and not here)])
    for r in range(max(len(lefts), len(rights))):
        left = sb.clip(lefts[r] if r < len(lefts) else [], left_w - 1)
        out.append(sb.paint(left + [P(' ' * (left_w - sb.cells(left)))] + sb.clip(rights[r] if r < len(rights) else [], w - left_w)))
    name = rows[st.row][0]
    out.append(sb.paint(sb.clip([dim('bars '), P(f"◀ {st.cfg['meter']} ▶", sb.ACCENT), dim('   palette '),
                                 P(st.cfg['palette'], sb.ACCENT), dim(f'   {name}: {WHAT[name]}')], w)))
    out.append(sb.paint(sb.clip([dim('arrows move · space on/off · [ ] reorder · a add row · x delete row · '
                                     '+ - bars · p palette · s save · q quit')], w)))
    out.append('')
    out += [' ' + sb.paint(line) for line in preview]
    return out


def save(cfg, path):
    """Writes the settings whole: a temporary file renamed over the old, so the card never reads half of one."""
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump({k: cfg[k] for k in sb.DEFAULT}, f, indent=2)
        f.write('\n')
    os.replace(tmp, path)


def main():
    st = State(sb.load_config(sb.CONFIG))
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        sys.stdout.write('\x1b[?1049h\x1b[?25l')  # the alternate screen, no cursor
        while True:
            w, h = shutil.get_terminal_size()
            screen = render(st, w, h, time.time(), sb.host(HERE))
            sys.stdout.write('\x1b[H\x1b[2J' + '\n'.join(screen))
            sys.stdout.flush()
            raw = os.read(fd, 16)
            key = KEYS.get(raw, raw.decode(errors='ignore'))
            if key in ('q', '\x1b'):
                break
            if key == 's':
                save(st.cfg, sb.CONFIG)
                st.saved = True
            else:
                st = step(st, key)
    finally:
        sys.stdout.write('\x1b[?25h\x1b[?1049l')
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


if __name__ == '__main__':
    main()
