# Claude Code Session Bar

Customizing how Claude Code looks, through the Session Bar status line card (`session-bar.py`) only. Read NOTES.md
first: it holds the state, the decisions and what Claude Code's code allows.

- **Language:** reply in Romanian; code, comments and commits are in English.
- **No change before approval:** show a preview first, using `preview/` or a new throwaway script, and wait for the
  user's choice.
- **Tests first:**
  - Write the test in `test_session_bar.py`, watch it fail, then write the code.
  - Mutate the new code once and check the test catches it.
  - Every row must stay exactly the card's width at every width from 30 to 240.
- **Speed:** keep a run far under 300 ms (it is ~20 ms now). No subprocesses, no network, only small file reads.
  Claude Code aborts a run that a newer trigger overtakes.
- **Glyphs:** every glyph must be one cell wide. Never use emoji.
- **Settings:** before changing `~/.claude/settings.json`, copy it to `settings.json.bak-<date>-<reason>`, then diff
  to show that only the intended key changed.
- **Facts about Claude Code:** take them from its binary, not from memory. Mark anything unread as a hypothesis.
