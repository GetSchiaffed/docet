#!/usr/bin/env python3
"""
docet.py — the engine: learner state, quizzes, grading, course adaptation.

Pedagogy lives in the prompts (`.claude/skills/docet-teach/`). This file holds
everything that must be DETERMINISTIC, i.e. what a model must not be able to
adjust after the fact:

  - committing to the correct answer before the question is asked;
  - grading, which is a string comparison, not a judgement;
  - the mastery of every concept, computed from evidence only;
  - the adaptation rules: descending into prerequisites, reinforcement
    lessons, chapter tests, final test, exit threshold, spaced review;
  - the Markdown views Obsidian shows (_course, _map, _review).

Standard library only. State is JSON in `<vault>/.docet/`, a folder Obsidian
does not show. The vault is `./vault` or `$DOCET_VAULT`.

Quick reference (details: `docet.py <command> -h`):

    docet.py new <slug> --title T --goal G --lang it   create a topic, make it active
             [--familiarity never|heard|some|solid] [--entry quick|skip|full]
    docet.py entry quick|skip|full                     change how the entry test runs
    docet.py profile [--background B --strong S]       the learner across topics
    docet.py plan            < json                    concept graph and/or blocks
    docet.py ask             < json                    commit questions (options shuffled, or numeric)
    docet.py grade           < json                    grade answers
    docet.py lesson <id> start|done                    lesson status
    docet.py note <lesson> "text"                      recalibration note of a lesson
    docet.py synth <block|all>                         synthesis page to complete
    docet.py archive <slug>                            put a topic aside
    docet.py test-end <block|final>                    close a test and adapt
    docet.py drop <Q…>                                 discard questions never written
    docet.py next                                      what to do now
    docet.py show [--json]                             readable state
    docet.py render                                    rebuild the Obsidian views
"""

import argparse
import base64
import datetime as dt
import json
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = os.path.abspath(os.environ.get("DOCET_VAULT") or os.path.join(ROOT, "vault"))
STATE = os.path.join(VAULT, ".docet")
LOG = os.path.join(STATE, "log.jsonl")
PENDING = os.path.join(STATE, "pending.json")
ACTIVE = os.path.join(STATE, "active")
PROFILE = os.path.join(STATE, "profile.json")

# --- rules: every threshold in one place -----------------------------------

EXIT_SHARE = 0.80        # share of required concepts that must be solid
TEST_PASS = 0.80         # share of right answers to pass a test
EMA_ALPHA = 0.5          # weight of the most recent answer in mastery
SOLID_MASTERY = 0.80     # minimum mastery for "solid"
SOLID_HITS = 2           # minimum right, non-guessed answers for "solid"
MAX_TEST_RETRIES = 2     # beyond this the problem is lower: go to prerequisites
REVIEW_STEPS = [3, 10, 30, 90]   # days between one review and the next
CHALLENGE_WINDOW = 8     # recent answers the pace is measured on (entry test excluded)
CHALLENGE_LOW = 0.60     # below: too hard, the learner is losing heart
CHALLENGE_HIGH = 0.90    # above, all "sure": too easy. Aim near 85% right
PRACTICE_MIN = 5         # produced answers in a block's practice set
REVIEW_CRITERION = 2     # right answers needed to close one review of a concept
STREAK_STOP = 3          # wrong answers in a row on one concept: stop asking at that level
ENTRY_MAX = 10           # entry test, improving on a topic: questions at most (a real run took 12)
ENTRY_QUICK = 5          # entry test, learning from scratch: a quick look at the foundations only
ENTRY_LEVEL_STOP = 2     # misses in a row on the foundations: stop, check the rest lesson by lesson

# How well the learner says they know the topic. "Teach me X" (never, heard)
# is a different start from "help me get better at X" (some, solid): X itself
# is never probed, the foundations are checked from the bottom, or not at all.
FAMILIARITY = ("never", "heard", "some", "solid")
LEARNING = ("never", "heard")
ENTRY_STYLES = {"full": ENTRY_MAX, "quick": ENTRY_QUICK, "skip": 0}

CONFIDENCE = {"sure": 1.0, "unsure": 0.7, "guess": 0.2}
KINDS = ("probe", "check", "retry", "chapter", "final", "review", "practice", "pretest")
# choice: recognise among options · numeric: produce a value · recall: state it
# from memory (a definition, a theorem), judged by the model against the notes
QTYPES = ("choice", "numeric", "recall")
PRODUCED = ("numeric", "recall")
OK_STATES = ("solid", "known", "assumed")

# --- the words the engine writes into the vault ----------------------------
# Everything the model writes follows the learner's language on its own; these
# pages are written by Python, so they need a table. Add a language by adding
# a dict with the same keys: missing keys fall back to English.

STRINGS = {
    "en": {
        "unknown": "not probed", "assumed": "assumed", "known": "already known",
        "missing": "missing", "shaky": "shaky", "solid": "solid",
        "phase.entry": "entry test", "phase.lessons": "lessons",
        "phase.analysis": "error analysis", "phase.done": "done",
        "goal": "Goal", "phase": "Phase", "mastery": "Mastery", "exit_at": "exit at",
        "misconceptions_open": "Misconceptions still open",
        "map": "Map",
        "map_legend": ("Roots at the top, the goal at the bottom (rounded). Dark green solid, "
                       "light green known or assumed, yellow shaky, red missing, grey not probed yet."),
        "course": "Course", "reinforcement": "reinforcement",
        "chapter_test": "Chapter test", "final_test": "Final test",
        "todo": "to do", "passed": "passed", "redo": "to redo",
        "concepts": "Concepts", "concept": "Concept", "status": "Status",
        "last_answer": "Last answer",
        "map_title": "What I know",
        "map_empty": "No topics yet. In the terminal: `/docet:start <what you want to learn>`.",
        "topic": "Topic", "reviews_due": "Reviews due",
        "thin": "Where knowledge is thin",
        "thin_legend": "Only shaky or missing concepts, with the prerequisites holding them up.",
        "review_title": "Review",
        "review_legend": "Concepts come back at growing intervals ({steps} days). "
                         "A right review stretches the interval, a wrong one resets it.",
        "review_today": "Due today", "review_next": "Coming up",
        "nothing": "Nothing.", "nothing_queued": "Nothing queued.",
        "calibration": "Calibration",
        "calibration_legend": ("How often you were right, by how sure you said you were. "
                               "Well calibrated: *sure* close to 100%, *guessed* close to chance."),
        "conf.sure": "sure", "conf.unsure": "unsure", "conf.guess": "guessed",
        "confidence": "Confidence", "right": "Right",
        "commands": "Commands",
        "commands_legend": "In the terminal: you read here in Obsidian, you answer there.",
        "cmd.next": "picks up where you left off: review, lesson, test or synthesis",
        "cmd.stop": "closes the session and writes down where to resume",
        "cmd.start": "starts a new topic", "cmd.what": "What it does",
        "files": "Files in this folder",
        "file.entry": "the entry test: where you started from",
        "file.lesson": "the lessons, with questions and folded corrections (open them after answering)",
        "file.tests": "chapter tests and final test",
        "file.synth": "the synthesis of a block or of the whole topic, readable as a presentation too",
        "synthesis": "Synthesis",
        "synth.slides": "Also a presentation: command palette → *Slides: Start presentation*.",
        "synth.map": "What it rests on",
        "synth.ideas": "The core ideas",
        "synth.oral": "Definitions, theorems, counterexamples",
        "synth.errors": "Your mistakes",
        "synth.errors_none": "No misconceptions in this part.",
        "synth.answer": "your answer", "synth.open": "still open", "synth.closed": "dismantled",
        "synth.selftest": "Test yourself",
        "profile_title": "Who is learning",
        "profile_legend": ("What you told docet, and what your answers show. A new topic starts "
                           "from here, and a concept solid in one topic is not asked again in another."),
        "profile_empty": "Nothing yet: it fills in with `/docet:start` and your answers.",
        "declared": "What you said", "background": "Background", "strong_in": "Strong in",
        "measured": "What your answers show", "answers": "Answers",
        "entry_right": "Right in entry tests", "lesson_right": "Right during lessons",
        "sure_wrong": "Wrong while sure", "per_lesson": "Questions per lesson",
        "known_concepts": "Concepts you already hold",
    },
    "it": {
        "unknown": "non sondato", "assumed": "presunto", "known": "già noto",
        "missing": "assente", "shaky": "fragile", "solid": "solido",
        "phase.entry": "test d'ingresso", "phase.lessons": "lezioni",
        "phase.analysis": "analisi degli errori", "phase.done": "completato",
        "goal": "Obiettivo", "phase": "Fase", "mastery": "Padronanza", "exit_at": "uscita a",
        "misconceptions_open": "Fraintendimenti ancora aperti",
        "map": "Mappa",
        "map_legend": ("Le radici in alto, l'obiettivo in fondo (forma arrotondata). Verde scuro solido, "
                       "verde chiaro già noto o presunto, giallo fragile, rosso assente, grigio non ancora sondato."),
        "course": "Percorso", "reinforcement": "rinforzo",
        "chapter_test": "Test di capitolo", "final_test": "Test finale",
        "todo": "da fare", "passed": "superato", "redo": "da rifare",
        "concepts": "Concetti", "concept": "Concetto", "status": "Stato",
        "last_answer": "Ultima prova",
        "map_title": "Mappa di ciò che so",
        "map_empty": "Ancora nessun argomento. Nel terminale: `/docet:start <cosa vuoi imparare>`.",
        "topic": "Argomento", "reviews_due": "Ripassi dovuti",
        "thin": "Dove la conoscenza è rada",
        "thin_legend": "Solo i concetti fragili o assenti, con i prerequisiti che li reggono.",
        "review_title": "Ripasso",
        "review_legend": "I concetti tornano a intervalli crescenti ({steps} giorni). "
                         "Un ripasso giusto allunga l'intervallo, uno sbagliato lo azzera.",
        "review_today": "Da ripassare oggi", "review_next": "Prossimi",
        "nothing": "Niente.", "nothing_queued": "Niente in coda.",
        "calibration": "Calibrazione",
        "calibration_legend": ("Quanto spesso avevi ragione, secondo quanto ti dicevi sicuro. "
                               "Ben calibrato: *sicuro* vicino al 100%, *tirato a indovinare* vicino al caso."),
        "conf.sure": "sicuro", "conf.unsure": "incerto", "conf.guess": "tirato a indovinare",
        "confidence": "Sicurezza", "right": "Giuste",
        "commands": "Comandi",
        "commands_legend": "Nel terminale: si legge qui in Obsidian, si risponde lì.",
        "cmd.next": "riprende da dove eri: ripasso, lezione, test o sintesi",
        "cmd.stop": "chiude la sessione e segna dove riprendere",
        "cmd.start": "inizia un nuovo argomento", "cmd.what": "Cosa fa",
        "files": "I file di questa cartella",
        "file.entry": "il test d'ingresso: da dove sei partito",
        "file.lesson": "le lezioni, con domande e correzioni chiuse (aprile dopo aver risposto)",
        "file.tests": "test di capitolo e test finale",
        "file.synth": "la sintesi di un blocco o dell'intero argomento, che si legge anche come presentazione",
        "synthesis": "Sintesi",
        "synth.slides": "È anche una presentazione: palette dei comandi → *Slides: Start presentation*.",
        "synth.map": "Su cosa poggia",
        "synth.ideas": "Le idee portanti",
        "synth.oral": "Definizioni, teoremi, controesempi",
        "synth.errors": "I tuoi errori",
        "synth.errors_none": "Nessun fraintendimento in questa parte.",
        "synth.answer": "risposta data", "synth.open": "ancora aperto", "synth.closed": "smontato",
        "synth.selftest": "Mettiti alla prova",
        "profile_title": "Chi sta imparando",
        "profile_legend": ("Quello che hai detto a docet e quello che mostrano le tue risposte. Un nuovo "
                           "argomento parte da qui, e un concetto solido in un argomento non viene "
                           "richiesto in un altro."),
        "profile_empty": "Ancora niente: si riempie con `/docet:start` e con le tue risposte.",
        "declared": "Cosa hai detto", "background": "Percorso", "strong_in": "Forte in",
        "measured": "Cosa mostrano le tue risposte", "answers": "Risposte",
        "entry_right": "Giuste nei test d'ingresso", "lesson_right": "Giuste durante le lezioni",
        "sure_wrong": "Sbagliate da sicuro", "per_lesson": "Domande per lezione",
        "known_concepts": "Concetti che hai già",
    },
}


