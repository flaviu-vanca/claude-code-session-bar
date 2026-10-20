# Session Bar: install anywhere, keep keys out — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Session Bar card runs on Linux, macOS and Windows, installs for the user or for one project through
`install.py`, opens its settings page with a `session-bar` command, and never holds a key from the environment.

**Architecture:** `session-bar.py` stays one stdlib script; its Linux-only reads become portable or fall away
quietly. A new `install.py` copies the code into Claude Code's folder and writes one `statusLine` whose command starts
Python under `env -i` with a short allowlist. `configure.py` learns which layout applies in the current folder and
can start its server detached, which the `session-bar` launcher uses.

**Tech Stack:** Python 3.8+ standard library only; POSIX `sh` and Git Bash; PowerShell as Windows' fallback.

**Spec:** `docs/superpowers/specs/2026-10-19-session-bar-install-design.md`

## Global Constraints

- Python 3.8+, standard library only. The card runs as `python3 -I -S`.
- `session-bar.py`: no subprocess, no network, only small reads; a run stays near today's ~20 ms, far under 300 ms.
- Tests go in `test_session_bar.py` (a flat script of `assert`s); `python3 -I test_session_bar.py` prints `ok`.
- Every test is written and seen failing before its code; each new piece of code gets one mutation the tests catch.
- Every row of the card is exactly the card's width at every width from 30 to 240.
- Every glyph is one cell wide; no emoji.
- Nothing reads another process's environment, and nothing reads, keeps, prints or sends a credential.
- An environment variable set to the empty string counts as unset.
- Code, comments, docs and commit messages in English; commits end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Facts about Claude Code come from its binary (`~/.local/share/claude/versions/2.1.303`); anything unread is marked
  as a hypothesis.
- Before `~/.claude/settings.json` on this machine changes: a copy `settings.json.bak-<date>-<reason>`, then a diff.

## Facts read for this plan (2.1.303)

- Settings layer from low to high: user, project, local, flag, policy (`gn()`, `Ps`). A `statusLine` in
  `.claude/settings.local.json` therefore wins over the user's.
- `versions` is `(XDG_DATA_HOME or ~/.local/share)/claude/versions` on every system (`dje`, `Fin`).
- Claude Code's folder is `CLAUDE_CONFIG_DIR` or `~/.claude`; `sessions` sits inside it (`Xte`).
- `~/.local/bin` is Claude Code's own bin folder on every system (`H5`).
- `!` (bash mode) runs through the Bash tool, or the PowerShell tool, with `dangerouslyDisableSandbox: true`, so a
  server can start from it. Its output enters the conversation as `<bash-stdout>`, and Claude answers after it unless
  `respondToBashCommands` is `false` (default `true`).

## Review Focus

- **A path with spaces or a quote** (`C:/Users/Ana Maria/…`, `/Users/o'neil/…`) in the command or the launcher: it
  must still run. Test in Task 5.
- **A settings file with non-ASCII text, in Claude Code's own formatting**: after an install only `statusLine`
  changes, and `Ș` stays `Ș`, not `\u0218`. Test in Task 5.
- **`COLUMNS` missing, empty or not a number**: the card draws at 120, never fails. Test in Task 1.
- **No browser can open** (SSH, a bare server): `session-bar` still prints the address and exits 0. Test in Task 7.
- **A folder outside any project, or a layout file above the home folder**: the launcher opens the user's layout and
  never climbs past home. Test in Task 7.

---

### Task 0: Branch and the finished changes

**Files:** none new; commits `session-bar.py`, `test_session_bar.py`, `NOTES.md` and the spec as they stand.

- [ ] **Step 1:** `git switch -c session-bar-install`
- [ ] **Step 2:** `python3 -I test_session_bar.py` → `ok`
- [ ] **Step 3:** Commit the `hits` comment, the environment change and the spec:

