#!/usr/bin/env python3
"""Throwaway preview of the V1 draft: the footer's states on the bottom edge, with icons; sandbox only when on;
meters 10, 12 and 15 cells. Draws the real card from ../session-bar.py with sample states.

Run: python3 -I <this file>
"""
import importlib.util
import os
import re
import time

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('sb', os.path.join(HERE, '..', 'session-bar.py'))
sb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sb)
P, dim = sb.P, (lambda t: sb.P(t, dim=True))

NOW = time.time()
D = {'session_id': '4222eae8-6194', 'model': {'id': 'claude-opus-5-5'}, 'effort': {'level': 'max'},
     'workspace': {'current_dir': os.path.expanduser('~/codewiki')}, 'cost': {'total_cost_usd': 12.34, 'total_duration_ms': 5_400_000},
     'context_window': {'total_input_tokens': 182_000, 'context_window_size': 1_000_000, 'used_percentage': 18.2},
     'rate_limits': {'five_hour': {'used_percentage': 64, 'resets_at': NOW + 7200}, 'seven_day': {'used_percentage': 31, 'resets_at': NOW + 400_000}}}
HOST = {'mem': (4.1, 7.5), 'disks': [('/tmp', 9), ('~/.cache', 58)]}
PURPLE, TEAL, ORANGE, YELLOW, RED = (175, 135, 255), (72, 150, 140), (255, 120, 20), (0xE3, 0xB3, 0x41), (0xF8, 0x51, 0x49)

# Claude Code's own footer states, each with its icon, in the order they are kept on a narrow card
CHIP = {
    'rc': [P('⇄ rc', sb.GREEN, bold=True)],
    'auto': [P('⏵⏵ auto', PURPLE)],
    'accept': [P('⏵⏵ accept edits', PURPLE)],
    'plan': [P('⏸ plan', TEAL)],
    'bypass': [P('⏵⏵ bypass', RED, bold=True)],
    'sandbox': [P('⧈ sandbox', sb.GREEN)],
    'working': [P('● ', YELLOW), dim('working')],
    'pr': [P('PR #12 ', sb.GREEN), P('✓', sb.GREEN, bold=True)],
    'pr-changes': [P('PR #12 ', RED), P('±', RED, bold=True)],
    'fast': [P('↯ fast', ORANGE)],
    'vim': [dim('-- INSERT --')],
    # events: each shows only while it is true, coloured by how much it asks of you
    'cloud': [P('◎ cloud', (71, 130, 200))],
    'update': [P('↑ 2.1.303', YELLOW, bold=True), dim(' restart')],
    'compact20': [P('◔ compact in 18%', YELLOW)],
    'compact9': [P('◔ compact in 9%', ORANGE, bold=True)],
    'compact3': [P('◔ compact in 3%', RED, bold=True)],
    'cache-soon': [P('◷ cache 1m', ORANGE)],
    'cache-cold': [P('◷ cache cold', YELLOW)],
    'debug': [P('debug', YELLOW)],
    'no-transcript': [P('⚠ no transcript', RED, bold=True)],
}
SCENES = [
    ('nothing on (sandbox off: gone from the second row too)', []),
    ('/rc on, auto mode, working', ['rc', 'auto', 'working']),
    ('everything at once', ['rc', 'auto', 'sandbox', 'working', 'pr', 'fast', 'vim']),
    ('plan mode, sandbox on, PR with changes asked', ['plan', 'sandbox', 'pr-changes']),
    ('bypass permissions', ['bypass']),
    ('event: a newer Claude Code is downloaded, restart to use it', ['rc', 'auto', 'update']),
    ('event: auto-compact getting close, three levels', ['rc', 'auto', 'compact20']),
    ('', ['rc', 'auto', 'compact9']),
    ('', ['rc', 'auto', 'working', 'compact3']),
    ('event: prompt cache about to expire, then gone cold', ['rc', 'auto', 'cache-soon']),
    ('', ['rc', 'auto', 'cache-cold']),
    ('event: attached to a cloud session', ['cloud', 'auto']),
    ('event: started with --debug, transcript saving off', ['rc', 'auto', 'debug', 'no-transcript']),
    ('everything at once: events right after the mode, so a narrow card keeps them', ['rc', 'auto', 'compact9', 'update', 'cache-cold', 'sandbox', 'working', 'pr', 'fast', 'vim']),
]


def show(title, width, meter, names):
    if title:
        print(f'\x1b[2m  {title}\x1b[0m')
    for line in sb.card(D, width, NOW, HOST, meter, [CHIP[n] for n in names]):
        print('  ' + sb.paint(line))


cols = sb.terminal_columns()
wide = min(110, cols - 4)
for width in sorted({wide, 72}, reverse=True):
    print(f'\n\x1b[1mV1 · the states on the bottom edge\x1b[0m  \x1b[2m(card width {width}, meters 10)\x1b[0m')
    for scene, names in SCENES:
        show(scene, width, 10, names)
for width in sorted({wide, 72}, reverse=True):
    print(f'\n\x1b[1mMeter length\x1b[0m  \x1b[2m(card width {width}; a meter shrinks on its own when the row does not fit)\x1b[0m')
    for meter in (10, 12, 15):
        show(f'meters {meter}', width, meter, ['rc', 'auto', 'working'])
print()

# self-check: every line is the card's width at every width, meter length and scene
ansi = re.compile(r'\x1b\[[\d;]*m')
for w in range(30, 200):
    for meter in (10, 12, 15):
        for _, names in SCENES:
            got = [len(ansi.sub('', sb.paint(line))) for line in sb.card(D, w, NOW, HOST, meter, [CHIP[n] for n in names])]
            assert got == [w] * len(got), (w, meter, names, got)
