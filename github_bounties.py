"""Find GitHub issues advertising bounties and save them for BountyCheck."""

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_QUERY = "is:issue is:open bounty in:title,body"
GITHUB_SEARCH_URL = "https://api.github.com/search/issues"
REWARD = re.compile(
    r"(?:\$\s?[\d,]+(?:\.\d{1,2})?|\b[\d,]+(?:\.\d{1,2})?\s*(?:USDC|USD)\b)",
    re.IGNORECASE,
)


def github_request(url, token=None, timeout=20):
    """Fetch one public GitHub API document without persisting credentials."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "BountyCheck/1.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def advertised_reward(issue):
    text = "\n".join(str(issue.get(field) or "") for field in ("title", "body"))
    values = []
    for match in REWARD.finditer(text):
        value = match.group(0).strip()
        if value not in values:
            values.append(value)
    return values


def normalize_issue(issue):
    """Convert one GitHub issue response into conservative BountyCheck input."""
    # GitHub's search response marks pull requests with this key. Its value can
    # be an empty object, so checking truthiness would accidentally keep a PR.
    if not isinstance(issue, dict) or "pull_request" in issue:
        return None
    html_url = issue.get("html_url")
    updated = issue.get("updated_at")
    if not isinstance(html_url, str) or not isinstance(updated, str):
        return None
    try:
        updated_date = datetime.fromisoformat(updated.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None
    assignees = issue.get("assignees")
    assigned = bool(assignees) if isinstance(assignees, list) else None
    reward = advertised_reward(issue)
    return {
        "title": str(issue.get("title") or "Untitled issue"),
        "url": html_url,
        "state": "open" if issue.get("state") == "open" else "closed",
        "updated_at": updated_date,
        "funding": "advertised" if reward else "unknown",
        "funding_evidence": None,
        "payment_terms": None,
        "submission_url": None,
        "assigned_to_other": assigned,
        "ai_allowed": None,
        "competing_submissions": None,
        "source_metadata": {
            "repository": str(issue.get("repository_url") or "").removeprefix("https://api.github.com/repos/"),
            "issue_number": issue.get("number"),
            "comments": issue.get("comments"),
            "advertised_reward": reward,
            "github_updated_at": updated,
        },
    }


def search(query, limit, token=None, request=github_request):
    if not query.strip():
        raise ValueError("query must not be empty")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    url = f"{GITHUB_SEARCH_URL}?{urlencode({'q': query, 'sort': 'updated', 'order': 'desc', 'per_page': limit})}"
    payload = request(url, token=token)
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise ValueError("GitHub returned a response without an issues list")
    return [record for issue in items if (record := normalize_issue(issue)) is not None]


def write_json(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default=DEFAULT_QUERY,
                        help="GitHub issue-search query; defaults to open issues mentioning bounty")
    parser.add_argument("--limit", type=int, default=30, help="Results to fetch, from 1 to 100")
    parser.add_argument("--token-env", default="GITHUB_TOKEN",
                        help="Environment variable containing an optional GitHub token")
    parser.add_argument("--output", type=Path, default=None,
                        help="Where to save JSON; default is scans/github-<UTC date>.json")
    args = parser.parse_args(argv)
    try:
        token = os.environ.get(args.token_env) if args.token_env else None
        records = search(args.query, args.limit, token=token)
        output = args.output or Path("scans") / f"github-{datetime.now(UTC).date().isoformat()}.json"
        write_json(output, records)
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        message = "GitHub request failed" if isinstance(exc, HTTPError) else str(exc)
        print(f"github_bounties: {message}", file=sys.stderr)
        return 2
    print(f"Saved {len(records)} issue record(s) to {output}.")
    print(f"Review them with: python3 bountycheck.py {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
