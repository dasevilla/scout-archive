#!/usr/bin/env bash
#
# Create compressed archives for GitHub release assets.
# Validates artifacts and creates tar.gz files for merit badges, cub adventures,
# and combined archives for distribution.
#
# Usage: create-release-archives.sh [artifacts_dir]
#   artifacts_dir - Directory containing release artifacts (default: release-assets)

set -euo pipefail

ARTIFACTS_DIR="${1:-release-assets}"

if [[ ! -d "$ARTIFACTS_DIR" ]]; then
    echo "Error: Artifacts directory '$ARTIFACTS_DIR' not found" >&2
    exit 1
fi

cd "$ARTIFACTS_DIR"

# Validate required artifacts exist
if [[ ! -d "merit-badge-json" ]] || [[ ! -d "merit-badge-markdown" ]]; then
    echo "Error: Required merit badge artifacts not found" >&2
    exit 1
fi

# Create merit badge archives
tar -czf ../merit-badge-json.tar.gz -C merit-badge-json .
tar -czf ../merit-badge-markdown.tar.gz -C merit-badge-markdown .

# Handle merit badge images
if [[ -d "merit-badge-markdown/images" ]]; then
    tar -czf ../merit-badge-images.tar.gz -C merit-badge-markdown images
else
    tar -czf ../merit-badge-images.tar.gz --files-from /dev/null
fi

# Create cub adventure archives if they exist
tar -czf ../cub-adventure-json.tar.gz -C cub-adventure-json .
tar -czf ../cub-adventure-markdown.tar.gz -C cub-adventure-markdown .

# Create combined archives
mkdir -p combined-json combined-markdown

# Combine all JSON files with subdirs
mkdir -p combined-json/merit-badge combined-json/cub-adventure
cp -r merit-badge-json/* combined-json/merit-badge/ 2>/dev/null || true
cp -r cub-adventure-json/* combined-json/cub-adventure/ 2>/dev/null || true
tar -czf ../scout-archive-json.tar.gz -C combined-json .

# Combine all markdown files with subdirs
mkdir -p combined-markdown/merit-badge combined-markdown/cub-adventure
cp -r merit-badge-markdown/* combined-markdown/merit-badge/ 2>/dev/null || true
cp -r cub-adventure-markdown/* combined-markdown/cub-adventure/ 2>/dev/null || true
tar -czf ../scout-archive-markdown.tar.gz -C combined-markdown .
