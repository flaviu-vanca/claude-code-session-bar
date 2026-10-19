# Claude Skin: notes

This project customizes how Claude Code looks. It started inside the codewiki sessions on 2026-10-18 and moved here
the same day as `~/session-bar`, then was renamed `~/claude-skin`. On 2026-10-19 the user narrowed it to the Session
Bar alone: the agents window's theme, its notes and the idea of a live agents dashboard were removed.

The Session Bar is a rounded card with segmented heat-coloured meters and the footer's states on its bottom edge. It
is Python 3 stdlib only, runs with `python3 -I -S`, and one run takes about 20 ms.

## Run

| What | Command |
|---|---|
| The card, on a payload | `python3 -I -S session-bar.py [--meter N] < payload.json` |
| The settings in the browser, drag and drop | `python3 configure.py [port]`, in a terminal of its own: it serves the page on 127.0.0.1, opens it, and stops a few seconds after the page closes |
| Tests (prints `ok`) | `python3 -I test_session_bar.py` |
| Preview of the chips with sample states | `python3 -I preview/chips.py` |

Live use: `statusLine.command` in `~/.claude/settings.json` points at `session-bar.py` in this folder, with
`"padding": 0` and `"refreshInterval": 1`.

## The card

`session-bar.json` beside the script holds the layout:
- `top_left` and `top_right`: text elements;
- `rows`: any number of rows, each holding meters and text;
- `edge`: the chips;
- `meter`: the bars in a meter, 3–30;
- `palette`: default, nord, dracula, gruvbox, tokyo or mono.

`SESSION_BAR_CONFIG` overrides the path. Without the file the card uses `DEFAULT`. Unknown elements are skipped.
The first settings' `meters` and `info` keys are read as two rows.

When a row is too long, its meters shrink to half their length, then it wraps onto more lines; a dim `·` sits
between elements. The edges still drop elements from the end of their lists.

`configure.py` edits the file through a page in the browser, `configure-web.html`, whose card and tiles are drawn by
the card itself:
- drag elements between the places, or click a place and then an element; `×` or `Del` removes one;
- `Alt` `←` `→` move an element within its place; rows are added, moved and deleted on the page;
- the palettes and the bars have their own controls; sliders move the sample session's ctx, 5h and week;
- `Ctrl` `S` saves (written whole, through a temporary file), `Ctrl` `Z` undoes.

The server answers only this machine's page (Host and Origin) and runs every setting through `load_config` before it
renders or saves. On 2026-10-19 it replaced the terminal configurator, which is in git at `899d14d` (MIX-12).

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
| Top edge, left and right; any row | **model**, **effort**, thinking, style, agent, name (`/rename`), version, **cost**, **time**, api (API time), lines (+/-), clock, **repo**, **cwd**, **session**, worktree, dirs (`/add-dir`), **mem**, **disks**, load, battery |
| Meters, on any row | **ctx**, **5h**, **week**, spend (gateway only), hits (prompt cache hit ratio, green is good; read as a fraction ≤ 1, unverified on a real payload) |
| Bottom edge (chips) | **cloud**, **rc**, mode, **no_transcript**, **update**, **cache**, big (context past 200k), drafts, **sandbox**, **working**, **pr**, **fast**, **vim** |

By default the top left holds model and effort, the top right cost and time, row 1 ctx, 5h and week, and row 2
repo, cwd, session, mem and disks. `repo` shows only inside a repository; `cwd` always shows.

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
- `~/.claude/statusline/`: the card as it was before this folder, plus its `.bak-2026-10-18-before-chips` copies.
