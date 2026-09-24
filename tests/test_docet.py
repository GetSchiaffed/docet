"""Engine tests: `python3 -m unittest discover tests`.

Every test runs in a temporary vault, so `vault/` is never touched.
"""

import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest

DOCET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "docet.py")


def b64(s):
    return base64.b64encode(s.encode()).decode()


class Vault(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(os.environ, DOCET_VAULT=self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_s(self, *args, stdin=None, ok=True):
        p = subprocess.run([sys.executable, DOCET, *args], input=stdin, text=True,
                           capture_output=True, env=self.env)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def ask(self, node, kind="check", block=None, right="A · yes", lesson=None):
        q = {"node": node, "kind": kind, "block": block, "lesson": lesson,
             "options": ["A · yes", "B · no"], "key": b64(right)}
        return self.run_s("ask", stdin=json.dumps(q)).stdout.splitlines()[0].split()[-1]

    def grade(self, q, answer, confidence="sure", error="gap"):
        g = {"q": q, "answer": answer, "confidence": confidence, "error": error}
        return self.run_s("grade", stdin=json.dumps(g)).stdout

    def fill_synth(self, scope):
        """What the model does after `synth`: replace every ✎ placeholder."""
        self.run_s("synth", scope)
        name = "synthesis.md" if scope == "all" else f"synthesis-{scope}.md"
        path = os.path.join(self.tmp.name, "t", name)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace("%% ✎", "%% done"))

    def state(self):
        return json.loads(self.run_s("show", "--json").stdout)

    def graph(self):
        self.run_s("new", "t", "--title", "T")
        self.run_s("plan", stdin=json.dumps({"nodes": [
            {"id": "base", "label": "base"},
            {"id": "middle", "label": "middle", "deps": ["base"]},
            {"id": "other", "label": "other"},
            {"id": "top", "label": "top", "deps": ["middle", "other"], "target": True},
        ]}))


class TestEntry(Vault):
    def test_descends_only_where_it_fails(self):
        self.graph()
        self.assertIn("targets: top", self.run_s("next").stdout)
        self.grade(self.ask("top", "probe"), "B · no")
        out = self.run_s("next").stdout
        self.assertIn("prerequisites: middle, other", out)
        self.grade(self.ask("middle", "probe"), "A · yes")
        self.grade(self.ask("other", "probe"), "B · no")
        st = self.state()["metrics"]
        self.assertEqual(st["base"]["status"], "assumed")   # below a yes: not probed
        self.assertEqual(st["middle"]["status"], "known")
        self.assertIn("ENTRY COMPLETE", self.run_s("next").stdout)

    def test_unsure_hit_does_not_hide_a_failed_prerequisite(self):
        # Found in the first real run: an unsure right answer high up made
        # everything below "assumed", including the prerequisites of a
        # concept that had just failed, and the descent stopped.
        self.graph()
        self.grade(self.ask("top", "probe"), "B · no")
        self.grade(self.ask("other", "probe"), "A · yes", confidence="unsure")
        self.assertEqual(self.state()["metrics"]["base"]["status"], "unknown")
        self.grade(self.ask("middle", "probe"), "B · no")
        self.assertIn("prerequisites: base", self.run_s("next").stdout)

    def test_assumed_prerequisite_of_a_failed_concept_is_probed(self):
        self.run_s("new", "t", "--title", "T")
        self.run_s("plan", stdin=json.dumps({"nodes": [
            {"id": "base", "label": "base"},
            {"id": "a", "label": "a", "deps": ["base"], "target": True},
            {"id": "b", "label": "b", "deps": ["base"], "target": True},
        ]}))
        self.grade(self.ask("a", "probe"), "A · yes")      # sure: base becomes assumed
        self.grade(self.ask("b", "probe"), "B · no")       # but b, resting on base, fails
        self.assertIn("prerequisites: base", self.run_s("next").stdout)

    def test_wrong_key_does_not_leak_the_answer(self):
        self.graph()
        q = {"node": "top", "kind": "probe", "options": ["A · x", "B · y"], "key": b64("none")}
        p = self.run_s("ask", stdin=json.dumps(q), ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("matches no option", p.stderr)
        self.assertNotIn("A · x", p.stderr)

    def test_free_answer_needs_a_verdict(self):
        self.graph()
        q = self.ask("top", "probe")
        p = self.run_s("grade", stdin=json.dumps({"q": q, "answer": "no idea"}), ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.run_s("grade", stdin=json.dumps({"q": q, "answer": "no idea", "verdict": "wrong"}))
        self.assertEqual(self.state()["metrics"]["top"]["status"], "missing")


# The real eigenvectors run: 7 targets resting on a few school foundations.
EIGEN = [
    {"id": "matrix-vector", "label": "matrix times vector"},
    {"id": "det-2x2", "label": "2x2 determinant"},
    {"id": "quadratic", "label": "quadratic equation"},
    {"id": "homogeneous", "label": "homogeneous systems"},
    {"id": "det-zero", "label": "det = 0 means non-trivial solutions", "deps": ["det-2x2", "homogeneous"]},
    {"id": "eigen-def", "label": "eigenvector", "deps": ["matrix-vector"], "target": True},
    {"id": "eigen-geometric", "label": "geometric meaning", "deps": ["eigen-def"], "target": True},
    {"id": "char-eq", "label": "characteristic equation", "deps": ["eigen-def", "det-zero"], "target": True},
    {"id": "eigenvalues-2x2", "label": "eigenvalues 2x2", "deps": ["char-eq", "quadratic"], "target": True},
    {"id": "eigenvalues-3x3", "label": "eigenvalues 3x3", "deps": ["char-eq"], "target": True},
    {"id": "eigenspace", "label": "eigenspace", "deps": ["eigen-def", "homogeneous"], "target": True},
    {"id": "multiplicity", "label": "multiplicity", "deps": ["eigenvalues-3x3", "eigenspace"], "target": True},
]


class TestFluidEntry(Vault):
    """"Teach me X" and "help me with X" start differently, and neither is long."""

    def eigen(self, *new_args):
        self.run_s("new", "t", "--title", "Eigenvectors", *new_args)
        self.run_s("plan", stdin=json.dumps({"nodes": EIGEN}))

    def probe_until_done(self, answer="B · no", confidence="guess"):
        """Answer every probe the engine asks for, the way the real run did."""
        asked = []
        for _ in range(30):
            out = self.run_s("next").stdout
            if "ENTRY COMPLETE" in out:
                return asked, out
            node = out.split(": ", 1)[1].split(" (")[0].split(", ")[0].strip()
            asked.append(node)
            self.grade(self.ask(node, "probe"), answer, confidence=confidence)
        self.fail("the entry test never ended")

    def targets(self):
        return {n["id"] for n in EIGEN if n.get("target")}

    def test_learning_never_asks_about_the_topic(self):
        self.eigen("--familiarity", "never")
        asked, out = self.probe_until_done()
        self.assertFalse(set(asked) & self.targets(), asked)
        self.assertLessEqual(len(asked), 5)
        # everything the learner asked to be taught is in the course
        for n in self.targets():
            self.assertIn(n, out)

    def test_learning_climbs_from_the_easiest(self):
        self.eigen("--familiarity", "heard")
        out = self.run_s("next").stdout
        self.assertIn("probe the foundations", out)
        self.assertNotIn("det-zero", out)          # rests on unchecked foundations: not yet
        self.grade(self.ask("det-2x2", "probe"), "A · yes")
        self.grade(self.ask("homogeneous", "probe"), "A · yes")
        self.assertIn("det-zero", self.run_s("next").stdout)

    def test_skip_goes_straight_to_the_course(self):
        self.eigen("--familiarity", "never", "--entry", "skip")
        out = self.run_s("next").stdout
        self.assertIn("ENTRY COMPLETE (entry test skipped)", out)
        self.assertIn("NOT CHECKED", out)
        self.assertEqual(len([e for e in self.state()["nodes"].values() if e["evidence"]]), 0)

    def test_skip_halfway(self):
        self.eigen()
        self.grade(self.ask("eigen-def", "probe"), "A · yes")
        self.run_s("entry", "skip")
        self.assertIn("ENTRY COMPLETE (entry test skipped)", self.run_s("next").stdout)

    def test_unchecked_prerequisite_is_asked_before_the_lesson(self):
        self.eigen("--familiarity", "never", "--entry", "skip")
        self.run_s("plan", stdin=json.dumps({"blocks": [{"id": "b1", "lessons": [
            {"id": "L1", "nodes": ["eigen-def"]}]}]}))
        out = self.run_s("next").stdout
        self.assertIn("CHECK FIRST — never checked: matrix-vector", out)
        self.grade(self.ask("matrix-vector", "probe"), "A · yes")
        self.assertNotIn("CHECK FIRST", self.run_s("next").stdout)

    def test_improving_is_capped_and_skips_what_rests_on_a_failure(self):
        self.eigen("--familiarity", "some")
        # the real run: the definition itself failed, answered with conviction
        self.grade(self.ask("eigen-def", "probe"), "B · no", confidence="sure", error="misconception")
        for n in self.targets() - {"eigen-def"}:
            self.assertEqual(self.state()["metrics"][n]["status"], "missing", n)
        asked, _ = self.probe_until_done()
        self.assertFalse(set(asked) & self.targets(), asked)   # no more questions on the topic
        self.assertLessEqual(len(asked) + 1, 10)

    def test_hard_cap(self):
        self.run_s("new", "t", "--title", "T")
        self.run_s("plan", stdin=json.dumps({"nodes": [
            {"id": f"n{i}", "label": f"n{i}", "target": True} for i in range(14)]}))
        asked, out = self.probe_until_done(answer="A · yes", confidence="sure")
        self.assertEqual(len(asked), 10)
        self.assertIn("(10 questions: the limit)", out)

    def test_two_misses_on_the_foundations_stop(self):
        self.eigen("--familiarity", "never")
        asked, out = self.probe_until_done()
        self.assertEqual(len(asked), 2)
        self.assertIn("misses in a row", out)

    def test_solid_declared_goes_to_the_final_test(self):
        self.eigen("--familiarity", "solid")
        out = self.run_s("next").stdout
        self.assertIn("ENTRY COMPLETE — nothing to teach", out)
        self.assertIn("FINAL TEST", out)
        self.assertIn("FINAL TEST", self.run_s("next").stdout)

    def test_changing_mind_probes_the_topic_again(self):
        self.eigen("--familiarity", "never")
        self.run_s("entry", "full", "--familiarity", "some")
        self.assertIn("probe the targets", self.run_s("next").stdout)
        self.run_s("entry", "full", "--familiarity", "solid")
        self.assertEqual(self.state()["metrics"]["eigen-def"]["status"], "assumed")


class TestProfile(Vault):
    def test_declared_and_measured(self):
        self.graph()
        self.run_s("profile", "--background", "economics degree", "--strong", "chess")
        self.grade(self.ask("top", "probe"), "B · no")
        prof = json.loads(self.run_s("profile", "--json").stdout)
        self.assertEqual(prof["background"], "economics degree")
        self.assertEqual(prof["measured"]["answers"], 1)
        self.assertEqual(prof["measured"]["entry_right"], 0)
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "_profile.md")))

    def test_a_concept_solid_elsewhere_is_not_asked_again(self):
        self.graph()
        self.grade(self.ask("other", "probe"), "A · yes")          # known in topic t
        self.run_s("new", "u", "--title", "U")
        out = self.run_s("plan", stdin=json.dumps({"nodes": [
            {"id": "other", "label": "other"},
            {"id": "goal", "label": "goal", "deps": ["other"], "target": True}]})).stdout
        self.assertIn("already solid in another topic, taken as known: other", out)
        st = self.state()
        self.assertEqual(st["metrics"]["other"]["status"], "assumed")
        self.assertEqual(st["nodes"]["other"]["carried"], "t")


