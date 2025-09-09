#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click",
# ]
# ///

"""
Create GitHub Actions job summary from change reports.
Reads merit badge and cub adventure change reports and formats them for display
in the GitHub Actions job summary.

Usage: create-job-summary.py <output_file> [--merit-badge-report FILE] [--cub-report FILE]
"""

import click
from pathlib import Path


@click.command()
@click.argument("output_file", type=click.Path())
@click.option(
    "--merit-badge-report",
    default="change-report.txt",
    help="Merit badge change report file",
)
@click.option(
    "--cub-report",
    default="cub-adventures-change-report.txt",
    help="Cub adventures change report file",
)
def main(output_file, merit_badge_report, cub_report):
    """Create GitHub Actions job summary from change reports."""
    summary_parts = []

    merit_badge_path = Path(merit_badge_report)
    if merit_badge_path.exists():
        summary_parts.append("### Merit Badge Change Report\n")
        summary_parts.append("\n")
        summary_parts.append(merit_badge_path.read_text())
        summary_parts.append("\n")

    cub_path = Path(cub_report)
    if cub_path.exists():
        summary_parts.append("### Cub Adventures Change Report\n")
        summary_parts.append("\n")
        summary_parts.append(cub_path.read_text())

    if summary_parts:
        with open(output_file, "a") as f:
            f.write("".join(summary_parts))


if __name__ == "__main__":
    main()
