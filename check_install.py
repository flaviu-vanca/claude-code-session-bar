#!/usr/bin/env python3
"""End-to-end check of the Session Bar on this machine, used the way Claude Code uses it; nothing of yours is touched.

  python3 check_install.py

In a temporary home (its name has a space and an Ș, as a real user folder can): install.py for the user; the status
line command it wrote, run through the shell Claude Code runs it in here (sh; on Windows Git Bash, and PowerShell
too, the way Claude Code calls it); a key planted in the environment that must not reach the card; the settings page
opened through the session-bar launcher and asked for its state; then the uninstall. CI runs it on Linux, macOS and
Windows (.github/workflows/ci.yml).
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ANSI = re.compile(r'\x1b\[[\d;]*m|\x1b\]8;;[^\x1b]*\x1b\\')
WINDOWS = os.name == 'nt'
WIDTH = 100  # COLUMNS; the card is 4 narrower: Claude Code's padding


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), os.path.join(HERE, name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inst = load('install')


def check(ok, what, detail=''):
    if not ok:
        print(f'FAIL {what}\n{detail}', flush=True)
        sys.exit(1)
    print(f'ok   {what}', flush=True)


def shells():
    """(name, argv for a command string, the command's form), as Claude Code would run a status line here."""
    if not WINDOWS:
        return [('sh', lambda cmd: ['/bin/sh', '-c', cmd], 'sh')]
    found = []
    bash = inst.git_bash()
    if bash:  # Claude Code hands the command to Git Bash with -c
        found.append(('Git Bash', lambda cmd: [bash, '-c', cmd], 'sh'))
    ps = shutil.which('pwsh') or shutil.which('powershell')
    if ps:  # C8() and XHn() in 2.1.303
        found.append(('PowerShell', lambda cmd: [ps, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                                 '-Command', cmd], 'powershell'))
    return found


def run(argv, env, data=None, cwd=None):
    return subprocess.run(argv, input=data, capture_output=True, env=env, cwd=cwd, timeout=120,
                          stdin=None if data is not None else subprocess.DEVNULL)


def text(raw):
    return raw.decode('utf-8', 'replace')


def api(root, path, session=None, body=None):
    headers = {'X-Session': session} if session else {}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(root + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def main():
    print(f'Python {sys.version.split()[0]} on {sys.platform}')
    with tempfile.TemporaryDirectory() as t:
        home = os.path.join(t, 'home Ș')
        os.makedirs(home)
        claude = os.path.join(home, '.claude')
        env = {k: v for k, v in os.environ.items() if k not in ('XDG_DATA_HOME', 'SESSION_BAR_CONFIG', 'BROWSER')}
        env.update(HOME=home, USERPROFILE=home, CLAUDE_CONFIG_DIR=claude, PYTHONIOENCODING='utf-8')

        r = run([sys.executable, '-I', os.path.join(HERE, 'install.py'), '--yes'], env)
        check(r.returncode == 0, 'install.py for the user', text(r.stdout) + text(r.stderr))
        with open(os.path.join(claude, 'settings.json'), encoding='utf-8') as f:
            command = json.load(f)['statusLine']['command']
        card = os.path.join(claude, 'session-bar', 'session-bar.py')
        check(os.path.isfile(card) and inst.is_ours({'command': command}, card), 'the statusLine runs the installed card')

        now = int(time.time())
        payload = json.dumps({
            'session_id': 'check', 'model': {'id': 'claude-opus-5-5', 'display_name': 'Opus 5.5'},
            'workspace': {'current_dir': home, 'project_dir': home}, 'version': '2.1.303',
            'cost': {'total_cost_usd': 1.25, 'total_duration_ms': 3_600_000},
            'context_window': {'used_percentage': 40, 'total_input_tokens': 80_000, 'context_window_size': 200_000},
            'rate_limits': {'five_hour': {'used_percentage': 20, 'resets_at': now + 3600},
                            'seven_day': {'used_percentage': 50, 'resets_at': now + 86_400}},
        }).encode()
        stub = os.path.join(t, 'stub.py')
        with open(stub, 'w', encoding='utf-8') as f:
            f.write('import json, os, sys; json.dump(sorted(os.environ), sys.stdout)')
        planted = {**env, 'COLUMNS': str(WIDTH), 'FAKE_SECRET': 'planted', 'ANTHROPIC_API_KEY': 'planted'}
        checked = shells()
        check(bool(checked), 'a shell Claude Code would use is here')
        for name, argv, form in checked:
            cmd = command if form == 'sh' else inst.card_command(sys.executable, card, shell='powershell')
            r = run(argv(cmd), planted, payload)
            lines = [ANSI.sub('', line) for line in text(r.stdout).splitlines()]
            check(r.returncode == 0 and len(lines) >= 3 and {len(line) for line in lines} == {WIDTH - 4},
                  f'{name}: the card draws, every row {WIDTH - 4} cells wide',
                  f'exit {r.returncode}\n' + '\n'.join(f'{len(l):3} {l}' for l in lines) + '\n' + text(r.stderr))
            r = run(argv(inst.card_command(sys.executable, stub, shell=form)), planted)
            seen = json.loads(text(r.stdout) or '[]')
            if form == 'sh':
                check(r.returncode == 0 and 'FAKE_SECRET' not in seen and 'ANTHROPIC_API_KEY' not in seen,
                      f'{name}: no key reaches the card (env -i)', f'{seen}\n{text(r.stderr)}')
            else:
                print(f'note {name}: no env -i there, the card {"gets" if "FAKE_SECRET" in seen else "does not get"} '
                      'the keys (README: Keys)')

        bindir = os.path.join(home, '.local', 'bin')
        url_file = os.path.join(t, 'opened.txt')
        if WINDOWS:  # %* keeps the address whole: cmd splits %1 at '='
            browser = os.path.join(t, 'browser.cmd')
            with open(browser, 'w', newline='\r\n') as f:
                f.write(f'@echo off\necho %*> "{url_file}"\n')
            launchers = [('session-bar.cmd', ['cmd', '/c', os.path.join(bindir, 'session-bar.cmd')])]
            bash = inst.git_bash()
            if bash:
                launchers.append(('session-bar in Git Bash', [bash, os.path.join(bindir, 'session-bar')]))
        else:
            browser = os.path.join(t, 'browser.sh')
            with open(browser, 'w') as f:
                f.write(f'#!/bin/sh\nprintf "%s" "$1" > "{url_file}"\n')
            os.chmod(browser, 0o755)
            launchers = [('session-bar', [os.path.join(bindir, 'session-bar')])]
        for name, argv in launchers:
            if os.path.exists(url_file):
                os.remove(url_file)
            r = run(argv, {**env, 'BROWSER': browser, 'FAKE_SECRET': 'planted'}, cwd=home)
            for _ in range(100):
                if os.path.exists(url_file) and os.path.getsize(url_file):
                    break
                time.sleep(0.1)
            check(r.returncode == 0 and os.path.exists(url_file), f'{name}: the settings page opens',
                  text(r.stdout) + text(r.stderr))
            with open(url_file, encoding='utf-8', errors='replace') as f:
                url = f.read().strip()
            check('/#t=' in url, f'{name}: its address carries the one-time token in the fragment', url)
            root, token = url.split('/#t=')
            session = api(root, '/api/open', body={'t': token})['session']
            state = api(root, '/api/state', session)
            layout = os.path.join(claude, 'session-bar', 'session-bar.json')
            check(state['scope'] == 'user' and os.path.realpath(state['file']) == os.path.realpath(layout),
                  f'{name}: the page edits the user layout', json.dumps({k: state[k] for k in ('scope', 'file')}))
            api(root, '/api/bye', session, body={})

        r = run([sys.executable, '-I', os.path.join(HERE, 'install.py'), '--uninstall'], env)
        with open(os.path.join(claude, 'settings.json'), encoding='utf-8') as f:
            left = json.load(f)
        check(r.returncode == 0 and 'statusLine' not in left and not os.path.exists(card)
              and os.path.isfile(os.path.join(claude, 'session-bar', 'session-bar.json')),
              'uninstall: the status line and the code go, the layout stays', text(r.stdout) + text(r.stderr))
    print('all checks passed')


if __name__ == '__main__':
    main()