class TestMastery(Vault):
    def test_guess_does_not_count(self):
        self.graph()
        for _ in range(3):
            self.grade(self.ask("other"), "A · yes", confidence="guess")
        self.assertNotEqual(self.state()["metrics"]["other"]["status"], "solid")

    def test_right_retry_means_slip(self):
        self.graph()
        self.grade(self.ask("other"), "A · yes")
        self.grade(self.ask("other"), "B · no")
        out = self.grade(self.ask("other", "retry"), "A · yes")
        self.assertIn("slip", out)
        self.assertEqual(self.state()["metrics"]["other"]["status"], "solid")

    def test_right_retry_does_not_erase_a_misconception(self):
        # Found in the first real run: the retry comes after the correction,
        # so a right retry proves the explanation landed, not a slip.
        self.graph()
        self.grade(self.ask("other"), "B · no", error="misconception")
        out = self.grade(self.ask("other", "retry"), "A · yes")
        self.assertNotIn("was a slip", out)
        st = self.state()
        self.assertEqual(st["nodes"]["other"]["evidence"][0]["error"], "misconception")
        self.assertTrue(st["metrics"]["other"]["open_misconception"])

    def test_wrong_retry_lowers_the_bar(self):
        self.graph()
        self.grade(self.ask("middle"), "B · no")
        out = self.grade(self.ask("middle", "retry"), "B · no")
        self.assertIn("lower the bar", out)
        self.assertIn("base", out)

    def test_misconception_stays_open(self):
        self.graph()
        self.grade(self.ask("other"), "B · no", error="misconception")
        self.grade(self.ask("other"), "A · yes")
        self.assertTrue(self.state()["metrics"]["other"]["open_misconception"])
        self.grade(self.ask("other"), "A · yes")
        self.assertFalse(self.state()["metrics"]["other"]["open_misconception"])


