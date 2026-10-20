# Claude Code Session Bar: notes

This project customizes how Claude Code looks. It started inside the codewiki sessions on 2026-10-18 and moved here
the same day as `~/session-bar`, then was renamed `~/claude-skin`. On 2026-10-19 the user narrowed it to the Session
Bar alone: the agents window's theme, its notes and the idea of a live agents dashboard were removed. On 2026-10-20 it
was renamed `claude-code-session-bar` and published at https://github.com/flaviu-vanca/claude-code-session-bar,
installed with `install.py`; CI runs it on Linux, macOS and Windows.

The Session Bar is a rounded card with segmented heat-coloured meters and the footer's states on its bottom edge. It
is Python 3 stdlib only, runs with `python3 -I -S`, and one run takes about 20 ms.

## Run

| What | Command |
|---|---|
| The card, on a payload | `python3 -I -S session-bar.py [--meter N] < payload.json` |
| The settings in the browser, drag and drop | `python3 configure.py [port]`, in a terminal of its own: it serves the page on 127.0.0.1, opens it, and stops a few seconds after the page closes |
| Tests (prints `ok`) | `python3 -I test_session_bar.py` |
| Preview of the chips with sample states | `python3 -I preview/chips.py` |
| Install for the user or a project, uninstall (README.md) | `python3 install.py [--scope user\|project] [--uninstall] [--dry-run] [--yes]` |
| The settings page for the layout that applies here, detached | `session-bar` (installed in `~/.local/bin`), or `python3 configure.py --detach` |

Live use: `statusLine.command` in `~/.claude/settings.json` points at `session-bar.py` in this folder, with
`"padding": 0` and `"refreshInterval": 1`. `install.py` writes an `env -i` command instead (see README.md); this
machine still runs the clone directly.

The card takes the terminal's width from `COLUMNS`, which Claude Code sets at every run; until 2026-10-20 it walked
the process tree to the terminal through `/proc`.

## The card

`session-bar.json` beside the script holds the layout:
- `top_left` and `top_right`: text elements;
- `rows`: any number of rows, each holding meters and text;
- `edge`: the chips;
- `meter`: the bars in a meter, 3–30;
- `palette`: default, nord, dracula, gruvbox, tokyo, catppuccin, rose-pine, solarized, one-dark, everforest,
  kanagawa, monokai, ayu, synthwave, or the monochrome mono, matrix and amber.

`SESSION_BAR_CONFIG` overrides the path. Without the file the card uses `DEFAULT`. Unknown elements are skipped.
The first settings' `meters` and `info` keys are read as two rows.

When a row is too long, its meters shrink to half their length, then it wraps onto more lines; a dim `·` sits
between elements. The edges still drop elements from the end of their lists.

`configure.py` edits the file through a page in the browser, `configure-web.html`, whose card and tiles are drawn by
the card itself. The page is always one screen: the card, its places and the elements each scroll in their own box.
- drag elements between the places, or click a place and then an element; `×`, `Del` or a drop on the elements
  removes one. Every place takes any number of elements, the top edge's two sides too;
- the elements fold in groups: Meters, Model, Session, Workspace, Machine and Chips. Hovering or focusing one shows
  what it shows (`WHAT` in `configure.py`), where it can go and where it is;
- `Alt` `←` `→` move an element within its place; rows are added and deleted on the page;
- the Look tab, beside Elements, holds the bars a meter has and the palettes, each drawn as a little card: its name in
  its top edge, in its accent, around a meter in its colours;
- `Ctrl` `S` saves (written whole, through a temporary file), `Ctrl` `Z` undoes.

The server answers only this machine's page (Host and Origin) and runs every setting through `load_config` before it
renders or saves. On 2026-10-19 it replaced the terminal configurator, which is in git at `899d14d` (MIX-12). The
page before this one, with sliders for the sample session and an actual-size view, is in git at `3d08aad`.

