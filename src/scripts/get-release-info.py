#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click",
# ]
# ///

import click
from datetime import datetime
from pathlib import Path


@click.command()
@click.argument("output_file", type=click.Path())
@click.option(
    "--artifacts-dir",
    default="release-assets",
    help="Directory containing release artifacts",
)
@click.option("--run-number", default="1", help="GitHub run number")
@click.option("--run-attempt", default="1", help="GitHub run attempt")
def main(output_file, artifacts_dir, run_number, run_attempt):
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

    merit_badge_report = Path(artifacts_dir) / "change-reports" / "change-report.txt"
    if merit_badge_report.exists():
        change_report_parts.append("## Merit Badge Changes\n")
        change_report_parts.append(merit_badge_report.read_text())
        change_report_parts.append("\n")

    cub_report = (
        Path(artifacts_dir) / "change-reports" / "cub-adventures-change-report.txt"
    )
    if cub_report.exists():
        change_report_parts.append("## Cub Adventures Changes\n")
        change_report_parts.append(cub_report.read_text())
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