class TestCourse(Vault):
    def plan(self):
        self.graph()
        self.run_s("plan", stdin=json.dumps({"blocks": [
            {"id": "b1", "title": "One", "lessons": [{"id": "l1", "title": "L1", "nodes": ["other"]}]},
        ]}))

    def test_failed_chapter_adds_reinforcement(self):
        self.plan()
        self.run_s("lesson", "l1", "done")
        self.assertIn("CHAPTER TEST b1", self.run_s("next").stdout)
        self.grade(self.ask("other", "chapter", "b1"), "B · no")
        out = self.run_s("test-end", "b1").stdout
        self.assertIn("to redo", out)
        self.assertIn("REINFORCEMENT b1-r1", self.run_s("next").stdout)

    def test_exit_at_80_percent(self):
        self.plan()
        self.run_s("lesson", "l1", "done")
        for n in ("other", "top"):
            for _ in range(2):
                self.grade(self.ask(n), "A · yes")
        self.grade(self.ask("other", "chapter", "b1"), "A · yes")
        self.run_s("test-end", "b1")
        self.assertIn("SYNTHESIS b1", self.run_s("next").stdout)
        self.fill_synth("b1")
        self.assertIn("FINAL TEST", self.run_s("next").stdout)
        for n in ("other", "top"):
            self.grade(self.ask(n, "final"), "A · yes")
        self.assertIn("goal reached", self.run_s("test-end", "final").stdout)
        self.assertEqual(self.state()["phase"], "done")

    def test_views_are_rendered(self):
        self.plan()
        for f in ("_map.md", "_review.md", os.path.join("t", "_course.md")):
            self.assertTrue(os.path.isfile(os.path.join(self.tmp.name, f)), f)

    def test_views_follow_topic_language(self):
        self.run_s("new", "t", "--title", "T", "--lang", "it")
        self.run_s("plan", stdin=json.dumps({"nodes": [{"id": "a", "label": "a", "target": True}]}))
        with open(os.path.join(self.tmp.name, "t", "_course.md"), encoding="utf-8") as fh:
            page = fh.read()
        self.assertIn("## Mappa", page)
        self.assertIn("non sondato", page)

    def test_cycle_rejected(self):
        self.graph()
        p = self.run_s("plan", stdin=json.dumps({"nodes": [{"id": "base", "deps": ["top"]}]}), ok=False)
        self.assertIn("cycle", p.stderr)


