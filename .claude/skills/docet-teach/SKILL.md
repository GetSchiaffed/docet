---
name: docet-teach
description: "How docet teaches: a course built as a graph of concepts, each one resting on what the learner already holds, checked by questions the engine grades. Use it every time you explain or teach anything, from a one-line answer to a full course."
---

# Teaching with docet

## What we are building

A fact survives in memory when something holds it up. Isolated facts decay; a fact that follows from other facts the learner already trusts gets rebuilt every time one of them is used. So the course is a **graph**: concepts are nodes, "this follows from that" is an edge, and teaching means adding nodes only where edges can reach them.

Two consequences shape every lesson.

**Start from bedrock.** The bottom of the graph is made of facts the learner can accept as they are, with no "usually" and no "except when": a real definition, a statement about *all* or *none* of something. Such facts are cheap to accept because nothing deeper will overturn them. If it only holds under conditions, it sits higher up the graph: keep digging. Before building on a bedrock fact, check it really is obvious *to this learner*.

**Every step earns its place.** A new idea should arrive as the answer to a problem the learner can already see. Show the problem first, then the move that solves it, so the learner feels they could have found it. An idea that appears from nowhere is memorised, not understood, and it is the first thing to go.

## At the edge

Teach one step beyond what holds, never two. The entry test finds that edge; the engine keeps it: before a lesson it checks that the prerequisites still hold, and it watches the pace.

**Aim for about 85% right answers.** Below that the learner is losing heart and not learning from the failures; above it, with everything "sure", they are coasting. The number comes from a result on machine learning and simple perceptual tasks (Wilson et al., 2019), not from studies of learning concepts: treat it as a sensible target, not a proven optimum. The engine prints `PACE — …` when the last answers fall outside that band. Follow it: smaller steps, an easy win, telling instead of asking when it's too hard; harder examples and merged steps when it's too easy. It is a heuristic, not a law: a run of failures on a misconception being dismantled is expected.

Curiosity comes before explanation: **open each block with the puzzle it solves** — the question that looked right and wasn't, the result that seemed impossible. The entry test usually hands you one.

## Ask first or tell first

- **Ask first** when the learner can reason their way there: pose the problem, let them try, then build on the attempt. It costs more and sticks better. A question with a definite answer goes through `ask` and `grade` like every other one.
- **Tell first** when the idea is out of reach of reasoning from what they hold, or when they are tired: walk the path yourself, every step still earned.

**Try before being told.** A wrong guess made just before the explanation makes the explanation land better than reading it cold. Two sizes:

- **A guess** (any node with a surprising answer): one question with `kind: "pretest"` before explaining. It is logged, never counted: failing it costs the learner nothing.
- **A real attempt** (target nodes): pose the problem the concept exists to solve, one the learner could attack by combining what they already hold, and let them work at it before any teaching. Then teach *from their attempt*: what they tried, where it stalled, what the concept adds. An attempt with nothing to build on is just frustration: skip it when the prerequisites are thin.

**Now and then, let them explain.** After establishing a node, a `recall` question — "in your own words, why does X hold?" — makes the learner connect it to what they know. Once or twice per lesson, not after every node.

**Build bridges from what they are strong in.** A concept lands faster when it hangs from something the learner already holds firmly, even in another field: chemical equilibrium for someone who thinks in philosophy is a balance of opposing forces that stops looking like change. Use such a bridge when it carries the real structure of the concept, say where it stops holding, then cross to the proper formulation.

**Leave out the decoration.** An anecdote, an analogy or a figure that doesn't carry the concept takes attention away from it. Every example is there because it shows something.

## Language

Teach in the learner's language, detected from how they write. Files, questions, options, labels, callouts and status lines are all in that language. Give it to the engine when creating a topic (`--lang it`) so its pages follow. Commands, JSON keys and values like `check` or `sure` are protocol and stay as documented.

---

## Two surfaces: Obsidian to read, terminal to answer

- **Everything to read goes into the lesson file**, written by you with Write/Edit: explanations, questions with full options, corrections. LaTeX, mermaid, SVG figures and callouts render there.
- **The terminal carries only** a one-line status ("node 2 in Obsidian → Q7"), the answer window, and ✓/✗. A paragraph of explanation in chat belongs in the file.
- **Write the question before asking it**: when the window opens, the question is already on the page.
- **Append only.** Every lesson file ends with `%% ↓ %%` (an invisible comment). Replace it with the new block followed by `%% ↓ %%` again. Never rewrite a lesson.
- **The page must stand alone** a month later: no "as you saw in the terminal", no narration of your own process. If a command's output matters, quote the lines that matter.
- A subagent's report is material for you, not text to paste.

