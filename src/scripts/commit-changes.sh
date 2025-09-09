#!/usr/bin/env bash
#
# Commit changes to the archive with a formatted commit message.
# Used by GitHub Actions to commit updated merit badge and cub adventure data.
#
# Usage: commit-changes.sh <output_file> [release_tag] [change_report]
#   output_file  - GitHub Actions output file to write has-changes status
#   release_tag  - Optional release tag for commit title
#   change_report - Optional formatted change report for commit body

set -euo pipefail

OUTPUT_FILE="${1:-}"
RELEASE_TAG="${2:-}"
CHANGE_REPORT="${3:-}"

if [[ -z "$OUTPUT_FILE" ]]; then
    echo "Usage: $0 <output_file> [release_tag] [change_report]" >&2
    exit 1
fi

# Configure git
git config --local user.email "action@github.com"
git config --local user.name "GitHub Action"

# Add files to the commit
git add build/merit-badges/*.json build/merit-badges/images/* build/cub-scout-adventures/*/*.json build/cub-scout-adventures/*/images/* build/cub-scout-adventures/index.md

# Check if there are changes
if git diff --staged --quiet; then
    echo "No changes detected"
    echo "has-changes=false" >> "$OUTPUT_FILE"
    exit 0
fi

echo "has-changes=true" >> "$OUTPUT_FILE"

# Create commit message
if [[ -n "$RELEASE_TAG" ]]; then
    COMMIT_TITLE="Update archive ($RELEASE_TAG)"
else
    COMMIT_TITLE="Update archive ($(date +"%Y-%m-%d"))"
fi

# Create commit with formatted change report or fallback
if [[ -n "$CHANGE_REPORT" ]]; then
    git commit -m "$COMMIT_TITLE" -m "$CHANGE_REPORT" -m "Automated archive via GitHub Actions"
else
    git commit -m "$COMMIT_TITLE" -m "Automated archive via GitHub Actions"
fi