class TestOptions(Vault):
    def test_engine_spreads_the_right_answer(self):
        # A model left alone puts the right answer on A or B: the engine
        # shuffles, so every position gets its share.
        self.graph()
        qs = [{"node": "top", "options": ["w", "x", "y", "z"], "key": b64("w")}] * 200
        out = self.run_s("ask", stdin=json.dumps(qs)).stdout.splitlines()[1:]
        pos = [next(o[0] for o in line.split(": ", 1)[1].split(" | ") if o.endswith("· w"))
               for line in out]
        for letter in "ABCD":
            self.assertTrue(20 <= pos.count(letter) <= 80, (letter, pos.count(letter)))

    def test_fixed_order_on_request(self):
        self.graph()
        q = {"node": "top", "options": ["1", "2", "3"], "key": b64("2"), "shuffle": False}
        self.assertIn("A · 1 | B · 2 | C · 3", self.run_s("ask", stdin=json.dumps(q)).stdout)

    def test_graded_on_text_not_letter(self):
        self.graph()
        q = {"node": "top", "options": ["A · yes", "B · no"], "key": b64("A · yes")}
        qid = self.run_s("ask", stdin=json.dumps(q)).stdout.split()[1]
        self.assertIn("✓", self.grade(qid, "yes"))

    def test_duplicate_options_rejected(self):
        self.graph()
        q = {"node": "top", "options": ["same", "Same"], "key": b64("same")}
        self.assertIn("same text", self.run_s("ask", stdin=json.dumps(q), ok=False).stderr)


