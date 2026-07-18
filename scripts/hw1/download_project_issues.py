"""
HW 1: Download Debezium project issues.

Run from the project root:
    python scripts/hw1/download_project_issues.py

Purpose:
    Download issue items from the Debezium GitHub project board into raw JSONL
    so they can be normalized later.

This script reads:
    - GitHub organization project `debezium` project number `5`

And produces:
    data/hw1/raw/issues/debezium-project-5.jsonl
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from jsonl_io import save_jsonl

PROJECT_OWNER = "debezium"
PROJECT_NUMBER = 5
OUTPUT_PATH = Path("data/hw1/raw/issues/debezium-project-5.jsonl")
PAGE_SIZE = 100

PROJECT_QUERY = """
query($owner: String!, $number: Int!, $pageSize: Int!, $cursor: String) {
  organization(login: $owner) {
    projectV2(number: $number) {
      title
      items(first: $pageSize, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          content {
            __typename
            ... on Issue {
              id
              number
              title
              body
              url
              state
              createdAt
              updatedAt
              closedAt
              author {
                login
              }
              repository {
                name
                owner {
                  login
                }
              }
              labels(first: 100) {
                nodes {
                  name
                }
              }
            }
          }
          fieldValues(first: 100) {
            nodes {
              __typename
              ... on ProjectV2ItemFieldTextValue {
                text
                field {
                  ... on ProjectV2FieldCommon {
                    name
                  }
                }
              }
              ... on ProjectV2ItemFieldNumberValue {
                number
                field {
                  ... on ProjectV2FieldCommon {
                    name
                  }
                }
              }
              ... on ProjectV2ItemFieldDateValue {
                date
                field {
                  ... on ProjectV2FieldCommon {
                    name
                  }
                }
              }
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field {
                  ... on ProjectV2FieldCommon {
                    name
                  }
                }
              }
              ... on ProjectV2ItemFieldIterationValue {
                title
                startDate
                duration
                field {
                  ... on ProjectV2FieldCommon {
                    name
                  }
                }
              }
              ... on ProjectV2ItemFieldLabelValue {
                labels(first: 20) {
                  nodes {
                    name
                  }
                }
                field {
                  ... on ProjectV2FieldCommon {
                    name
                  }
                }
              }
              ... on ProjectV2ItemFieldMilestoneValue {
                milestone {
                  title
                }
                field {
                  ... on ProjectV2FieldCommon {
                    name
                  }
                }
              }
              ... on ProjectV2ItemFieldRepositoryValue {
                repository {
                  nameWithOwner
                }
                field {
                  ... on ProjectV2FieldCommon {
                    name
                  }
                }
              }
              ... on ProjectV2ItemFieldUserValue {
                users(first: 20) {
                  nodes {
                    login
                  }
                }
                field {
                  ... on ProjectV2FieldCommon {
                    name
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""


def run_gh(args: list[str]) -> dict[str, Any]:
    """
    Run a GitHub CLI command that returns JSON.
    """
    try:
        result = subprocess.run(
            ["gh", *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit(
            "GitHub CLI is not installed. Install `gh`, then run `gh auth login`."
        ) from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip()
        raise SystemExit(f"GitHub CLI command failed:\n{message}") from exc

    return json.loads(result.stdout)


def require_gh_auth() -> None:
    """
    Ensure the user has authenticated before making project API requests.
    """
    if shutil.which("gh") is None:
        raise SystemExit(
            "GitHub CLI is not installed. Install `gh`, then run `gh auth login`."
        )

    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            "GitHub CLI is not authenticated. Run `gh auth login`, then retry."
        )


def field_name(field_value: dict[str, Any]) -> str | None:
    """
    Extract the display name for a GitHub project field value.
    """
    field = field_value.get("field")
    if not isinstance(field, dict):
        return None
    name = field.get("name")
    return name if isinstance(name, str) else None


def scalar_field_value(field_value: dict[str, Any]) -> Any:
    """
    Convert supported GitHub project field value types into simple JSON values.
    """
    typename = field_value.get("__typename")

    if typename == "ProjectV2ItemFieldTextValue":
        return field_value.get("text")
    if typename == "ProjectV2ItemFieldNumberValue":
        return field_value.get("number")
    if typename == "ProjectV2ItemFieldDateValue":
        return field_value.get("date")
    if typename == "ProjectV2ItemFieldSingleSelectValue":
        return field_value.get("name")
    if typename == "ProjectV2ItemFieldIterationValue":
        return {
            "title": field_value.get("title"),
            "start_date": field_value.get("startDate"),
            "duration": field_value.get("duration"),
        }
    if typename == "ProjectV2ItemFieldLabelValue":
        labels = field_value.get("labels", {}).get("nodes") or []
        return [label["name"] for label in labels if label.get("name")]
    if typename == "ProjectV2ItemFieldMilestoneValue":
        milestone = field_value.get("milestone") or {}
        return milestone.get("title")
    if typename == "ProjectV2ItemFieldRepositoryValue":
        repository = field_value.get("repository") or {}
        return repository.get("nameWithOwner")
    if typename == "ProjectV2ItemFieldUserValue":
        users = field_value.get("users", {}).get("nodes") or []
        return [user["login"] for user in users if user.get("login")]

    return None


def extract_project_fields(item: dict[str, Any]) -> dict[str, Any]:
    """
    Extract scalar-ish project field values keyed by field display name.
    """
    project_fields: dict[str, Any] = {}
    nodes = item.get("fieldValues", {}).get("nodes") or []

    for field_value in nodes:
        name = field_name(field_value)
        value = scalar_field_value(field_value)
        if name and value is not None:
            project_fields[name] = value

    return project_fields


def build_issue_record(
    issue: dict[str, Any],
    item: dict[str, Any],
    project_title: str,
) -> dict[str, Any]:
    """
    Convert a GitHub project Issue item into the raw JSONL record shape.
    """
    repository = issue["repository"]
    repository_owner = repository["owner"]["login"]
    labels = issue.get("labels", {}).get("nodes") or []
    author = issue.get("author") or {}

    return {
        "project_owner": PROJECT_OWNER,
        "project_number": PROJECT_NUMBER,
        "project_title": project_title,
        "repository_owner": repository_owner,
        "repository_name": repository["name"],
        "id": issue["id"],
        "number": issue["number"],
        "title": issue["title"],
        "body": issue.get("body") or "",
        "url": issue["url"],
        "state": issue["state"],
        "created_at": issue["createdAt"],
        "updated_at": issue["updatedAt"],
        "closed_at": issue.get("closedAt"),
        "author": author.get("login"),
        "labels": [label["name"] for label in labels if label.get("name")],
        "project_fields": extract_project_fields(item),
    }


def fetch_project_items() -> tuple[str, list[dict[str, Any]]]:
    """
    Fetch every item from the configured GitHub organization project.
    """
    all_items: list[dict[str, Any]] = []
    cursor: str | None = None
    project_title = ""

    while True:
        args = [
            "api",
            "graphql",
            "-f",
            f"query={PROJECT_QUERY}",
            "-F",
            f"owner={PROJECT_OWNER}",
            "-F",
            f"number={PROJECT_NUMBER}",
            "-F",
            f"pageSize={PAGE_SIZE}",
        ]
        if cursor is not None:
            args.extend(["-F", f"cursor={cursor}"])

        response = run_gh(args)
        project = response["data"]["organization"]["projectV2"]
        project_title = project["title"]
        items = project["items"]
        all_items.extend(items["nodes"])

        page_info = items["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]

    return project_title, all_items


def main() -> None:
    require_gh_auth()
    project_title, items = fetch_project_items()

    issue_records: list[dict[str, Any]] = []
    skipped_counts: dict[str, int] = {}

    for item in items:
        content = item.get("content")
        typename = content.get("__typename") if isinstance(content, dict) else "NoContent"
        if typename != "Issue":
            skipped_counts[typename] = skipped_counts.get(typename, 0) + 1
            continue
        issue_records.append(build_issue_record(content, item, project_title))

    save_jsonl(issue_records, OUTPUT_PATH)

    print("=" * 80)
    print("HW 1: DOWNLOAD DEBEZIUM PROJECT ISSUES")
    print("=" * 80)
    print(f"Project: {PROJECT_OWNER}/{PROJECT_NUMBER} - {project_title}")
    print(f"Project items scanned: {len(items)}")
    print(f"Issues downloaded: {len(issue_records)}")
    print(f"Output file: {OUTPUT_PATH}")
    if skipped_counts:
        skipped = ", ".join(
            f"{typename}: {count}" for typename, count in sorted(skipped_counts.items())
        )
        print(f"Skipped non-issue items: {skipped}")


if __name__ == "__main__":
    main()
