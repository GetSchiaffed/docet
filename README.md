# docet

A study system for [Claude Code](https://claude.com/claude-code) and [Obsidian](https://obsidian.md). You name a topic; it finds out what you already know, teaches only what's missing, and keeps checking until the understanding holds.

Inspired by the idea behind [amosblomqvist/learn](https://github.com/amosblomqvist/learn).

## The idea

**Knowledge is a graph.** Every concept rests on others: the gradient on partial derivatives, those on the one-variable derivative, that on limits. A fact you can derive from things you already trust stays; a fact that floats on its own fades. So docet maps a topic as a graph of prerequisites and teaches it bottom-up, each step shown as the answer to a problem you can already see.

**It measures before it teaches, briefly.** Asking to be taught something and asking to get better at it are different starts. *Teach me eigenvectors* means you don't know them: they are never asked; docet looks at the foundations from the easiest up, a handful of questions, or none at all if you'd rather start the first lesson now. *Help me with eigenvectors* gets the test from the top: where you answer confidently and correctly, everything underneath is taken as known; where you don't, everything resting on it is taken as missing, and it goes one level down. Ten questions at most. Whatever was not checked is asked once, right before the lesson that needs it.

**It teaches at the edge and keeps you there.** Each lesson adds one step beyond what holds. Before a lesson, the engine checks its prerequisites are still solid. During it, it tracks how many of your recent answers were right and aims for **about 85%**. Much lower and failures stop being informative and start being discouraging; much higher and you are rehearsing, not learning. The figure comes from Wilson et al. (2019), a result on machine learners and simple perceptual tasks — here it is a working target, not a law.

**What it leans on**, all well replicated in learning research:
- answering questions beats rereading (retrieval practice);
- reviews at growing intervals beat cramming, and each review relearns until two answers are right (spacing, successive relearning);
- a try before the explanation, even a wrong one, makes the explanation land (pretesting, productive failure);
- worked examples first, then fading support, for procedures;
- asking how sure you were: a wrong answer given with confidence is a wrong model, and it is corrected best right then (hypercorrection); a wrong guess is only a gap.

**Code grades, not the model.** The correct answer is committed before each question, and grading is a comparison done by a small Python engine. Mastery, thresholds and course changes come from your answers only. The model writes the lessons; it can't soften a mark afterwards.

**It knows who is learning.** Your background and what your answers show across topics (how often you're right, how much your *sure* can be trusted) live in one profile. A concept solid in one topic is not asked again in the next.

**You read in Obsidian and answer in the terminal.** Lessons, formulas, figures and corrections live in Markdown files you keep. The terminal is only for picking or typing an answer. It teaches in the language you write in.

## A course

```
/docet:start multivariable differential calculus
```

1. **Goal** — exam, work or curiosity, how deep, and where you start: learning it from scratch or getting better at it. It changes the course.
2. **Graph** — concepts and prerequisites down to school level, with the typical misconceptions of each.
3. **Entry test** — short: the foundations from the bottom when you're new to it (or skipped), from the topic downward when you're not.
4. **Course** — the missing concepts in order, grouped into blocks. You approve it.
5. **Lessons** — each concept motivated, built from what you know, then checked. A wrong answer gets a second question on a new example: right means a slip, wrong means a gap, and the lesson goes back a step or explains another way.
6. **Chapter test** — cumulative, with problems that combine concepts. Failing adds a reinforcement lesson.
7. **Synthesis** — one page per block: the few ideas everything rests on, flashcards for definitions and theorems, *your own* mistakes with what dismantled them, a self-test. Obsidian also shows it as slides.
8. **Practice** — numeric exercises for the procedures, until they are fluent.
9. **Final test** — including a problem shaped by your goal. Exit at 80% of concepts solid, with no misconception left open.
10. **Review** — every solid concept returns at growing intervals (3, 10, 30, 90 days), closed by two right answers; a miss halves the interval.

```
/docet:next     picks up where you left off
/docet:stop     closes the session and notes where to resume
```

## In Obsidian

```
vault/
  _map.md                  all topics, and where knowledge is thin
  _review.md               what to review today
  _profile.md              who is learning: background, and what the answers show
  multivariable-calculus/
    _course.md             map coloured by mastery, course, commands
    entry-test.md
    01-limits.md
    chapter-test-b1.md
    synthesis-b1.md
    fig/                   figures (SVG)
```

Every question is on the page before the terminal asks for the answer. Corrections are folded, so rereading you can try first.

## Setup

- Claude Code
- Python 3.9+ (standard library only)
- Obsidian: open `vault/` as a vault
- Chrome or Chromium, optional: lets the drawing agents look at their figures before handing them over

```bash
git clone https://github.com/GetSchiaffed/docet.git && cd docet
python3 -m unittest discover tests
claude          # then: /docet:start <topic>
```

The vault can live elsewhere: `export DOCET_VAULT=/path/to/vault`.

## Layout

| Path | Role |
|---|---|
| `.claude/skills/docet-teach/` | how it teaches |
| `.claude/skills/docet-figure/` | when a figure is worth it |
| `.claude/agents/` | `docet-diagram`, `docet-svg`, `docet-research` |
| `.claude/commands/docet/` | `/docet:start`, `/docet:next`, `/docet:stop` |
| `bin/docet.py` | the engine; every threshold at the top |
| `bin/render.sh` | diagram → PNG, for checking |

Everything personal stays in `vault/`, which git ignores.

## License

MIT — see [LICENSE](LICENSE).
