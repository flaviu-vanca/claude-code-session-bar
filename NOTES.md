# Claude Skin: notes

This project customizes how Claude Code looks. It started inside the codewiki sessions on 2026-10-18 and moved here
the same day as `~/session-bar`. It was renamed `~/claude-skin` once the scope grew beyond the status line.

| Part | State |
|---|---|
| **Session Bar** (`session-bar.py`), the status line card | live |
| **The agents window**, the `/workflows` panel: Phases, agents, the key hints | theme `custom:workflows-card` live; agent meters: not doable without a mod, closed |

The Session Bar is a rounded card with segmented heat-coloured meters and the footer's states on its bottom edge. It
is Python 3 stdlib only, runs with `python3 -I -S`, and one run takes about 20 ms.

## Run

| What | Command |
|---|---|
| The card, on a payload | `python3 -I -S session-bar.py [--meter N] < payload.json` |
| The settings, with the card drawn live | `python3 configure.py`, in a terminal of its own (`!` is not interactive) |
| Tests (prints `ok`) | `python3 -I test_session_bar.py` |
| Preview of the chips with sample states | `python3 -I preview/chips.py` |

Live use: `statusLine.command` in `~/.claude/settings.json` points at `session-bar.py` in this folder, with
`"padding": 0` and `"refreshInterval": 5`.

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

`configure.py` edits the file:
- left and right pick a place, up and down an element;
- space turns it on or off, `[` `]` reorder;
- `a` adds a row, `x` deletes the row under the cursor;
- `+` `-` set the bars, `p` cycles the palettes;
- `s` saves (written whole, through a temporary file), `q` quits.

The card picks up a save on its next run. `statusLine.refreshInterval` is 1 s since 2026-10-18, so the card also
follows a window resize within a second: Claude Code reruns the command on its triggers and that timer, never on a
resize.

No element costs tokens: the status line's output never reaches the model.

| Place | Elements (the default ones in bold) |
|---|---|
| Top edge, left and right; any row | **model**, **effort**, thinking, style, agent, name (`/rename`), version, **cost**, **time**, api (API time), lines (+/-), clock, **repo**, **cwd**, **session**, worktree, dirs (`/add-dir`), **mem**, **disks**, load, battery |
| Meters, on any row | **ctx**, **5h**, **week**, spend (gateway only), hits (prompt cache hit ratio, green is good; read as a fraction ≤ 1, unverified on a real payload) |
| Bottom edge (chips) | **cloud**, **rc**, mode, **no_transcript**, **update**, **cache**, big (context past 200k), drafts, **sandbox**, **working**, **pr**, **fast**, **vim** |

By default the top left holds model and effort, the top right cost and time, row 1 ctx, 5h and week, and row 2
repo, cwd, session, mem and disks. `repo` shows only inside a repository; `cwd` always shows.

## Open decision (2026-10-18)

The user asked what a chip is worth when the native one under the card cannot be hidden. I proposed keeping on the
card only what is not already on screen. On 2026-10-18 the user had the mode chip and the drafts chip removed; the
other rows are still unanswered.

| Chip | Native under the card | Proposal |
|---|---|---|
| mode | yes, and cannot be hidden | removed from the card on 2026-10-18 |
| `⇄ rc`, `◎ cloud`, `↯ fast`, `⚠ no transcript`, `● working` | yes, and cannot be hidden | remove from the card |
| `✎ drafts` | `N feedback drafts` | removed from the card on 2026-10-18. The native one hides only with `feedbackDrafts: "off"`, which stops Claude drafting feedback |
| `PR #N`, `-- INSERT --` | yes, hideable | real move: `prStatusFooterEnabled: false` (~/.claude.json) and `statusLine.hideVimModeIndicator: true` |
| `↑ update`, `◷ cache`, `⧈ sandbox` | absent, or only for a few seconds | keep |

Also deferred: a way to add elements at will, each with its own preview. The language question is open: Python
starts in 6.4 ms against Node's 26.5 ms (15-run medians, Node v24). TS would buy a typed payload, a web preview and
npm.

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

### Custom themes

- Each theme is `~/.claude/themes/<slug>.json`: `{"name", "base", "overrides"}`.
- One is turned on with `"theme": "custom:<slug>"`.
- There are 72 colour tokens.
- Tried on 2026-10-18 as `~/.claude/themes/session-bar.json`. The user saw no difference: it was never turned on and
  changed only tokens near their defaults. It is still there and not active, beside `workflows-quiet.json` (theme B).
- **Live since 2026-10-18:** `custom:workflows-card` (theme C1), in the Session Bar's colours: `text` rgb(92,92,92),
  `permission` rgb(217,119,87), `success` rgb(63,185,80), `error` rgb(248,81,73), `subtle` rgb(124,128,146),
  `inactive` rgb(176,180,196).
- **How tokens reach the screen:**
  - `dimColor` is not SGR faint at truecolor: the themed Text swaps the colour for the token `inactive`.
  - Text with no colour gets no SGR at all: it stays the terminal's foreground, and no theme reaches it.
  - Bold and italic are fixed SGR codes.
- **Tokens are global:**
  - `text` also draws the user's own prompts in the transcript (`MGt`), on `userMessageBackground` (55,55,55), and
    the `●` before Claude's replies. With C1's rgb(92,92,92) a prompt is at 1.8:1; the user chose it knowing that.
  - `permission` also colours inline code in replies and the frame of dialogs.
  - `inactive` colours every dim text in the app.