The card picks up a save on its next run. `statusLine.refreshInterval` is 1 s since 2026-10-18, so the card also
follows a window resize within a second: Claude Code reruns the command on its triggers and that timer, never on a
resize.

No element costs tokens: the status line's output never reaches the model.

5h and week show 1 point more than the payload, up to 100. The payload's figure comes from the headers of this
session's last response, and it trails claude.ai and `/usage`: on 2026-10-19 the card said 23% and 72% where
`/usage`, which rounds down, said 24% and 73%. The offset is the user's choice: an estimate, so right after a reset
the card shows 1%. Spend is shown as it comes.

| Place | Elements (the default ones in bold) |
|---|---|
| Top edge, left and right; any row | **model**, **effort**, thinking, style, agent, name (`/rename`), version, **cost**, **time**, api (API time), lines (+/-), clock, **repo** (linked to origin; ⇡ ⇣ ⇅), **cwd**, **session**, worktree, dirs (`/add-dir`), **mem**, **disks**, load, battery |
| Meters, on any row | **ctx**, **5h**, **week**, spend (gateway only), hits (prompt cache hit ratio, green is good: cache read tokens / all input tokens, 0..1, read in 2.1.303) |
| Bottom edge (chips) | **cloud**, **rc**, mode, **no_transcript**, **update**, **cache** (and what a cold start costs), **miss** (a cache miss and why), idle (Claude Code's "new task? /clear" hint on fixed thresholds, 75 min and 100k; with `CLAUDE_CODE_IDLE_TOKEN_THRESHOLD` set high where `claude` starts, only this one shows), big (context past 200k), drafts, **sandbox**, **working**, **pr**, **fast**, **vim** |

By default the top left holds model and effort, the top right cost and time, row 1 ctx, 5h and week, and row 2
repo, cwd, session, mem and disks. `repo` shows only inside a repository; `cwd` always shows.

`repo` links its name to the branch's page on origin, from the payload's `workspace.repo` (host, owner, name: Claude
Code reads the remote itself, `kR` in 2.1.303, credentials dropped and remotes on disk left out), and marks the branch
ahead of origin's (`⇡`), behind (`⇣`) or apart (`⇅`). Without running git that comes from
the reflogs (the last 64 KB of each): the branch that once stood where the other stands now is the one that moved
on. A fetch moves origin's branch, so `⇣` shows what the last fetch brought.

The cache chip adds, in brackets, the payload's `prompt_cache.recache_tokens_if_cold`: what the next request costs
once the cache is gone (Claude Code's own estimate, 2.1.303). `miss` shows for 5 minutes after the cache missed
(`last_miss_at`), with the first of `last_miss_cause.causes` in short words: Claude Code's causes and its own words
for them are in `RLs` (system prompt, tools, model, effort, idle past the 5m or 1h TTL, server side, and others).

The cache's lifetime (Claude Code's docs, prompt-caching and settings-reference, read through Context7 on
2026-10-19): on a Claude subscription within the plan, the main conversation gets 1 hour and everything else 5
minutes; on usage credits Claude Code drops the main conversation to 5 minutes. `promptCacheTtl: "1h"` in
`~/.claude/settings.json` keeps the hour there too, set 2026-10-19: a 1-hour write costs 2x the input price against
1.25x, a read 0.1x, and one rebuild of a large context costs far more than the extra on each turn's new part. This
session's transcript showed only 1-hour writes. `subagentPromptCacheTtl` stays unset: subagents rarely pause 5
minutes between steps.

`thinking` shows `∴ thinking` while Claude works out its next step: the session file says `busy` and the transcript's
last message is the user's or a tool's result (`last_speaker`, from the last 256 KB). Claude Code writes a message
only once it is whole, so the element goes when the step's first block lands, and stays off while a tool runs or
Claude waits. Read in 2.1.303:
- the payload's `thinking.enabled` is the mode only: on unless turned off (`/config`, which writes
  `alwaysThinkingEnabled: false`, or `MAX_THINKING_TOKENS=0`), and always on for a model with
  `rejects_disabled_thinking`, Opus 5.5 among them. Until 2026-10-19 the element showed that, so it never changed;