class TestNumeric(Vault):
    def ask_num(self, key, tol=0.01):
        q = {"node": "top", "type": "numeric", "key": b64(key), "tol": tol}
        return self.run_s("ask", stdin=json.dumps(q)).stdout.split()[1]

    def test_within_tolerance(self):
        self.graph()
        self.assertIn("✓", self.grade(self.ask_num("3.1416"), "3.14"))
        self.assertIn("✓", self.grade(self.ask_num("3.1416"), "3,1416"))   # decimal comma
        self.assertIn("✓", self.grade(self.ask_num("0.5", tol=0), "1/2"))
        out = self.grade(self.ask_num("3.1416"), "3.2")
        self.assertIn("✗", out)
        self.assertIn("correct: 3.1416", out)

    def test_trap_value_is_a_misconception(self):
        # 13 instead of 2.6: the direction vector was not normalised.
        self.graph()
        q = {"node": "top", "type": "numeric", "key": b64("2.6"), "tol": 0.01, "traps": [b64("13")]}
        qid = self.run_s("ask", stdin=json.dumps(q)).stdout.split()[1]
        out = self.grade(qid, "13", error="gap")
        self.assertIn("misconception", out)
        self.assertIn("known wrong model", out)
        q["traps"] = [b64("13")]
        qid = self.run_s("ask", stdin=json.dumps(q)).stdout.split()[1]
        self.assertIn("gap", self.grade(qid, "7", error="gap"))

    def test_key_must_be_a_number(self):
        self.graph()
        q = {"node": "top", "type": "numeric", "key": b64("pi")}
        p = self.run_s("ask", stdin=json.dumps(q), ok=False)
        self.assertIn("not a number", p.stderr)
        self.assertNotIn("pi", p.stderr.replace("re-encode", ""))

    def test_non_number_is_a_free_answer(self):
        self.graph()
        qid = self.ask_num("2")
        p = self.run_s("grade", stdin=json.dumps({"q": qid, "answer": "no idea"}), ok=False)
        self.assertIn("verdict", p.stderr)
        self.run_s("grade", stdin=json.dumps({"q": qid, "answer": "no idea", "verdict": "wrong"}))


class TestInterruptions(Vault):
    def test_unanswered_question_survives_a_break(self):
        self.graph()
        self.run_s("plan", stdin=json.dumps({"blocks": [
            {"id": "b1", "title": "One", "lessons": [{"id": "l1", "title": "L1", "nodes": ["other"]}]}]}))
        self.run_s("lesson", "l1", "start", "--file", "t/01-l1")
        q = self.ask("other", lesson="l1")
        out = self.run_s("next").stdout           # a new session, no memory
        self.assertIn(f"LOST — committed but never written to any file: {q}", out)
        os.makedirs(os.path.join(self.tmp.name, "t"), exist_ok=True)
        with open(os.path.join(self.tmp.name, "t", "01-l1.md"), "w", encoding="utf-8") as fh:
            fh.write(f"> [!quiz] {q} · other\n")
        out = self.run_s("next").stdout
        self.assertIn(f"OPEN — committed, not answered yet (already in the file): {q}", out)
        self.assertIn("file: t/01-l1.md", out)
        self.assertNotIn(b64("A · yes"), out)     # never the key
        self.grade(q, "A · yes")
        self.assertNotIn("OPEN", self.run_s("next").stdout)

    def test_lost_question_is_dropped_without_a_grade(self):
        self.graph()
        q = self.ask("other")
        self.assertIn("dropped", self.run_s("drop", q).stdout)
        self.assertEqual(self.state()["nodes"]["other"]["evidence"], [])
        self.assertNotIn("LOST", self.run_s("next").stdout)


