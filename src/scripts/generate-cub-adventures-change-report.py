#!/usr/bin/env python3
"""
Generate a report of changes between the current and previous Cub Scout adventure JSON files.
This is used to create informative commit messages for git archiving.
"""

import os
import json
import subprocess
from datetime import datetime


def get_adventure_files():
    """Get all adventure JSON files in the build directory"""
    json_files = []
    for root, dirs, files in os.walk("build/cub-scout-adventures"):
        for file in files:
            if file.endswith(".json"):
                json_files.append(os.path.join(root, file))
    return json_files


def get_adventure_name_from_file(file_path):
    """Extract the adventure name from a file path"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            rank = data.get("rank_name", "Unknown")
            name = data.get("adventure_name", os.path.basename(file_path))
            return f"{rank}: {name}"
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading {file_path}: {e}")
        return os.path.basename(file_path)


def get_file_changes():
    """Get lists of added, modified, and deleted files"""
    # Get all current adventure files
    current_files = get_adventure_files()

    # Get list of untracked (new) files
    added = []
    modified = []
    deleted = []

    for file_path in current_files:
        try:
            # Check if file is tracked by git
            result = subprocess.run(
                ["git", "ls-files", "--error-unmatch", file_path],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                # File is not tracked, so it's new
                added.append(file_path)
            else:
                # File is tracked, check if it's modified
                result = subprocess.run(
                    ["git", "diff", "--name-only", file_path],
                    capture_output=True,
                    text=True,
                )
                if result.stdout.strip():
                    modified.append(file_path)
        except Exception as e:
            print(f"Error checking {file_path}: {e}")
            continue

    # Get list of deleted files (tracked files not in current directory)
    try:
        all_tracked = (
            subprocess.run(
                ["git", "ls-files", "build/cub-scout-adventures/"],
                capture_output=True,
                text=True,
            )
            .stdout.strip()
            .split("\n")
        )
        deleted = [
            f
            for f in all_tracked
            if f and f.endswith(".json") and f not in current_files
        ]
    except Exception:
        deleted = []

    return added, modified, deleted


def compare_adventure_files(file_path):
    """Compare current adventure file with previous version"""
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
                "added": len(current_data.get("requirements", [])),
                "removed": 0,
            }

        try:
            previous_data = json.loads(previous_data_str)
        except json.JSONDecodeError:
            return {"added": 0, "removed": 0}

        # Compare requirements
        current_reqs = current_data.get("requirements", [])
        previous_reqs = previous_data.get("requirements", [])

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

    # Get adventure names
    added_adventures = [get_adventure_name_from_file(f) for f in added_files]
    modified_adventures = [get_adventure_name_from_file(f) for f in modified_files]
    deleted_adventures = []  # We can't get names from deleted files easily

    # Get detailed changes for modified adventures
    modified_details = {}
    for file_path in modified_files:
        adventure_name = get_adventure_name_from_file(file_path)
        if adventure_name:
            modified_details[adventure_name] = compare_adventure_files(file_path)

    # Generate report
    report = []
    current_date = datetime.now().strftime("%Y-%m-%d")

    report.append(f"Cub Scout Adventures change report: {current_date}")
    total_adventures = len(get_adventure_files())
    report.append(f"Archived {total_adventures} Cub Scout adventures")

    if added_adventures:
        report.append(f"\nNew adventures ({len(added_adventures)}):")
        for adventure in sorted(added_adventures):
            report.append(f"- {adventure}")

    if deleted_adventures:
        report.append(f"\nRemoved adventures ({len(deleted_adventures)}):")
        for adventure in sorted(deleted_adventures):
            report.append(f"- {adventure}")

    if modified_adventures:
        report.append(f"\nUpdated requirements ({len(modified_adventures)}):")
        for adventure in sorted(modified_adventures):
            details = modified_details.get(adventure, {})
            added_count = details.get("added", 0)
            removed_count = details.get("removed", 0)

            detail = []
            if added_count:
                detail.append(f"+{added_count} reqs")
            if removed_count:
                detail.append(f"-{removed_count} reqs")

            detail_str = f" ({', '.join(detail)})" if detail else ""
            report.append(f"- {adventure}{detail_str}")

    if not (added_adventures or modified_adventures or deleted_adventures):
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
