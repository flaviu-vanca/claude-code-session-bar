#!/usr/bin/env python3
"""Installs the Session Bar for the user (every project) or for one project, on Linux, macOS and Windows.

  python3 install.py [--scope user|project] [--project PATH] [--uninstall] [--dry-run] [--yes]

It copies the card's code into Claude Code's folder and writes one statusLine, whose command starts Python with an
empty environment and the few names the card reads, so no key Claude Code was started with reaches the card. A
settings file is written only when it can be read, after a backup, with the diff shown. Stdlib only, like the card.
"""
import argparse
import difflib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = ['session-bar.py', 'configure.py', 'configure-web.html']
MARKER = 'session-bar launcher (claude-skin install.py)'  # uninstall removes only launchers that carry it

# what the card reads from its environment; anything else Claude Code holds, keys among it, stays out
CARD_ENV = ['HOME', 'USERPROFILE', 'SYSTEMROOT', 'COLUMNS', 'CLAUDE_CONFIG_DIR', 'XDG_DATA_HOME',
            'CLAUDE_CODE_SKIP_PROMPT_HISTORY', 'CLAUDE_CODE_IDLE_THRESHOLD_MINUTES', 'CLAUDE_CODE_IDLE_TOKEN_THRESHOLD']
# what the settings page needs on top: a browser to open, a folder for its temporary files
PAGE_ENV = CARD_ENV + ['PATH', 'DISPLAY', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS',
                       'BROWSER', 'TMPDIR', 'TEMP', 'TMP']
PROJECT_LAYOUT = '$CLAUDE_PROJECT_DIR/.claude/session-bar.json'
CONTROL = re.compile(r'[\x00-\x08\x0b-\x1f\x7f-\x9f]')  # C0 but tab and newline, and C1


def shown(text):
    """`text` from a file, fit to print: a repository's settings cannot drive the terminal."""
    return CONTROL.sub('', text)


class SettingsError(Exception):
    """A settings file that cannot be read, or holds something other than a JSON object."""


def sh_word(path):
    """`path` as one single-quoted sh word, with forward slashes (Git Bash drops unquoted backslashes)."""
    return "'" + path.replace('\\', '/').replace("'", "'\\''") + "'"


def ps_word(path):
    """`path` as one single-quoted PowerShell string, with forward slashes."""
    return "'" + path.replace('\\', '/').replace("'", "''") + "'"


def card_command(python, script, project=False, shell='sh'):
    """The statusLine command: `script` under `python`. In sh (Linux, macOS, Git Bash) it starts under env -i with
    CARD_ENV only; PowerShell has no env -i, so there the card gets Claude Code's whole environment."""
    if shell == 'powershell':
        layout = f'$env:SESSION_BAR_CONFIG = "{PROJECT_LAYOUT.replace("$", "$env:", 1)}"; ' if project else ''
        return f'{layout}& {ps_word(python)} -I -S {ps_word(script)}'
    names = ' '.join(f'{n}="${n}"' for n in CARD_ENV)
    layout = f' SESSION_BAR_CONFIG="{PROJECT_LAYOUT}"' if project else ''
    return f'env -i {names}{layout} {sh_word(python)} -I -S {sh_word(script)}'


def status_line(command):
    return {'type': 'command', 'command': command, 'padding': 0, 'refreshInterval': 1}


def read_settings(path):
    """A settings file as a dict; {} when it does not exist yet."""
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise SettingsError(f'{path} cannot be read ({e}); nothing was changed') from None
    if not isinstance(data, dict):
        raise SettingsError(f'{path} does not hold a JSON object; nothing was changed')
    return data