```bash
git add session-bar.py test_session_bar.py NOTES.md docs/superpowers/specs/2026-10-19-session-bar-install-design.md
git commit -m "Session Bar: read only named variables from the card's own environment

- launch_env and env_value are gone: the card no longer reads Claude Code's
  /proc/<pid>/environ, which held every key it was started with.
- hits: hit_ratio is cache read / all input tokens, 0..1 (read in 2.1.303).
- The design for installing on Linux, macOS and Windows.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 1: The width from `COLUMNS`

**Files:**
- Modify: `session-bar.py` (imports at the top, `terminal_columns` at line ~224, `main`)
- Modify: `configure.py:189`
- Test: `test_session_bar.py`, beside the `card_width` asserts (line ~53)

**Interfaces:**
- Produces: `columns(env) -> int`, used by `main`. `terminal_columns()` is deleted.

- [ ] **Step 1: Write the failing test**

```python
# the card takes the terminal's width from COLUMNS, which Claude Code sets at every run; 120 without a usable one
assert sb.columns({'COLUMNS': '100'}) == 100 and sb.columns({}) == 120
assert sb.columns({'COLUMNS': ''}) == 120 and sb.columns({'COLUMNS': 'x'}) == 120 and sb.columns({'COLUMNS': '-5'}) == 120
src = open(spec.origin).read()
assert 'fcntl' not in src and 'termios' not in src and '/fd/' not in src, 'no Linux-only terminal probe'
```

And, after the `env = {**os.environ, 'SESSION_BAR_CONFIG': …}` line (~348):

```python
with tempfile.TemporaryDirectory() as t:  # an empty home: no session file, no newer version, no notice
    for cols, width in (('100', 96), ('x', 116)):
        run = subprocess.run([sys.executable, '-I', '-S', spec.origin], input=json.dumps(FULL).encode(),
                             capture_output=True, env={**env, 'HOME': t, 'COLUMNS': cols})
        assert {len(ANSI.sub('', l)) for l in run.stdout.decode().splitlines()} == {width}, (cols, run)
```

- [ ] **Step 2:** `python3 -I test_session_bar.py` → `AttributeError: … has no attribute 'columns'`
- [ ] **Step 3: Implement `columns(env) -> int` in `session-bar.py`** in place of `terminal_columns()`: the integer
  in `env['COLUMNS']` when it is a positive integer, else 120. `main` calls `card_width(columns(os.environ), …)`.
  Delete the `fcntl`, `struct` and `termios` imports. In `configure.py`, the page's `columns` becomes
  `shutil.get_terminal_size((160, 24)).columns`.
- [ ] **Step 4:** `python3 -I test_session_bar.py` → `ok`
- [ ] **Step 5:** Mutation: make `columns` return 120 always; the tests fail; restore.
- [ ] **Step 6:** Commit: `Session Bar: the width from COLUMNS, no terminal probe through /proc`

### Task 2: Claude Code's folders from the environment

**Files:**
- Modify: `session-bar.py` (`host`, `main`)
- Test: `test_session_bar.py`, the readers section (line ~142) and the Remote Control block (line ~360)

**Interfaces:**
- Consumes: `columns(env)` (Task 1).
- Produces: `claude_dir(env) -> str`, `versions_dir(env) -> str`, `host(project, env=os.environ) -> dict`. Task 6
  imports `claude_dir` through `importlib`, as `configure.py` imports the card.

- [ ] **Step 1: Write the failing test**

```python
# Claude Code's folder moves with CLAUDE_CONFIG_DIR, its downloads with XDG_DATA_HOME; empty means unset
home = os.path.expanduser('~')
assert sb.claude_dir({'CLAUDE_CONFIG_DIR': '/c'}) == '/c' and sb.claude_dir({'CLAUDE_CONFIG_DIR': ''}) == os.path.join(home, '.claude')
assert sb.versions_dir({'XDG_DATA_HOME': '/d'}) == os.path.join('/d', 'claude', 'versions')
assert sb.versions_dir({}) == os.path.join(home, '.local', 'share', 'claude', 'versions')
```

In the Remote Control block, a second run with the session file under `t/cfg/sessions` and
`env={**env, 'HOME': t, 'COLUMNS': '188', 'CLAUDE_CONFIG_DIR': os.path.join(t, 'cfg')}` whose bottom line holds
`⇄ rc`, and one with `XDG_DATA_HOME=t/data` holding `claude/versions/9.9.9` whose bottom line holds `↑ 9.9.9`.

- [ ] **Step 2:** `python3 -I test_session_bar.py` → `AttributeError: … 'claude_dir'`
- [ ] **Step 3: Implement** `claude_dir(env)` and `versions_dir(env)` in `session-bar.py`; `main` uses them for
  `sessions`, `feedback/drafts` and `newest_version`; `host(project, env=os.environ)` reads the sandbox setting from
  `<claude_dir(env)>/settings.json` instead of `~/.claude/settings.json`.
- [ ] **Step 4:** `python3 -I test_session_bar.py` → `ok`
- [ ] **Step 5:** Mutation: `claude_dir` ignores `CLAUDE_CONFIG_DIR`; the tests fail; restore.
- [ ] **Step 6:** Commit: `Session Bar: Claude Code's folders follow CLAUDE_CONFIG_DIR and XDG_DATA_HOME`

