import argparse
import json
import sys

from core.publishing_smoke import run_publishing_smoke


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a non-destructive publishing smoke test for a project.")
    parser.add_argument("project_name", help="Project name under data/projects")
    parser.add_argument(
        "--platform",
        action="append",
        dest="platforms",
        default=[],
        help="Platform name to check. Repeat to check multiple platforms.",
    )
    parser.add_argument(
        "--headless",
        choices=("true", "false"),
        default=None,
        help="Override headless browser mode.",
    )
    args = parser.parse_args()

    headless = None if args.headless is None else args.headless == "true"
    report = run_publishing_smoke(
        project_name=args.project_name,
        platforms=args.platforms or None,
        headless=headless,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
