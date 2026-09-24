---
description: Pick up where you left off — review, lesson, chapter test, final test or analysis
argument-hint: "[topic]"
---

# Resume

Use the **`docet-teach`** skill. You don't need to know where we are: the engine does.

1. If a topic is given (`$ARGUMENTS`), activate it: `python3 bin/docet.py use <slug>`. If none is active, run `python3 bin/docet.py status` and ask with a Choice which one to resume, or suggest `/docet:start`.
2. `python3 bin/docet.py next`, and do exactly what it says:

   | `next` says | do | file |
   |---|---|---|
   | `OPEN` | questions committed in a session that was interrupted: ask them again (same id, already in the file), grade, then go on | the file where they are |
   | `LOST` | questions committed but never written (the session broke in between): `drop <ids>`, never guess their text | — |
   | `REVIEW` | one `review` question per node, new examples | `review-<date>.md` |
   | `ENTRY …` | continue the entry test; `ENTRY COMPLETE` lists what to teach, `NOT CHECKED` what stays out of the course | `entry-test.md` |
   | `LESSON` / `REINFORCEMENT` | `lesson <id> start --file …` (if `in progress`: read the end of its file first, and continue after the last `[!abstract]` pause — never restart it), the per-node loop, `lesson <id> done`, recalibrate | `NN-<title>.md` |
   | `CHAPTER TEST` | cumulative test, then `test-end <b>` | `chapter-test-<b>.md` |
   | `SYNTHESIS` | `synth <scope>`, then replace every ✎ (skill: Synthesis) | `synthesis-<b>.md` / `synthesis.md` |
   | `PRACTICE` | numeric exercises, `kind: "practice"`, until the engine stops asking | `practice-<b>.md` |
   | `FINAL TEST` | final test, then `test-end final` | `final-test.md` |
   | `ANALYSIS` | a retry on every unresolved node: slip or gap | `analysis.md` |
   | `DONE` | say so, and suggest reviews or a new topic | — |

   `CHECK FIRST`, `PREREQUISITE` and `PACE` lines come with another instruction. `CHECK FIRST`: a prerequisite never checked; one easy `probe` question on it at the top of the lesson file, before explaining; if it fails, teach it first (add it to the course with `plan`). `PREREQUISITE`: a retry on each weak prerequisite before the lesson. `PACE`: adjust the difficulty as the skill says.
3. In the terminal, before starting, **one line** in the learner's language: what's next and what it rests on among what's already established. Explanations belong in the lesson file.
4. At the end of a unit (a lesson, a test) call `next` again and ask with a Choice whether to continue or stop. To close: `/docet:stop`.
