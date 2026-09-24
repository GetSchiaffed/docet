---
name: docet-figure
description: "For concepts that are easier to grasp by seeing than by reading, adds a single checked figure to the lesson: a graph of dependencies, a process, an exchange, states, a hierarchy, or a geometry (curves, vectors, regions, number lines). A maker agent draws it, renders it and inspects the image before it reaches the learner."
---

# Figures

A figure is worth adding when it shows what a paragraph can't: how things connect, in what order they happen, where they sit. If the sentence next to it already says everything, the figure only adds a way to be wrong. When unsure, leave it out.

You decide **what** the figure says. A maker agent decides **how** to draw it, renders it, looks at the result and fixes it until it is right. You never put a figure in a lesson that nobody has looked at.

## Which maker

| The idea is… | Maker | What goes in the lesson |
|---|---|---|
| nodes and arrows: dependencies, a flow, a sequence of messages, states, a tree, a timeline | `docet-diagram` | the mermaid source, in a ```mermaid block |
| positions and shapes: a curve, paths to a point, vectors, a region, a number line, a triangle with its angles | `docet-svg` | the `.svg` file, embedded with `![[fig/<name>.svg\|420]]` |

Rule of thumb: if moving an element somewhere else would make the figure *false*, it's geometry → SVG. If only the connections matter, it's a graph → mermaid.

Both keep the lesson a text vault: mermaid is text, SVG is text. Both stay sharp at any zoom.

## Writing the brief

The agent sees only the brief, never the lesson, so the brief carries:

1. **The claim**: one sentence the figure must make true at a glance. ("Along every line through the origin f tends to 0, along y = x² it stays ½.")
2. **The elements**: the few things that carry the claim, with exact labels in the learner's language. Everything else is noise.
3. **For geometry**: the exact mathematics — equations, coordinates, which point is where, what must be visibly true (the vertex at the origin, the angle marked on the right corner).
4. **For docet-svg**: the topic slug and a short file name, so it saves to `vault/<slug>/fig/<name>.svg`.

Five elements beat fifteen. If the claim needs two figures, it is two ideas: pick one.

## What comes back

```
RESULT:
<mermaid source>            (docet-diagram)
fig/<name>.svg              (docet-svg)
CHECKED: <what the agent confirmed on the rendered image>
```

If it answers `RESULT: NONE`, it explains why the figure can't be made true. Then simplify the brief or drop the figure. **Never draw one yourself instead**: the whole guarantee is the look.

If the maker reports that no browser was available (exit 3), the figure can go in the lesson with a line under it: *(figure not verified)*.

## In the lesson

Put it right after the sentence it illustrates, with a one-line caption in italics saying what to look at. Don't describe the figure in prose as well: the caption is enough.