def dump(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + '\n'  # Claude Code's own layout, Ș kept as Ș


def write_settings(path, data, stamp, backup_dir=None):
    """Writes `data` whole to `path`, or to the file a symlink there points at: a backup of the old file first
    (<file>.bak-<stamp>-session-bar, then -2, -3 ...), then a temporary file renamed over it with the old mode.
    The backup goes into `backup_dir` when given, else beside the file. Returns its path, or None for a new file."""
    real = os.path.realpath(path)
    backup, mode = None, 0o600  # a new settings file is private: its env block can hold keys
    if os.path.exists(real):
        mode = stat.S_IMODE(os.stat(real).st_mode)
        if backup_dir:
            os.makedirs(backup_dir, exist_ok=True)
        base = os.path.join(backup_dir or os.path.dirname(real), f'{os.path.basename(real)}.bak-{stamp}-session-bar')
        n = 1
        while True:
            backup = base if n == 1 else f'{base}-{n}'
            try:  # O_EXCL: a name taken by anything, a planted symlink too, is skipped, never written through
                fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                break
            except FileExistsError:
                n += 1
        with os.fdopen(fd, 'wb') as out, open(real, 'rb') as src:
            shutil.copyfileobj(src, out)
        shutil.copystat(real, backup)
    folder = os.path.dirname(real)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix='.session-bar-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(dump(data))
            if hasattr(os, 'fchmod'):  # on the open file, not by name: no symlink can be slipped in between
                os.fchmod(f.fileno(), mode)
            else:
                os.chmod(tmp, mode)
        os.replace(tmp, real)
    except BaseException:
        os.unlink(tmp)
        raise
    return backup


def settings_diff(old, new, path):
    return ''.join(difflib.unified_diff(dump(old).splitlines(True), dump(new).splitlines(True), path, path))


def is_ours(line, script):
    """Whether a statusLine runs the installed card at `script`."""
    return isinstance(line, dict) and isinstance(line.get('command'), str) and script.replace('\\', '/') in line['command']


def git_bash(env=os.environ):
    """Git Bash as Claude Code finds it on Windows (mQ in 2.1.303), or None, when it falls back to PowerShell."""
    given = env.get('CLAUDE_CODE_GIT_BASH_PATH')
    if given and os.path.basename(given).lower() in ('bash.exe', 'sh.exe', 'bash', 'sh') and os.path.exists(given):
        return given
    for path in ('C:\\Program Files\\Git\\bin\\bash.exe', 'C:\\Program Files (x86)\\Git\\bin\\bash.exe'):
        if os.path.exists(path):
            return path
    git = shutil.which('git')
    path = git and os.path.join(git, '..', '..', 'bin', 'bash.exe')
    return path if path and os.path.exists(path) else None


def write_launcher(bin_dir, python, configure, windows):
    """`session-bar`, which opens the settings page detached: a sh script (Linux, macOS, Git Bash) under env -i with
    PAGE_ENV, and on Windows a .cmd for PowerShell too. Returns the paths written."""
    os.makedirs(bin_dir, exist_ok=True)
    names = ' '.join(f'{n}="${n}"' for n in PAGE_ENV)
    sh = os.path.join(bin_dir, 'session-bar')
    with open(sh, 'w', newline='\n') as f:
        f.write(f'#!/bin/sh\n# {MARKER}\nexec env -i {names} {sh_word(python)} -I -S {sh_word(configure)} --detach "$@"\n')
    os.chmod(sh, 0o755)
    paths = [sh]
    if windows:
        cmd = os.path.join(bin_dir, 'session-bar.cmd')
        with open(cmd, 'w', newline='\r\n') as f:
            f.write(f'@echo off\nrem {MARKER}\n"{python}" -I -S "{configure}" --detach %*\n')
        paths.append(cmd)
    return paths


def saved(backup):
    if backup:
        print(f'Backed up the old file to {backup}')


def load_card():
    spec = importlib.util.spec_from_file_location('session_bar', os.path.join(HERE, 'session-bar.py'))
    card = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(card)
    return card


def uninstall(args, old, path, code, script, bin_dir, layouts, backups):
    current = old.get('statusLine')
    if is_ours(current, script):
        new = {k: v for k, v in old.items() if k != 'statusLine'}
        print(shown(settings_diff(old, new, path)), end='')
        if not args.dry_run:
            saved(write_settings(path, new, time.strftime('%Y-%m-%d'), backups))
    elif current is not None:
        print(f'The statusLine in {path} does not run the installed card; left as it is.')
    if args.scope == 'user' and not args.dry_run:
        for name in CODE:
            if os.path.isfile(os.path.join(code, name)):
                os.remove(os.path.join(code, name))
        for name in ('session-bar', 'session-bar.cmd'):
            launcher = os.path.join(bin_dir, name)
            try:
                with open(launcher, encoding='utf-8', errors='replace') as f:
                    mine = MARKER in f.read(4096)
            except OSError:
                continue
            if mine:
                os.remove(launcher)
    for kept in dict.fromkeys(layouts):
        if os.path.isfile(kept):
            print(f'Kept the layout {kept}')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='Install the Session Bar for the user (every project) or for one project.')
    ap.add_argument('--scope', choices=('user', 'project'), default='user')
    ap.add_argument('--project', default=os.getcwd(), help='the project folder (default: this one)')
    ap.add_argument('--uninstall', action='store_true')
    ap.add_argument('--dry-run', action='store_true', help='show the change, write nothing')
    ap.add_argument('--yes', action='store_true', help='replace a status line that is not the Session Bar')
    args = ap.parse_args(argv)
    card = load_card()
    claude, windows = card.claude_dir(os.environ), os.name == 'nt'
    code = os.path.join(claude, 'session-bar')
    script, user_layout = os.path.join(code, 'session-bar.py'), os.path.join(code, 'session-bar.json')
    bin_dir = os.path.join(os.path.expanduser('~'), '.local', 'bin')  # Claude Code's own bin folder (H5 in 2.1.303)
    if args.scope == 'user':
        path, layout, backups = os.path.join(claude, 'settings.json'), user_layout, None
    else:
        project = os.path.abspath(args.project)
        path = os.path.join(project, '.claude', 'settings.local.json')
        layout = os.path.join(project, '.claude', 'session-bar.json')
        root = os.path.realpath(project)
        # a project's old settings can hold keys: backed up in the user's folder, out of the repository's sight
        key = hashlib.sha256(root.encode()).hexdigest()[:12]
        backups = os.path.join(code, 'backups', f'{os.path.basename(root)}-{key}')
        for p in (path, layout):  # a cloned repository controls its .claude folder: nothing it links to elsewhere
            real = os.path.realpath(p)
            if real != root and not real.startswith(root + os.sep):
                print(f'{p} leads outside {project}; nothing was changed.')
                return 1
    try:
        old = read_settings(path)
    except SettingsError as e:
        print(e)
        return 1
    if args.uninstall:
        return uninstall(args, old, path, code, script, bin_dir, [user_layout, layout], backups)

    current = old.get('statusLine')
    if current is not None and not is_ours(current, script) and not args.yes:
        print(shown(f'{path} already has a statusLine:\n  {current.get("command") if isinstance(current, dict) else current}'))
        answer = input('Replace it? [y/N] ') if sys.stdin.isatty() else ''
        if answer.strip().lower() != 'y':
            print('Nothing was changed (--yes replaces it).')
            return 1
    shell = 'sh'
    if windows and not git_bash():
        shell = 'powershell'
        print('Git Bash was not found, so Claude Code runs the status line through PowerShell, which has no env -i: '
              "the card receives Claude Code's whole environment, keys included.")
    new = {**old, 'statusLine': status_line(card_command(sys.executable, script, args.scope == 'project', shell))}
    print(shown(settings_diff(old, new, path)), end='')
    if args.dry_run:
        print('Dry run: nothing was written.')
        return 0
    if args.scope == 'user' or not os.path.isfile(script):
        os.makedirs(code, exist_ok=True)
        for name in CODE:
            shutil.copy2(os.path.join(HERE, name), os.path.join(code, name))
        for launcher in write_launcher(bin_dir, sys.executable, os.path.join(code, 'configure.py'), windows):
            print(f'Wrote {launcher}')
        if bin_dir not in os.environ.get('PATH', '').split(os.pathsep):
            print(f'{bin_dir} is not on PATH: add it to run session-bar by its name.')
    for target in dict.fromkeys([user_layout, layout]):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        try:  # O_EXCL: an existing layout is kept, a planted symlink is not written through
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            continue
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(dump(card.DEFAULT))
        print(f'Wrote the layout {target}')
    saved(write_settings(path, new, time.strftime('%Y-%m-%d'), backups))
    print(f'Wrote {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
