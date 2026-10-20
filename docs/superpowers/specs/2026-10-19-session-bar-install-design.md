# Session Bar: install anywhere, keep keys out

Date: 2026-10-19. Status: reviewed once; waiting for the user's approval.

## Why

The Session Bar (`session-bar.py`, the status line card) works on one Linux machine, through a `statusLine` entry
written by hand and a settings page (`configure.py`) started by hand in a terminal of its own. The user wants other
people, organizations among them, to use it on Linux, macOS and Windows, installed the way plugins are: for the user
(every project) or for one project.

Organizations do not want any key held in the environment (not only `ANTHROPIC_API_KEY`) to reach the card's process.
Until today the card read Claude Code's whole launch environment from `/proc/<pid>/environ` to look up three names;
that read is gone (2026-10-19, uncommitted): the card now reads those three names from its own environment.

## Goals

1. The card runs on Linux, macOS and Windows.
2. No key from the environment reaches the card's Python process, and the card never reads another process's
   environment.
3. `install.py` installs and uninstalls the card for the user (every project) or for one project, and changes a
   Claude Code settings file only after a backup, showing a diff. A project shares only its layout through git; no
   code that runs and no machine's path is ever committed (the user's choice, 2026-10-19).
4. A `session-bar` command opens the settings page for the layout that applies in the current folder. It returns at
   once, so the user can type `! session-bar` inside Claude Code (the user's chosen way), and it also works from a
   separate terminal.
5. Hostile-input tests cover what an untrusted repository, file or web page can feed the card, the page's server and
   the installer; `/security-review` runs on the finished branch.

## Non-goals

- An OS-enforced sandbox (bubblewrap, `sandbox-exec`). Tested on Linux on 2026-10-19: `bwrap --ro-bind / /
  --unshare-net --new-session --die-with-parent` gives the same output once `COLUMNS` is set, blocks writes, network
  and reads of other processes' `/proc`, and costs 3.6 ms. A later step.
- Shipping the card as a Claude Code plugin: a plugin's settings may set only `agent` and `subagentStatusLine`
  (`yho=["agent","subagentStatusLine"]` in 2.1.303), never `statusLine`.
- Deploying through managed settings: one note in the README, nothing built.
- A bar that appears for a teammate who never ran the installer: each teammate runs it once (the user's choice).
- A pip or pipx package: people get the card as a git clone or a zip of the repository (my call).
- A slash command for the page: it would send a prompt to the model and cost tokens on every use.

## Anti-goals: a failure even if everything works

- The card, the page or the installer reads, keeps, prints or sends a credential, or reads another process's
  environment.
- A subprocess, a network call or a large read in the card, or a run noticeably slower than the ~20 ms of today.
- The installer writing a settings file it could not parse, or changing any key other than `statusLine`, or writing
  without a backup.
- A row that is not exactly the card's width at some width from 30 to 240; a glyph wider than one cell; emoji.

## Facts from Claude Code 2.1.303

Read in the binary (`~/.local/share/claude/versions/2.1.303`) unless marked as a hypothesis.

- **How the command runs:** `executeStatusLineCommand` (`Pbr`) hands it to the hook runner `$H`, always in shell form.
  The `statusLine` schema has only `type`, `command`, `padding`, `refreshInterval` and `hideVimModeIndicator`: no
  `args`, no `shell`.
- **Which shell:** `/bin/sh` on Linux and macOS. On Windows, Git Bash when it is found (or `CLAUDE_CODE_GIT_BASH_PATH`),
  else PowerShell (`Oj`, `Xl`). The docs add: write paths in the command with forward slashes; `~` works.
- **Which environment:** `os()`, which is `process.env` plus the settings' `env`, returned as it is unless
  `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` (or GitHub Actions) turns on a deny list of credential-like names; then
  `COLUMNS` and `LINES`, taken from Claude Code's own stdout at every run, and `CLAUDE_PROJECT_DIR`.
- **When it does not run:** `disableAllHooks` in managed settings; with `allowManagedHooksOnly`, only the managed
  `statusLine` runs; a workspace whose trust is not accepted; cloud sessions.
- **Hypotheses to check before building on them:**
  - which `statusLine` wins when user, project and local settings each set one. The project scope rests on the local
    file's winning over the user's; if it does not, stop and bring it back to the user;
  - where `sessions` and `versions` live on macOS and Windows, and which folders move with `CLAUDE_CONFIG_DIR`;
  - whether `!` (bash mode) runs inside Claude Code's sandbox when it is on, so that the page's server could not
    start, and whether its output enters the conversation;
  - on Windows, which `PATH` the `!` shell sees, and whether Git Bash finds a `.cmd` file by its bare name.

## Design

### 1. The card on three systems

- **Width:** from `COLUMNS`, which Claude Code sets at every run; 120 when it is missing. The walk up the process tree
  through `/proc` to the terminal goes, and with it `fcntl`, `termios` and `struct` (Windows has no `fcntl` or
  `termios`, so today the card fails there on import).
- **Claude Code's folder:** `CLAUDE_CONFIG_DIR` when set and not empty, else `~/.claude`, wherever the card reads
  `sessions`, `feedback/drafts` and `settings.json`. The `versions` folder per system comes from the check above.
- **What only Linux offers:** memory (`/proc/meminfo`), load, battery (`/sys`) and the check that Claude Code's process
  is alive (`/proc/<pid>`). On the other systems each one either has a stdlib way with no subprocess (for example
  `shutil.disk_usage`, `os.getloadavg`, `ctypes` on Windows) or shows nothing, as an element of another shape does
  today (`safe()`). Never `os.kill(pid, 0)` on Windows: signal 0 is `CTRL_C_EVENT` there.
- **Unchanged:** stdlib only, `python3 -I -S`, no subprocess, no network, only small reads, ~20 ms.

### 2. Keys out of the card's process

The shell Claude Code starts receives its whole environment; nothing the card does can change that. The command the
installer writes therefore starts Python with an empty environment and a short allowlist:

```sh
env -i HOME="$HOME" COLUMNS="$COLUMNS" CLAUDE_CONFIG_DIR="$CLAUDE_CONFIG_DIR" \
  CLAUDE_CODE_SKIP_PROMPT_HISTORY="$CLAUDE_CODE_SKIP_PROMPT_HISTORY" \
  CLAUDE_CODE_IDLE_THRESHOLD_MINUTES="$CLAUDE_CODE_IDLE_THRESHOLD_MINUTES" \
  CLAUDE_CODE_IDLE_TOKEN_THRESHOLD="$CLAUDE_CODE_IDLE_TOKEN_THRESHOLD" \
  "/absolute/python3" -I -S "/absolute/session-bar.py"
```

- At project scope the list also carries `SESSION_BAR_CONFIG="$CLAUDE_PROJECT_DIR/.claude/session-bar.json"`, so the
  user's own copy of the card draws the project's layout. The card already reads that variable.
- An allowlisted name that is unset arrives empty; the card must read an empty value as unset.
- `env -i` works in `/bin/sh` and in Git Bash. Windows probably also needs `USERPROFILE` and `SYSTEMROOT` in the list
  (hypothesis: check on a real Windows machine).
- The launcher starts the page's server with the same allowlist, so the server never holds a key either (my call).
- Windows with PowerShell only and no Git Bash: there is no `env -i`, so the keys reach the card. The installer warns
  and the README says so (my call).
- The README tells organizations they can also set `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`, which narrows what even the
  shell receives.

### 3. `install.py`

`python3 install.py [--scope user|project] [--uninstall] [--dry-run]`, stdlib only, the same on every system. People
get it as a git clone or a zip; to update, they pull and run it again.

- **user:** copies the card's code (`session-bar.py`, `configure.py`, `configure-web.html`) into
  `<claude dir>/session-bar/`, adds a default `session-bar.json` there if none exists, writes `statusLine` into
  `<claude dir>/settings.json`, and installs the launcher.
- **project:** does the user install first when it is missing, since the code always comes from there. It adds a
  default `<project>/.claude/session-bar.json` if none exists, for the team to commit, and writes `statusLine` into
  `<project>/.claude/settings.local.json`, which stays out of git. A teammate who clones the project runs
  `python3 install.py --scope project` once.
- There is no third, local scope: at project scope the command already lives in the local settings file (my call).
- It writes only `statusLine` (`type`, `command`, `padding: 0`, `refreshInterval: 1`) and keeps every other key.
- Before writing: a backup `<file>.bak-<date>-session-bar`, then the diff. The write is atomic and keeps the file's
  permissions.
- It stops without writing when the settings file cannot be read or parsed. When a `statusLine` is already there, it
  shows it and asks before replacing it; the old one stays in the backup.
- The Python path is the absolute one the installer runs under (`sys.executable`), with forward slashes on Windows.
- **A layout is never lost (my call):** a second install replaces the code and keeps every `session-bar.json`.
  `--uninstall` removes the `statusLine` only while its command still points at the installed card's path, removes
  the code and the launcher, and keeps the layouts, naming them; at project scope it touches only
  `settings.local.json`.

### 4. `session-bar`, the settings page's launcher

- **Where it goes:** `~/.local/bin/session-bar` on Linux and macOS, with a hint when that folder is not on `PATH`. On
  Windows a `session-bar` shell script for Git Bash and a `session-bar.cmd` for PowerShell, in a folder on the user's
  `PATH` (which one comes from the check above).
- **Which layout:** it walks up from the current folder to a project layout (`.claude/session-bar.json`), else it
  opens the user's.
- **Whose code:** always the user install's `configure.py`; a project's layout is read as data only, through
  `load_config`, which already skips elements it does not know. A cloned repository never runs code through the
  launcher (my call).
- **It returns at once:** `configure.py` starts its server in a detached process (a new session on POSIX, a detached
  process on Windows), prints the page's address and exits. The server still stops a few seconds after the page
  closes, as it does today.
- **The page says what it edits:** the scope and the file's path sit at its top, so a change to the team's bar is never
  mistaken for a change to one's own.
- The page's preview width comes from `shutil.get_terminal_size()`, because a terminal does not export `COLUMNS`.
- If the check shows that `!` cannot start a server while Claude Code's sandbox is on, `session-bar` says so in one
  line and points to a separate terminal.

### 5. Security testing

New tests in `test_session_bar.py`, written first like every other test:
- **The card:**
  - a repository whose `HEAD` is a FIFO, or a symlink to `/dev/zero`;
  - a huge `packed-refs`;
  - control characters and escape sequences in branch, repository, session and model names;
  - a PR link whose scheme is not `https`: links become `https` only, a one-line change in `P()`;
  - malformed session files;
  - `NaN` and `Infinity` in the payload;
  - a fake secret in the environment that must not reach the card through the installed command (run the command
    through `sh` with a stub that prints the names in its environment).
- **The server:** a wrong `Host`, a wrong `Origin`, an oversized body, a body that is not JSON, and paths that try to
  leave the page.
- **The installer:** a settings file that is invalid JSON, unreadable, or a symlink; an existing `statusLine`; a
  second install that must keep an edited layout; an uninstall after the user changed the command.
- **The launcher:** a hostile project layout (unknown elements, wrong types, huge file) opened as data.

At the end, `/security-review` on the branch, and `ponytail-audit` if the user wants a whole-repository pass.

## Constraints

- Every rule in `CLAUDE.md`: tests first, one mutation per new piece of code, the width rule from 30 to 240,
  one-cell glyphs, the speed budget, and backup plus diff before `~/.claude/settings.json` changes on this machine.
- Code, comments, docs and commits in English.
- Facts about Claude Code come from its binary; anything unread is marked as a hypothesis.

## Left to the builder

- Memory and disks on macOS and Windows: a stdlib way, or nothing.
- The test layout for simulated systems (no `/proc`, `os.name == 'nt'`, `sys.platform == 'darwin'`).
- The launcher's exact files on Windows, once the `PATH` check is done.
- The minimum Python version (3.8 unless the code needs more).

## What cannot be verified here

This machine is Linux only. macOS and Windows are covered by tests that simulate them, not by real runs. The
document ends the build with a short checklist for a real Mac and a real Windows machine: install at each scope, the
card's look, `! session-bar`, uninstall.