### Task 3: Readers that work on three systems

**Files:**
- Modify: `session-bar.py` (`DISKS` line ~104, `host`, `session_record` line ~657, the module docstring)
- Test: `test_session_bar.py`, the readers section

**Interfaces:**
- Produces: `alive(pid) -> bool`, used by `session_record`.

- [ ] **Step 1: Write the failing test**

```python
# a process is alive without /proc: os.kill(pid, 0) on POSIX, OpenProcess on Windows (never kill there: 0 is Ctrl+C)
dead = subprocess.Popen([sys.executable, '-c', '']); dead.wait()
assert sb.alive(os.getpid()) is True and sb.alive(dead.pid) is False and sb.alive('x') is False and sb.alive(None) is False
assert '/proc/{' not in open(spec.origin).read().split('def session_record')[1].split('\ndef ')[0]
# a system without a load average (Windows) loses that element, never the card
saved = os.getloadavg
del os.getloadavg
try:
    assert 'load' not in sb.host('/nonexistent')
finally:
    os.getloadavg = saved
```

- [ ] **Step 2:** `python3 -I test_session_bar.py` → `AttributeError: … 'alive'`
- [ ] **Step 3: Implement**
  - `alive(pid) -> bool`: not an `int` (or a `bool`) → `False`. POSIX: `os.kill(pid, 0)`; `ProcessLookupError` →
    `False`, `PermissionError` → `True`. Windows (`os.name == 'nt'`): `ctypes.windll.kernel32.OpenProcess(0x1000,
    False, pid)`, `GetExitCodeProcess` equal to 259 (`STILL_ACTIVE`), `CloseHandle`.
  - `session_record` calls `alive(rec.get('pid'))` instead of `os.path.exists(f"/proc/…")`.
  - Disks through `shutil.disk_usage`, the same percentage as now (`used / (used + free)`);
    `DISKS = ['~'] if os.name == 'nt' else ['/tmp', '~/.cache']`.
  - Load: `except (OSError, AttributeError)`.
  - Memory: `/proc/meminfo` on Linux as now; on Windows `GlobalMemoryStatusEx` through `ctypes`; on macOS none.
  - Battery: unchanged (`/sys`, `None` elsewhere).
  - The docstring's "one statvfs per disk" becomes "one disk_usage per disk".
- [ ] **Step 4:** `python3 -I test_session_bar.py` → `ok`
- [ ] **Step 5:** Speed: 15 runs of the card on `FULL` → median under 40 ms.
- [ ] **Step 6:** Mutation: `alive` returns `True` always; the tests fail; restore.
- [ ] **Step 7:** Commit: `Session Bar: process, disk and load readers without /proc`

### Task 4: Hostile input to the card

**Files:**
- Modify: `session-bar.py` (`P` line ~137, `load_config` line ~377, `main`'s `json.loads`)
- Test: `test_session_bar.py`, beside the existing hostile-`.git` tests (line ~147)

**Interfaces:**
- Produces: `MAX_CONFIG = 64 * 1024`; `load_config(path)` returns `DEFAULT`'s values for a file larger than that.
  Task 7 relies on it for a project's layout.

- [ ] **Step 1: Write the failing tests** (keep the existing FIFO and long-`HEAD` tests)

```python
# links are https only: a file://, javascript: or ssh:// link would open on a click
assert sb.P('x', link='file:///etc/passwd')[4] is None and sb.P('x', link='javascript:x')[4] is None
assert sb.P('x', link='https://github.com/o/r')[4] == 'https://github.com/o/r'
```

Plus, in a temporary folder:
- `.git/HEAD` a symlink to `/dev/zero`: `git_info` returns `(name, '')` within the 2 s alarm;
- a 2 MB `packed-refs`: `git_sync` returns without raising;
- `sessions/<pid>.json` holding `[]`, `null`, `{"pid": "x"}` and bytes `b'\xff\xfe'`: `session_record` returns `{}`;
- a layout of 70 KiB (a valid custom setting padded with spaces): `load_config` equals `load_config('/nonexistent')`;
- the script on a payload whose `used_percentage` is `NaN` and `hit_ratio` `Infinity`: exit 0, 4 lines, no stderr.

- [ ] **Step 2:** `python3 -I test_session_bar.py` → the first failing assert is the `file://` link
- [ ] **Step 3: Implement**
  - In `P`, a link that does not start with `https://` becomes `None`.
  - `load_config` reads at most `MAX_CONFIG + 1` bytes and treats a longer file as missing.
  - `main` parses stdin with `json.loads(…, parse_constant=lambda c: None)`.
  - The symlink, `packed-refs` and session-file tests are expected to pass on today's readers (`head_of` checks the
    target is a regular file, `packed-refs` is read up to 1 MiB, `session_record` keeps dicts only); they pin that
    behaviour. One that fails is fixed in the reader it names.