def tr(lang, key):
    return STRINGS.get(lang, {}).get(key) or STRINGS["en"][key]


# --- I/O -------------------------------------------------------------------

def die(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def today():
    return dt.date.today()


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def read_stdin_json():
    raw = sys.stdin.read()
    if not raw.strip():
        die("expected JSON on stdin")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"invalid JSON on stdin: {e}")


def slugify(text, limit=50):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:limit].strip("-") or "topic"


def topic_path(slug):
    return os.path.join(STATE, f"{slug}.json")


def read_active():
    try:
        with open(ACTIVE, encoding="utf-8") as fh:
            return fh.read().strip()
    except FileNotFoundError:
        return ""


def active_slug(explicit=None):
    slug = explicit or read_active()
    if not slug:
        die("no active topic: `docet.py new <slug>` or `docet.py use <slug>`")
    return slug


def load_topic(slug):
    t = load_json(topic_path(slug), None)
    if t is None:
        die(f"no such topic: {slug}")
    return t


def save_topic(t):
    save_json(topic_path(t["slug"]), t)


def all_topics():
    if not os.path.isdir(STATE):
        return []
    out = []
    for name in sorted(os.listdir(STATE)):
        if name.endswith(".json") and name != "pending.json":
            t = load_json(os.path.join(STATE, name), None)
            if isinstance(t, dict) and "nodes" in t:
                out.append(t)
    return out


def log_seq():
    try:
        with open(LOG, encoding="utf-8") as fh:
            return sum(1 for _ in fh)
    except FileNotFoundError:
        return 0


def read_log(slug=None):
    out = []
    try:
        with open(LOG, encoding="utf-8") as fh:
            for line in fh:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if slug is None or e.get("topic") == slug:
                    out.append(e)
    except FileNotFoundError:
        pass
    return out


