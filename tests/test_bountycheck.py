import contextlib
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from bountycheck import assess, main, markdown


TODAY = date(2026, 9, 10)


def listing(**changes):
    value = dict(title="SDK fix", url="https://example.com/1", state="open",
                 updated_at="2026-09-10", funding="confirmed",
                 funding_evidence="https://example.com/escrow",
                 payment_terms="https://example.com/terms",
                 submission_url="https://example.com/submit",
                 assigned_to_other=False, ai_allowed=True, competing_submissions=0)
    return value | changes


class AssessmentTests(unittest.TestCase):
    def test_complete_record_is_only_a_candidate(self):
        self.assertEqual(assess(listing(), TODAY)["status"], "candidate")

    def test_confirmation_without_evidence_is_insufficient(self):
        result = assess(listing(funding_evidence=None), TODAY)
        self.assertEqual(result["status"], "review")
        self.assertIn("Confirmed funding", result["reasons"][0])

    def test_advertised_reward_is_not_confirmed(self):
        self.assertEqual(assess(listing(funding="advertised"), TODAY)["status"], "review")

    def test_hard_blockers_override_review(self):
        for change in ({"state": "closed"}, {"assigned_to_other": True}, {"ai_allowed": False}):
            with self.subTest(change=change):
                self.assertEqual(assess(listing(**change, funding="unknown"), TODAY)["status"], "skip")

    def test_unknown_checks_never_pass(self):
        for field in ("assigned_to_other", "ai_allowed", "competing_submissions",
                      "submission_url", "payment_terms"):
            with self.subTest(field=field):
                self.assertEqual(assess(listing(**{field: None}), TODAY)["status"], "review")

    def test_staleness_boundary_and_future(self):
        self.assertEqual(assess(listing(updated_at="2026-08-11"), TODAY)["status"], "candidate")
        self.assertEqual(assess(listing(updated_at="2026-08-10"), TODAY)["status"], "review")
        self.assertEqual(assess(listing(updated_at="2026-09-11"), TODAY)["status"], "review")

    def test_competition_is_flagged(self):
        self.assertEqual(assess(listing(competing_submissions=1), TODAY)["status"], "review")

    def test_bad_inputs_are_rejected(self):
        for change in ({"competing_submissions": True}, {"competing_submissions": -1},
                       {"updated_at": "20260901"}, {"updated_at": "2026-W36-4"},
                       {"ai_allowed": "false"}, {"funding": "guaranteed"},
                       {"updated_at": "yesterday"}, {"state": "OPEN"},
                       {"url": "javascript:alert(1)"},
                       {"url": "https://user:secret@example.com"},
                       {"url": "https://example.com/\nspoof"},
                       {"payment_terms": 100}, {"title": ""}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                assess(listing(**change), TODAY)

    def test_markdown_escapes_untrusted_titles(self):
        report = markdown([assess(listing(title="<script> [click](evil)\n# fake"), TODAY)])
        self.assertNotIn("<script>", report)
        self.assertNotIn("[click](evil)", report)
        self.assertNotIn("\n# fake", report)


class CommandTests(unittest.TestCase):
    def invoke(self, contents, *args):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.json"
            path.write_text(contents, encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main([str(path), "--today", "2026-09-10", *args])
            return code, out.getvalue(), err.getvalue()

    def test_json_output_orders_candidates_first(self):
        code, out, err = self.invoke(json.dumps([listing(state="closed"), listing()]), "--format", "json")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual([r["status"] for r in json.loads(out)], ["candidate", "skip"])

    def test_invalid_document_returns_error_without_partial_report(self):
        for data in ("{", "{}", "[null]", json.dumps([listing(), {}])):
            with self.subTest(data=data):
                code, out, err = self.invoke(data)
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn("bountycheck:", err)

    def test_demo_runs(self):
        fixture = Path(__file__).resolve().parents[1] / "examples/listings.json"
        code, out, _ = self.invoke(fixture.read_text())
        self.assertEqual(code, 0)
        self.assertIn("CANDIDATE", out)
        self.assertIn("REVIEW", out)
        self.assertIn("SKIP", out)


if __name__ == "__main__":
    unittest.main()
