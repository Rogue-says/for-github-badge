"""Offline, evidence-first screening of bounty listings. Python 3.10+."""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit


def checked_url(value):
    if not isinstance(value, str):
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and bool(url.hostname)
                and url.username is None and url.password is None
                and not any(c.isspace() or ord(c) < 32 for c in value))
    except ValueError:
        return False


def validate(item):
    """Reject malformed inputs instead of silently interpreting them as facts."""
    if not isinstance(item, dict):
        raise ValueError("each listing must be an object")
    for field in ("title", "url", "state", "updated_at"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if not checked_url(item["url"]):
        raise ValueError("url must be an HTTPS URL without credentials or whitespace")
    if item["state"] not in ("open", "closed"):
        raise ValueError("state must be open or closed")
    try:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", item["updated_at"]):
            raise ValueError("invalid date format")
        date.fromisoformat(item["updated_at"])
    except ValueError as exc:
        raise ValueError("updated_at must be an ISO date (YYYY-MM-DD)") from exc
    count = item.get("competing_submissions")
    if count is not None and (type(count) is not int or count < 0):
        raise ValueError("competing_submissions must be a nonnegative integer or null")
    for field in ("assigned_to_other", "ai_allowed"):
        if item.get(field) is not None and type(item[field]) is not bool:
            raise ValueError(f"{field} must be boolean or null")
    if item.get("funding", "unknown") not in ("unknown", "advertised", "confirmed"):
        raise ValueError("funding must be unknown, advertised, or confirmed")
    for field in ("funding_evidence", "payment_terms", "submission_url"):
        if item.get(field) is not None and not checked_url(item[field]):
            raise ValueError(f"{field} must be an HTTPS URL or null")


def assess(item, today, stale_days=30):
    """Assess recorded evidence; never assert that funds actually exist."""
    validate(item)
    blockers, review = [], []
    if item["state"] == "closed":
        blockers.append("Listing is closed.")
    if item.get("assigned_to_other") is True:
        blockers.append("Already assigned to another contributor.")
    elif item.get("assigned_to_other") is None:
        review.append("Assignment status is unknown.")
    if item.get("ai_allowed") is False:
        blockers.append("AI-assisted delivery is not permitted.")
    elif item.get("ai_allowed") is None:
        review.append("AI-assisted delivery policy needs confirmation.")
    age = (today - date.fromisoformat(item["updated_at"])).days
    if age < 0:
        review.append("Update date is in the future; check the source.")
    elif age > stale_days:
        review.append(f"Listing has not been updated for {age} days.")
    if item.get("funding") != "confirmed" or not item.get("funding_evidence"):
        review.append("Confirmed funding with an evidence link is missing.")
    if not item.get("payment_terms"):
        review.append("Payment terms need a source link.")
    if not item.get("submission_url"):
        review.append("Submission path is not recorded.")
    count = item.get("competing_submissions")
    if count is None:
        review.append("Competing submissions have not been checked.")
    elif count:
        review.append(f"{count} competing submission(s); confirm eligibility before coding.")
    status = "skip" if blockers else "review" if review else "candidate"
    return {"title": item["title"], "url": item["url"], "status": status,
            "days_since_update": age,
            "reasons": blockers + review or ["Recorded checks pass. Recheck the linked evidence before claiming."],
            "evidence": {k: item.get(k) for k in
                         ("funding_evidence", "payment_terms", "submission_url")}}


def markdown(results):
    # Escape source text so input cannot inject Markdown links or raw HTML.
    import html

    def literal(value):
        value = html.escape(str(value)).replace("\n", " ").replace("\r", " ")
        for char in "\\`*_{}[]()#+-.!|":
            value = value.replace(char, "\\" + char)
        return value

    lines = ["# BountyCheck report", "",
             "Offline screening of supplied records. Funding and eligibility are not independently verified.", ""]
    for result in results:
        lines.extend([f"## {literal(result['title'])}", "",
                      f"Status: **{result['status'].upper()}**", "",
                      f"Source: {literal(result['url'])}", ""])
        for reason in result["reasons"] or ["Recorded checks pass. Recheck the linked evidence before claiming."]:
            lines.append(f"- {literal(reason)}")
        lines.append("")
        for name, url in result["evidence"].items():
            if url:
                lines.append(f"- {name.replace('_', ' ').capitalize()}: {literal(url)}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON array of normalized listing records")
    parser.add_argument("--today", type=date.fromisoformat, default=date.today(),
                        help="Override today's date for reproducible reports")
    parser.add_argument("--stale-days", type=int, default=30)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args(argv)
    if args.stale_days < 0:
        parser.error("--stale-days must be nonnegative")
    try:
        records = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("input must be a JSON array")
        results = []
        for index, item in enumerate(records):
            try:
                results.append(assess(item, args.today, args.stale_days))
            except ValueError as exc:
                raise ValueError(f"listing {index + 1}: {exc}") from exc
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"bountycheck: {exc}", file=sys.stderr)
        return 2
    order = {"candidate": 0, "review": 1, "skip": 2}
    results.sort(key=lambda r: (order[r["status"]], r["title"].casefold()))
    print(json.dumps(results, indent=2) if args.format == "json" else markdown(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