def append_log(entry):
    os.makedirs(STATE, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# --- the mastery model -----------------------------------------------------

def node_metrics(node):
    """Mastery and status of a concept, derived ONLY from evidence.

    Slips do not count: a wrong answer that the retry reclassified as a slip
    says nothing about what the learner knows.
    """
    ev = [e for e in node.get("evidence", []) if e.get("error") != "slip"]
    if not ev:
        # Inference, never evidence: "assumed" below a concept that held,
        # "missing" above one that gave way (or declared: "teach me X").
        status = "assumed" if node.get("assumed") else "missing" if node.get("gap") else "unknown"
        return {"mastery": None, "status": status, "hits": 0, "open_misconception": False}

    m = None
    for e in ev:
        x = CONFIDENCE.get(e.get("confidence"), 0.8) if e["correct"] else 0.0
        m = x if m is None else (1 - EMA_ALPHA) * m + EMA_ALPHA * x

    hits = sum(1 for e in ev if e["correct"] and e.get("confidence") != "guess")

    # A misconception stays open until two genuine right answers come AFTER
    # it: a wrong model held with conviction is not dismantled in one go.
    open_misc = False
    for i, e in enumerate(ev):
        if not e["correct"] and e.get("error") == "misconception":
            after = sum(1 for f in ev[i + 1:]
                        if f["correct"] and f.get("confidence") != "guess")
            open_misc = open_misc or after < 2

    all_right = all(e["correct"] for e in ev)
    from_probe = any(e.get("kind") == "probe" for e in ev)

    # A procedure is known when it can be carried out, not just recognised.
    produced = any(e["correct"] and e.get("type") in PRODUCED and e.get("confidence") != "guess"
                   for e in ev)
    doable = node.get("kind") != "procedural" or produced

    if m >= SOLID_MASTERY and hits >= SOLID_HITS and not open_misc and doable:
        status = "solid"
    elif all_right and from_probe and hits >= 1 and m >= SOLID_MASTERY:
        status = "known"         # shown in the entry test: no need to teach it
    elif hits == 0:
        status = "missing"
    else:
        status = "shaky"
    return {"mastery": m, "status": status, "hits": hits, "open_misconception": open_misc}


def status_of(t, nid):
    return node_metrics(t["nodes"][nid])["status"]


def ancestors(t, nid, seen=None):
    seen = set() if seen is None else seen
    for d in t["nodes"].get(nid, {}).get("deps", []):
        if d not in seen and d in t["nodes"]:
            seen.add(d)
            ancestors(t, d, seen)
    return seen


def descendants(t, nid):
    """Concepts that rest on nid, directly or not."""
    return {n for n in t["nodes"] if nid in ancestors(t, n)}


def learning(t):
    """"Teach me X": the learner declared they don't know the topic."""
    return t.get("familiarity") in LEARNING


def entry_style(t):
    return t.get("entry") or ("quick" if learning(t) else "full")


def infer(t, nid, flag):
    """Set an inference ("assumed" or "gap") on a concept with no evidence of
    its own. The first inference holds: another one never flips it."""
    n = t["nodes"][nid]
    if not n.get("evidence") and not n.get("assumed") and not n.get("gap"):
        n[flag] = True
        return True
    return False


def declare(t):
    """What the learner said about the topic, applied to its targets: never
    probe what they asked to be taught; skip what they say they master (the
    final test still covers every target)."""
    flag = "gap" if learning(t) else "assumed" if t.get("familiarity") == "solid" else None
    if flag:
        for n, v in t["nodes"].items():
            if v.get("target") and infer(t, n, flag):
                v["declared"] = True


def undeclare(t):
    """Forget what was declared, before declaring again: the learner changed
    their mind about where they start. Evidence and grading inferences stay."""
    for v in t["nodes"].values():
        if v.pop("declared", False) and not v.get("evidence"):
            v["gap"] = v["assumed"] = False


def topo_order(t, ids=None):
    ids = set(t["nodes"]) if ids is None else set(ids)
    order, state = [], {}

    def visit(n):
        if state.get(n) == 2:
            return
        if state.get(n) == 1:
            die(f"the graph has a cycle through '{n}'")
        state[n] = 1
        for d in t["nodes"][n].get("deps", []):
            if d in t["nodes"]:
                visit(d)
        state[n] = 2
        if n in ids:
            order.append(n)

    for n in sorted(t["nodes"]):
        visit(n)
    return order


def lesson_nodes(t):
    out = []
    for b in t["blocks"]:
        for les in b["lessons"]:
            out.extend(n for n in les["nodes"] if n not in out)
    return out


def required_nodes(t):
    """What must be known for this topic: targets + concepts taught."""
    req = [n for n, v in t["nodes"].items() if v.get("target")]
    req += [n for n in lesson_nodes(t) if n not in req]
    return req


def progress(t):
    req = required_nodes(t)
    if not req:
        return 0.0, [], []
    ok = [n for n in req if status_of(t, n) in OK_STATES]
    misc = [n for n in req if node_metrics(t["nodes"][n])["open_misconception"]]
    return len(ok) / len(req), ok, misc


# --- commands --------------------------------------------------------------

def cmd_new(a):
    slug = slugify(a.slug)
    if os.path.exists(topic_path(slug)):
        die(f"'{slug}' already exists: `docet.py use {slug}` to resume it")
    t = {
        "slug": slug,
        "title": a.title or a.slug,
        "goal": a.goal or "",
        "lang": a.lang,
        "created": now(),
        "phase": "entry",
        "familiarity": a.familiarity,
        "entry": a.entry,
        "next_q": 1,
        "nodes": {},
        "blocks": [],
        "final": {"attempts": 0, "status": None},
    }
    save_topic(t)
    os.makedirs(os.path.join(VAULT, slug), exist_ok=True)
    with open(ACTIVE, "w", encoding="utf-8") as fh:
        fh.write(slug)
    render_all()
    print(f"topic:  {slug}")
    print(f"folder: {os.path.join(VAULT, slug)}")
    print(f"entry:  {entry_style(t)} ({'learning from scratch' if learning(t) else 'improving'})")


def cmd_use(a):
    load_topic(a.slug)
    os.makedirs(STATE, exist_ok=True)
    with open(ACTIVE, "w", encoding="utf-8") as fh:
        fh.write(a.slug)
    print(f"active topic: {a.slug}")


def cmd_entry(a):
    """Change how the entry test runs, even halfway: `skip` ends it now."""
    t = load_topic(active_slug(a.topic))
    t["entry"] = a.style
    if a.familiarity:
        t["familiarity"] = a.familiarity
        undeclare(t)
        declare(t)
    save_topic(t)
    render_all()
    print(f"entry: {entry_style(t)} ({'learning from scratch' if learning(t) else 'improving'})")


def cmd_plan(a):
    """Update the graph and/or the course. Nodes merge by id; blocks, when
    given, replace the course but keep the status of lessons and tests with
    the same id."""
    t = load_topic(active_slug(a.topic))
    data = read_stdin_json()

    others = {n: o["slug"] for o in all_topics() if o["slug"] != t["slug"]
              for n in o["nodes"] if status_of(o, n) in ("solid", "known")}
    carried = []
    for n in data.get("nodes", []):
        nid = n.get("id")
        if not nid or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", nid):
            die(f"invalid node id: {nid!r} (lowercase, digits, hyphens)")
        new = nid not in t["nodes"]
        cur = t["nodes"].setdefault(nid, {"evidence": [], "assumed": False, "review": None})
        # Already solid in another topic: the same concept, not a new one.
        if new and nid in others and infer(t, nid, "assumed"):
            cur["carried"] = others[nid]
            carried.append(nid)
        # Bedrock the learner's declared background clearly implies.
        if n.get("assumed"):
            infer(t, nid, "assumed")
        cur["label"] = n.get("label", cur.get("label", nid))
        cur["deps"] = list(n.get("deps", cur.get("deps", [])))
        cur["target"] = bool(n.get("target", cur.get("target", False)))
        for extra in ("kind", "misconceptions"):
            if extra in n:
                cur[extra] = n[extra]

    for nid, n in t["nodes"].items():
        for d in n.get("deps", []):
            if d not in t["nodes"]:
                die(f"'{nid}' depends on '{d}', which is not in the graph")
    topo_order(t)  # fails on a cycle
    declare(t)

    if "blocks" in data:
        old_lessons = {les["id"]: les for b in t["blocks"] for les in b["lessons"]}
        old_blocks = {b["id"]: b for b in t["blocks"]}
        blocks = []
        for b in data["blocks"]:
            ob = old_blocks.get(b["id"], {})
            lessons = []
            for les in b.get("lessons", []):
                for n in les.get("nodes", []):
                    if n not in t["nodes"]:
                        die(f"lesson '{les['id']}' refers to node '{n}', which does not exist")
                ol = old_lessons.get(les["id"], {})
                lessons.append({
                    "id": les["id"],
                    "title": les.get("title", les["id"]),
                    "nodes": list(les.get("nodes", [])),
                    "kind": les.get("kind", ol.get("kind", "lesson")),
                    "status": ol.get("status", "todo"),
                    "file": les.get("file", ol.get("file")),
                    "note": les.get("note", ol.get("note")),
                })
            blocks.append({
                "id": b["id"],
                "title": b.get("title", b["id"]),
                "lessons": lessons,
                "test": ob.get("test", {"attempts": 0, "status": None}),
            })
        t["blocks"] = blocks
        if t["phase"] == "entry" and blocks:
            t["phase"] = "lessons"

    save_topic(t)
    render_all()
    print(f"graph: {len(t['nodes'])} concepts · course: "
          f"{sum(len(b['lessons']) for b in t['blocks'])} lessons in {len(t['blocks'])} blocks")
    if carried:
        print("already solid in another topic, taken as known: " + ", ".join(carried))


def _decode_key(key):
    try:
        return base64.b64decode(str(key).strip(), validate=True).decode("utf-8")
    except Exception:
        return None


def _norm(s):
    return re.sub(r"\s+", " ", str(s)).strip().casefold()


def _label_text(label):
    """'B · the gradient is zero' → 'the gradient is zero'."""
    m = re.match(r"^\s*[A-D]\s*[·.):—-]\s*(.+)$", str(label))
    return m.group(1) if m else str(label)


def _match_option(options, text):
    """Index of the option matching `text`, by full label or by the part
    after the letter. Letters are assigned by the engine, so a label typed
    with a stale letter still matches on its text."""
    if text is None:
        return None
    n = _norm(text)
    for i, o in enumerate(options):
        if n in (_norm(o), _norm(_label_text(o))):
            return i
    n = _norm(_label_text(text))
    for i, o in enumerate(options):
        if n == _norm(_label_text(o)):
            return i
    return None


def _letter_options(texts, shuffle):
    """The engine, not the model, decides where the right answer sits: a
    model left alone puts it on A or B far too often, and the learner learns
    the position instead of the concept."""
    texts = list(texts)
    if shuffle:
        random.SystemRandom().shuffle(texts)
    return [f"{'ABCD'[i]} · {s}" for i, s in enumerate(texts)]


def _parse_number(text):
    """'3.14', '3,14', '-2', '1/3', '1e-3' → float; anything else → None.
    A decimal comma is accepted: learners write numbers the way they learnt."""
    s = str(text).strip().replace(" ", "")
    m = re.fullmatch(r"([+-]?\d+)/(\d+)", s)
    if m:
        return int(m.group(1)) / int(m.group(2)) if int(m.group(2)) else None
    if re.fullmatch(r"[+-]?\d+,\d+", s):
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def cmd_ask(a):
    """Commit one or more questions. The correct answer arrives as base64 of
    its label, so it cannot be read in the command shown on screen."""
    slug = active_slug(a.topic)
    t = load_topic(slug)
    data = read_stdin_json()
    items = data if isinstance(data, list) else [data]
    pending = load_json(PENDING, {})
    ids, shown = [], []
    for q in items:
        node = q.get("node")
        if node not in t["nodes"]:
            die(f"no such node: {node!r} — add it to the graph with `plan` first")
        kind = q.get("kind", "check")
        if kind not in KINDS:
            die(f"invalid kind: {kind!r} (one of {', '.join(KINDS)})")
        qtype = q.get("type", "choice")
        if qtype not in QTYPES:
            die(f"invalid type: {qtype!r} (one of {', '.join(QTYPES)})")
        rec = {"topic": slug, "node": node, "kind": kind, "type": qtype,
               "block": q.get("block"), "lesson": q.get("lesson"), "key": q.get("key", "")}
        # Recall has no key: the reference is in the notes, and committing it
        # would put the answer on screen. The model's verdict decides.
        plain = "" if qtype == "recall" else _decode_key(q.get("key", ""))
        if plain is None:
            die("the key is not valid base64")

        if qtype == "recall":
            rec["options"] = []
        elif qtype == "numeric":
            # The learner produces the value instead of recognising it.
            if _parse_number(plain) is None:
                die("the key is not a number: re-encode the value")
            tol = q.get("tol", 0)
            if not isinstance(tol, (int, float)) or tol < 0:
                die("tol must be a number ≥ 0 (absolute tolerance)")
            rec["tol"] = tol
            rec["options"] = []
            # Wrong values a known wrong model produces (13 instead of 2.6:
            # the vector was not normalised). Committed now, like the key,
            # so the diagnosis is decided before the answer.
            traps = []
            for tr_key in q.get("traps", []):
                v = _parse_number(_decode_key(tr_key) or "")
                if v is None:
                    die("a trap is not a base64 number")
                traps.append(v)
            rec["traps"] = traps
        else:
            texts = [_label_text(o) for o in q.get("options") or []]
            if not 2 <= len(texts) <= 4:
                die("2 to 4 options are needed (AskUserQuestion takes no more)")
            if len({_norm(x) for x in texts}) != len(texts):
                die("two options have the same text")
            if _match_option(texts, plain) is None:
                # Never say WHICH option was expected: that would be the answer.
                die("the key matches no option: re-encode the correct option text")
            rec["options"] = _letter_options(texts, q.get("shuffle", True))

        qid = f"Q{t['next_q']}"
        t["next_q"] += 1
        rec.update(q=qid, asked=now())
        pending[f"{slug}:{qid}"] = rec
        ids.append(qid)
        shown.append((qid, rec["options"]))
    save_topic(t)
    save_json(PENDING, pending)
    print("committed: " + " ".join(ids))
    # The order the learner will see, in Obsidian and in the terminal alike.
    for qid, options in shown:
        print(f"{qid}: " + (" | ".join(options) if options else "typed answer"))


def _schedule(days):
    return (today() + dt.timedelta(days=days)).isoformat()


def _review_after(node, before, after, entry):
    """Spaced review, as successive relearning: a review closes only after
    REVIEW_CRITERION right answers, then the interval grows to the next step.
    A wrong answer halves the interval instead of starting over. A concept
    that was right and sure from its very first answer skips the first,
    shortest interval: reviewing what is already firm wastes the learner's
    patience."""
    r = node.get("review")
    if entry["kind"] == "review" and r:
        interval = r.get("interval", REVIEW_STEPS[min(r.get("step", 0), len(REVIEW_STEPS) - 1)])
        if entry["correct"] and entry.get("confidence") != "guess":
            hits = r.get("hits", 0) + 1
            if hits < REVIEW_CRITERION:
                node["review"] = dict(r, hits=hits)        # still due: one more today
                return "review: one more right answer closes it"
            longer = [d for d in REVIEW_STEPS if d > interval]
            interval = longer[0] if longer else REVIEW_STEPS[-1]
            node["review"] = {"interval": interval, "hits": 0, "due": _schedule(interval)}
            return f"review closed: next in {interval} days"
        interval = max(1, interval // 2)
        node["review"] = {"interval": interval, "hits": 0, "due": _schedule(interval)}
        return f"review failed: next in {interval} days"
    if after == "solid" and before != "solid" and not r:
        first = next((e for e in node.get("evidence", []) if e.get("kind") != "review"), None)
        firm = first is not None and first["correct"] and first.get("confidence") == "sure"
        interval = REVIEW_STEPS[1] if firm and len(REVIEW_STEPS) > 1 else REVIEW_STEPS[0]
        node["review"] = {"interval": interval, "hits": 0, "due": _schedule(interval)}
    return None


def cmd_grade(a):
    """Grade against the commitment. The verdict on listed options is
    mechanical; only free answers ("Other") need an explicit verdict."""
    slug = active_slug(a.topic)
    t = load_topic(slug)
    data = read_stdin_json()
    items = data if isinstance(data, list) else [data]
    pending = load_json(PENDING, {})
    seq = log_seq()
    lines = []

    for g in items:
        qid = str(g.get("q", "")).upper()
        rec = pending.get(f"{slug}:{qid}")
        if rec is None:
            die(f"{qid}: no committed question with this id")
        options = rec["options"]
        numeric = rec.get("type") == "numeric"
        recall = rec.get("type") == "recall"
        key_plain = "" if recall else _decode_key(rec["key"])
        answer = str(g.get("answer", ""))
        conf = g.get("confidence")
        if conf is not None and conf not in CONFIDENCE:
            die(f"{qid}: confidence must be one of {', '.join(CONFIDENCE)}")

        if recall:
            correct_text, idx = "see the notes", None
        elif numeric:
            correct_text = key_plain
            value, key_value = _parse_number(answer), _parse_number(key_plain)
            idx = None if value is None else 0
        else:
            correct_idx = _match_option(options, key_plain)
            correct_text = options[correct_idx]
            idx = _match_option(options, answer)

        if numeric and value is not None:
            # Absolute tolerance, plus a hair of float noise.
            correct = abs(value - key_value) <= rec.get("tol", 0) + 1e-9 * max(1.0, abs(key_value))
            free = False
        elif idx is not None:
            correct = idx == correct_idx
            free = False
        else:
            free = True
            verdict = g.get("verdict")
            if verdict not in ("right", "wrong"):
                die(f"{qid}: free answer — \"verdict\": \"right\" | \"wrong\" is required")
            correct = verdict == "right"

        error = None
        trapped = (numeric and not correct and value is not None
                   and any(abs(value - v) <= rec.get("tol", 0) + 1e-9 * max(1.0, abs(v))
                           for v in rec.get("traps", [])))
        if trapped:
            error = "misconception"
        elif not correct:
            error = g.get("error") or "gap"
            if error not in ("gap", "misconception"):
                die(f"{qid}: error must be 'gap' or 'misconception'")
        # A guess holds no model, right or wrong: it can reveal a gap, never
        # a misconception.
        downgraded = not correct and conf == "guess" and error == "misconception"
        if downgraded:
            error = "gap"

        node = t["nodes"][rec["node"]]
        before = node_metrics(node)["status"]
        entry = {
            "seq": seq, "topic": slug, "q": qid, "node": rec["node"], "kind": rec["kind"],
            "block": rec.get("block"), "lesson": rec.get("lesson"), "date": today().isoformat(),
            "answer": answer, "free": free, "correct": correct, "confidence": conf, "error": error,
            "type": rec.get("type", "choice"),
        }
        seq += 1
        append_log(entry)
        if rec["kind"] == "pretest":
            # A try before the explanation: failing is expected and useful,
            # it only primes what comes next. Logged, never counted.
            del pending[f"{slug}:{qid}"]
            lines.append(f"{qid} {'✓' if correct else '✗'}  pretest: not counted · correct: {correct_text}")
            continue
        node.setdefault("evidence", []).append(
            {k: entry[k] for k in ("q", "kind", "type", "date", "correct", "confidence", "error")})

        note = ""
        # The retry decides between slip and gap: right the second time, on a
        # different example, means the concept was there.
        if rec["kind"] == "retry":
            prev = [e for e in node["evidence"][:-1] if not e["correct"] and e.get("error") != "slip"]
            if prev and correct and conf != "guess" and prev[-1]["error"] == "gap":
                prev[-1]["error"] = "slip"
                note = "the previous error was a slip"
            elif prev and correct and prev[-1]["error"] == "misconception":
                # The retry comes after the correction: a right answer shows
                # the explanation landed, not that the error was a slip. A
                # misconception closes only with two right answers after it.
                note = "misconception: one right answer after it, it needs two"
            elif prev and not correct:
                note = f"{prev[-1]['error']} confirmed"

        # A confident right answer in the entry test makes the prerequisites
        # assumed: no probing below a concept that holds. Only "sure": an
        # unsure right answer is not enough to skip a whole subtree.
        if rec["kind"] == "probe" and correct and conf == "sure":
            for anc in ancestors(t, rec["node"]):
                if not t["nodes"][anc].get("evidence"):
                    t["nodes"][anc]["assumed"] = True
        # And the other way round: what rests on a concept that gave way is
        # missing too. Asking about it would only collect "don't know".
        if rec["kind"] == "probe" and not correct:
            for desc in descendants(t, rec["node"]):
                infer(t, desc, "gap")

        after = node_metrics(node)["status"]
        review_note = _review_after(node, before, after, entry)
        del pending[f"{slug}:{qid}"]

        mark = "✓" if correct else "✗"
        extra = []
        if not correct:
            extra.append(f"correct: {correct_text}")
            extra.append(error)
        if trapped:
            extra.append("the value a known wrong model gives")
        if downgraded:
            extra.append("guessed: counted as a gap, not a misconception")
        if review_note:
            extra.append(review_note)
        if conf == "guess" and correct:
            extra.append("right but guessed: does not count as evidence")
        if before != after:
            extra.append(f"{rec['node']}: {before} → {after}")
        if note:
            extra.append(note)
        lines.append(f"{qid} {mark}  " + " · ".join(extra) if extra else f"{qid} {mark}")

        # Wrong while sure: the correction is remembered best right now.
        if not correct and conf == "sure":
            lines.append("    → HYPERCORRECTION: wrong and sure. Correct it now and explicitly: "
                         "why the belief felt right, where exactly it breaks")
        # Too many misses in a row on one concept turn confusion into
        # frustration: stop asking at that level.
        streak = 0
        for e in reversed(node["evidence"]):
            if e["correct"] or e.get("kind") == "probe":
                break
            streak += 1
        if streak >= STREAK_STOP:
            lines.append(f"    → STOP: {streak} wrong in a row on '{rec['node']}'. No more questions at "
                         "this level: go down to a prerequisite, or explain it again, told not asked, "
                         "starting from an easier example")
            continue

        # The hint the skill's protocol expects.
        if not correct and rec["kind"] in ("check", "chapter", "final", "review"):
            lines.append(f"    → retry: a variant on '{rec['node']}' (slip or gap?)")
        if not correct and rec["kind"] == "retry":
            weak = [d for d in node.get("deps", []) if status_of(t, d) not in OK_STATES]
            if weak:
                lines.append("    → lower the bar: prerequisites not solid: " + ", ".join(weak))
            else:
                lines.append(f"    → reinforce '{rec['node']}' before moving on")

    save_topic(t)
    save_json(PENDING, pending)
    render_all()
    pace = pace_line(slug)
    if pace:
        lines.append(pace)
    print("\n".join(lines))


def cmd_lesson(a):
    t = load_topic(active_slug(a.topic))
    for b in t["blocks"]:
        for les in b["lessons"]:
            if les["id"] == a.id:
                les["status"] = {"start": "doing", "done": "done"}[a.action]
                if a.file:
                    les["file"] = a.file
                save_topic(t)
                render_all()
                print(f"{a.id}: {les['status']}")
                return
    die(f"no such lesson: {a.id}")


def cmd_note(a):
    """Set the note of a lesson: the recalibration shown in _course.md."""
    t = load_topic(active_slug(a.topic))
    for b in t["blocks"]:
        for les in b["lessons"]:
            if les["id"] == a.id:
                les["note"] = a.text or None
                save_topic(t)
                render_all()
                print(f"{a.id}: note {'set' if a.text else 'cleared'}")
                return
    die(f"no such lesson: {a.id}")


def cmd_archive(a):
    """Put a topic aside: its state moves to .docet/archive/, its notes stay
    in the vault, and it leaves status, _map and _review. Nothing is deleted:
    moving the file back restores it."""
    src = topic_path(a.slug)
    if not os.path.exists(src):
        die(f"no such topic: {a.slug}")
    os.makedirs(os.path.join(STATE, "archive"), exist_ok=True)
    os.replace(src, os.path.join(STATE, "archive", f"{a.slug}.json"))
    pending = load_json(PENDING, {})
    save_json(PENDING, {k: v for k, v in pending.items() if v.get("topic") != a.slug})
    if read_active() == a.slug:
        os.remove(ACTIVE)
    render_all()
    print(f"archived: {a.slug} (state in .docet/archive/, notes left in the vault)")


def _test_answers(t, which, kind):
    """The answers of the LATEST attempt at that test."""
    test = t["final"] if which == "final" else next(b for b in t["blocks"] if b["id"] == which)["test"]
    since = test.get("since_seq", -1)
    return [e for e in read_log(t["slug"])
            if e["kind"] == kind and e["seq"] > since
            and (which == "final" or e.get("block") == which)]


def cmd_test_end(a):
    """Close a test: compute the result and, if needed, add reinforcement."""
    t = load_topic(active_slug(a.topic))
    final = a.which == "final"
    if final:
        test, kind, block = t["final"], "final", None
    else:
        block = next((b for b in t["blocks"] if b["id"] == a.which), None)
        if block is None:
            die(f"no such block: {a.which}")
        test, kind = block["test"], "chapter"

    ans = _test_answers(t, a.which, kind)
    if not ans:
        die(f"no '{kind}' answers recorded for {a.which}")
    right = sum(e["correct"] for e in ans)
    score = right / len(ans)
    misc = sorted({e["node"] for e in ans if e.get("error") == "misconception"})
    wrong = sorted({e["node"] for e in ans if not e["correct"]})
    passed = score >= TEST_PASS and not misc

    test["attempts"] = test.get("attempts", 0) + 1
    test["status"] = "passed" if passed else "redo"
    test["score"] = round(score, 2)
    test["date"] = today().isoformat()
    test["weak"] = wrong
    test["since_seq"] = max(e["seq"] for e in ans)

    out = [f"{'final test' if final else 'chapter test ' + a.which}: "
           f"{right}/{len(ans)} ({round(score * 100)}%) — {'passed' if passed else 'to redo'}"]
    if misc:
        out.append("misconceptions: " + ", ".join(misc))
    if wrong:
        out.append("to retry (slip or gap?): " + ", ".join(wrong))

    if not passed:
        if final:
            target = next((b for b in t["blocks"] if b["id"] == "recovery"), None)
            if target is None:
                target = {"id": "recovery", "title": "Recovery after the final test",
                          "lessons": [], "test": {"attempts": 0, "status": None}}
                t["blocks"].append(target)
            t["phase"] = "analysis"
        else:
            target = block
        n = sum(1 for les in target["lessons"] if les["kind"] == "reinforcement") + 1
        labels = ", ".join(t["nodes"][x]["label"] for x in wrong) or "general review"
        target["lessons"].append({
            "id": f"{target['id']}-r{n}", "title": labels,
            "nodes": wrong, "kind": "reinforcement", "status": "todo", "file": None, "note": None,
        })
        out.append(f"added reinforcement lesson {target['id']}-r{n}")
        if test["attempts"] >= MAX_TEST_RETRIES:
            deps = sorted({d for x in wrong for d in t["nodes"][x].get("deps", [])
                           if status_of(t, d) != "solid"})
            out.append("→ second failed attempt: the problem is lower. "
                       + ("Probe/teach the prerequisites: " + ", ".join(deps) if deps
                          else "Rewrite the block's lessons with a different approach."))
    elif final:
        share, _, open_misc = progress(t)
        if share >= EXIT_SHARE and not open_misc:
            t["phase"] = "done"
            out.append(f"goal reached: {round(share * 100)}% of concepts solid")
        else:
            t["phase"] = "analysis"
            out.append(f"test passed but only {round(share * 100)}% of concepts are solid: "
                       "error analysis before closing")

    save_topic(t)
    render_all()
    print("\n".join(out))


def due_reviews(t):
    d = today().isoformat()
    return [n for n, v in t["nodes"].items() if v.get("review") and v["review"]["due"] <= d]


def entry_frontier(t):
    """Entry test: what to probe next, or why it is over.

    Improving on a topic: from the top (the targets) towards the foundations;
    where it gives way, descend into its prerequisites; where it holds, what
    lies below is assumed. Learning it from scratch: the targets are never
    asked; the foundations are checked from the easiest up, while they hold.
    Either way the test is short, and it stops after misses in a row on the
    foundations: what is left unchecked is asked right before the lesson that
    needs it."""
    probes = [e for e in read_log(t["slug"]) if e["kind"] == "probe"]
    cap = ENTRY_STYLES[entry_style(t)]
    if len(probes) >= cap:
        return ("skipped" if cap == 0 else "cap"), []
    last = probes[-ENTRY_LEVEL_STOP:]
    if (len(last) == ENTRY_LEVEL_STOP and not any(e["correct"] for e in last)
            and not any(t["nodes"].get(e["node"], {}).get("target") for e in last)):
        return "stop", []

    if learning(t):
        ok = lambda n: all(status_of(t, d) in OK_STATES for d in t["nodes"][n].get("deps", []))  # noqa: E731
        return "foundations", [n for n in topo_order(t) if not t["nodes"][n].get("target")
                               and status_of(t, n) == "unknown" and ok(n)]

    targets = [n for n, v in t["nodes"].items() if v.get("target")]
    unprobed = [n for n in targets if status_of(t, n) == "unknown"]
    if unprobed:
        return "targets", unprobed
    failed = [n for n in t["nodes"] if status_of(t, n) in ("missing", "shaky")]
    below = []
    for n in failed:
        for d in t["nodes"][n].get("deps", []):
            # "assumed" is an inference from another concept that held; a
            # concept that gave way is direct evidence, and it wins.
            if status_of(t, d) in ("unknown", "assumed") and d not in below:
                below.append(d)
    return "prerequisites", below


def _note_of(slug, qid):
    """The note (name without .md) where a question id was written, or None."""
    folder = os.path.join(VAULT, slug)
    pat = re.compile(rf"\[!quiz\][^\n]*\b{re.escape(qid)}\b")
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if name.endswith(".md") and not name.startswith("_"):
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                if pat.search(fh.read()):
                    return name[:-3]
    return None


def _in_vault(slug, qid):
    return _note_of(slug, qid) is not None


# --- synthesis --------------------------------------------------------------
# A block, once its chapter test is passed, and the topic, once the goal is
# reached, get one page that compresses them: the few ideas the rest derives
# from, what to say at an oral exam, the learner's OWN misconceptions and a
# self-test. The engine writes what it knows for certain (the graph, the
# mistakes from the log); every ✎ placeholder is for the model, and `next`
# does not move on while one is left. `---` separates slides.

PLACEHOLDER = "%% ✎"


def _synth_file(t, scope):
    name = "synthesis.md" if scope == "all" else f"synthesis-{scope}.md"
    return os.path.join(VAULT, t["slug"], name)


def _synth_state(t, scope):
    path = _synth_file(t, scope)
    if not os.path.exists(path):
        return "missing"
    with open(path, encoding="utf-8") as fh:
        return "unfinished" if PLACEHOLDER in fh.read() else "done"


def _synth_scope(t, scope):
    if scope == "all":
        return t["title"], required_nodes(t)
    b = next((b for b in t["blocks"] if b["id"] == scope), None)
    if b is None:
        die(f"no such block: {scope} (or 'all' for the whole topic)")
    return b["title"], list(dict.fromkeys(n for les in b["lessons"] for n in les["nodes"]))


def cmd_synth(a):
    t = load_topic(active_slug(a.topic))
    title, nodes = _synth_scope(t, a.scope)
    path = _synth_file(t, a.scope)
    if os.path.exists(path):
        print(f"exists, not overwritten: {path}")
        return
    s = lambda k: tr(t.get("lang", "en"), k)  # noqa: E731
    keep = set(nodes)
    for n in nodes:
        keep |= set(t["nodes"][n].get("deps", []))

    errors = []
    for e in read_log(t["slug"]):
        if e.get("error") != "misconception" or e["node"] not in nodes or e["kind"] == "pretest":
            continue
        ev = t["nodes"][e["node"]].get("evidence", [])
        if any(x["q"] == e["q"] and x.get("error") == "slip" for x in ev):
            continue
        errors.append(e)

    L = ["---", f"topic: {t['slug']}", "type: synthesis", f"scope: {a.scope}",
         "cssclasses: [docet]", "---", f"# {s('synthesis')} · {title}", "",
         "[[_course|← " + s("course").lower() + "]]", "", s("synth.slides"), "",
         "---", "", f"## {s('synth.map')}", "", mermaid_graph(t, only=keep), "",
         "---", "", f"## {s('synth.ideas')}", "",
         f"{PLACEHOLDER} the few bedrock facts this part rests on, and how the rest follows from them %%", "",
         "---", "", f"## {s('synth.oral')}", "",
         f"{PLACEHOLDER} one flashcard per definition, theorem (every hypothesis) or classic counterexample: "
         f"'> [!question] …' then a folded '> [!success]- …' with the exact statement, a --- between cards %%", "",
         "---", "", f"## {s('synth.errors')}", ""]
    if not errors:
        L += [s("synth.errors_none"), ""]
    # One callout per concept: the same wrong belief often shows up twice.
    for n in dict.fromkeys(e["node"] for e in errors):
        state = s("synth.open") if node_metrics(t["nodes"][n])["open_misconception"] \
            else s("synth.closed")
        L.append(f"> [!warning] {t['nodes'][n].get('label', n)} — {state}")
        for e in (e for e in errors if e["node"] == n):
            where = _note_of(t["slug"], e["q"])
            ref = f"[[{where}|{e['q']}]]" if where else e["q"]
            L.append(f"> {ref} · {s('synth.answer')}: «{e['answer']}»")
        L += [f"> {PLACEHOLDER} the sentence that dismantles this belief %%", ""]
    L += ["---", "", f"## {s('synth.selftest')}", "",
          f"{PLACEHOLDER} 3–5 questions on this part, each with its answer in a folded callout, a --- between them %%", ""]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    render_all()
    print(f"written: {path} — {len(errors)} misconception(s) from the log; fill every ✎")


def cmd_drop(a):
    """Discard committed questions that were never shown (a session that
    broke between `ask` and writing the question). No grade, no evidence."""
    slug = active_slug(a.topic)
    pending = load_json(PENDING, {})
    for qid in a.ids:
        qid = qid.upper()
        if pending.pop(f"{slug}:{qid}", None) is None:
            die(f"{qid}: no committed question with this id")
        if _in_vault(slug, qid):
            die(f"{qid} is already in a file: ask it again instead of dropping it")
    save_json(PENDING, pending)
    print("dropped: " + " ".join(q.upper() for q in a.ids))


def pace_line(slug):
    """How hard the last answers were. Too many failures in a row discourage,
    too few bore. The ~85% target is a heuristic borrowed from Wilson et al.
    (2019), a result on gradient-descent learners and simple perceptual tasks.
    The entry test is left out, where failing is the point."""
    recent = [e for e in read_log(slug) if e["kind"] not in ("probe", "pretest")][-CHALLENGE_WINDOW:]
    if len(recent) < CHALLENGE_WINDOW:
        return None
    right = sum(e["correct"] for e in recent)
    share = right / len(recent)
    if share < CHALLENGE_LOW:
        return (f"PACE — {right}/{len(recent)} right lately: too hard. Give an easy win, "
                "go expository, cut the next step smaller.")
    if share >= CHALLENGE_HIGH and all(e.get("confidence") == "sure" for e in recent):
        return (f"PACE — {right}/{len(recent)} right, all sure: too easy. Raise the level of "
                "the examples, merge the next steps.")
    return None


def weak_prerequisites(t, les):
    """Prerequisites of a lesson that are no longer holding: teach one level
    above what is known, never two."""
    own = set(les["nodes"])
    return [d for n in les["nodes"] for d in t["nodes"][n].get("deps", [])
            if d not in own and status_of(t, d) in ("shaky", "missing")]


def unchecked_prerequisites(t, les):
    """Prerequisites of a lesson never checked (a short or skipped entry
    test): one easy question each, right before the lesson that needs them."""
    own = set(les["nodes"])
    return [d for n in les["nodes"] for d in t["nodes"][n].get("deps", [])
            if d not in own and status_of(t, d) == "unknown"]


def cmd_next(a):
    t = load_topic(active_slug(a.topic))
    out = []

    # Questions committed but never answered: a session interrupted between
    # `ask` and `grade`. Ids only — the pending file holds the keys.
    open_q = [r["q"] for r in load_json(PENDING, {}).values() if r.get("topic") == t["slug"]]
    written = [q for q in open_q if _in_vault(t["slug"], q)]
    lost = [q for q in open_q if q not in written]
    if written:
        out.append("OPEN — committed, not answered yet (already in the file): "
                   + ", ".join(written) + ". Ask them again before anything new.")
    if lost:
        out.append("LOST — committed but never written to any file: " + ", ".join(lost)
                   + ". Discard with `drop " + " ".join(lost) + "`, then commit new questions.")

    rev = due_reviews(t)
    if rev:
        out.append("REVIEW — before anything new, one 'review' question on: " + ", ".join(rev))

    def done():
        print("\n".join(out))

    if t["phase"] == "entry":
        if not t["nodes"]:
            out.append("ENTRY — no graph yet: build it (targets + foundations) with `plan`")
        else:
            where, nodes = entry_frontier(t)
            if nodes:
                left = ENTRY_STYLES[entry_style(t)] - sum(
                    1 for e in read_log(t["slug"]) if e["kind"] == "probe")
                how = ("; easiest first, the topic itself is never asked" if where == "foundations"
                       else "")
                out.append(f"ENTRY — probe the {where}: " + ", ".join(nodes)
                           + f" ({left} more question(s) at most{how})")
            else:
                why = {"skipped": " (entry test skipped)",
                       "cap": f" ({ENTRY_STYLES[entry_style(t)]} questions: the limit)",
                       "stop": f" ({ENTRY_LEVEL_STOP} misses in a row on the foundations)"}.get(where, "")
                order = topo_order(t)
                teach = [n for n in order if status_of(t, n) in ("missing", "shaky")
                         or (t["nodes"][n].get("target") and status_of(t, n) not in OK_STATES)]
                rest = [n for n in order if status_of(t, n) == "unknown" and n not in teach]
                if not teach:
                    # Nothing to teach (declared solid, or all known): no
                    # course, straight to the final test, which checks it all.
                    t["phase"] = "lessons"
                    save_topic(t)
                    render_all()
                    out.append(f"ENTRY COMPLETE{why} — nothing to teach")
                else:
                    out.append(f"ENTRY COMPLETE{why} — plan the course (blocks → lessons) on these "
                               "concepts, in this order: " + ", ".join(teach))
                    if rest:
                        out.append("NOT CHECKED — " + ", ".join(rest) + ": leave them out of the "
                                   "course unless the goal needs them; each gets one easy question "
                                   "right before the first lesson resting on it")
                    return done()
        if t["phase"] == "entry":
            return done()

    def synth_step(scope, title):
        state = _synth_state(t, scope)
        name = os.path.basename(_synth_file(t, scope))
        if state == "missing":
            out.append(f"SYNTHESIS {scope} — {title}: `synth {scope}` writes {name}, then fill every ✎")
        elif state == "unfinished":
            out.append(f"SYNTHESIS {scope} (unfinished) — fill the ✎ left in {name}")
        return state != "done"

    if t["phase"] == "done":
        if synth_step("all", t["title"]):
            return done()
        out.append("DONE — goal reached. Only reviews are left.")
        return done()

    for b in t["blocks"]:
        for les in b["lessons"]:
            if les["status"] == "doing":
                pace = pace_line(t["slug"])
                if pace:
                    out.append(pace)
                out.append(f"LESSON (in progress) {les['id']} — {les['title']}"
                           + (f" — file: {les['file']}.md, read its end before continuing"
                              if les.get("file") else ""))
                return done()
        todo = [les for les in b["lessons"] if les["status"] == "todo"]
        if todo:
            les = todo[0]
            fresh = list(dict.fromkeys(unchecked_prerequisites(t, les)))
            if fresh:
                out.append("CHECK FIRST — never checked: " + ", ".join(fresh)
                           + f". One easy 'probe' question on each before {les['id']}; if one fails, "
                           f"teach it before {les['id']} (add it to the course with `plan`).")
            weak = list(dict.fromkeys(weak_prerequisites(t, les)))
            if weak:
                out.append("PREREQUISITE — not holding any more: " + ", ".join(weak)
                           + f". One retry on each before {les['id']}; if it fails, reinforce it.")
            tag = "REINFORCEMENT" if les["kind"] == "reinforcement" else "LESSON"
            out.append(f"{tag} {les['id']} — {les['title']} (nodes: {', '.join(les['nodes'])})")
            return done()
        if b["lessons"] and b["test"].get("status") != "passed":
            focus = b["test"].get("weak") if b["test"].get("status") == "redo" else None
            nodes = focus or [n for les in b["lessons"] for n in les["nodes"]]
            out.append(f"CHAPTER TEST {b['id']} — {b['title']} "
                       f"(attempt {b['test'].get('attempts', 0) + 1}; nodes: {', '.join(dict.fromkeys(nodes))})")
            return done()
        if b["lessons"] and b["id"] != "recovery" and synth_step(b["id"], b["title"]):
            return done()
        procedural = [n for les in b["lessons"] for n in les["nodes"]
                      if t["nodes"][n].get("kind") == "procedural"]
        if procedural and b["id"] != "recovery":
            done_n = sum(1 for e in read_log(t["slug"])
                         if e["kind"] == "practice" and e.get("block") == b["id"])
            if done_n < PRACTICE_MIN:
                out.append(f"PRACTICE {b['id']} — {PRACTICE_MIN - done_n} more numeric exercise(s), "
                           f"kind 'practice', block '{b['id']}', on: {', '.join(dict.fromkeys(procedural))} "
                           f"(file practice-{b['id']}.md)")
                return done()

    pace = pace_line(t["slug"])
    if pace:
        out.append(pace)

    if t["final"].get("status") != "passed":
        focus = t["final"].get("weak") if t["final"].get("status") == "redo" else None
        out.append(f"FINAL TEST (attempt {t['final'].get('attempts', 0) + 1}; nodes: "
                   f"{', '.join(focus or required_nodes(t))})")
        return done()

    share, ok, misc = progress(t)
    weak = [n for n in required_nodes(t) if n not in ok]
    out.append(f"ANALYSIS — {round(share * 100)}% solid. Retry on: {', '.join(weak) or '—'}"
               + (f"; open misconceptions: {', '.join(misc)}" if misc else ""))
    return done()


def cmd_show(a):
    t = load_topic(active_slug(a.topic))
    if a.json:
        view = dict(t)
        view["metrics"] = {n: node_metrics(v) for n, v in t["nodes"].items()}
        print(json.dumps(view, ensure_ascii=False, indent=2))
        return
    share, _, _ = progress(t)
    print(f"{t['title']}  [{t['phase']}]  {round(share * 100)}% solid  (lang: {t.get('lang', 'en')})")
    for n in topo_order(t):
        m = node_metrics(t["nodes"][n])
        pct = "  —" if m["mastery"] is None else f"{round(m['mastery'] * 100):3d}"
        flag = " ⚠ misconception" if m["open_misconception"] else ""
        print(f"  {pct}%  {m['status']:<8} {n}{flag}")
    for b in t["blocks"]:
        print(f"  [{b['id']}] {b['title']} — test: {b['test'].get('status') or 'todo'}")
        for les in b["lessons"]:
            print(f"      {les['status']:<6} {les['id']} {les['title']}")


def cmd_status(_a):
    ts = all_topics()
    if not ts:
        print("no topics")
        return
    act = read_active()
    for t in ts:
        share, _, _ = progress(t)
        mark = "*" if t["slug"] == act else " "
        print(f"{mark} {t['slug']:<40} {t['phase']:<9} {round(share * 100):3d}%  "
              f"reviews due: {len(due_reviews(t))}")


# --- the learner across topics ---------------------------------------------
# What they declared (background, where they are strong) and what the log
# shows. It grows with every topic: the more data, the less a new topic asks.

LESSON_KINDS = ("check", "retry", "practice", "chapter", "final", "review")


def load_profile():
    return load_json(PROFILE, {})


def measured(ts):
    log = [e for e in read_log() if e.get("kind") != "pretest"]
    share = lambda xs: (sum(e["correct"] for e in xs) / len(xs)) if xs else None  # noqa: E731
    entry = [e for e in log if e["kind"] == "probe"]
    lessons = [e for e in log if e["kind"] in LESSON_KINDS]
    per = {}
    for e in lessons:
        if e.get("lesson"):
            per[(e["topic"], e["lesson"])] = per.get((e["topic"], e["lesson"]), 0) + 1
    known = [{"id": n, "label": v.get("label", n), "topic": t["slug"]}
             for t in ts for n, v in t["nodes"].items() if status_of(t, n) in ("solid", "known")]
    return {
        "topics": len(ts), "answers": len(log),
        "entry_right": share(entry), "lesson_right": share(lessons),
        "sure_wrong": sum(1 for e in log if not e["correct"] and e.get("confidence") == "sure"),
        "per_lesson": round(sum(per.values()) / len(per), 1) if per else None,
        "known": known,
    }


def cmd_profile(a):
    prof = load_profile()
    if a.background is not None or a.strong is not None:
        if a.background is not None:
            prof["background"] = a.background
        if a.strong is not None:
            prof["strong_in"] = a.strong
        prof["updated"] = today().isoformat()
        save_json(PROFILE, prof)
        render_all()
    view = dict(prof, measured=measured(all_topics()))
    if a.json:
        print(json.dumps(view, ensure_ascii=False, indent=2))
        return
    m = view["measured"]
    pct = lambda x: "—" if x is None else f"{round(x * 100)}%"  # noqa: E731
    print(f"background: {prof.get('background') or '—'}")
    print(f"strong in:  {prof.get('strong_in') or '—'}")
    print(f"{m['topics']} topics, {m['answers']} answers · right in entry tests {pct(m['entry_right'])}, "
          f"in lessons {pct(m['lesson_right'])} · wrong while sure: {m['sure_wrong']}"
          + (f" · {m['per_lesson']} questions per lesson" if m["per_lesson"] else ""))
    if m["known"]:
        print("already held (reuse these ids): "
              + ", ".join(f"{k['id']} ({k['topic']})" for k in m["known"]))


def render_profile(ts, lang):
    s = lambda k: tr(lang, k)  # noqa: E731
    prof = load_profile()
    m = measured(ts)
    L = ["---", "cssclasses: [docet-course]", "---", f"# {s('profile_title')}", "", s("profile_legend"), ""]
    if not prof and not m["answers"]:
        L.append(s("profile_empty"))
    else:
        if prof.get("background") or prof.get("strong_in"):
            L += [f"## {s('declared')}", ""]
            if prof.get("background"):
                L.append(f"- **{s('background')}:** {prof['background']}")
            if prof.get("strong_in"):
                L.append(f"- **{s('strong_in')}:** {prof['strong_in']}")
            L.append("")
        pct = lambda x: "—" if x is None else f"`{_bar(x, 10)}` {round(x * 100)}%"  # noqa: E731
        L += [f"## {s('measured')}", "", "| | |", "|---|---|",
              f"| {s('answers')} | {m['answers']} |",
              f"| {s('entry_right')} | {pct(m['entry_right'])} |",
              f"| {s('lesson_right')} | {pct(m['lesson_right'])} |",
              f"| {s('sure_wrong')} | {m['sure_wrong']} |"]
        if m["per_lesson"]:
            L.append(f"| {s('per_lesson')} | {m['per_lesson']} |")
        L.append("")
        L += calibration_table(read_log(), s)
        if m["known"]:
            L += [f"## {s('known_concepts')}", ""]
            L += [f"- {k['label']} — [[{k['topic']}/_course|{k['topic']}]]" for k in m["known"]]
            L.append("")
    with open(os.path.join(VAULT, "_profile.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L).rstrip() + "\n")


# --- Obsidian views --------------------------------------------------------

MERMAID_CLASSES = """\
  classDef solid fill:#2e7d32,stroke:#1b5e20,color:#fff
  classDef known fill:#66bb6a,stroke:#2e7d32,color:#fff
  classDef assumed fill:#c8e6c9,stroke:#81c784,color:#1b5e20
  classDef shaky fill:#ffb300,stroke:#e65100,color:#000
  classDef missing fill:#e53935,stroke:#b71c1c,color:#fff
  classDef unknown fill:#eceff1,stroke:#90a4ae,color:#455a64"""


def _mid(nid):
    return "n_" + re.sub(r"[^A-Za-z0-9_]", "_", nid)


def _mlabel(s):
    return str(s).replace('"', "'")


def mermaid_graph(t, only=None):
    ids = [n for n in topo_order(t) if only is None or n in only]
    if not ids:
        return ""
    lines = ["```mermaid", "graph TD"]
    for n in ids:
        v = t["nodes"][n]
        m = node_metrics(v)
        text = _mlabel(v.get("label", n)) + ("" if m["mastery"] is None else f"<br/>{round(m['mastery'] * 100)}%")
        lines.append(f'  {_mid(n)}(["{text}"])' if v.get("target") else f'  {_mid(n)}["{text}"]')
    for n in ids:
        for d in t["nodes"][n].get("deps", []):
            if d in ids:
                lines.append(f"  {_mid(d)} --> {_mid(n)}")
    lines.append(MERMAID_CLASSES)
    for n in ids:
        lines.append(f"  class {_mid(n)} {node_metrics(t['nodes'][n])['status']}")
    lines.append("```")
    return "\n".join(lines)


def calibration_table(entries, s):
    """Right answers per declared confidence, from the log. It tells the
    learner whether their own "sure" can be trusted: the part of studying
    that is knowing what you don't know."""
    entries = [e for e in entries if e.get("kind") != "pretest"]
    rows = []
    for conf in CONFIDENCE:
        got = [e for e in entries if e.get("confidence") == conf]
        if got:
            right = sum(1 for e in got if e.get("correct"))
            rows.append(f"| {s('conf.' + conf)} | {right}/{len(got)} | "
                        f"`{_bar(right / len(got), 10)}` {round(100 * right / len(got))}% |")
    if not rows:
        return []
    return [f"## {s('calibration')}", "", s("calibration_legend"), "",
            f"| {s('confidence')} | {s('right')} | % |", "|---|---|---|", *rows, ""]


def _bar(share, width=20):
    full = round(share * width)
    return "█" * full + "░" * (width - full)


def render_topic(t):
    L_ = t.get("lang", "en")
    s = lambda k: tr(L_, k)  # noqa: E731
    share, _, misc = progress(t)
    L = ["---", f"topic: {t['slug']}", f"phase: {t['phase']}", f"mastery: {round(share * 100)}",
         "cssclasses: [docet-course]", "---", f"# {t['title']}", ""]
    if t.get("goal"):
        L += [f"> [!abstract] {s('goal')}", f"> {t['goal']}", ""]
    L += [f"**{s('phase')}:** {s('phase.' + t['phase'])} · **{s('mastery')}:** "
          f"`{_bar(share)}` {round(share * 100)}% ({s('exit_at')} {round(EXIT_SHARE * 100)}%)", ""]
    if misc:
        L += [f"> [!warning] {s('misconceptions_open')}",
              "> " + ", ".join(t["nodes"][n]["label"] for n in misc), ""]

    if t["nodes"]:
        L += [f"## {s('map')}", "", s("map_legend"), "", mermaid_graph(t), ""]

    if t["blocks"]:
        L += [f"## {s('course')}", ""]
        icon = {"todo": "○", "doing": "◐", "done": "●"}
        badge_of = lambda test: {  # noqa: E731
            "passed": f"✓ {round(test.get('score', 0) * 100)}%",
            "redo": f"✗ {round(test.get('score', 0) * 100)}% — {s('redo')}",
        }.get(test.get("status"), s("todo"))
        for b in t["blocks"]:
            L += [f"### {b['title']}", ""]
            for les in b["lessons"]:
                name = f"[[{les['file']}|{les['title']}]]" if les.get("file") else les["title"]
                tag = f" *({s('reinforcement')})*" if les["kind"] == "reinforcement" else ""
                L.append(f"- {icon.get(les['status'], '○')} {name}{tag}")
                if les.get("note") and les["status"] != "done":
                    L.append(f"    - *{les['note']}*")
            L.append(f"- 📝 {s('chapter_test')}: {badge_of(b['test'])}")
            if os.path.exists(_synth_file(t, b["id"])):
                L.append(f"- 🧾 [[{t['slug']}/synthesis-{b['id']}|{s('synthesis')}]]")
            L.append("")
        L += [f"**{s('final_test')}:** {badge_of(t['final'])}", ""]
        if os.path.exists(_synth_file(t, "all")):
            L += [f"**{s('synthesis')}:** [[{t['slug']}/synthesis|{t['title']}]]", ""]

    if t["nodes"]:
        L += [f"## {s('concepts')}", "",
              f"| {s('concept')} | {s('status')} | {s('mastery')} | {s('last_answer')} |",
              "|---|---|---|---|"]
        for n in topo_order(t):
            v = t["nodes"][n]
            m = node_metrics(v)
            pct = "—" if m["mastery"] is None else f"{round(m['mastery'] * 100)}%"
            last = ""
            if v.get("evidence"):
                e = v["evidence"][-1]
                last = f"{e['q']} {'✓' if e['correct'] else '✗'} {e.get('error') or ''}".strip()
            warn = " ⚠" if m["open_misconception"] else ""
            L.append(f"| {v.get('label', n)} | {s(m['status'])}{warn} | {pct} | {last} |")
        L.append("")

    L += calibration_table(read_log(t["slug"]), s)

    # Always at the bottom: how to drive the course, and what the files are.
    L += [f"## {s('commands')}", "", s("commands_legend"), "",
          f"| {s('commands')} | {s('cmd.what')} |", "|---|---|",
          f"| `/docet:next` | {s('cmd.next')} |",
          f"| `/docet:stop` | {s('cmd.stop')} |",
          f"| `/docet:start <…>` | {s('cmd.start')} |", "",
          f"**{s('files')}**", "",
          f"- `entry-test` — {s('file.entry')}",
          f"- `01-…`, `02-…` — {s('file.lesson')}",
          f"- `chapter-test-…`, `final-test` — {s('file.tests')}",
          f"- `synthesis-…` — {s('file.synth')}", ""]

    path = os.path.join(VAULT, t["slug"], "_course.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L).rstrip() + "\n")


def vault_lang(ts):
    """Language of the vault-wide pages: $DOCET_LANG, else the active topic's."""
    if os.environ.get("DOCET_LANG"):
        return os.environ["DOCET_LANG"]
    act = read_active()
    for t in ts:
        if t["slug"] == act:
            return t.get("lang", "en")
    return ts[-1].get("lang", "en") if ts else "en"


def render_global(ts, lang):
    s = lambda k: tr(lang, k)  # noqa: E731
    L = ["---", "cssclasses: [docet-course]", "---", f"# {s('map_title')}", ""]
    if not ts:
        L.append(s("map_empty"))
    else:
        L += [f"| {s('topic')} | {s('phase')} | {s('mastery')} | {s('reviews_due')} |", "|---|---|---|---|"]
        for t in ts:
            share, _, _ = progress(t)
            L.append(f"| [[{t['slug']}/_course\\|{t['title']}]] | {s('phase.' + t['phase'])} | "
                     f"`{_bar(share, 10)}` {round(share * 100)}% | {len(due_reviews(t))} |")
        L.append("")
        header_done = False
        for t in ts:
            weak = [n for n in t["nodes"] if status_of(t, n) in ("shaky", "missing")]
            if not weak:
                continue
            if not header_done:
                L += [f"## {s('thin')}", "", s("thin_legend"), ""]
                header_done = True
            keep = set(weak)
            for n in weak:
                keep |= set(t["nodes"][n].get("deps", []))
            L += [f"### {t['title']}", "", mermaid_graph(t, only=keep), ""]
        L += calibration_table(read_log(), s)
    with open(os.path.join(VAULT, "_map.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L).rstrip() + "\n")


def render_reviews(ts, lang):
    s = lambda k: tr(lang, k)  # noqa: E731
    L = ["---", "cssclasses: [docet-course]", "---", f"# {s('review_title')}", "",
         s("review_legend").format(steps=", ".join(str(d) for d in REVIEW_STEPS)), ""]
    d = today().isoformat()
    rows = sorted(((v["review"]["due"], t, n, v) for t in ts for n, v in t["nodes"].items()
                   if v.get("review")), key=lambda x: x[0])
    due = [r for r in rows if r[0] <= d]
    later = [r for r in rows if r[0] > d]
    L += [f"## {s('review_today')}", ""]
    L += [f"- **{v.get('label', n)}** — [[{t['slug']}/_course|{t['title']}]]" for _, t, n, v in due] \
        or [s("nothing")]
    L += ["", f"## {s('review_next')}", ""]
    L += [f"- {due_d} · {v.get('label', n)} — {t['title']}" for due_d, t, n, v in later[:30]] \
        or [s("nothing_queued")]
    with open(os.path.join(VAULT, "_review.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L).rstrip() + "\n")


def render_all():
    os.makedirs(VAULT, exist_ok=True)
    ts = all_topics()
    for t in ts:
        render_topic(t)
    lang = vault_lang(ts)
    render_global(ts, lang)
    render_reviews(ts, lang)
    render_profile(ts, lang)


def cmd_render(_a):
    render_all()
    print(f"views rebuilt in {VAULT}")


# --- CLI -------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(prog="docet.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--topic", help="topic slug (default: the active one)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new", help="create a topic and make it active")
    s.add_argument("slug")
    s.add_argument("--title")
    s.add_argument("--goal")
    s.add_argument("--lang", default="en", help="learner's language, e.g. en, it (default en)")
    s.add_argument("--familiarity", choices=FAMILIARITY,
                   help="how well they know it: never/heard = teach me (the topic is never probed)")
    s.add_argument("--entry", choices=list(ENTRY_STYLES),
                   help=f"quick: foundations only, ≤{ENTRY_QUICK} · skip: straight to the course · "
                        f"full: from the top, ≤{ENTRY_MAX} (default: quick when learning, else full)")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("entry", help="change how the entry test runs (skip ends it now)")
    s.add_argument("style", choices=list(ENTRY_STYLES))
    s.add_argument("--familiarity", choices=FAMILIARITY)
    s.set_defaults(fn=cmd_entry)

    s = sub.add_parser("profile", help="the learner across topics: declared and measured")
    s.add_argument("--background", help="studies, work: what a lesson can take for granted")
    s.add_argument("--strong", help="what they know well, in any field: a source of bridges")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_profile)

    s = sub.add_parser("use", help="make an existing topic active")
    s.add_argument("slug")
    s.set_defaults(fn=cmd_use)

    sub.add_parser("plan", help="graph/course from stdin (JSON)").set_defaults(fn=cmd_plan)
    sub.add_parser("ask", help="commit questions from stdin (JSON)").set_defaults(fn=cmd_ask)
    sub.add_parser("grade", help="grade answers from stdin (JSON)").set_defaults(fn=cmd_grade)

    s = sub.add_parser("lesson", help="mark a lesson started or done")
    s.add_argument("id")
    s.add_argument("action", choices=["start", "done"])
    s.add_argument("--file", help="Obsidian note of the lesson (no .md)")
    s.set_defaults(fn=cmd_lesson)

    s = sub.add_parser("note", help="set (or clear) the note of a lesson")
    s.add_argument("id")
    s.add_argument("text", nargs="?", default="")
    s.set_defaults(fn=cmd_note)

    s = sub.add_parser("synth", help="write the synthesis page of a block, or 'all'")
    s.add_argument("scope", help="block id, or 'all' for the whole topic")
    s.set_defaults(fn=cmd_synth)

    s = sub.add_parser("archive", help="put a topic aside (nothing is deleted)")
    s.add_argument("slug")
    s.set_defaults(fn=cmd_archive)

    s = sub.add_parser("test-end", help="close a chapter test or the final test")
    s.add_argument("which", help="block id, or 'final'")
    s.set_defaults(fn=cmd_test_end)

    s = sub.add_parser("drop", help="discard committed questions never written to a file")
    s.add_argument("ids", nargs="+")
    s.set_defaults(fn=cmd_drop)

    sub.add_parser("next", help="what to do now").set_defaults(fn=cmd_next)
    s = sub.add_parser("show", help="topic state")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_show)
    sub.add_parser("status", help="all topics").set_defaults(fn=cmd_status)
    sub.add_parser("render", help="rebuild the Obsidian views").set_defaults(fn=cmd_render)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
