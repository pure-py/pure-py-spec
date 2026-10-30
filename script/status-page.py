#!/usr/bin/env python3
"""HTML status page of the organisation, with the dependency diagram and the open pull requests of the
repositories cloned under a directory, written to standard output"""

import datetime
import html
import json
import pathlib
import subprocess
import sys
from typing import Any

ORG = "pure-py"
FIELDS = "number,title,url,author,isDraft,updatedAt,reviewDecision,statusCheckRollup"
FAILED = {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"}
REVIEW = {
    "APPROVED": "approved",
    "CHANGES_REQUESTED": "changes requested",
    "REVIEW_REQUIRED": "review required",
}
STYLE = """
body { font-family: system-ui, sans-serif; max-width: 70em; margin: 2em auto; padding: 0 1em; }
img { max-width: 100%; }
table { border-collapse: collapse; }
th, td { text-align: left; padding: 0.3em 0.8em; border-bottom: 1px solid #ccc; white-space: nowrap; }
td:nth-child(2) { white-space: normal; }
.draft { color: #777; }
"""


def pull_requests(repo: str) -> list[dict[str, Any]]:
    listing = subprocess.run(
        ["gh", "pr", "list", "--repo", f"{ORG}/{repo}", "--state", "open", "--json", FIELDS],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    result: list[dict[str, Any]] = json.loads(listing)
    return result


def checks(pr: dict[str, Any]) -> str:
    outcomes = [check.get("conclusion") or check.get("state") for check in pr["statusCheckRollup"]]
    if not outcomes:
        return "none"
    if any(outcome in FAILED for outcome in outcomes):
        return "failing"
    if any(outcome in (None, "", "PENDING", "EXPECTED") for outcome in outcomes):
        return "running"
    return "passing"


def row(repo: str, pr: dict[str, Any]) -> str:
    title = html.escape(f"#{pr['number']} {pr['title']}")
    draft = ' class="draft"' if pr["isDraft"] else ""
    link = f'<a href="{pr["url"]}"{draft}>{title}</a>' + (" (draft)" if pr["isDraft"] else "")
    cells = [
        repo,
        link,
        html.escape(pr["author"]["login"]),
        REVIEW.get(pr["reviewDecision"], "none"),
        checks(pr),
        pr["updatedAt"][:10],
    ]
    return "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>\n"


def page(repos: list[str]) -> str:
    rows = "".join(row(repo, pr) for repo in repos for pr in pull_requests(repo))
    updated = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>PurePy status</title>
<style>{STYLE}</style>
</head>
<body>
<h1>PurePy status</h1>
<p>Updated <time>{updated}</time> UTC.</p>
<h2>Dependencies</h2>
<img src="dependencies.svg" alt="Dependencies between repositories">
<h2>Open pull requests</h2>
<table>
<tr><th>Repository</th><th>Pull request</th><th>Author</th><th>Review</th><th>Checks</th><th>Updated</th></tr>
{rows}</table>
</body>
</html>
"""


def main() -> None:
    (root,) = map(pathlib.Path, sys.argv[1:])
    repos = sorted(path.name for path in root.iterdir() if (path / ".git").exists())
    sys.stdout.write(page(repos))


if __name__ == "__main__":
    main()
