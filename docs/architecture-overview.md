# Architecture Overview

This document describes how Scout Archive is structured, how data flows through the system, and where to look when making changes.

## Purpose

Scout Archive crawls requirements from Scouting America pages, normalizes the content into a structured schema, renders Markdown, and writes a static archive of JSON/Markdown files. It supports:

- **Merit Badges** (primary)
- **Merit Badge Test Lab badges** (special layout, different scraping logic)
- **Cub Scout Adventures** (separate spider and output directory)

## High-Level Data Flow

```
Scouting.org pages
    │
    │  (Scrapy spiders)
    ▼
Scrapy Items (MeritBadgeItem / CubScoutAdventureItem)
    │
    │  (requirements pipeline + normalization)
    ▼
Structured requirement trees (JSON-friendly models)
    │
    │  (Jinja templates + pipelines)
    ▼
build/merit-badges/*.json + *.md
build/cub-scout-adventures/**/*
```

## Repository Layout

```
src/
  scout_archive/
    spiders/
      merit_badges.py
      cub_scout_adventures.py
    requirements_pipeline.py
    items.py
    pipelines.py
    settings.py
  scripts/
    validate-merit-badges-archive.py
    make-merit-badges-index-file.py
    generate-merit-badges-change-report.py
    ... (cub adventure equivalents)
docs/
  architecture-overview.md
  json-format.md
```

## Core Components

### 1) Spiders

#### MeritBadgesSpider (`src/scout_archive/spiders/merit_badges.py`)

Responsibilities:
- Discover and crawl merit badge pages.
- Discover and crawl **Test Lab** badge pages.
- Extract badge metadata (name, overview, images, PDFs, shop links).
- Extract requirements HTML and feed it into the **requirements pipeline**.

Key behaviors:
- **Standard badges**: crawl from `https://www.scouting.org/skills/merit-badges/all/`
- **Test Lab badges**: crawl from `https://www.scouting.org/skills/merit-badges/test-lab/`
- **`labs_only` param**: crawl Test Lab only (useful for debugging or a limited run)

Test Lab specifics:
- The HTML layout is different; requirements are parsed from text-editor blocks.
- Badge images are in a different part of the DOM; a separate selector is used.
- Workbooks typically do not exist, so workbook URLs are left `None`.

#### CubScoutAdventureSpider (`src/scout_archive/spiders/cub_scout_adventures.py`)

Responsibilities:
- Discover and crawl Cub Scout adventure pages by rank.
- Extract adventure metadata and requirements.
- Uses the requirements pipeline for requirement structure.

### 2) Requirements Pipeline

File: `src/scout_archive/requirements_pipeline.py`

This pipeline turns raw HTML into clean, structured requirements with a deterministic Markdown rendering. It has two extraction paths:

#### Standard Merit Badge Pipeline

```
HTML
  └─ HtmlExtractor
       └─ RawRequirementItem[] (lossless raw tree)
           └─ SemanticProcessor
                └─ SemanticRequirement[] (clean, normalized tree)
                    └─ MarkdownGenerator
                         └─ Markdown output
```

- **HtmlExtractor**
  - Finds `div.mb-requirement-item`.
  - Builds a lossless node tree (text + elements) to preserve formatting.

- **SemanticProcessor**
  - Promotes labels (e.g., `1.`, `(a)`).
  - Extracts and normalizes resources into a list.
  - Cleans attributes to a controlled HTML subset.
  - Normalizes whitespace and inline spacing.

- **MarkdownGenerator**
  - Renders labels as `(1)` style markers.
  - Renders resources as a single paragraph:
    - `**Resources:** link1, link2, ...`
  - Preserves formatting (bold/italics/br links).

#### Test Lab Pipeline

Test Lab pages do not use `mb-requirement-item` containers. The lab extractor:

- Locates the “REQUIREMENTS” block.
- Collects **text editor widgets** as requirement blocks.
- Splits **top-level numbered requirements** (e.g., `1.`).
- Splits **inline sub-requirements** (e.g., `(a)`, `(b)`) into nested nodes.
- Detects **resource-only lists** and assigns them to the closest requirement or sub-requirement.

This yields the same semantic tree type, so Markdown/JSON output stays consistent.

### 3) Items & Pipelines

#### Items (`src/scout_archive/items.py`)

MeritBadgeItem includes:
- `badge_name`, `badge_url`, `badge_overview`, `badge_image_url`
- `badge_pdf_url`, `badge_shop_url`
- `workbook_pdf_url`, `workbook_docx_url`
- `is_eagle_required`
- `is_lab`
- `requirements_data`, `requirements_markdown`

CubScoutAdventureItem includes:
- Rank/adventure metadata
- Requirements data

#### Pipeline (`src/scout_archive/pipelines.py`)

Writes:
- JSON files for badges/adventures
- Markdown files via Jinja2 templates

Merit badge JSON includes:
- `requirements` (structured tree)
- `is_lab` flag

### 4) Templates

`src/scout_archive/templates/merit_badge_template.md`
- Renders `requirements_markdown` directly.
- Shows an Overview note for Test Lab badges:
  - **Test Lab Merit Badge**, Verify current status at the Test Lab page.

### 5) Validation & Reports

Scripts under `src/scripts/` provide:
- Validation (size, minimum requirements, missing URLs)
- Index generation
- Change reports