- **Loading:**
  - `BZt` keeps an override only for a key the base has and a value `z5` accepts: `rgb(r,g,b)`, `#hex`,
    `ansi256(n)` or `ansi:<name>`.
  - The themes folder is watched live, but only if it existed when the session started.
  - The `theme` setting is read once, at start (hypothesis); `/theme` switches live.

## Backups

- `~/.claude/settings.json.bak-2026-10-18-before-session-bar`: before the Session Bar replaced ccstatusline.
- `~/.claude/settings.json.bak-2026-10-18-before-chips`: before `refreshInterval`.
- `~/.claude/settings.json.bak-2026-10-18-before-move`: before `statusLine.command` pointed at `~/session-bar`.
- `~/.claude/settings.json.bak-2026-10-18-before-rename`: before the path became `~/claude-skin`.
- `~/.claude/settings.json.bak-2026-10-18-before-theme`: before `theme` became `custom:workflows-quiet`.
- `~/.claude/settings.json.bak-2026-10-18-before-theme-card`: before it became `custom:workflows-card`.
- `~/.claude/settings.json.bak-2026-10-18-before-refresh-1s`: before `refreshInterval` went from 5 to 1.
- `~/.claude/statusline/`: the card as it was before this folder, plus its `.bak-2026-10-18-before-chips` copies.

## The agents window (the `/workflows` panel)

Reference screenshot: `~/Pictures/Screenshots/footer.png`. The panel is `stt` (`Ca("workflow-detail-dialog")`); `hwt`
next to it is the save dialog. Read in 2.1.302 on 2026-10-18 and checked against the screenshot's pixels.

| What shows | Token |
|---|---|
| frame, corners, box titles, the rule above the title | `text` |
| title (bold), selected phase, `❯`, blocked `✘` | `permission` |
| done `✔` | `success` |
| failed `✘` | `error` |
| phase numbers, unselected counts, running `●`, queued `◌`, skipped `✘` | `subtle` (dark: 80,80,80, 1.8:1) |
| description, counter, models, a not-started phase, hints (also italic) | `inactive`, through `dimColor` |
| a running phase's title, finished agents' labels | none: the terminal's foreground |

### What can and cannot change

- **A theme recolours it, nothing more.**
- **A patch is ruled out.** To test whether an edit to the JS in the binary would run, the experiment needs a copy of
  the binary. The auto-mode classifier blocked even that copy as self-modification, and every update would undo a
  patch anyway.
- **What mods can draw:** `RenderComponent` lists AskUserQuestion, UserMessage, AssistantMessage, ToolUse,
  ToolResult, ToolGroup, ToolProgress, CommandOutput, Spinner, TurnDuration, InfoNotice, SessionMode, PromptHint,
  AbovePrompt and Pane.
  - Neither the panel nor the workflow row under the prompt is on that list, so no mod can redraw them.
  - The nearest seats: `AbovePrompt`, a band of several rows right above the input, and `PromptHint`, the dim hint
    line under it.
- **Claude Code's own bar:** the workflow row under the prompt already carries a `▰▱` bar (done/total, 20 cells). It
  takes no theme token: the fill is the terminal's foreground, the rest dim.
- **The status line during the panel:**
  - When `/workflows` is opened while idle, or from the pill, the prompt is unmounted, the status line with it, and
    its command stops running.
  - It stays on screen only when `/workflows` is opened mid-turn.

### Agent meters: the data, and an open decision

The user wants the agents' meters (one segment per agent, a context meter per running agent) in the footer where
the runs show, not in the Session Bar.
- **Tried and removed:** on 2026-10-18 they were built as Session Bar rows, then removed at the user's word.
  Its preview and the others of that day were deleted too.
- **Not mods, zero tokens, not built:**
  - a separate monitor in a terminal split that draws the panel's frame from the run's files;
  - `subagentStatusLine` (settings), whose script draws each Agent-tool subagent's row in the footer task list.
    It gets `tokenCount`, `contextWindowSize` and the label, and its output replaces the row after the status
    circle. Workflow agents are not covered.
- **Closed on 2026-10-18:** the user wants no mods, because they burned through tokens. Do not propose them
  again. Without a mod there are no meters, so the theme is all the agents window gets.

What a reader can rely on (`P` = transcript_path without `.jsonl`; the status line payload has no workflow fields):
- **Files:**
  - Each run: `P/subagents/workflows/<runId>/journal.jsonl`, `agent-<id>.meta.json` (its mtime is the agent's start)
    and `agent-<id>.jsonl`.
  - The end snapshot: `P/workflows/<runId>.json`.
  - The script copy: `P/workflows/scripts/<slug>-<runId>.js`, which holds `meta.phases`; inline and named runs
    only.
- **Journal lines:**
  - `started{key,agentId,label,phase}` comes at spawn, never while queued.
  - `result{key,...}` means done; `failed{key,agentId}`, with agentId `""` when the agent never started.
  - A retry appends `started` again under the same key. There are no timestamps and no end event.
- **Live:**
  - The journal was written after the process started (`startedAt` in `~/.claude/sessions/<pid>.json`).
  - No snapshot is newer than it: the snapshot comes about 20 ms after the last line, and pause and stop count as
    killed.
  - Something was written recently: a crash leaves no snapshot.
- **Tokens:** the last assistant `usage` (input + cache creation + cache read + output) in a 256 KB tail of the
  agent's jsonl. The context window is known only for the session's own model.
