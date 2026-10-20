# Claude Code Session Bar

[![CI](https://github.com/flaviu-vanca/claude-code-session-bar/actions/workflows/ci.yml/badge.svg)](https://github.com/flaviu-vanca/claude-code-session-bar/actions/workflows/ci.yml)

A status line for Claude Code, drawn as a card: the model, the cost and time, segmented meters for the context and
the usage limits, the workspace and the machine, and the footer's states on its bottom edge. One Python script,
standard library only, about 20 ms a run, no network. Nothing it shows reaches the model, so it costs no tokens.

```
╭─ ✻ Opus 5.5 · xhigh ────────────────────────────────────────────────── $73.50 · ◷ 6h42m ─╮
│ ctx ▰▰▰▰▱▱▱▱▱▱ 38% 383k/1M · 5h ▰▰▱▱▱▱▱▱▱▱ 20% ↻1h33m · week ▰▰▰▰▰▰▰▱▱▱ 69% ↻4d12h       │
│ ⎇ my-app main · ⌂ ~/work/my-app · # 804d5fae · mem 5.1/14.9G · /tmp 51% · ~/.cache 74%   │
╰─ ↑ 2.1.304 restart · PR #12 ✓ · ↯ fast · -- INSERT -- ───────────────────────────────────╯
```

## Install

You need Python 3.8 or newer: on Windows from python.org, on macOS `python3` from Xcode's command line tools or
Homebrew, on Linux from your distribution. Get the code, then run the installer from its folder (on Windows, `py`
in place of `python3`):

```sh
git clone https://github.com/flaviu-vanca/claude-code-session-bar
cd claude-code-session-bar
python3 install.py                     # for you, in every project
python3 install.py --scope project     # for the project in this folder
```

- **For you:** the card's code goes to `~/.claude/session-bar/` (or `$CLAUDE_CONFIG_DIR/session-bar/`), its layout
  beside it, and the `statusLine` into `~/.claude/settings.json`.
- **For a project:** the layout goes to `.claude/session-bar.json`, for the team to commit; the command goes to
  `.claude/settings.local.json`, which stays out of git; the code comes from your own install, made on the way if it
  is missing. Each teammate runs `python3 install.py --scope project` once. No code that runs and no path of one
  machine ever enters the repository.
- **Every change** to a settings file is shown as a diff, after a backup (`<file>.bak-<date>-session-bar`; for a
  project, under `~/.claude/session-bar/backups/`). `--dry-run` shows the diff and writes nothing. A status line of
  another tool is replaced only with `--yes`, or a `y` typed at the prompt.
- **To update:** pull, or download the zip again, and run the same command. The code is replaced; every layout stays.

Claude Code then draws the card on its next refresh, within a second.

## Change the card

```sh
session-bar
```

It opens the settings page in your browser: drag elements between the card's places, pick a palette and the meters'
length, save. It edits the layout that applies in the folder you run it from, a project's when there is one, else
yours, and the page says which at its top. The page runs on 127.0.0.1 only and stops a few seconds after you close
it. `session-bar` lives in `~/.local/bin`, Claude Code's own bin folder; the installer says so when that folder is not
on your `PATH`.

**From a terminal**, it costs nothing. **Inside Claude Code**, `! session-bar` works too, but by default Claude answers
after every `!` command, and an answer re-reads the whole conversation: one model call per opening. Moving elements
on the page costs nothing either way. To stop Claude answering after `!` commands (all of them, not only this one),
set `"respondToBashCommands": false` in your settings.

## Keys

Claude Code starts the status line command through a shell, `/bin/sh` on Linux and macOS, Git Bash (or PowerShell
when Git Bash is missing) on Windows, and hands that shell its whole environment, keys included. The installed command
therefore starts Python under `env -i`, with only the names the card reads: `HOME`, `USERPROFILE`, `SYSTEMROOT`,
`COLUMNS`, `CLAUDE_CONFIG_DIR`, `XDG_DATA_HOME` and three `CLAUDE_CODE_*` switches. No key reaches the card's
process, and the card never reads another process's environment. The `session-bar` launcher starts the page the same
way, with a few more names for the browser.

- The shell itself still receives everything; that part is Claude Code's.
- **Windows with PowerShell only** has no `env -i`: there the card gets the whole environment. The installer warns.
  Installing Git for Windows fixes it.
- Organizations can also set `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`, which makes Claude Code drop credential-like
  names from every process it starts.

## Organizations

- With `allowManagedHooksOnly` in managed settings, only a `statusLine` set there runs: deploy the command through
  managed settings instead of `install.py`.
- With `disableAllHooks` in managed settings, no status line runs at all.
- A workspace has to be trusted before Claude Code runs any status line in it.

## Uninstall

```sh
python3 install.py --uninstall                     # yours
python3 install.py --uninstall --scope project     # a project's
```

It removes the `statusLine` only while it still runs the installed card, then the code and the launcher. Layouts are
kept, and named, so a reinstall picks them up.

## Checking it on your machine

```sh
python3 check_install.py
```

It installs into a temporary home and runs the installed status line the way Claude Code would, through `sh`, or on
Windows through Git Bash and PowerShell. It checks that no key planted in the environment reaches the card, opens the
settings page through `session-bar`, and uninstalls. Nothing of yours is touched. CI runs it, with the unit tests, on
Linux, macOS and Windows at every push.

What only a person can check, in a real Claude Code session: the card's look, a save in the page showing on the card
within a second, and a project's layout in that project.