class TestHousekeeping(Vault):
    def test_note_without_replanning(self):
        self.graph()
        self.run_s("plan", stdin=json.dumps({"blocks": [
            {"id": "b1", "title": "One", "lessons": [{"id": "l1", "title": "L1", "nodes": ["other"]}]}]}))
        self.run_s("note", "l1", "one more example")
        self.assertEqual(self.state()["blocks"][0]["lessons"][0]["note"], "one more example")

    def test_archive_keeps_notes_and_leaves_the_views(self):
        self.graph()
        note = os.path.join(self.tmp.name, "t", "01-x.md")
        with open(note, "w", encoding="utf-8") as fh:
            fh.write("mine")
        self.run_s("archive", "t")
        self.assertTrue(os.path.isfile(note))
        self.assertTrue(os.path.isfile(os.path.join(self.tmp.name, ".docet", "archive", "t.json")))
        self.assertEqual(self.run_s("status").stdout.strip(), "no topics")


class TestSynthesis(Vault):
    def test_mistakes_come_from_the_log(self):
        self.graph()
        self.run_s("plan", stdin=json.dumps({"blocks": [
            {"id": "b1", "title": "One", "lessons": [{"id": "l1", "title": "L1", "nodes": ["other"]}]}]}))
        q = self.ask("other")
        with open(os.path.join(self.tmp.name, "t", "01-l1.md"), "w", encoding="utf-8") as fh:
            fh.write(f"> [!quiz] {q} · other\n")
        self.grade(q, "B · no", error="misconception")
        self.grade(self.ask("top"), "B · no", error="misconception")   # other block: left out
        out = self.run_s("synth", "b1").stdout
        self.assertIn("1 misconception", out)
        with open(os.path.join(self.tmp.name, "t", "synthesis-b1.md"), encoding="utf-8") as fh:
            page = fh.read()
        self.assertIn("> [!warning] other — still open", page)
        self.assertIn(f"> [[01-l1|{q}]] · your answer: «B · no»", page)
        self.assertIn("```mermaid", page)
        self.assertGreaterEqual(page.count("\n---\n"), 5)            # slides
        self.assertIn("exists, not overwritten", self.run_s("synth", "b1").stdout)

    def test_course_page_has_the_commands_legend(self):
        self.run_s("new", "t", "--title", "T", "--lang", "it")
        with open(os.path.join(self.tmp.name, "t", "_course.md"), encoding="utf-8") as fh:
            page = fh.read()
        self.assertIn("## Comandi", page)
        self.assertIn("`/docet:next`", page)
        self.assertIn("`synthesis-…`", page)


class TestPace(Vault):
    def test_too_hard_and_too_easy(self):
        self.graph()
        for _ in range(7):
            self.grade(self.ask("other"), "B · no")
        out = self.grade(self.ask("other"), "B · no")
        self.assertIn("PACE — 0/8 right lately: too hard", out)
        for _ in range(7):
            self.grade(self.ask("other"), "A · yes")
        out = self.grade(self.ask("other"), "A · yes")
        self.assertIn("too easy", out)

    def test_entry_test_does_not_count(self):
        self.graph()
        for _ in range(8):
            out = self.grade(self.ask("other", "probe"), "B · no")
        self.assertNotIn("PACE", out)


class TestPrerequisites(Vault):
    def test_shaky_prerequisite_is_flagged_before_the_lesson(self):
        self.graph()
        self.run_s("plan", stdin=json.dumps({"blocks": [
            {"id": "b1", "title": "One", "lessons": [{"id": "l1", "title": "L1", "nodes": ["middle"]}]}]}))
        self.grade(self.ask("base"), "A · yes")
        self.grade(self.ask("base"), "B · no")                 # base: shaky again
        out = self.run_s("next").stdout
        self.assertIn("PREREQUISITE — not holding any more: base", out)
        self.assertIn("LESSON l1", out)


class TestPractice(Vault):
    def graph_proc(self):
        self.run_s("new", "t", "--title", "T")
        self.run_s("plan", stdin=json.dumps({
            "nodes": [{"id": "calc", "label": "calc", "kind": "procedural", "target": True}],
            "blocks": [{"id": "b1", "title": "One", "lessons": [{"id": "l1", "title": "L1", "nodes": ["calc"]}]}]}))

    def ask_num(self, kind="check", block=None):
        q = {"node": "calc", "kind": kind, "block": block, "type": "numeric", "key": b64("4")}
        return self.run_s("ask", stdin=json.dumps(q)).stdout.split()[1]

    def test_procedure_needs_a_produced_answer(self):
        self.graph_proc()
        for _ in range(3):
            self.grade(self.ask("calc"), "A · yes")
        self.assertEqual(self.state()["metrics"]["calc"]["status"], "shaky")
        self.grade(self.ask_num(), "4")
        self.assertEqual(self.state()["metrics"]["calc"]["status"], "solid")

    def test_practice_set_after_the_synthesis(self):
        self.graph_proc()
        self.run_s("lesson", "l1", "done")
        self.grade(self.ask_num("chapter", "b1"), "4")
        self.run_s("test-end", "b1")
        self.fill_synth("b1")
        self.assertIn("PRACTICE b1 — 5 more", self.run_s("next").stdout)
        for _ in range(5):
            self.grade(self.ask_num("practice", "b1"), "4")
        self.assertIn("FINAL TEST", self.run_s("next").stdout)