- Opus 5.5 also has `adaptive_thinking`: it decides at each step whether to think, so on a step without thinking
  the element shows while Claude writes;
- the session file's `status` is `busy`, `waiting` or `idle`, nothing finer;
- the transcript keeps a thinking block's signature, not its text, unless `showThinkingSummaries` is on.

## Chips that Claude Code also shows

The user asked what a chip is worth when the native one under the card cannot be hidden. I proposed keeping on the
card only what is not already on screen. On 2026-10-18 the user had the mode chip and the drafts chip removed. On
2026-10-19 (MIX-12) the rest went to the settings page: the user keeps or drops each chip there, and nothing more is
built for it.

| Chip | Native under the card | Decision |
|---|---|---|
| mode | yes, and cannot be hidden | removed from the card on 2026-10-18 |
| `⇄ rc` | yes, from 60 columns up, and cannot be hidden | kept at the user's word on 2026-10-19; the card leaves room so the native pill sits beside it (see Drawing) |
| `◎ cloud`, `↯ fast`, `⚠ no transcript`, `● working` | yes, and cannot be hidden | the user's call in the settings page; my proposal stays: drop them |
| `✎ drafts` | `N feedback drafts` | removed from the card on 2026-10-18. The native one hides only with `feedbackDrafts: "off"`, which stops Claude drafting feedback |
| `PR #N`, `-- INSERT --` | yes, hideable | real move: `prStatusFooterEnabled: false` (~/.claude.json) and `statusLine.hideVimModeIndicator: true` |
| `↑ update`, `◷ cache`, `⧈ sandbox` | absent, or only for a few seconds | keep |

Done on 2026-10-19: adding elements at will, each with its own preview, is the settings page. Closed the same day: the
language question. TS would have bought a typed payload, a web preview and npm; the web preview now exists in
Python, and Python starts in 6.4 ms against Node's 26.5 ms (15-run medians, Node v24).

## Facts from Claude Code 2.1.303's code (2026-10-20)

- **The runner:** `executeStatusLineCommand` (`Pbr`) hands the command to the hook runner `$H`, always in shell
  form; the `statusLine` schema has only `type`, `command`, `padding`, `refreshInterval`, `hideVimModeIndicator`.
  `/bin/sh` on Linux and macOS; on Windows Git Bash when `mQ()` finds it (`CLAUDE_CODE_GIT_BASH_PATH`, then
  `C:\Program Files\Git\bin\bash.exe`, `C:\Program Files (x86)\Git\bin\bash.exe`, then next to `git` on `PATH`),
  else PowerShell.
- **Its environment:** `os()`, that is `process.env` plus the settings' `env`, as it is unless
  `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` (or GitHub Actions) drops credential-like names; then `COLUMNS` and `LINES` from
  Claude Code's stdout at every run, and `CLAUDE_PROJECT_DIR`.
- **When it does not run:** `disableAllHooks` in managed settings; under `allowManagedHooksOnly` only the managed
  `statusLine`; an untrusted workspace; cloud sessions.
- **Settings layer** from low to high: user, project, local, flag, policy (`gn()`, `Ps`).
- **A plugin's settings** apply only `agent` and `subagentStatusLine` (`yho`), never `statusLine`.
- **Folders:** `CLAUDE_CONFIG_DIR` or `~/.claude`, `sessions` inside it (`Xte`); versions in
  `(XDG_DATA_HOME or ~/.local/share)/claude/versions` on every system (`dje`, `Fin`); `~/.local/bin` is Claude Code's
  own bin folder (`H5`).
- **`!` (bash mode):** runs through the Bash or PowerShell tool with `dangerouslyDisableSandbox: true`; its output
  enters the conversation as `<bash-stdout>`, and Claude answers after it unless `respondToBashCommands` is `false`
  (default `true`).
