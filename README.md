# BountyCheck

**Find likely bounties, then check the evidence before you write the code.**

A small Python CLI for finding GitHub issues that advertise bounties and screening
them before you spend time coding. It flags stale dates,
missing payment terms, unverified funding, existing assignments, competing
submissions, and restrictions on AI-assisted work. Every decision includes reasons.

Built from a practical frustration: a dollar amount in an issue title does not
tell you whether the task is still available or whether you can get paid.

## Scan GitHub

Requires Python 3.10 or newer. No dependencies, API keys, or installation step.

```sh
git clone https://github.com/Rogue-says/for-github-badge.git
cd for-github-badge
python3 bountycheck.py examples/listings.json --today 2026-09-10
python3 github_bounties.py
python3 bountycheck.py scans/github-YYYY-MM-DD.json
python3 -m unittest discover -s tests -v
```

`github_bounties.py` searches public GitHub issues for current open listings that
mention “bounty,” saves normalized results under `scans/`, and prints the exact
BountyCheck command to review them. It filters out pull requests and records an
advertised dollar or USDC amount when it appears in the issue title or body.

Use a more focused GitHub issue-search query when needed:

```sh
python3 github_bounties.py --query 'is:issue is:open org:projectdiscovery bounty' --limit 20
```

It works without an account, but GitHub's anonymous search limit is small. To use
your own GitHub token for higher limits, set `GITHUB_TOKEN` in your terminal before
running it. The token is only sent to GitHub and is never saved by BountyCheck.

All bundled listings are **fictional examples**, not available jobs.

## Your own records

Copy `examples/listings.json`, replace the examples with listings you have checked,
then run:

```sh
python3 bountycheck.py my-listings.json --stale-days 14 > report.md
```

The input is a JSON array. Required fields:

| Field | Value |
| --- | --- |
| `title` | Non-empty text |
| `url` | HTTPS source URL without embedded credentials |
| `state` | `open` or `closed` |
| `updated_at` | Source update date, `YYYY-MM-DD` |

Record these optional fields after reviewing the source. Missing values remain unknown.

| Field | Value |
| --- | --- |
| `funding` | `unknown`, `advertised`, or `confirmed` |
| `funding_evidence` | HTTPS link to the evidence you checked |
| `payment_terms` | HTTPS link covering amount, currency, eligibility and acceptance terms |
| `submission_url` | HTTPS submission destination |
| `assigned_to_other` | `true`, `false`, or `null` |
| `ai_allowed` | `true`, `false`, or `null` |
| `competing_submissions` | Nonnegative integer, or `null` if unchecked |

Do not mark funding confirmed just because a title advertises a reward. Review the
sponsor's commitment or escrow evidence and record its link. Do not put credentials,
private client data, or personal payment details in your input or published reports.

## Reading the report

- **SKIP:** closed, assigned to another contributor, or AI-assisted delivery prohibited.
- **REVIEW:** missing evidence, unknown checks, competing submissions, an old update,
  or an update date in the future.
- **CANDIDATE:** all recorded checks pass. Reopen the evidence and confirm eligibility
  before claiming the task.

Candidates appear first. A record is stale when its age is greater than
`--stale-days` (default 30). `--today` makes reports reproducible; otherwise the
computer's local date is used. Exit code 0 means the report was generated, including
reports with no candidates. Exit code 2 means invalid input or a read error.

## Boundaries

The GitHub scanner finds issues that *advertise* bounties. It cannot independently
verify escrow, payment, eligibility, task availability, competing submissions, or
whether AI assistance is permitted. Those fields remain unknown and BountyCheck
marks the record for review. It never applies for work or claims a payout is
guaranteed. An issue's update date may reflect unrelated activity. Reports are a
review checklist, not a scam detector or funding audit.

## Contributing

Small, tested improvements are welcome. Run the test command above and include a
reproducer for bug fixes. Useful next steps: importing GitHub issue exports and
recording when each evidence link was last checked.

Developed with AI assistance; the screening rules are deterministic and inspectable.