class TestRecall(Vault):
    def test_recall_has_no_key_and_needs_a_verdict(self):
        self.graph()
        q = self.run_s("ask", stdin=json.dumps({"node": "top", "kind": "review", "type": "recall"})).stdout
        qid = q.split()[1]
        self.assertIn("typed answer", q)
        p = self.run_s("grade", stdin=json.dumps({"q": qid, "answer": "f is ..."}), ok=False)
        self.assertIn("verdict", p.stderr)
        self.run_s("grade", stdin=json.dumps({"q": qid, "answer": "f is ...", "verdict": "right",
                                              "confidence": "sure"}))


class TestReview(Vault):
    def make_due(self, node):
        path = os.path.join(self.tmp.name, ".docet", "t.json")
        with open(path, encoding="utf-8") as fh:
            t = json.load(fh)
        t["nodes"][node]["review"]["due"] = "2000-01-01"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(t, fh)
        return t["nodes"][node]["review"]

    def test_firm_from_the_start_skips_the_first_interval(self):
        self.graph()
        self.grade(self.ask("other"), "A · yes")
        self.grade(self.ask("other"), "A · yes")
        self.assertEqual(self.state()["nodes"]["other"]["review"]["interval"], 10)
        self.grade(self.ask("top"), "B · no")
        for _ in range(3):
            self.grade(self.ask("top"), "A · yes")
        self.assertEqual(self.state()["nodes"]["top"]["review"]["interval"], 3)

    def test_review_needs_two_right_then_grows_and_a_miss_halves(self):
        self.graph()
        for _ in range(2):
            self.grade(self.ask("other"), "A · yes")
        self.make_due("other")
        self.assertIn("one more right answer", self.grade(self.ask("other", "review"), "A · yes"))
        self.assertIn("REVIEW", self.run_s("next").stdout)          # still due
        self.assertIn("next in 30 days", self.grade(self.ask("other", "review"), "A · yes"))
        self.make_due("other")
        self.assertIn("next in 15 days", self.grade(self.ask("other", "review"), "B · no"))


class TestFeedback(Vault):
    def test_a_guess_is_never_a_misconception(self):
        self.graph()
        out = self.grade(self.ask("other"), "B · no", confidence="guess", error="misconception")
        self.assertIn("counted as a gap", out)
        self.assertFalse(self.state()["metrics"]["other"]["open_misconception"])

    def test_wrong_and_sure_asks_for_a_hypercorrection(self):
        self.graph()
        self.assertIn("HYPERCORRECTION", self.grade(self.ask("other"), "B · no", confidence="sure"))
        self.assertNotIn("HYPERCORRECTION", self.grade(self.ask("other"), "B · no", confidence="unsure"))

    def test_pretest_is_logged_but_not_counted(self):
        self.graph()
        out = self.grade(self.ask("other", "pretest"), "B · no")
        self.assertIn("pretest: not counted", out)
        self.assertEqual(self.state()["nodes"]["other"]["evidence"], [])

    def test_three_misses_in_a_row_stop_the_questions(self):
        self.graph()
        self.grade(self.ask("other"), "B · no")
        self.grade(self.ask("other", "retry"), "B · no")
        out = self.grade(self.ask("other", "retry"), "B · no")
        self.assertIn("STOP: 3 wrong in a row on 'other'", out)
        self.assertNotIn("→ retry", out)


class TestCalibration(Vault):
    def test_calibration_view(self):
        self.graph()
        self.grade(self.ask("top"), "A · yes", confidence="sure")
        self.grade(self.ask("top"), "B · no", confidence="sure")
        self.grade(self.ask("other"), "A · yes", confidence="guess")
        for f in ("_map.md", os.path.join("t", "_course.md")):
            with open(os.path.join(self.tmp.name, f), encoding="utf-8") as fh:
                page = fh.read()
            self.assertIn("## Calibration", page, f)
            self.assertIn("| sure | 1/2 |", page, f)
            self.assertIn("| guessed | 1/1 |", page, f)
            self.assertNotIn("| unsure |", page, f)


