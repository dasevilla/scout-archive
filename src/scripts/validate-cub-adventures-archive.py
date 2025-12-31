#!/usr/bin/env python3
"""
Validate that the Cub Scout adventure archive process produced expected output.
This helps detect if the source website has changed in a way that breaks our archiving.
"""

import os
import json
import glob
import sys
import re
from urllib.parse import urlparse

# Import settings from Scrapy project
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scout_archive.settings import (
    CUB_SCOUT_RANK_NAMES,
    VALID_ADVENTURE_TYPES,
    EXPECTED_REQUIRED_COUNTS,
    VALID_ACTIVITY_LOCATIONS,
    VALID_NUMERIC_RANGE,
    MIN_ADVENTURE_COUNT,
    MIN_REQUIREMENTS,
    MIN_FILE_SIZE_BYTES,
    MIN_IMAGE_SIZE_BYTES,
    MIN_OVERVIEW_WORDS,
    MAX_EMPTY_FIELDS,
)

ALLOWED_NODE_TAGS = {"b", "strong", "i", "em", "a", "br"}


def _node_text(nodes):
    parts = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = node.get("type")
        if node_type == "text":
            parts.append(node.get("value", ""))
        elif node_type == "element":
            parts.append(_node_text(node.get("children", [])))
    return "".join(parts)


def _validate_nodes(nodes, path, errors, warnings):
    if not isinstance(nodes, list):
        errors.append(f"{path} content is not a list")
        return
    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"{path} content[{idx}] is not an object")
            continue
        node_type = node.get("type")
        if node_type == "text":
            if "value" not in node:
                errors.append(f"{path} content[{idx}] missing text value")
            continue
        if node_type == "element":
            tag = node.get("tag")
            if tag not in ALLOWED_NODE_TAGS:
                warnings.append(f"{path} content[{idx}] unexpected tag '{tag}'")
            attrs = node.get("attrs", {})
            if tag == "a":
                if not attrs or not attrs.get("href"):
                    warnings.append(f"{path} content[{idx}] link missing href")
            elif attrs:
                warnings.append(f"{path} content[{idx}] unexpected attrs on '{tag}'")
            _validate_nodes(node.get("children", []), path, errors, warnings)
            continue
        errors.append(f"{path} content[{idx}] has invalid type '{node_type}'")


def _validate_requirement_tree(requirements, path, errors, warnings, require_text):
    if not isinstance(requirements, list):
        errors.append(f"{path} is not a list")
        return
    for idx, req in enumerate(requirements):
        req_path = f"{path}[{idx}]"
        if not isinstance(req, dict):
            errors.append(f"{req_path} is not an object")
            continue
        if "id" not in req:
            errors.append(f"{req_path} missing id")
        label = req.get("label")
        if label is not None:
            if not isinstance(label, str):
                errors.append(f"{req_path} label is not a string")
            elif label.endswith(".") or label.startswith("(") or label.endswith(")"):
                warnings.append(f"{req_path} label not normalized: '{label}'")

        content = req.get("content")
        if content is None:
            errors.append(f"{req_path} missing content")
        else:
            _validate_nodes(content, req_path, errors, warnings)
            if not _node_text(content).strip() and not req.get("sub_requirements"):
                warnings.append(f"{req_path} has empty content")

        resources = req.get("resources")
        if resources is None:
            errors.append(f"{req_path} missing resources")
        elif not isinstance(resources, list):
            errors.append(f"{req_path} resources is not a list")
        else:
            for ridx, resource in enumerate(resources):
                if not isinstance(resource, dict):
                    errors.append(f"{req_path} resources[{ridx}] is not an object")
                    continue
                if not resource.get("title") or not resource.get("url"):
                    warnings.append(
                        f"{req_path} resources[{ridx}] missing title or url"
                    )

        sub_requirements = req.get("sub_requirements")
        if sub_requirements is None:
            errors.append(f"{req_path} missing sub_requirements")
        else:
            _validate_requirement_tree(
                sub_requirements,
                f"{req_path}.sub_requirements",
                errors,
                warnings,
                require_text=False,
            )

        if require_text:
            text = req.get("text", "")
            if not text:
                errors.append(f"{req_path} missing text")
            elif not text.strip():
                warnings.append(f"{req_path} has empty text")


