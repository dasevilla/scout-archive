# Copilot Instructions for Scout Requirements Archive

## Repository Overview

This is a **Python web scraping project** that archives Scouts BSA merit badge requirements from scouting.org. The project uses **Scrapy** for web scraping, **uv** for Python package management, and **GitHub Actions** for automated archiving. The repository generates both JSON and Markdown files for each merit badge and deploys a static website to GitHub Pages.

**Repository Stats:**
- Language: Python 3.12
- Framework: Scrapy 2.11.2+
- Package Manager: uv (NOT pip/pipenv/poetry)
- Size: ~150 merit badges archived
- CI/CD: GitHub Actions with weekly automated runs

## Build and Development Commands

**CRITICAL: Always use `uv run` prefix for Python commands. Never use bare `python` or `pip`.**

### Environment Setup
```bash
# Install uv first (if not available)
# Check version: uv --version

# Install dependencies (uv handles virtual environment automatically)
uv sync
```

### Core Development Commands
```bash
# Clean all build artifacts (always run first when debugging)
make clean

# Run all code quality checks (REQUIRED before commits)
make check

# Individual quality checks
make lint      # Fix linting issues
make format    # Format code with ruff
make pre-commit # Run all pre-commit hooks
```

### Scraping Commands
```bash
# Create required directories
make dirs

# Run full archive process (takes 10-15 minutes)
make archive

# Test single merit badge (for development)
make archive-url URL="https://www.scouting.org/merit-badges/camping/"

# Generate index file
make index

# Validate archive results
make validate

# Generate change report
make report

# Run complete pipeline
make all
```

### Browser-Based Spider Development

**For debugging scrapers, use Playwright MCP tools to validate selectors against live websites:**

```bash
# Test CSS selectors in browser
browser_navigate("https://www.scouting.org/skills/merit-badges/all/")
browser_evaluate(() => {
  return {
    linkCount: document.querySelectorAll("h2 a[href*='/merit-badges/']").length,
    badgeNames: Array.from(document.querySelectorAll("h2 a")).slice(0,3).map(a => a.textContent)
  };
})

# Test individual badge page structure
browser_navigate("https://www.scouting.org/merit-badges/camping/")
browser_evaluate(() => {
  return {
    badgeName: document.querySelector("h1.elementor-heading-title")?.textContent,
    requirementItems: document.querySelectorAll("div.mb-requirement-item").length,
    eagleRequired: !!document.querySelector("h2:contains('Eagle Required')")
  };
})
```

**Browser validation workflow:**
1. Navigate to target pages with `browser_navigate`
2. Test selectors with `browser_evaluate` 
3. Validate structure across multiple badge types
4. Document findings before updating spider code

**Available browser tools:**
- `browser_navigate` - Visit target URLs
- `browser_evaluate` - Test JavaScript/selectors in browser context
- `browser_snapshot` - Capture page structure for analysis
- `browser_click`, `browser_type`, `browser_wait_for` - Interact with pages

**Key benefits:**
- Real-time validation against live site structure
- Detect when websites update their HTML structure
- Identify overly broad or broken selectors
- Test consistency across different page types

### Common Issues and Solutions

**Problem: `Error: build/merit-badges is not a valid directory`**
- Solution: Run `make dirs` first, then `make archive`

**Problem: Scrapy command not found**
- Solution: Always use `uv run` prefix: `uv run python -m scrapy`

**Problem: Pre-commit hooks fail**
- Solution: Run `make check` to fix all formatting/linting issues

**Problem: uv.lock out of date**
- Solution: Run `uv lock` to update lock file

## Project Architecture

### Directory Structure
```
├── src/                              # Source code
│   ├── scout_archive/                # Scrapy project
│   │   ├── spiders/                  # Web scrapers
│   │   │   └── merit_badges.py       # Main merit badge spider
│   │   ├── items.py                  # Data models
│   │   ├── pipelines.py              # Data processing
│   │   └── settings.py               # Scrapy configuration
│   ├── scripts/                      # Utility scripts
│   │   ├── validate_archive.py       # Archive validation
│   │   ├── make-index-file.py        # Index generation
│   │   └── generate-change-report.py # Change detection
│   └── scrapy.cfg                    # Scrapy project config
├── build/                            # Generated output (gitignored)
│   └── merit-badges/                 # JSON/MD files + assets
├── .github/workflows/                # CI/CD automation
│   └── archive.yml                   # Weekly archiving workflow
├── Makefile                          # Build automation
├── pyproject.toml                    # Python project config
├── uv.lock                           # Dependency lock file
└── .pre-commit-config.yaml           # Code quality hooks
```

### Key Files to Understand

**`src/scout_archive/spiders/merit_badges.py`** - Main spider that:
- Discovers merit badge URLs from scouting.org/skills/merit-badges/all/
- Extracts badge name, overview, requirements, PDFs, images
- Uses CSS selectors: `h2 a[href*='/merit-badges/']` for discovery
- Parses complex nested requirement structures

**`Makefile`** - All build commands use `uv run` prefix. Key targets:
- `make all` - Complete pipeline (archive → index → validate → report)
- `make check` - Code quality (lint → format → pre-commit)
- `make clean` - Remove all build artifacts

**`.github/workflows/archive.yml`** - Automated weekly archiving:
- Runs every Sunday at 9 AM UTC
- Creates GitHub releases with archived data
- Deploys website to GitHub Pages
- Commits changes only when merit badge requirements change

### Configuration Files

**`pyproject.toml`** - Python project configuration:
- Requires Python >=3.12
- Dependencies: scrapy, jinja2, markdownify, pillow
- Dev dependencies: pre-commit

**`.pre-commit-config.yaml`** - Code quality enforcement:
- prettier (YAML/JSON formatting)
- ruff (Python linting and formatting)
- uv lock check (dependency validation)

### CI/CD Pipeline

**Pre-commit Checks (runs on every commit):**
1. prettier formatting
2. ruff format (code formatting)
3. ruff check (linting with auto-fix)
4. uv lock validation

**GitHub Actions Workflow:**
1. Archive merit badges (10-15 min)
2. Generate index and validate
3. Create release if changes detected
4. Deploy website to GitHub Pages
5. Upload artifacts (JSON, Markdown, images)

### Data Flow

1. **Scraping**: `merit_badges.py` spider crawls scouting.org
2. **Processing**: Pipelines generate JSON + Markdown files
3. **Validation**: `validate_archive.py` checks data integrity
4. **Change Detection**: `generate-change-report.py` compares versions
5. **Deployment**: GitHub Pages serves static site

### Development Guidelines

**Always run before making changes:**
```bash
make clean && make check
```

**Test changes with single badge:**
```bash
make archive-url URL="https://www.scouting.org/merit-badges/camping/"
```

**Validate changes:**
```bash
make validate
```

**For scraper modifications:**
- Use Playwright MCP tools to test selectors in browser first
- Test CSS selectors with `browser_evaluate` before updating spider
- Navigate to live pages with `browser_navigate` to validate structure
- Update both JSON and Markdown output
- Validate against multiple badge types (Eagle-required vs regular)

**Trust these instructions** - they are validated and current. Only search for additional information if these instructions are incomplete or incorrect.
