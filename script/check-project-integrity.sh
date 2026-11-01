#!/usr/bin/env bash
set -e

if [ $# -ne 4 ]; then
  echo "Usage: $0 <organisation> <repository> <project number> <comma-separated Statuses whose issues must have a milestone>" >&2
  exit 1
fi

ORG="$1"
REPO="$2"
PROJECT="$3"
ACTIVE="$4"
ERRORS=0

echo "Checking project integrity for $ORG/$REPO (project $PROJECT)..."

ALL_ITEMS=$(gh api graphql --paginate -f org="$ORG" -F project="$PROJECT" -f query='
  query($endCursor: String, $org: String!, $project: Int!) {
    organization(login: $org) {
      projectV2(number: $project) {
        items(first: 100, after: $endCursor) {
          pageInfo { hasNextPage endCursor }
          nodes {
            fieldValueByName(name: "Status") {
              ... on ProjectV2ItemFieldSingleSelectValue { name }
            }
            content {
              ... on Issue {
                number
                title
                state
                milestone { title }
                repository { name }
              }
            }
          }
        }
      }
    }
  }
' --jq '[.data.organization.projectV2.items.nodes[] | select(.content != null and .content.repository.name == "'"$REPO"'")]')

CLOSED_ISSUES=$(gh api graphql --paginate -f org="$ORG" -f repo="$REPO" -f query='
  query($endCursor: String, $org: String!, $repo: String!) {
    repository(owner: $org, name: $repo) {
      issues(first: 100, states: CLOSED, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          number
          title
          subIssues(first: 100) { nodes { number state } }
        }
      }
    }
  }
' --jq '[.data.repository.issues.nodes[]]')

OPEN_ISSUES=$(gh api graphql --paginate -f org="$ORG" -f repo="$REPO" -f query='
  query($endCursor: String, $org: String!, $repo: String!) {
    repository(owner: $org, name: $repo) {
      issues(first: 100, states: OPEN, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes { number title }
      }
    }
  }
' --jq '[.data.repository.issues.nodes[]]')

ON_BOARD=$(echo "$ALL_ITEMS" | jq -cs 'add | map(.content.number)')
CLOSED_MILESTONES=$(gh api "repos/$ORG/$REPO/milestones?state=closed" --jq '[.[].title]')
ACTIVE_STATUSES=$(jq -cn --arg s "$ACTIVE" '$s | split(",") | map(ltrimstr(" ") | rtrimstr(" "))')

# Rule, its tab-separated column headings, the items, the jq filter selecting failures and the jq format of a
# tab-separated row; headings printed before the first failure only
check() {
  local rule="$1"
  local headings="$2"
  local items="$3"
  local filter="$4"
  local fmt="$5"
  local found=0

  echo ""
  echo "=== $rule ==="
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    [ "$found" -eq 0 ] && printf '%s\n' "$headings"
    found=1
    printf '%s\n' "$line"
    ERRORS=$((ERRORS + 1))
  done < <(echo "$items" | jq -r ".[] | $filter | $fmt")
}

check "Every open issue is on the project board" $'Issue\tTitle' "$OPEN_ISSUES" \
  'select(.number as $n | '"$ON_BOARD"' | index($n) | not)' \
  '"#\(.number)\t\(.title)"'

check "Every open issue has a Status" $'Issue\tTitle' "$ALL_ITEMS" \
  'select(.content.state == "OPEN" and .fieldValueByName == null)' \
  '"#\(.content.number)\t\(.content.title)"'

check "Milestoned issues are not Proposed" $'Issue\tTitle\tMilestone' "$ALL_ITEMS" \
  'select(.content.state == "OPEN" and .content.milestone != null and .fieldValueByName.name == "Proposed")' \
  '"#\(.content.number)\t\(.content.title)\t\(.content.milestone.title)"'

check "Active issues have a milestone" $'Issue\tTitle\tStatus' "$ALL_ITEMS" \
  'select(.content.state == "OPEN" and .content.milestone == null and (.fieldValueByName.name as $s | '"$ACTIVE_STATUSES"' | index($s)))' \
  '"#\(.content.number)\t\(.content.title)\t\(.fieldValueByName.name)"'

check "Closed milestones contain only Done or Rejected issues" $'Issue\tTitle\tStatus\tMilestone' "$ALL_ITEMS" \
  'select(.content.milestone != null and (.content.milestone.title as $m | '"$CLOSED_MILESTONES"' | index($m)) and (.fieldValueByName.name != "Done" and .fieldValueByName.name != "Rejected"))' \
  '"#\(.content.number)\t\(.content.title)\t\(.fieldValueByName.name // "none")\t\(.content.milestone.title)"'

check "Sub-issues of closed issues are closed" $'Issue\tTitle\tOpen sub-issues' "$CLOSED_ISSUES" \
  'select(any(.subIssues.nodes[]; .state == "OPEN"))' \
  '"#\(.number)\t\(.title)\t\([.subIssues.nodes[] | select(.state == "OPEN") | "#\(.number)"] | join(", "))"'

echo ""
if [ "$ERRORS" -eq 0 ]; then
  echo "All checks passed."
else
  echo "$ERRORS issue(s) found."
  exit 1
fi
