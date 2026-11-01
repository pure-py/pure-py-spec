#!/usr/bin/env python3
"""HTML status page of the organisation, with the dependency diagram, the open pull requests of the
repositories cloned under a directory, the output of the project integrity check and the report of the latest
submission run, written to standard output"""

import datetime
import html
import json
import pathlib
import re
import subprocess
import sys
import tempfile
from typing import Any

ORG = "pure-py"
SPEC_REPO = "pure-py-spec"
SUBMISSION_WORKFLOW = "submission.yml"
SUBMISSION_REPORT = "submission-report"
ISSUE = re.compile(r"#(\d+)")
FIELDS = "number,title,url,author,isDraft,updatedAt,reviewDecision,statusCheckRollup"
FAILED = {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"}
REVIEW = {
    "APPROVED": "approved",
    "CHANGES_REQUESTED": "changes requested",
    "REVIEW_REQUIRED": "review required",
}
STYLE = """
body { font-family: system-ui, sans-serif; max-width: 70em; margin: 2em auto; padding: 0 1em; }
img { width: 36em; max-width: 100%; }
table { border-collapse: collapse; }
th, td { text-align: left; padding: 0.3em 0.8em; border-bottom: 1px solid #ccc; white-space: nowrap; }
th:nth-child(2), td:nth-child(2) { width: 1%; }
td:nth-child(3) { white-space: normal; }
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
    cells = [
        repo,
        f'<a href="{pr["url"]}">#{pr["number"]}</a>',
        f'<a href="{pr["url"]}">{html.escape(pr["title"])}</a>',
        html.escape(pr["author"]["login"]),
        REVIEW.get(pr["reviewDecision"], "none"),
        checks(pr),
        pr["updatedAt"][:10],
    ]
    return "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>\n"


def integrity(report: str) -> str:
    """Subsection per failing rule of the project integrity report, with a table of its failures, or a line
    saying that all rules passed"""
    rules: list[tuple[str, list[list[str]]]] = []
    for line in report.splitlines():
        if line.startswith("=== "):
            rules.append((line.strip("= "), []))
        elif "\t" in line:
            rules[-1][1].append(line.split("\t"))
    if not any(rows for _, rows in rules):
        return "<p>All rules passed.</p>"

    def cell(text: str) -> str:
        link = rf'<a href="https://github.com/{ORG}/{SPEC_REPO}/issues/\1">#\1</a>'
        return ISSUE.sub(link, html.escape(text))

    def table(rows: list[list[str]]) -> str:
        headings = "".join(f"<th>{html.escape(h)}</th>" for h in rows[0])
        body = "".join(
            "<tr>" + "".join(f"<td>{cell(c)}</td>" for c in row) + "</tr>\n" for row in rows[1:]
        )
        return f"<table>\n<tr>{headings}</tr>\n{body}</table>"

    return "\n".join(f"<h3>{html.escape(rule)}</h3>\n{table(rows)}" for rule, rows in rules if rows)


def submission() -> str:
    """Section with the latest completed run of the submission workflow on main and its report, or that
    there is none"""
    listing = subprocess.run(
        ["gh", "run", "list", "--repo", f"{ORG}/{SPEC_REPO}", "--workflow", SUBMISSION_WORKFLOW]
        + ["--branch", "main", "--status", "completed", "--limit", "1"]
        + ["--json", "databaseId,conclusion,createdAt,url,headSha"],
        capture_output=True,
        text=True,
        check=False,
    )
    runs: list[dict[str, Any]] = json.loads(listing.stdout) if listing.returncode == 0 else []
    if not runs:
        return "<p>No run yet.</p>"
    run = runs[0]
    with tempfile.TemporaryDirectory() as directory:
        subprocess.run(
            ["gh", "run", "download", str(run["databaseId"]), "--repo", f"{ORG}/{SPEC_REPO}"]
            + ["--name", SUBMISSION_REPORT, "--dir", directory],
            capture_output=True,
            check=False,
        )
        report = pathlib.Path(directory, "submission.tsv")
        rows = (
            [line.split("\t") for line in report.read_text().splitlines()]
            if report.exists()
            else []
        )
    when = run["createdAt"][:16].replace("T", " ")
    heading = (
        f'<p>Run of <a href="{run["url"]}">{when}</a> UTC on commit {run["headSha"][:7]}: '
        f"{html.escape(run['conclusion'])}.</p>"
    )
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>\n" for row in rows
    )
    return (
        f"{heading}\n<table>\n<tr><th>Target</th><th>Check</th><th>Result</th></tr>\n{body}</table>"
    )


def page(repos: list[str], report: str) -> str:
    prs = [(repo, pr) for repo in repos for pr in pull_requests(repo)]
    updated = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M")

    def table(draft: bool) -> str:
        rows = "".join(row(repo, pr) for repo, pr in prs if pr["isDraft"] == draft)
        return f"""<table>
<tr><th>Repository</th><th>#</th><th>Title</th><th>Author</th><th>Review</th><th>Checks</th><th>Updated</th></tr>
{rows}</table>"""

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
{table(draft=False)}
<h2>Draft pull requests</h2>
{table(draft=True)}
<h2>Project integrity</h2>
{integrity(report)}
<h2>Submission</h2>
{submission()}
</body>
</html>
"""


def main() -> None:
    root, report = map(pathlib.Path, sys.argv[1:])
    repos = sorted(path.name for path in root.iterdir() if (path / ".git").exists())
    sys.stdout.write(page(repos, report.read_text()))


if __name__ == "__main__":
    main()
