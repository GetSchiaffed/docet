# docet

A study system for Claude Code. It maps what the learner already knows (an
entry test that descends from the topic to its foundations), builds a course
on the gaps, and adjusts it after every answer.

Two surfaces, never mixed: **reading happens in Obsidian** (`vault/`),
**answering happens in the terminal**.

Infrastructure in English; teaching in the learner's language (the model
follows it, the engine's pages use each topic's `lang`).

## Layout

```
.claude/
  skills/docet-teach/  pedagogy and protocol: change HOW it teaches here
  skills/docet-figure/ when a figure is worth it, and who draws it
  agents/              docet-diagram, docet-svg (draw, render, look), docet-research
  commands/docet/      /docet:start, /docet:next, /docet:stop
bin/docet.py           the engine: state, commitment, grading, adaptation, views
bin/render.sh          .mmd or .svg → PNG with the system Chrome/Chromium
tests/                 engine tests (unittest, temporary vault)
vault/                 the Obsidian vault — personal, gitignored
  .obsidian/           config, style (snippets/docet.css), plugins: versioned
  .docet/              JSON state, answer log, pending questions
vendor/mermaid.min.js  vendored mermaid, to render offline
```

## Commands

```bash
python3 -m unittest discover tests      # engine tests (system python3 is 3.9, the minimum)
uv run --no-project --python 3.13 python -m unittest discover tests   # on a recent Python
python3 bin/docet.py -h                 # engine commands
python3 bin/docet.py status             # all topics
DOCET_VAULT=/other/vault python3 bin/docet.py …   # vault elsewhere
```

## Conventions

- **Pedagogy in the prompts, rules in the engine.** How to explain, how to
  build distractors, when to ask first: `skills/docet-teach/SKILL.md`. Whatever must
  be deterministic — grading, mastery, thresholds, pace, when to reinforce —
  lives in `bin/docet.py`, thresholds at the top.
- **Standard library only** in the engine. A study tool that breaks on a
  dependency stops being used.
- **Engine-written text goes through `STRINGS`.** A language is a dict;
  missing keys fall back to English.
- **Claude writes the lesson into the file**, piece by piece, before asking.
  The terminal gets a status line and the answer window.
- **The key is committed as base64** before the question, because the command
  is on screen. The engine checks it matches an option and never says which.
- **Figures are text in the vault**: mermaid source in the lesson, or an `.svg`
  in `<slug>/fig/`. The PNG from `render.sh` is only proof someone looked.
- Math in LaTeX in files; short plain text in terminal labels.
- **Nothing personal in the repo.** Before a commit, `git status` shows nothing
  under `vault/` except `.obsidian/`.

## Gotchas

- **The terminal shows every command.** Whatever must stay hidden until the
  answer can't appear in plain text, not even in an `echo`.
- **`AskUserQuestion` labels are the ones `ask` returns**: the engine shuffles
  and letters the options. The grade is decided on the option's text, ignoring its letter.
- **Numeric and recall questions have no options**: the learner types in chat.
  Recall has no key; the model's verdict decides.
- **Headless Chrome doesn't exit after `--screenshot`**: `render.sh` waits for
  the PNG to stop growing and kills it. No browser → exit 3, figure marked
  unverified.
- **`test-end` counts only answers after the previous attempt**: a retaken
  chapter test doesn't mix attempts.
- **`next` waits on unfinished synthesis pages**: any `%% ✎` left blocks it.
- **The entry test depends on how the learner started.** `--familiarity never|heard`
  ("teach me X"): the targets are never probed, only the foundations from the
  bottom, at most `ENTRY_QUICK`, or none with `--entry skip`. Otherwise from the
  top, at most `ENTRY_MAX`. What stays unchecked comes back as `CHECK FIRST`
  before the lesson that rests on it.
- **The profile is cross-topic** (`.docet/profile.json`, `vault/_profile.md`):
  a node id solid in one topic is carried as assumed into the next, so reuse ids.