- **The idle hint** reads `CLAUDE_CODE_IDLE_TOKEN_THRESHOLD` and `CLAUDE_CODE_IDLE_THRESHOLD_MINUTES` from
  `process.env` each time it decides, so a huge token threshold set where `claude` starts turns it off.
- **Mods** can draw only AskUserQuestion, UserMessage, AssistantMessage, ToolUse, ToolResult, ToolGroup,
  ToolProgress, CommandOutput, Spinner, TurnDuration, InfoNotice, SessionMode, PromptHint, AbovePrompt and Pane:
  not the status line, not the footer's notifications.

## Learned on real machines (CI, 2026-10-20)

`check_install.py` and the unit tests run at every push on Ubuntu (Python 3.8, latest), macOS (latest) and Windows
(3.8, latest); all green from `bdbebea` on. What the runs taught:
- **Windows:** Git Bash's `env -i` hands `SYSTEMROOT` and `USERPROFILE` on to a native `python.exe`, and the card
  draws through it; through PowerShell (`-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command`), `& python`
  gets the payload on stdin. `session-bar.cmd` and the sh launcher in Git Bash both open the page. A folder that is a
  process's working folder cannot be removed, so a check waits for the page's server to stop.
- **macOS:** `/var` is `/private/var` and `getcwd()` returns the latter, so paths are compared by their real path;
  `http.server`'s `server_bind` calls `socket.getfqdn()`, a reverse lookup that took over 10 s there, so the server
  binds without it; Python's `webbrowser` runs `/usr/bin/osascript` by its absolute path, so a browser is always
  found, and it can be slow, so the launcher waits for it 5 s at most; under `env -i` the system adds
  `__CF_USER_TEXT_ENCODING` (the text encoding, no key).
- **Not covered by CI:** Claude Code drawing the card itself, a real browser opening on macOS under `env -i`.

## Facts from Claude Code 2.1.302's code

All of these were read in the binary's strings (`strings -n 8 ~/.local/share/claude/versions/2.1.302`). Use python3,
not grep: the local grep is ugrep and refuses wide patterns.

### The payload

- **Where it is built:** in `function btr(...)`.
- **Fields:** session_id, transcript_path, cwd, session_name, model, workspace (current_dir, project_dir, added_dirs,
  git_worktree, repo), version, output_style, cost, context_window, exceeds_200k_tokens, prompt_cache,
  fast_mode, effort, thinking, rate_limits, vim, agent, remote, pr, worktree.
- **The permission mode is NOT in it.** `btr` calls `ou(e,ke)` without the mode argument.
  - The card used to read the last `permission-mode` entry in the transcript's final 256 KB. Claude Code writes
    that entry only at its next metadata re-append, so the chip trailed shift+tab. The chip and its reader are
    gone since 2026-10-18.
- **`remote` is not Remote Control.** It is set when this CLI is a client of a cloud, ssh or direct session.

### Remote Control

- **The signal a script can read:** `bridgeSessionId` in `~/.claude/sessions/<pid>.json`. It is set while
  Remote Control is on and set to null when it goes off. The record is matched by sessionId and a live pid.
- **The link:** `https://claude.ai/code/<bridgeSessionId>`.
- **What a script cannot see:** connecting, reconnecting and failed. These states live only in memory.

### When the command reruns

- **Triggers:**
  - a change to the tokens, permission mode, vim mode, model, fast mode, effort, thinking or PR status;
  - a new assistant message;
  - `refreshInterval`;
  - one timer at the earliest rate-limit reset or prompt-cache expiry, plus 1 s.
- **Debounce:** 300 ms.
- **A slow command loses.** Each new run aborts the one still running, and the aborted result is thrown away. This
  is why `npx ccstatusline@latest`, at 414–667 ms, lagged.

### Drawing

- **Rows:** each row is `Text dimColor wrap="truncate"`. There is no row limit.
- **Placement:** the status line sits above the footer's hint row. The right column of the footer holds the
  notifications and `/rc`.