class TestEndToEnd(Vault):
    """The whole course, as the skill drives it: every `next` along the way."""

    def next_is(self, text):
        out = self.run_s("next").stdout
        self.assertIn(text, out)
        return out

    def test_full_course(self):
        self.graph()
        # Entry: the target gives way, the test descends where it fails.
        self.next_is("probe the targets: top")
        self.grade(self.ask("top", "probe"), "B · no")
        self.next_is("probe the prerequisites: middle, other")
        self.grade(self.ask("middle", "probe"), "B · no")
        self.grade(self.ask("other", "probe"), "A · yes")
        self.next_is("probe the prerequisites: base")
        self.grade(self.ask("base", "probe"), "A · yes")
        self.next_is("ENTRY COMPLETE — plan the course (blocks → lessons) on these concepts, "
                     "in this order: middle, top")

        self.run_s("plan", stdin=json.dumps({"blocks": [
            {"id": "b1", "title": "One", "lessons": [{"id": "l1", "title": "L1", "nodes": ["middle"]}]},
            {"id": "b2", "title": "Two", "lessons": [{"id": "l2", "title": "L2", "nodes": ["top"]}]},
        ]}))
        self.assertEqual(self.state()["phase"], "lessons")

        # Block 1: lesson, failed chapter test, reinforcement, passed retake.
        self.next_is("LESSON l1")
        self.run_s("lesson", "l1", "start", "--file", "t/01-l1")
        self.next_is("LESSON (in progress) l1")
        for _ in range(3):
            self.grade(self.ask("middle", lesson="l1"), "A · yes")
        self.run_s("lesson", "l1", "done")
        self.next_is("CHAPTER TEST b1")
        self.grade(self.ask("middle", "chapter", "b1"), "B · no")
        self.assertIn("added reinforcement lesson b1-r1", self.run_s("test-end", "b1").stdout)
        self.next_is("REINFORCEMENT b1-r1")
        self.run_s("lesson", "b1-r1", "done")
        self.next_is("CHAPTER TEST b1 — One (attempt 2; nodes: middle)")
        self.grade(self.ask("middle", "chapter", "b1"), "A · yes")
        self.assertIn("passed", self.run_s("test-end", "b1").stdout)   # only the retake counts
        self.next_is("SYNTHESIS b1 — One: `synth b1` writes synthesis-b1.md")
        self.run_s("synth", "b1")
        self.next_is("SYNTHESIS b1 (unfinished)")
        self.fill_synth("b1")

        # Block 2, then the final test and the exit.
        self.next_is("LESSON l2")
        self.run_s("lesson", "l2", "start")
        for _ in range(3):
            self.grade(self.ask("top", lesson="l2"), "A · yes")
        self.run_s("lesson", "l2", "done")
        self.next_is("CHAPTER TEST b2")
        self.grade(self.ask("top", "chapter", "b2"), "A · yes")
        self.run_s("test-end", "b2")
        self.fill_synth("b2")
        self.next_is("FINAL TEST (attempt 1; nodes: top, middle)")
        self.grade(self.ask("top", "final"), "A · yes")
        self.grade(self.ask("middle", "final"), "A · yes")
        self.assertIn("goal reached", self.run_s("test-end", "final").stdout)
        self.next_is("SYNTHESIS all")
        self.fill_synth("all")
        self.next_is("DONE")

        st = self.state()
        self.assertEqual(st["phase"], "done")
        self.assertEqual({n: m["status"] for n, m in st["metrics"].items()},
                         {"base": "known", "middle": "solid", "other": "known", "top": "solid"})
        self.assertIsNotNone(st["nodes"]["top"]["review"])    # solid → queued for review
        with open(os.path.join(self.tmp.name, "t", "_course.md"), encoding="utf-8") as fh:
            page = fh.read()
        self.assertIn("[[t/01-l1|L1]]", page)
        self.assertIn("[[t/synthesis-b1|Synthesis]]", page)
        self.assertIn("**Synthesis:** [[t/synthesis|T]]", page)


if __name__ == "__main__":
    unittest.main()
