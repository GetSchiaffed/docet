---
description: Start learning something new — goal, where you start, a short entry test (or none), course
argument-hint: <what you want to learn>
---

# New topic: $ARGUMENTS

Use the **`docet-teach`** skill and follow it to the letter: the question protocol, the two-surfaces rule and the language rule apply from the start. Talk to the learner in the language they wrote `$ARGUMENTS` in.

0. **Who is learning.** `python3 bin/docet.py profile`: background, where they are strong, concepts they already hold in other topics. What it already says is never asked again.
1. **Goal.** A Choice to find out what they really want from `$ARGUMENTS`: an exam, work, curiosity, how deep. Push until it's concrete.
2. **Where they start.** Read how they asked. "Teach me X", "explain X", "I want to learn X" means they don't know X: familiarity `never` (or `heard` if they say they've met it), no question needed. "Help me get better at X", "review X" means `some`. Only if it's unclear, a Choice: never heard of it / heard of it / use it sometimes / know it well → `never` / `heard` / `some` / `solid`.
   - If the profile has no background: one open question, studies or work and what they know well in any field (a job, a sport, music, philosophy). Save it: `python3 bin/docet.py profile --background "…" --strong "…"`. It sets the tone of every lesson and is a source of bridges.
   - **Learning from scratch** (`never`, `heard`): a Choice between a quick check of the basics (a few easy questions, `quick`) and starting the first lesson right away (`skip`). Nothing is lost by skipping: every prerequisite is checked with one easy question right before the lesson that needs it.
3. **Create the topic** with a short, readable slug and the learner's language:
   ```bash
   python3 bin/docet.py new <slug> --title "<title>" --goal "<concrete goal>" --lang <xx> --familiarity <f> [--entry quick|skip]
   ```
   Then one line in the terminal: open the `vault/` folder in Obsidian, subfolder `<slug>/`.
4. **Graph.** Scope the field with `docet-research`: targets, prerequisites down to the foundations, typical errors per concept. Then `plan` with `nodes` only (step 1 of the course in the skill). Reuse the ids the profile lists as already held, so they carry over. Mark `"assumed": true` only on foundations the declared background makes certain (school algebra for an engineer).
5. **Entry test** in `vault/<slug>/entry-test.md`, driven by `python3 bin/docet.py next` until it says `ENTRY COMPLETE` (skipped: it says so at once). If the learner says "skip" halfway, `python3 bin/docet.py entry skip`. Close the file with the summary.
6. **Course.** Blocks and lessons with `plan` on what `ENTRY COMPLETE` lists; leave `NOT CHECKED` concepts out unless the goal needs them. Pitch the first lesson at the declared level. Then the checkpoint: one line ("course in Obsidian → `_course`") and a Choice to go ahead.
7. With the go-ahead, **first lesson** (as in `/docet:next`), or stop there if the learner prefers.

If a topic on the same subject already exists (`python3 bin/docet.py status`), ask whether to resume it with `/docet:next` instead of starting over.