def validate_adventures_directory(directory):
    """Validate that the adventures directory contains expected files"""
    errors = []

    # Check for JSON files in subdirectories (organized by rank)
    json_files = glob.glob(os.path.join(directory, "*", "*.json"))
    if len(json_files) < MIN_ADVENTURE_COUNT:
        errors.append(
            f"Only found {len(json_files)} adventure JSON files, expected at least {MIN_ADVENTURE_COUNT}"
        )

    # Check for Markdown files in subdirectories
    md_files = glob.glob(os.path.join(directory, "*", "*.md"))
    if len(md_files) < MIN_ADVENTURE_COUNT:
        errors.append(
            f"Only found {len(md_files)} adventure Markdown files, expected at least {MIN_ADVENTURE_COUNT}"
        )

    return errors


def validate_adventure_content(file_path):
    """Validate the content of a single adventure JSON file"""
    errors = []
    warnings = []
    file_size = os.path.getsize(file_path)

    if file_size < MIN_FILE_SIZE_BYTES:
        errors.append(f"File size too small: {file_size} bytes")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        errors.append("Invalid JSON format")
        return errors, warnings

    # Check required fields
    required_fields = ["adventure_name", "rank_name", "url", "requirements"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Validate rank name
    if "rank_name" in data:
        rank_name = data["rank_name"]
        if rank_name not in CUB_SCOUT_RANK_NAMES and rank_name != "Unknown":
            warnings.append(f"Unexpected rank name: {rank_name}")

    # Validate adventure type
    if "adventure_type" in data:
        adventure_type = data["adventure_type"]
        if adventure_type:
            if adventure_type not in VALID_ADVENTURE_TYPES:
                errors.append(
                    f"Invalid adventure type: '{adventure_type}', expected one of {VALID_ADVENTURE_TYPES}"
                )
        else:
            warnings.append("Missing adventure type")

    # Validate URL format
    if "url" in data and data["url"]:
        url = data["url"]
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            errors.append(f"Malformed URL: {url}")
        elif not url.startswith("https://www.scouting.org/"):
            warnings.append(f"Unexpected URL domain: {url}")

    # Validate adventure overview word count
    if "adventure_overview" in data and data["adventure_overview"]:
        overview_words = len(data["adventure_overview"].split())
        if overview_words < MIN_OVERVIEW_WORDS:
            warnings.append(
                f"Adventure overview too short: {overview_words} words, expected at least {MIN_OVERVIEW_WORDS}"
            )
    else:
        warnings.append("Missing or empty adventure overview")

    # Check requirements data
    if "requirements" in data:
        requirements = data["requirements"]
        if not isinstance(requirements, list):
            errors.append("Requirements data is not a list")
        elif len(requirements) < MIN_REQUIREMENTS:
            errors.append(
                f"Only {len(requirements)} requirements found, expected at least {MIN_REQUIREMENTS}"
            )
        else:
            _validate_requirement_tree(
                requirements, "requirements", errors, warnings, require_text=True
            )
            # Validate activities within requirements
            for i, req in enumerate(requirements):
                if not isinstance(req, dict):
                    errors.append(f"Requirement {i} is not a dictionary")
                    continue

                if "activities" in req and isinstance(req["activities"], list):
                    for j, activity in enumerate(req["activities"]):
                        if not isinstance(activity, dict):
                            errors.append(
                                f"Requirement {i}, activity {j} is not a dictionary"
                            )
                            continue

                        # Validate required activity fields
                        for field in ["name", "url", "description"]:
                            if field not in activity or not activity[field].strip():
                                warnings.append(
                                    f"Requirement {i}, activity {j} missing or empty '{field}'"
                                )

                        # Validate location
                        if "location" in activity:
                            if activity["location"] not in VALID_ACTIVITY_LOCATIONS:
                                warnings.append(
                                    f"Requirement {i}, activity {j} invalid location: '{activity['location']}', expected one of {VALID_ACTIVITY_LOCATIONS}"
                                )

                        # Validate numeric fields
                        for field in ["energy_level", "supply_list", "prep_time"]:
                            if field in activity and activity[field]:
                                if activity[field] not in VALID_NUMERIC_RANGE:
                                    warnings.append(
                                        f"Requirement {i}, activity {j} invalid {field}: '{activity[field]}', expected {','.join(VALID_NUMERIC_RANGE)}"
                                    )

    # Check optional fields (warn but don't fail)
    if not data.get("adventure_overview"):
        warnings.append("Missing adventure overview")

    if not data.get("image_url"):
        warnings.append("Missing image URL")

    return errors, warnings


def validate_file_pairs(directory):
    """Validate that JSON and Markdown files exist for each adventure"""
    errors = []

    # Get all JSON files
    json_files = glob.glob(os.path.join(directory, "*", "*.json"))

    for json_file in json_files:
        # Check for corresponding markdown file
        md_file = json_file.replace(".json", ".md")
        if not os.path.exists(md_file):
            errors.append(f"Missing markdown file for {os.path.basename(json_file)}")

        # Validate adventure name matches filename
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                adventure_name = data.get("adventure_name", "")
                filename_base = os.path.basename(json_file).replace(".json", "")

                # Convert adventure name to expected filename format (more lenient)
                expected_filename = adventure_name.lower()
                expected_filename = re.sub(
                    r"[''']", "", expected_filename
                )  # Remove apostrophes
                expected_filename = re.sub(
                    r"[^\w\s-]", "", expected_filename
                )  # Remove other special chars
                expected_filename = re.sub(r"[-\s]+", "-", expected_filename).strip("-")

                # Also check if filename matches adventure name directly (for exact matches)
                if (
                    expected_filename != filename_base
                    and adventure_name.lower().replace(" ", "-") != filename_base
                ):
                    # Only report if it's a significant mismatch (not just punctuation)
                    base_name_clean = re.sub(r"[^\w]", "", filename_base.lower())
                    adventure_clean = re.sub(r"[^\w]", "", adventure_name.lower())
                    if base_name_clean != adventure_clean:
                        errors.append(
                            f"Adventure name '{adventure_name}' doesn't match filename '{filename_base}'"
                        )
        except (json.JSONDecodeError, IOError):
            continue

    return errors


def validate_images(directory):
    """Validate image files exist and are properly sized"""
    errors = []
    warnings = []

    # Get all JSON files to check their image references
    json_files = glob.glob(os.path.join(directory, "*", "*.json"))

    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "image_url" in data and data["image_url"]:
                # Determine expected image file path
                rank_dir = os.path.dirname(json_file)
                adventure_name = data.get("adventure_name", "")

                # Convert adventure name to expected image filename (more lenient)
                image_filename = adventure_name.lower()
                image_filename = re.sub(
                    r"[''']", "", image_filename
                )  # Remove apostrophes
                image_filename = re.sub(
                    r"[^\w\s-]", "", image_filename
                )  # Remove other special chars
                image_filename = re.sub(r"[-\s]+", "-", image_filename).strip("-")

                # Check for common image extensions and filename variations
                image_found = False
                possible_names = [
                    image_filename,  # hyphenated version
                    adventure_name.lower(),  # original with spaces
                    adventure_name.lower().replace(" ", "-"),  # spaces to hyphens
                ]

                for name_variant in possible_names:
                    for ext in [".jpg", ".jpeg", ".png"]:
                        image_path = os.path.join(
                            rank_dir, "images", f"{name_variant}{ext}"
                        )
                        if os.path.exists(image_path):
                            image_found = True

                            # Check image file size
                            image_size = os.path.getsize(image_path)
                            if image_size < MIN_IMAGE_SIZE_BYTES:
                                warnings.append(
                                    f"Image file too small for {adventure_name}: {image_size} bytes"
                                )
                            break
                    if image_found:
                        break

                if not image_found:
                    warnings.append(f"Image file not found for {adventure_name}")
        except (json.JSONDecodeError, IOError):
            continue

    return errors, warnings


def check_duplicate_adventures(directory):
    """Check for duplicate adventures within ranks"""
    errors = []

    for rank in CUB_SCOUT_RANK_NAMES:
        rank_dir = os.path.join(directory, rank.lower().replace(" ", "-"))
        if not os.path.exists(rank_dir):
            continue

        adventure_names = []
        json_files = glob.glob(os.path.join(rank_dir, "*.json"))

        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    adventure_name = data.get("adventure_name", "")
                    if adventure_name in adventure_names:
                        errors.append(
                            f"Duplicate adventure '{adventure_name}' in {rank}"
                        )
                    else:
                        adventure_names.append(adventure_name)
            except (json.JSONDecodeError, IOError):
                continue

    return errors


def check_rank_coverage(directory):
    """Check that all ranks have at least some adventures and required adventure counts"""
    rank_counts = {rank: {"total": 0, "required": 0} for rank in CUB_SCOUT_RANK_NAMES}
    missing_ranks = []
    required_count_errors = []

    for json_file in glob.glob(os.path.join(directory, "*", "*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                rank_name = data.get("rank_name")
                adventure_type = data.get("adventure_type", "")

                if rank_name in rank_counts:
                    rank_counts[rank_name]["total"] += 1
                    if adventure_type == "Required":
                        rank_counts[rank_name]["required"] += 1
        except (json.JSONDecodeError, IOError):
            continue

    for rank, counts in rank_counts.items():
        if counts["total"] == 0:
            missing_ranks.append(rank)
        else:
            expected_required = EXPECTED_REQUIRED_COUNTS.get(rank, 5)
            if counts["required"] < expected_required:
                required_count_errors.append(
                    f"{rank} has {counts['required']} required adventures, expected {expected_required}"
                )

    return missing_ranks, rank_counts, required_count_errors


def main():
    """Main validation function"""
    if len(sys.argv) < 2:
        print("Usage: python validate-cub-adventures-archive.py <adventures_directory>")
        sys.exit(1)

    directory = sys.argv[1]

    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a valid directory")
        sys.exit(1)

    all_errors = []
    all_warnings = []

    # Validate directory structure
    dir_errors = validate_adventures_directory(directory)
    all_errors.extend(dir_errors)

    # Validate each adventure file
    json_files = glob.glob(os.path.join(directory, "*", "*.json"))
    empty_field_count = 0
    adventures_with_missing_fields = 0

    for file_path in json_files:
        adventure_name = os.path.basename(file_path).replace(".json", "")
        adventure_errors, adventure_warnings = validate_adventure_content(file_path)

        if adventure_errors:
            if (
                len(adventure_errors) == 1
                and "file size too small" in adventure_errors[0].lower()
            ):
                empty_field_count += 1
            else:
                all_errors.append(
                    f"Errors in {adventure_name}: {', '.join(adventure_errors)}"
                )

        if adventure_warnings:
            all_warnings.append(
                f"Warnings in {adventure_name}: {', '.join(adventure_warnings)}"
            )
            adventures_with_missing_fields += 1

    # Check if too many adventures have empty fields
    if empty_field_count > MAX_EMPTY_FIELDS:
        all_errors.append(
            f"{empty_field_count} adventures have suspiciously small file sizes"
        )

    # Check rank coverage
    missing_ranks, rank_counts, required_count_errors = check_rank_coverage(directory)
    if missing_ranks:
        all_errors.append(f"No adventures found for ranks: {', '.join(missing_ranks)}")

    # Add required adventure count errors
    all_errors.extend(required_count_errors)

    # Validate file pairs (JSON/Markdown)
    file_pair_errors = validate_file_pairs(directory)
    all_errors.extend(file_pair_errors)

    # Validate images
    image_errors, image_warnings = validate_images(directory)
    all_errors.extend(image_errors)
    all_warnings.extend(image_warnings)

    # Check for duplicate adventures
    duplicate_errors = check_duplicate_adventures(directory)
    all_errors.extend(duplicate_errors)

    # Output results
    adventure_count = len(json_files)

    # Print warnings first
    if all_warnings:
        print(f"Found {len(all_warnings)} warnings:")

        # Group warnings by type
        missing_overviews = []
        missing_images = []
        missing_types = []

        for warning in all_warnings:
            print(f"- {warning}")
            adventure_name = warning.split(":")[0].replace("Warnings in ", "")

            if "Missing adventure overview" in warning:
                missing_overviews.append(adventure_name)
            if "Missing image URL" in warning:
                missing_images.append(adventure_name)
            if "Missing adventure type" in warning:
                missing_types.append(adventure_name)

        print(
            f"\n{adventures_with_missing_fields} of {adventure_count} adventures are missing optional fields"
        )

        # Print summary of each missing field type
        if missing_overviews:
            print(f"- {len(missing_overviews)} adventures missing overview")
        if missing_images:
            print(f"- {len(missing_images)} adventures missing image URLs")
        if missing_types:
            print(f"- {len(missing_types)} adventures missing type")

        print("These warnings won't fail validation, but should be investigated")
        print()

    # Print rank distribution
    if not missing_ranks:
        print("Adventure distribution by rank:")
        for rank, counts in rank_counts.items():
            total = counts["total"]
            required = counts["required"]
            print(f"- {rank}: {total} adventures ({required} required)")
        print()

    if all_errors:
        print(f"Validation failed with {len(all_errors)} errors:")
        for error in all_errors:
            print(f"- {error}")
        sys.exit(1)
    else:
        print(f"Validation successful! Found {adventure_count} Cub Scout adventures.")
        sys.exit(0)


if __name__ == "__main__":
    main()