- [ ] **Step 4:** `python3 -I test_session_bar.py` → `ok`
- [ ] **Step 5:** Mutation: drop the `https://` check; the tests fail; restore.
- [ ] **Step 6:** Commit: `Session Bar: https links only, a capped layout, NaN-safe payloads`

### Task 5: `install.py`, the command and the settings file

**Files:**
- Create: `install.py`
- Test: `test_session_bar.py`, a new section at the end: `# the installer (install.py)`

**Interfaces:**
- Produces, in `install.py`:
  - `CARD_ENV = ['HOME', 'USERPROFILE', 'SYSTEMROOT', 'COLUMNS', 'CLAUDE_CONFIG_DIR', 'XDG_DATA_HOME',
    'CLAUDE_CODE_SKIP_PROMPT_HISTORY', 'CLAUDE_CODE_IDLE_THRESHOLD_MINUTES', 'CLAUDE_CODE_IDLE_TOKEN_THRESHOLD']`
  - `PAGE_ENV = CARD_ENV + ['PATH', 'DISPLAY', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS',
    'BROWSER', 'TMPDIR', 'TEMP', 'TMP']`
  - `card_command(python: str, script: str, project: bool = False, shell: str = 'sh') -> str`
  - `status_line(command: str) -> dict` → `{'type': 'command', 'command': command, 'padding': 0, 'refreshInterval': 1}`
  - `class SettingsError(Exception)`; `read_settings(path: str) -> dict`
  - `write_settings(path: str, data: dict, stamp: str) -> str | None` (the backup's path, or `None` for a new file)
  - `settings_diff(old: dict, new: dict, path: str) -> str`
  - `is_ours(status_line, script: str) -> bool`

- [ ] **Step 1: Write the failing tests**

```python
ispec = importlib.util.spec_from_file_location('install', os.path.join(os.path.dirname(spec.origin), 'install.py'))
inst = importlib.util.module_from_spec(ispec)
ispec.loader.exec_module(inst)
with tempfile.TemporaryDirectory() as t:
    folder = os.path.join(t, "a b'c")  # a space and a quote in the path
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
assert "'C:/Py/python.exe'" in inst.card_command('C:\\Py\\python.exe', 'C:\\x\\s.py')
ps = inst.card_command('C:/Py/python.exe', 'C:/x/s.py', project=True, shell='powershell')
assert 'env -i' not in ps and ps.startswith('$env:SESSION_BAR_CONFIG') and "& 'C:/Py/python.exe'" in ps
```

And for the settings file, in a temporary folder:
- `read_settings` of a missing file is `{}`; of `{oops`, of `[]` and of a file with mode `000` (skipped as root) it
  raises `SettingsError`;
- a file written the way Claude Code writes it (`json.dumps(old, indent=2) + '\n'`, `old` holding `"name": "Ștefan"`
  and other keys), mode `0o600`, reached through a symlink: after `write_settings(link, {**old, 'statusLine': sl},
  '2026-10-20')`, the link is still a link, the target's JSON is `{**old, 'statusLine': sl}`, its text contains `Ștefan`
  as is, its mode is `0o600`, and the returned backup holds the old bytes exactly;
- a second write the same day returns a backup ending in `-session-bar-2`;
- `is_ours(status_line(inst.card_command(sys.executable, '/x/session-bar/session-bar.py')),
  '/x/session-bar/session-bar.py')` is `True`; `is_ours({'type': 'command', 'command': 'npx ccstatusline'}, …)` is
  `False`; `is_ours(None, …)` is `False`.

- [ ] **Step 2:** `python3 -I test_session_bar.py` → `FileNotFoundError` or `ModuleNotFoundError` for `install.py`
- [ ] **Step 3: Implement in `install.py`**
  - `card_command`, `sh` form: `env -i` followed by `NAME="$NAME"` for each name in `CARD_ENV`, then, at project
    scope, `SESSION_BAR_CONFIG="$CLAUDE_PROJECT_DIR/.claude/session-bar.json"`, then the Python and the script as
    single-quoted `sh` words (a `'` becomes `'\''`), then `-I -S` after the Python. Backslashes in both paths become
    `/`.
  - `card_command`, `powershell` form: at project scope `$env:SESSION_BAR_CONFIG =
    "$env:CLAUDE_PROJECT_DIR/.claude/session-bar.json"; `, then `& '<python>' -I -S '<script>'` (a `'` doubled).
  - `write_settings`: follow a symlink to its target; back up the target with `shutil.copy2` to
    `<target>.bak-<stamp>-session-bar` (then `-2`, `-3` …); write `json.dumps(data, indent=2, ensure_ascii=False) +
    '\n'` to a temporary file in the target's folder; copy the old mode; `os.replace`.
  - `settings_diff`: `difflib.unified_diff` of the two dumps.
  - `is_ours`: a dict whose `command` contains the script's path with forward slashes.
- [ ] **Step 4:** `python3 -I test_session_bar.py` → `ok`
- [ ] **Step 5:** Mutation: drop `env -i` from the `sh` form; the tests fail; restore.
- [ ] **Step 6:** Commit: `install.py: the status line command under env -i, and safe settings writes`

### Task 6: `install.py`, install and uninstall

**Files:**
- Modify: `install.py`
- Test: `test_session_bar.py`, the installer section

**Interfaces:**
- Consumes: everything Task 5 produces; `claude_dir(env)` and `DEFAULT` from `session-bar.py` (imported through
  `importlib`).
- Produces: `main(argv: list) -> int`, with
  `install.py [--scope user|project] [--project PATH] [--uninstall] [--dry-run] [--yes]` (`--scope user` and the
  current folder by default); `CODE = ['session-bar.py', 'configure.py', 'configure-web.html']`;
  `write_launcher(bin_dir: str, python: str, configure: str, windows: bool) -> list`.
  The launcher's first comment line is `# session-bar launcher (claude-skin install.py)` (`rem …` in the `.cmd`):
  uninstall removes only files that carry it.

- [ ] **Step 1: Write the failing tests.** Run `install.py` as a subprocess with `HOME=t`,
  `CLAUDE_CONFIG_DIR=t/c`, a project `t/p` and stdin not a terminal, and check:
  - `--scope user --yes`: exit 0; `t/c/session-bar/` holds `CODE` and a `session-bar.json` equal to `DEFAULT`;
    `t/c/settings.json`'s `statusLine` is ours and its command contains `env -i`; `t/.local/bin/session-bar` exists, is
    executable and carries the marker;
  - the end-to-end run: that `statusLine`'s command through `sh -c`, `FULL` on stdin and
    `{**os.environ, 'HOME': t, 'CLAUDE_CONFIG_DIR': t/c, 'COLUMNS': '100', 'FAKE_SECRET': 'k'}` → exit 0, every line
    96 cells;
  - an edited user layout survives a second install; the second install's backup exists;
  - `--uninstall`: the `statusLine` is gone, `CODE` and the launcher are gone, the layout stays and its path is in
    the output;
  - an uninstall after the user changed the command leaves that `statusLine` in place and says so;
  - `t/c/settings.json` holding `{oops`: exit 1, the file's bytes unchanged;
  - a foreign `statusLine` (`npx ccstatusline`) without `--yes`: exit 1, unchanged; with `--yes`: replaced, and the
    backup holds the old one;
  - `--scope project --project t/p --yes` on a fresh `t/c`: `t/p/.claude/session-bar.json` equals `DEFAULT`;
    `t/p/.claude/settings.local.json`'s command contains `SESSION_BAR_CONFIG="$CLAUDE_PROJECT_DIR/`; the code is in
    `t/c/session-bar/`; `t/c/settings.json` does not exist;
  - `--dry-run`: the diff is printed and no file changes.
- [ ] **Step 2:** `python3 -I test_session_bar.py` → the first `install.py` run exits non-zero
- [ ] **Step 3: Implement `main`**
  - **user:** copy `CODE` with `shutil.copy2` into `<claude_dir>/session-bar/`; write `DEFAULT` there as
    `session-bar.json` only when that file does not exist; set `statusLine` in `<claude_dir>/settings.json`; write
    the launcher into `<home>/.local/bin`, and print one line when that folder is not on `PATH`.
  - **project:** copy the code and write the launcher when `<claude_dir>/session-bar/session-bar.py` is missing,
    without touching the user's settings; write `DEFAULT` to `<project>/.claude/session-bar.json` only when missing;
    set `statusLine` (project form) in `<project>/.claude/settings.local.json`.
  - **Before any write:** `read_settings` (a `SettingsError` → message, exit 1); a `statusLine` that is not ours →
    replace only with `--yes` or a `y` typed at a terminal; print `settings_diff`; with `--dry-run` stop there.
  - **Shell:** `sh` off Windows. On Windows, Git Bash when found in the order of Claude Code's `mQ()` (read in
    2.1.303): `CLAUDE_CODE_GIT_BASH_PATH` when its name is `bash.exe`, `sh.exe`, `bash` or `sh` and it exists; then
    `C:\Program Files\Git\bin\bash.exe`; then `C:\Program Files (x86)\Git\bin\bash.exe`; then `<git on PATH>/../../bin/bash.exe`.
    None found → `powershell`, with a warning that the keys reach the card.
  - **`--uninstall`:** remove our `statusLine` from the scope's settings file; at user scope remove `CODE` and the
    launcher files that carry the marker; never remove a `session-bar.json`, and print each one kept.
  - `write_launcher`: `session-bar`, a `#!/bin/sh` script, mode `0o755`, that runs
    `exec env -i <PAGE_ENV pairs> '<python>' -I -S '<configure>' --detach "$@"`; on Windows also `session-bar.cmd`
    running `"<python>" -I -S "<configure>" --detach %*`.
