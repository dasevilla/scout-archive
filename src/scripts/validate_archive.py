#!/usr/bin/env python3
"""
Validate that the archive process produced expected output.
This helps detect if the source website has changed in a way that breaks our archiving.
"""

import os
import json
import glob
import sys


# Known Eagle-required badges that should always be present
EAGLE_REQUIRED_BADGES = [
    "Camping",
    "Citizenship in the Community",
    "Citizenship in the Nation",
    "Citizenship in Society",
    "Citizenship in the World",
    "Communication",
    "Cooking",
    "Emergency Preparedness",
    "Environmental Science",
    "Family Life",
    "First Aid",
    "Personal Fitness",
    "Personal Management",
    "Swimming",
]

# Minimum acceptable values
MIN_BADGE_COUNT = 135  # There should be at least this many merit badges
MIN_REQUIREMENTS = 2  # Each badge should have at least this many requirements
MIN_FILE_SIZE = 500  # Each JSON file should be at least this many bytes
MAX_EMPTY_FIELDS = 3  # Maximum number of badges with empty fields allowed


def validate_badges_directory(directory):
    """Validate that the badges directory contains expected files"""
    errors = []

    # Check for index file
    if not os.path.exists(os.path.join(directory, "index.md")):
        errors.append("Missing index.md file")

    # Check for JSON files
    json_files = glob.glob(os.path.join(directory, "*.json"))
    if len(json_files) < MIN_BADGE_COUNT:
        errors.append(
            f"Only found {len(json_files)} badge JSON files, expected at least {MIN_BADGE_COUNT}"
        )

    # Check for Markdown files
    md_files = glob.glob(os.path.join(directory, "*.md"))
    # Subtract 1 for index.md
    if len(md_files) - 1 < MIN_BADGE_COUNT:
        errors.append(
            f"Only found {len(md_files) - 1} badge Markdown files, expected at least {MIN_BADGE_COUNT}"
        )

    return errors


def validate_badge_content(file_path):
    """Validate the content of a single badge JSON file"""
    errors = []
    warnings = []
    file_size = os.path.getsize(file_path)

    if file_size < MIN_FILE_SIZE:
        errors.append(f"File size too small: {file_size} bytes")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        errors.append("Invalid JSON format")
        return errors, warnings

    # Check required fields
    required_fields = ["name", "url", "requirements"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Check requirements data
    if "requirements" in data:
        requirements = data["requirements"]
        if not isinstance(requirements, list):
            errors.append("Requirements data is not a list")
        elif len(requirements) < MIN_REQUIREMENTS:
            errors.append(
                f"Only {len(requirements)} requirements found, expected at least {MIN_REQUIREMENTS}"
            )

    # Check optional URLs (warn but don't fail)
    if not data.get("image_url"):
        warnings.append("Missing image URL")

    if not data.get("pdf_url"):
        warnings.append("Missing PDF URL")

    if not data.get("shop_url"):
        warnings.append("Missing shop URL")

    return errors, warnings


def check_eagle_required_badges(directory):
    """Check that all Eagle-required badges are present"""
    missing_eagle_badges = []

    for badge_name in EAGLE_REQUIRED_BADGES:
        # Try different filename formats
        potential_filenames = [
            os.path.join(directory, f"{badge_name}.json"),
            os.path.join(directory, f"{badge_name.lower()}.json"),
            os.path.join(directory, f"{badge_name.replace(' ', '-')}.json"),
            os.path.join(directory, f"{badge_name.lower().replace(' ', '-')}.json"),
        ]

        if not any(os.path.exists(filename) for filename in potential_filenames):
            # Try a more flexible approach - look for badge name in content
            found = False
            for json_file in glob.glob(os.path.join(directory, "*.json")):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if (
                            data.get("name") == badge_name
                            or data.get("badge_name") == badge_name
                        ):
                            found = True
                            break
                except (json.JSONDecodeError, IOError):
                    continue

            if not found:
                missing_eagle_badges.append(badge_name)

    return missing_eagle_badges


def main():
    """Main validation function"""
    if len(sys.argv) < 2:
        print("Usage: python validate_archive.py <badges_directory>")
        sys.exit(1)

    directory = sys.argv[1]

    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a valid directory")
        sys.exit(1)

    all_errors = []
    all_warnings = []

    # Validate directory structure
    dir_errors = validate_badges_directory(directory)
    all_errors.extend(dir_errors)

    # Validate each badge file
    json_files = glob.glob(os.path.join(directory, "*.json"))
    empty_field_count = 0
    badges_with_missing_urls = 0

    for file_path in json_files:
        badge_name = os.path.basename(file_path).replace(".json", "")
        badge_errors, badge_warnings = validate_badge_content(file_path)

        if badge_errors:
            if (
                len(badge_errors) == 1
                and "file size too small" in badge_errors[0].lower()
            ):
                empty_field_count += 1
            else:
                all_errors.append(f"Errors in {badge_name}: {', '.join(badge_errors)}")

        if badge_warnings:
            all_warnings.append(
                f"Warnings in {badge_name}: {', '.join(badge_warnings)}"
            )
            if any(
                "Missing" in warning and "URL" in warning for warning in badge_warnings
            ):
                badges_with_missing_urls += 1

    # Check if too many badges have empty fields
    if empty_field_count > MAX_EMPTY_FIELDS:
        all_errors.append(
            f"{empty_field_count} badges have suspiciously small file sizes"
        )

    # Check for Eagle-required badges
    missing_eagle = check_eagle_required_badges(directory)
    if missing_eagle:
        all_errors.append(f"Missing Eagle-required badges: {', '.join(missing_eagle)}")

    # Output results
    badge_count = len(json_files)

    # Print warnings first
    if all_warnings:
        print(f"Found {len(all_warnings)} warnings:")

        # Group warnings by type
        missing_pdf_urls = []
        missing_image_urls = []
        missing_shop_urls = []

        for warning in all_warnings:
            print(f"- {warning}")
            badge_name = warning.split(":")[0].replace("Warnings in ", "")

            if "Missing PDF URL" in warning:
                missing_pdf_urls.append(badge_name)
            if "Missing image URL" in warning:
                missing_image_urls.append(badge_name)
            if "Missing shop URL" in warning:
                missing_shop_urls.append(badge_name)

        print(
            f"\n{badges_with_missing_urls} of {badge_count} badges are missing one or more URLs"
        )

        # Print summary of each missing URL type
        if missing_pdf_urls:
            print(f"- {len(missing_pdf_urls)} badges missing PDF URLs")
        if missing_image_urls:
            print(f"- {len(missing_image_urls)} badges missing image URLs")
        if missing_shop_urls:
            print(f"- {len(missing_shop_urls)} badges missing shop URLs")

        print("These warnings won't fail validation, but should be investigated")
        print()

    if all_errors:
        print(f"Validation failed with {len(all_errors)} errors:")
        for error in all_errors:
            print(f"- {error}")
        sys.exit(1)
    else:
        print(f"Validation successful! Found {badge_count} merit badges.")
        sys.exit(0)


if __name__ == "__main__":
    main()
