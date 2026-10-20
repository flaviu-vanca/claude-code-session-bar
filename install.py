#!/usr/bin/env python3
"""Installs the Session Bar for the user (every project) or for one project, on Linux, macOS and Windows.

  python3 install.py [--scope user|project] [--project PATH] [--uninstall] [--dry-run] [--yes]

It copies the card's code into Claude Code's folder and writes one statusLine, whose command starts Python with an
empty environment and the few names the card reads, so no key Claude Code was started with reaches the card. A
settings file is written only when it can be read, after a backup, with the diff shown. Stdlib only, like the card.
"""
import difflib
import json
import os
import shutil
import stat
import tempfile

# what the card reads from its environment; anything else Claude Code holds, keys among it, stays out
CARD_ENV = ['HOME', 'USERPROFILE', 'SYSTEMROOT', 'COLUMNS', 'CLAUDE_CONFIG_DIR', 'XDG_DATA_HOME',
            'CLAUDE_CODE_SKIP_PROMPT_HISTORY', 'CLAUDE_CODE_IDLE_THRESHOLD_MINUTES', 'CLAUDE_CODE_IDLE_TOKEN_THRESHOLD']
# what the settings page needs on top: a browser to open, a folder for its temporary files
PAGE_ENV = CARD_ENV + ['PATH', 'DISPLAY', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS',
                       'BROWSER', 'TMPDIR', 'TEMP', 'TMP']
PROJECT_LAYOUT = '$CLAUDE_PROJECT_DIR/.claude/session-bar.json'


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


def write_settings(path, data, stamp):
    """Writes `data` whole to `path`, or to the file a symlink there points at: a backup of the old file first
    (<file>.bak-<stamp>-session-bar, then -2, -3 ...), then a temporary file renamed over it with the old mode.
    Returns the backup's path, or None for a new file."""
    real = os.path.realpath(path)
    backup, mode = None, 0o600  # a new settings file is private: its env block can hold keys
    if os.path.exists(real):
        mode = stat.S_IMODE(os.stat(real).st_mode)
        base = backup = f'{real}.bak-{stamp}-session-bar'
        n = 2
        while os.path.exists(backup):
            backup, n = f'{base}-{n}', n + 1
        shutil.copy2(real, backup)
    folder = os.path.dirname(real)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix='.session-bar-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(dump(data))
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
