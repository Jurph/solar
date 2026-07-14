"""Create GitHub issues from the code-quality issue draft document.

This intentionally uses ``gh issue create --repo`` for every operation so it
does not change or depend on the GitHub CLI default repository.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO = "Jurph/solar"
DEFAULT_DRAFT = Path("docs/CODE_QUALITY_ISSUE_DRAFTS_2026-06-03.md")
TITLE_RE = re.compile(r"^## \d+\. (?P<title>.+)$", re.MULTILINE)


@dataclass(frozen=True)
class IssueDraft:
    title: str
    labels: list[str]
    body: str


def parse_drafts(path: Path) -> list[IssueDraft]:
    text = path.read_text(encoding="utf-8")
    matches = list(TITLE_RE.finditer(text))
    drafts: list[IssueDraft] = []

    for index, match in enumerate(matches):
        title = match.group("title").strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[start:end].strip()

        labels_match = re.search(r"^Labels:\s*(?P<labels>.+)$", section, re.MULTILINE)
        labels = []
        if labels_match:
            labels = [
                label.strip().strip("`")
                for label in labels_match.group("labels").split(",")
                if label.strip()
            ]
            section = section[: labels_match.start()] + section[labels_match.end() :]

        body = section.strip()
        drafts.append(IssueDraft(title=title, labels=labels, body=body))

    return drafts


def run_gh(
    args: list[str], input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args],
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def issue_exists(title: str) -> bool:
    result = run_gh(
        [
            "issue",
            "list",
            "--repo",
            REPO,
            "--state",
            "all",
            "--search",
            f'in:title "{title}"',
            "--json",
            "title",
            "--jq",
            ".[].title",
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return any(line.strip() == title for line in result.stdout.splitlines())


def create_issue(draft: IssueDraft) -> str:
    args = [
        "issue",
        "create",
        "--repo",
        REPO,
        "--title",
        draft.title,
        "--body-file",
        "-",
    ]
    for label in draft.labels:
        args.extend(["--label", label])

    result = run_gh(args, input_text=draft.body)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", type=Path, default=DEFAULT_DRAFT)
    parser.add_argument(
        "--execute", action="store_true", help="Create issues; default is dry-run."
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Create at most N issues."
    )
    args = parser.parse_args()

    drafts = parse_drafts(args.draft)
    if args.limit is not None:
        drafts = drafts[: args.limit]

    if not drafts:
        print(f"No issue drafts found in {args.draft}", file=sys.stderr)
        return 1

    for draft in drafts:
        labels = ", ".join(draft.labels) if draft.labels else "(none)"
        print(f"- {draft.title} [{labels}]")
        if not args.execute:
            continue

        if issue_exists(draft.title):
            print("  skipped: issue with exact title already exists")
            continue

        url = create_issue(draft)
        print(f"  created: {url}")

    if not args.execute:
        print("\nDry run only. Re-run with --execute to create issues.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