- [ ] **Step 4:** `python3 -I test_session_bar.py` → `ok`
- [ ] **Step 5:** Mutation: `--uninstall` also removes `session-bar.json`; the tests fail; restore.
- [ ] **Step 6:** Commit: `install.py: install and uninstall for the user or a project`

### Task 7: `configure.py`, the launcher's side

**Files:**
- Modify: `configure.py` (`SAVE`, `do_GET`'s `/api/state`, `main`)
- Modify: `configure-web.html` (one line at the top of the page)
- Test: `test_session_bar.py`, the settings page section (line ~436)

**Interfaces:**
- Consumes: `MAX_CONFIG` and `load_config` (Task 4).
- Produces: `layout_for(cwd: str, user_layout: str, home: str) -> tuple` → `(path, 'project' | 'user')`;
  `/api/state` gains `'file'` and `'scope'`; `configure.py --detach [port]`, and the internal `--serve [port]`.

- [ ] **Step 1: Write the failing tests**

```python
# the launcher edits the layout that applies here: the nearest project's, else the user's; never one above home
with tempfile.TemporaryDirectory() as t:
    home, user = os.path.join(t, 'h'), os.path.join(t, 'h', '.claude', 'session-bar', 'session-bar.json')
    proj = os.path.join(home, 'work', 'app')
    os.makedirs(os.path.join(proj, '.claude')); os.makedirs(os.path.join(proj, 'src', 'deep'))
    os.makedirs(os.path.join(t, '.claude'))
    open(os.path.join(t, '.claude', 'session-bar.json'), 'w').close()  # above home: never used
    assert web.layout_for(os.path.join(home, 'work'), user, home) == (user, 'user')
    layout = os.path.join(proj, '.claude', 'session-bar.json')
    open(layout, 'w').close()
    assert web.layout_for(os.path.join(proj, 'src', 'deep'), user, home) == (layout, 'project')
```

And a run of `configure.py --detach 0` as a subprocess, from `proj`, with `HOME=home`, `PATH=/nonexistent` and no
`DISPLAY`, `WAYLAND_DISPLAY` or `BROWSER` (no browser can open): it exits 0 within 5 s, its one line of output holds
`http://127.0.0.1:` (with `BROWSER=true`, a browser that "opens", the output is empty); `GET <url>api/state` answers with `scope == 'project'` and `file == layout`; then
`POST <url>api/bye` (the server goes a few seconds later).

Before that run, the project layout is hostile: 70 KiB, with unknown elements and wrong types. `/api/state`'s `cfg`
then equals `load_config('/nonexistent')`, and the server keeps answering.

The server's guards, beside the existing `Host` and `Origin` tests (line ~461), each answered without touching the
layout file:
- a POST body over `MAX_BODY` → 400;
- a body that is not JSON → 400;
- `Content-Type` other than `application/json` → 400;
- `GET /../session-bar.py`, `GET /%2e%2e/session-bar.json` and `GET /configure.py` → 404.

- [ ] **Step 2:** `python3 -I test_session_bar.py` → `AttributeError: … 'layout_for'`
- [ ] **Step 3: Implement**
  - `layout_for`: from `cwd` up to `home`, or to the root when `cwd` is not under `home`, the first
    `<dir>/.claude/session-bar.json` that is a regular file; else the user's.
  - `SAVE`: `SESSION_BAR_CONFIG` when set (the tests use it), else `layout_for(os.getcwd(), <HERE>/session-bar.json,
    ~)`.
  - `/api/state`: `'file': SAVE, 'scope': SCOPE`. The page shows `<scope> layout · <file>` above the card.
  - `--detach`: start `[sys.executable, '-I', '-S', __file__, '--serve', port]` with stdin and stderr to
    `DEVNULL`, stdout to a pipe, `start_new_session=True` on POSIX or `creationflags=0x8 | 0x200` on Windows, the same
    folder and environment. Read its first line, waiting at most 10 s, and exit 0. Print nothing when the browser
    opened, so `! session-bar` adds next to nothing to the conversation; print the line when it did not. No line → a
    message, exit 1.
  - `--serve`: as today's `main`, but open the browser first, then print one line, `opened <url>` or
    `Session Bar settings (<scope>: <file>): <url>` when `webbrowser.open` returned `False`, then point file
    descriptor 1 at `os.devnull`, so the parent and Claude Code's `!` see the end of the output.
  - Without a flag, `configure.py` behaves as it does today.
- [ ] **Step 4:** `python3 -I test_session_bar.py` → `ok`
- [ ] **Step 5:** Mutation: `layout_for` keeps climbing past `home`; the tests fail; restore.
- [ ] **Step 6:** Commit: `Settings page: the layout that applies here, and a detached start for session-bar`

### Task 8: README and notes

**Files:**
- Create: `README.md`
- Modify: `NOTES.md` (the Run table, the facts section)

- [ ] **Step 1: Write `README.md`**, in this order:
  1. **What it is:** one paragraph and one sample of the card.
  2. **Install:** clone or download the zip, then `python3 install.py`. Each teammate runs
     `python3 install.py --scope project`. Python 3.8+ is needed: on Windows from python.org, on macOS `python3` from
     Xcode's tools or Homebrew.
  3. **Settings:** `session-bar` in a terminal costs nothing. `! session-bar` inside Claude Code also works, but by
     default Claude answers after it, which costs tokens; `"respondToBashCommands": false` stops that, for every `!`
     command.
  4. **Keys:** what `env -i` keeps out, and that the shell Claude Code starts still receives them. Windows with
     PowerShell only gets no `env -i`. Organizations can add `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`.
  5. **Organizations:** under `allowManagedHooksOnly`, only a `statusLine` in managed settings runs; under
     `disableAllHooks`, none; a workspace has to be trusted.
  6. **Uninstall.**
  7. **Checking on a real Mac and a real Windows machine:** install at each scope, look at the card, run
     `session-bar`, uninstall.
- [ ] **Step 2: Update `NOTES.md`**: `install.py` and `session-bar` in the Run table; the "Facts read for this plan"
  above, under a 2.1.303 heading; the width now from `COLUMNS`.
- [ ] **Step 3:** `python3 -I test_session_bar.py` → `ok`
- [ ] **Step 4:** Commit: `README: install, settings, keys and organizations`

### Task 9: Security review

- [ ] **Step 1:** Run the `security-review` skill on the branch (`git diff main...session-bar-install`).
- [ ] **Step 2:** For each finding that holds up, a failing test first, then the fix, then `python3 -I
  test_session_bar.py` → `ok`, then a commit per fix.
- [ ] **Step 3:** Report the findings and what was done with each; offer `ponytail-audit` for a whole-repository
  pass.

## Not in this plan

- Switching this machine's own `~/.claude/settings.json` to the installed copy: it points at the clone and stays so
  unless the user asks, and then with a backup and a diff.
- An OS sandbox, a pip package, managed-settings tooling: non-goals in the spec.