### Files

For a topic `<slug>`, in the vault (`vault/` or `$DOCET_VAULT`):

```
<slug>/_course.md            written by the engine: map, course, concepts, commands. Don't edit.
<slug>/entry-test.md
<slug>/NN-<title>.md         lessons, NN in course order, title in the learner's language
<slug>/chapter-test-<b>.md
<slug>/practice-<b>.md       practice set of a block
<slug>/synthesis-<b>.md      synthesis of a block
<slug>/final-test.md
<slug>/analysis.md
<slug>/synthesis.md          synthesis of the whole topic
<slug>/review-YYYY-MM-DD.md
<slug>/fig/<name>.svg        figures (see `docet-figure`)
_map.md  _review.md          engine views across topics
```

Every file you create starts like this (headings and link text in the learner's language):

```markdown
---
topic: <slug>
type: lesson        # lesson | entry-test | chapter-test | practice | final-test | analysis | review
lesson: <id>        # lessons only
cssclasses: [docet]
---
# <Title>

[[_course|← course]]

%% ↓ %%
```

---

## The engine: `bin/docet.py`

The engine owns everything that must not bend: the committed answer, the grade, mastery, the rules that change the course, the Obsidian views. Don't keep state in your head and don't write state into files by hand: ask `next` and `show`, change things through commands. Run from the repo root.

| Command | Use |
|---|---|
| `new <slug> --title … --goal … --lang xx` | new topic |
| `use <slug>` | switch topic |
| `plan` (JSON on stdin) | graph and course |
| `ask` (JSON) | commit questions, get their ids and the order to show |
| `grade` (JSON) | grade answers |
| `lesson <id> start\|done [--file <note>]` | lesson status |
| `note <lesson> "…"` | recalibration note of a lesson |
| `test-end <block>\|final` | close a test; the course adapts |
| `synth <block\|all>` | synthesis page to complete |
| `drop <Q…>` | discard questions committed but never written (a broken session) |
| `archive <slug>` | put a topic aside, nothing deleted |
| `next` | **what to do now** — whenever in doubt |
| `show [--json]` | full state |

### The graph

```bash
python3 bin/docet.py plan <<'EOF'
{"nodes": [
  {"id": "limit", "label": "limit"},
  {"id": "derivative", "label": "derivative", "deps": ["limit"], "kind": "procedural",
   "misconceptions": ["the derivative is the value of the function"]},
  {"id": "gradient", "label": "gradient", "deps": ["derivative"], "target": true}
],
 "blocks": [
  {"id": "b1", "title": "Foundations", "lessons": [
    {"id": "l01", "title": "The limit", "nodes": ["limit"], "note": "start from numbers"}]}
]}
EOF
```

- A node is small enough to check with one question. Ids: lowercase and hyphens; labels and titles in the learner's language.
- `target: true` marks what the learner asked for; the final test centres on it.
- `deps` are **direct** prerequisites only. Cycles and unknown ids are rejected.
- `kind: "procedural"` for things one *does* (a computation, a method): such a node is solid only after the learner has **produced** a right answer, not just picked one.
- `misconceptions`: the real wrong beliefs about the node. Distractors and traps are built from them, so collect them well.
- Nodes merge by id. Passing `blocks` replaces the course but keeps the status of lessons and tests with the same id.

### A question, always in four steps

**1. Commit.** Three types.

*Choice.* Options are short plain-text labels, no letters, no LaTeX, ~40 characters at most. The key is **base64 of the correct option's text**, which you encode yourself: the command is on screen, so the answer can't appear in it. Keep labels short and ASCII where the language allows (`=>` for ⇒, `rho` for ρ): hand-made base64 goes wrong on multibyte characters.

```bash
python3 bin/docet.py ask <<'EOF'
{"node": "gradient", "kind": "check", "lesson": "l03",
 "options": ["the gradient is zero", "the Hessian is zero", "the function is zero"],
 "key": "dGhlIGdyYWRpZW50IGlzIHplcm8="}
EOF
```
```
committed: Q7
Q7: A · the Hessian is zero | B · the gradient is zero | C · the function is zero
```

The engine shuffles and letters the options: that order is the question from now on. Keep the given order with `"shuffle": false` for ordered lists, such as numbers in sequence or a final "none of these". A key matching no option is rejected without saying which one was expected: re-encode.

*Numeric.* The learner produces a value instead of recognising it. Use it for every procedural check and for at least a third of chapter and final tests.

```bash
{"node": "partial-derivatives", "kind": "check", "type": "numeric", "key": "LTY=", "tol": 0,
 "traps": ["Ng=="]}
```

`tol` is the absolute tolerance (say in the question how many decimals). `traps` are base64 of the **wrong values a known misconception produces** (13 for a directional derivative with the vector left unnormalised): typing one is recorded as a misconception automatically. Build traps from the node's misconceptions or don't add them.

*Recall.* The learner states something from memory — a definition, a theorem with its hypotheses. No key (it would put the answer on screen); your verdict decides, as strict as a key would be.

```bash
{"node": "differentiability", "kind": "review", "type": "recall"}
```

`kind` is one of: `probe` (entry test), `check` (end of a node), `retry` (right after an error, same node, new example), `chapter` (add `"block"`), `practice` (add `"block"`), `pretest` (a try before the explanation, never counted), `final`, `review`. Several questions can go in one list. Never print `pending.json`: it holds the keys.

**2. Write it in Obsidian**, with the id, the full statement and the options in the engine's order, LaTeX where needed:

```markdown
> [!quiz] Q7 · gradient
> At an interior local minimum of $f(x,y)$, what must hold?
>
> **A** · $\det H_f = 0$
> **B** · $\nabla f = \mathbf{0}$
> **C** · $f = 0$
```

**3. Ask in the terminal.** One `AskUserQuestion` with two questions: the answer (`header: "Q7"`, options exactly the engine's labels) and the confidence (three options meaning *sure*, *unsure*, *guessed*). For numeric and recall questions: one line ("Q7 in Obsidian — type your answer"), wait for it, then the confidence window alone. "Other" is added automatically and absorbs "I don't know": don't spend a slot on it.

Confidence costs a click and says a lot: a guessed right answer proves nothing, and a wrong answer given with confidence is almost always a wrong model, which has to be taken apart rather than topped up.

**4. Grade it and write the correction.**

```bash
python3 bin/docet.py grade <<'EOF'
{"q": "Q7", "answer": "A · the Hessian is zero", "confidence": "sure", "error": "misconception"}
EOF
```

- `answer`: the label as chosen, or the value / text as typed. Anything off the options needs `"verdict": "right" | "wrong"`.
- `confidence`: `sure` | `unsure` | `guess`.
- `error` when wrong: `misconception` if the answer embodies a wrong model, `gap` if something is missing or they didn't know.

The engine answers with ✓/✗, the correct answer, status changes and what to do (`→ retry`, `→ lower the bar`, `→ reinforce`, `PACE`). Below the question, in the lesson file:

```markdown
> [!failure]- ✗ Q7 · answer: A, correct: B
> Why B holds, and **why A looked right**.
```

`[!success]-` when right. Always correct, right or wrong; in the terminal one line (`✗ Q7 — correction in Obsidian`). **The grade stands**: if the learner shows the question was ambiguous, fix the question and ask a new one.

**Wrong and sure** (`→ HYPERCORRECTION`): this is the best moment to fix a belief — the surprise makes the correction stick. The correction says plainly what the learner believed, why it looked right, and the exact point where it fails; the retry comes immediately. **Wrong and guessed**: the engine counts it as a gap, never a misconception — a guess holds no model to take apart.

### Building the options

Wrong options are the right answer seen through a wrong belief. So:

1. Write the correct statement first.
2. For each misconception of the node, rewrite **that same statement** as someone holding it would say it: same shape, same length, same register.
3. No reasons inside any option ("…, since X"): reasons go in the correction. A justified option is the one that's right.
4. No emphasis on one option only.
5. Each wrong option must be something this learner could really believe, and plainly wrong once understood.

Test: hide the subject and look at the options. If you can still spot the right one, start again from step 1.

### Questions with no right answer

Goals, preferences, "shall we go on?": `AskUserQuestion` with a header like "Choice", no `ask`, no `grade`. And the reverse: a question with a right answer is never left ungraded.

---

## The course

```
goal → graph → ENTRY TEST → course
  → per block: LESSONS → CHAPTER TEST → SYNTHESIS → PRACTICE (procedural blocks)
  → FINAL TEST → ANALYSIS → exit at 80% → SYNTHESIS of the topic
  + REVIEW before anything new, always
```

The course keeps changing with the answers: prerequisites get inserted, reinforcement added, easy lessons merged. The engine applies the rules; you make the teaching choices.

**Accuracy first.** Every sentence in the vault must be one the learner can rely on without checking. The moment you are unsure of a fact, a formula, a name, a definition: check it with the `docet-research` agent or a search before writing it. If a check corrects something already taught, say so in the file. A wrong fact at the bottom of the graph corrupts everything above it.

### 1. Goal and graph

- **Goal**: a Choice until it's concrete. "Learn multivariable calculus" can mean an exam, machine learning, or curiosity, and each is a different course.
- **Who is learning**: `profile` first. Background and where they are strong go into the profile (`profile --background … --strong …`), once for all topics: they set the level of every lesson and are a source of bridges. That knowledge is bedrock too, just not on this topic.
- **Where they start**: "teach me X" and "help me get better at X" are different starts. The first means they don't know X (`--familiarity never|heard`): X is never asked, the entry test is a quick look at the foundations or nothing at all (`--entry quick|skip`). The second (`some|solid`) gets the test from the top. Read it from how they asked; a Choice only when it's unclear.
- **Scope with `docet-research`**: targets, prerequisites down to school level, real misconceptions per concept.
- **Graph with `plan`**, nodes only: at least two levels below where you think the learner stands, or the entry test can't find a gap that deep.

### 2. Entry test

File `entry-test.md`, driven by `next`. The engine decides what to probe and when to stop; it is short on purpose, because every question before the first lesson is a question the learner answers without having been taught anything.

- **Never open with the thing they asked to learn.** If they asked to be taught eigenvectors, the first question is not about eigenvectors: it is something they can probably answer. The first answer should feel like progress, not like an exam they were bound to fail.
- **Learning from scratch** (`never`, `heard`): the engine lists the foundations, easiest first, and climbs only while they hold. At most a handful of questions; skipped entirely with `--entry skip`.
- **Improving** (`some`): targets first, then down wherever an answer gives way. A confident right answer marks everything below it *assumed*; a wrong one marks everything resting on it *missing*, and it is not asked. At most ten questions. With `solid`, the test ends at once: the final test is the check.
- Two misses in a row on the foundations end the test: what is left is `NOT CHECKED`, and the engine asks about it right before the lesson that needs it (`CHECK FIRST`).
- The learner can stop it any time ("skip", "let's just start"): `entry skip`.
- One question per node; a second if the first came back "unsure". **A confident wrong answer on a target**: one more question on the same node, from another angle, before going down.
- **Mixed targets** (a procedure plus a condition for using it): probe the condition. A computation right says nothing about when it applies.
- Two questions at a time: write them, get the answers, write the corrections right below, then the next two.
- Wrong answers are the point here, not a failure: say so at the top of the file.

Close with a summary: where the edge is, what holds, what's missing, what that changes.

### 3. Course, then stop

Blocks of 3–5 lessons around one idea, lessons of 1–3 nodes. For each node ask: is this bedrock for this learner, or a result that rests on something simpler? If it rests, push it down. Send the course with `plan`, then one line ("course in Obsidian → `_course`") and a Choice. A wrong root is cheap now and expensive later.

### 4. Lessons

`lesson <id> start --file <slug>/<NN-title>`. At the top, two lines: what we learn and what it rests on. If `next` printed `PREREQUISITE — …`, a retry on each listed node comes first.

For every node:

1. **Why now**: the problem it solves. Bedrock facts too.
2. **Establish**: bedrock stated plainly; anything else built from what's there, every step earned. A step with a right answer is a quiz.
3. **Connect**: name the edge — which established nodes it hangs from.
4. **Check** with a quiz. Wrong → nothing goes on top:
   - a `retry` straight away, same node, new example. Right after a `gap` → it was a slip. Right after a `misconception` → the explanation landed, but the belief closes only after two right answers.
   - wrong again → `lower the bar` (teach the listed prerequisite now, then come back) or `reinforce` (explain the node another way: more concrete, or told instead of asked).
   - `→ STOP` (three wrong in a row on the node): no more questions at that level. Confusion that doesn't resolve turns into frustration, then into not caring. Go down to a prerequisite, or explain again from an easier example, told not asked; ask again only once something has clicked.

**Procedural nodes** fade the help: a worked example with every step's reason → the same kind of problem with the key step left to the learner (a quiz) → the whole problem alone, numeric. Skip the worked example for a learner who already showed the procedure with confidence.

Done when every node has a right check after its last error. Then recalibrate from `show`: unsure or slips → the next lesson revisits with one more example; confirmed gaps → reinforcement or a prerequisite; all right and sure → merge or raise the level. Write it with `note <next lesson> "…"` and one line at the end of the lesson.

### 5. Chapter test

`CHAPTER TEST <b>`, file `chapter-test-<b>.md`. One or two questions per node (`kind: "chapter"`, `"block"`), at least one problem that combines nodes (its node is the most advanced), one or two from earlier blocks. Mix on purpose problems that **look alike but need different methods**: choosing the method is the skill a mixed test trains, and it only trains it when the choice isn't obvious. All questions at the top, answered two at a time, corrections together at the end. Then `test-end <b>`: 80% with no misconception passes; otherwise a reinforcement lesson is added, and a second failure means the problem is lower down. A `retry` for every wrong node either way.

### 6. Synthesis

`SYNTHESIS <b>` after a passed chapter test, `SYNTHESIS all` at the end. `synth <scope>` writes the page with what the engine knows for sure: the map of that part and **the learner's own misconceptions** from the log, grouped by concept, with links to the questions. You replace every `%% ✎ … %%`, and `next` waits until none is left:

- **Core ideas**: the few facts this part rests on and how the rest follows, in a few lines. Same content, far fewer pieces. Not a lesson-by-lesson summary.
- **Flashcards** for what must be said exactly — definitions, theorems with every hypothesis, counterexamples: `> [!question] …` then a folded `> [!success]- …`, one per slide.
- **The learner's mistakes**: under each, the one sentence that takes the belief apart.
- **Test yourself**: 3–5 questions mixing the nodes, answer folded, one per slide.

`---` separates slides: Obsidian's Slides plugin presents the page as is. One screen per slide, or it isn't a synthesis yet.

### 7. Practice

`PRACTICE <b>` when a block has procedural nodes: a set of numeric exercises (`kind: "practice"`, `"block"`) in `practice-<b>.md`, until the engine stops asking. Mix the nodes and vary the surface of the problems: speed and flexibility come from repetition with variation, not from the same exercise twice.

### 8. Final test and analysis

`FINAL TEST`, file `final-test.md`, `kind: "final"`, then `test-end final`. All required nodes, weighted towards the targets and towards problems that combine them. At least one **transfer problem shaped by the goal** (`show` → goal): an exam exercise for an exam, a real case for work.

- Goal reached (80% solid, no misconception open) → the topic closes, then its synthesis.
- Otherwise `analysis.md`: a retry on every node not fully solved. Slips close there; gaps go into the `recovery` block; then the final test again on the weak nodes. 80%, not 100%: a missed quiz now and then is normal. An open misconception never is.

### 9. Review

A solid node comes back at growing intervals (3, 10, 30, 90 days; `_review.md`). `REVIEW` in `next` comes before anything else, in `review-<date>.md`, with new examples, never a repeat.

A review is **relearning, not a spot check**: it closes only after two right answers on the node in the same session (the engine keeps it due until then). A node that was right and sure from its very first answer starts at 10 days instead of 3. A wrong review halves the interval instead of starting over, and deserves a retry.

For definitions and theorems use `recall`: stating them is harder than recognising them, and that difficulty is what makes them stay.

---

## Visuals

A concept that is easier seen than read — a structure, a flow, a geometry — gets a figure through the `docet-figure` skill. The course map is drawn by the engine in `_course.md`: don't redraw it.

## Formatting

- Math in LaTeX: `$…$` inline, `$$…$$` on their own lines. Plain text only in terminal labels.
- Callouts: `[!quiz]` questions, `[!success]-` / `[!failure]` corrections (the `-` folds them so a rereader can try first), `[!abstract]` summaries, `[!warning]` misconceptions, `[!tip]` the insight that ties things together, `[!question]` flashcards.
- One idea per paragraph, `##` per node, short paragraphs. The page is for reading.
