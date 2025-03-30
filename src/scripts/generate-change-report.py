#!/usr/bin/env python3
"""
Generate a report of changes between the current and previous badge JSON files.
This is used to create informative commit messages for git archiving.
"""

import os
import json
import subprocess
import glob
from datetime import datetime


def get_badge_files():
    """Get all badge JSON files in the build directory"""
    json_files = glob.glob("build/merit-badges/*.json")
    # Filter out index.json if it exists
    return [f for f in json_files if not f.endswith("index.json")]


def get_badge_name_from_file(file_path):
    """Extract the badge name from a file path"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("name", os.path.basename(file_path))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading {file_path}: {e}")
        return os.path.basename(file_path)


def is_file_tracked(file_path):
    """Check if a file is tracked by git"""
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", file_path],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def get_file_changes():
    """Get lists of added, modified, and deleted files"""
    # Get list of untracked (new) files
    untracked_output = (
        subprocess.run(
            [
                "git",
                "ls-files",
                "--others",
                "--exclude-standard",
                "build/merit-badges/*.json",
            ],
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .split("\n")
    )
    added = [f for f in untracked_output if f]

    # Get list of modified files
    modified_output = (
        subprocess.run(
            ["git", "diff", "--name-only", "build/merit-badges/*.json"],
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .split("\n")
    )
    modified = [f for f in modified_output if f]

    # Get list of deleted files (tracked files not in current directory)
    all_tracked = (
        subprocess.run(
            ["git", "ls-files", "build/merit-badges/*.json"],
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .split("\n")
    )
    current_files = get_badge_files()
    deleted = [f for f in all_tracked if f and f not in current_files]

    return added, modified, deleted


def compare_badge_files(file_path):
    """Compare current badge file with previous version"""
    try:
        # Get current data
        with open(file_path, "r", encoding="utf-8") as f:
            current_data = json.load(f)

        # Get previous version from git
        previous_data_str = subprocess.run(
            ["git", "show", f"HEAD:{file_path}"], capture_output=True, text=True
        ).stdout.strip()

        if not previous_data_str:
            return {
                "added": len(current_data.get("requirements_data", [])),
                "removed": 0,
            }

        try:
            previous_data = json.loads(previous_data_str)
        except json.JSONDecodeError:
            return {"added": 0, "removed": 0}

        # Compare requirements
        current_reqs = current_data.get("requirements_data", [])
        previous_reqs = previous_data.get("requirements_data", [])

        if not isinstance(current_reqs, list) or not isinstance(previous_reqs, list):
            return {"added": 0, "removed": 0}

        # Convert to sets of strings for comparison
        current_set = {json.dumps(r, sort_keys=True) for r in current_reqs}
        previous_set = {json.dumps(r, sort_keys=True) for r in previous_reqs}

        added_reqs = len(current_set - previous_set)
        removed_reqs = len(previous_set - current_set)

        return {"added": added_reqs, "removed": removed_reqs}
    except Exception as e:
        print(f"Error comparing {file_path}: {e}")
        return {"added": 0, "removed": 0}


def generate_report():
    """Generate a change report for the current changes"""
    added_files, modified_files, deleted_files = get_file_changes()

    # Get badge names
    added_badges = [get_badge_name_from_file(f) for f in added_files]
    modified_badges = [get_badge_name_from_file(f) for f in modified_files]
    deleted_badges = []  # We can't get names from deleted files easily

    # Get detailed changes for modified badges
    modified_details = {}
    for file_path in modified_files:
        badge_name = get_badge_name_from_file(file_path)
        if badge_name:
            modified_details[badge_name] = compare_badge_files(file_path)

    # Generate report
    report = []
    current_date = datetime.now().strftime("%Y-%m-%d")

    report.append(f"Change report: {current_date}")
    total_badges = len(get_badge_files())
    report.append(f"Archived {total_badges} merit badges")

    if added_badges:
        report.append(f"\nNew badges ({len(added_badges)}):")
        for badge in sorted(added_badges):
            report.append(f"- {badge}")

    if deleted_badges:
        report.append(f"\nRemoved badges ({len(deleted_badges)}):")
        for badge in sorted(deleted_badges):
            report.append(f"- {badge}")

    if modified_badges:
        report.append(f"\nUpdated requirements ({len(modified_badges)}):")
        for badge in sorted(modified_badges):
            details = modified_details.get(badge, {})
            added_count = details.get("added", 0)
            removed_count = details.get("removed", 0)

            detail = []
            if added_count:
                detail.append(f"+{added_count} reqs")
            if removed_count:
                detail.append(f"-{removed_count} reqs")

            detail_str = f" ({', '.join(detail)})" if detail else ""
            report.append(f"- {badge}{detail_str}")

    if not (added_badges or modified_badges or deleted_badges):
        report.append("\nNo changes detected in requirements")

    return "\n".join(report)


def main():
    """Main function"""
    try:
        report = generate_report()
        print(report)
    except Exception as e:
        print(f"Error generating report: {e}")
        print("No changes detected")


if __name__ == "__main__":
    main()
