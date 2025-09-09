#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click",
# ]
# ///

"""
Generate release information for GitHub Actions.
Creates release tags, names, and combines change reports for GitHub release creation.

Usage: get-release-info.py <output_file> [--merit-badge-report FILE] [--cub-report FILE] [--run-number NUM] [--run-attempt NUM]
"""

import click
from datetime import datetime
from pathlib import Path


@click.command()
@click.argument("output_file", type=click.Path())
@click.option(
    "--merit-badge-report",
    default="change-report.txt",
    help="Merit badge change report file path",
)
@click.option(
    "--cub-report",
    default="cub-adventures-change-report.txt",
    help="Cub adventures change report file path",
)
@click.option("--run-number", default="1", help="GitHub run number")
@click.option("--run-attempt", default="1", help="GitHub run attempt")
def main(output_file, merit_badge_report, cub_report, run_number, run_attempt):
    """Generate release information for GitHub Actions."""
    # Generate release info
    date = datetime.now().strftime("%Y-%m-%d")

    release_tag = f"archive-{date}-{run_number}-{run_attempt}"
    generated_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    if run_attempt == "1":
        release_name = f"Scout Archive Update - {date}"
    else:
        release_name = f"Scout Archive Update - {date} (Attempt {run_attempt})"

    # Read change reports
    change_report_parts = []

    merit_badge_path = Path(merit_badge_report)
    if merit_badge_path.exists():
        change_report_parts.append("## Merit Badge Changes\n")
        change_report_parts.append(merit_badge_path.read_text())
        change_report_parts.append("\n")

    cub_path = Path(cub_report)
    if cub_path.exists():
        change_report_parts.append("## Cub Adventures Changes\n")
        change_report_parts.append(cub_path.read_text())
        change_report_parts.append("\n")

    if not change_report_parts:
        change_report_parts.append("No change reports available")

    change_report = "".join(change_report_parts).strip()

    # Write to output file
    with open(output_file, "a") as f:
        f.write(f"release-tag={release_tag}\n")
        f.write(f"generated-date={generated_date}\n")
        f.write(f"release-name={release_name}\n")
        f.write(f"change-report<<EOF\n{change_report}\nEOF\n")


if __name__ == "__main__":
    main()