- **Width:** the footer row keeps 2 columns of padding on each side (`oQe=2`), so the card is the terminal's
  width less 4 (`card_width`). The notifications share that row, which wraps (`flexWrap`), so they go under a
  full-width card. Until 2026-10-18 the card left 40 columns free past 60 % context, a rule copied from
  ccstatusline.
- **Beside `/rc`:** the footer row is `flexWrap: "wrap"`, `alignItems: "flex-start"`, `columnGap: 1`; its right
  column (`marginLeft: "auto"`) holds the notifications, then the pill. While Remote Control is on, the card is 4
  columns narrower (`RC_PILL`, from 60 columns up, where Claude Code shows the pill: `Tbn=60`), so the pill sits
  beside the card's top edge (2.1.303). A notification, or a longer label (`/rc active` for the first 5 sightings,
  counted in `seenNotifications`; reconnecting states), makes that column wider, and it wraps under the card again
  until it goes.
- **Beside the notices:** two notifications in that column can be foreseen, so the card makes room for them too: 39
  columns (`NOTICE`, 38, and the gap), with `/rc` under them, as long as the card keeps 80 columns. Read in 2.1.303:
  - `✔ Update installed · Restart to update`: the auto-updater succeeded, until a restart. The card takes a newer
    version in `~/.local/share/claude/versions` than the payload's (`update_ready`), as for the update chip; only the
    session that installed it shows the notice, so another open one makes room for nothing;
  - `new task? /clear to save N tokens`: idle for `CLAUDE_CODE_IDLE_THRESHOLD_MINUTES` (75) since the last turn,
    with `CLAUDE_CODE_IDLE_TOKEN_THRESHOLD` (100k) tokens or more, until the next activity. The card takes the session
    file's `status: idle` and `statusUpdatedAt`, the context's tokens and those two variables from its own
    environment (`idle_hint`). Since 2026-10-19 the card never reads another process's environment
    (`/proc/<pid>/environ` held every key Claude Code was started with).
- **What a configured status line hides:** `? for shortcuts`, `esc to interrupt` and the ctrl+t hints.

### Hiding native items

- **Can be hidden:**
  - `statusLine.hideVimModeIndicator`;
  - `prStatusFooterEnabled: false`;
  - `feedbackDrafts: "off"`;
  - `spinnerTipsEnabled: false`;
  - `leftArrowOpensAgents: false`, which also changes the arrow key.
- **Cannot be hidden:**
  - the mode pill;
  - `/rc`, except below 60 columns or with Remote Control off;
  - the notification queue;
  - the background-task pill.

### Not computable

- **"% until auto-compact":** the threshold uses the auto-compact window (`Ob`: settings, env, server clientdata,
  the model table), not `context_window_size`. Formula (`qqe`): warn at threshold − 20k, where threshold = effective
  window − 13k.

## Backups

- `~/.claude/settings.json.bak-2026-10-18-before-session-bar`: before the Session Bar replaced ccstatusline.
- `~/.claude/settings.json.bak-2026-10-18-before-chips`: before `refreshInterval`.
- `~/.claude/settings.json.bak-2026-10-18-before-move`: before `statusLine.command` pointed at `~/session-bar`.
- `~/.claude/settings.json.bak-2026-10-18-before-rename`: before the path became `~/claude-skin`.
- `~/.claude/settings.json.bak-2026-10-18-before-theme`: before `theme` became `custom:workflows-quiet`.
- `~/.claude/settings.json.bak-2026-10-18-before-theme-card`: before it became `custom:workflows-card`.
- `~/.claude/settings.json.bak-2026-10-18-before-refresh-1s`: before `refreshInterval` went from 5 to 1.
- `~/.claude/settings.json.bak-2026-10-19-before-theme-revert`: before `theme` went back to `dark`.
- `~/.claude/settings.json.bak-2026-10-19-before-prompt-cache-ttl`: before `promptCacheTtl` became `1h`.
- `~/.claude/statusline/`: the card as it was before this folder, plus its `.bak-2026-10-18-before-chips` copies.
