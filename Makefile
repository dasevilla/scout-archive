.PHONY: all archive archive-url index validate report clean test-site format lint pre-commit check

RUN_CMD=uv run

# Default target - runs a complete archiving process
all: archive index validate report

# Create required directories
dirs:
	mkdir -p build/merit-badges/files build/merit-badges/images

# Run the merit badge archiver
archive: dirs
	cd src && $(RUN_CMD) python -m scrapy crawl merit_badges \
		--set MERIT_BADGE_OUTPUT_DIR=../build/merit-badges \
		--set FILES_STORE=../build/merit-badges/files \
		--set IMAGES_STORE=../build/merit-badges/images \
		--output ../build/merit-badges.jsonl \
		--logfile ../run.log

# Archive a specific URL for testing
archive-url: dirs
	cd src && $(RUN_CMD) python -m scrapy parse --spider merit_badges --callback parse_merit_badge  --pipelines "$(URL)" \
		-a url=$(URL) \
		--set MERIT_BADGE_OUTPUT_DIR=../build/merit-badges \
		--set FILES_STORE=../build/merit-badges/files \
		--set IMAGES_STORE=../build/merit-badges/images \
		--output ../build/merit-badges-test.jsonl \
		--logfile ../run-test.log

# Generate the index file
index:
	$(RUN_CMD) python src/scripts/make-index-file.py build/merit-badges

# Validate the archive results
validate:
	$(RUN_CMD) python src/scripts/validate_archive.py build/merit-badges

# Generate a change report
report:
	$(RUN_CMD) python src/scripts/generate-change-report.py > change-report.txt
	cat change-report.txt

# Generate test site
test-site:
	mkdir -p _site/merit-badges
	cp -R build/merit-badges/* _site/merit-badges/

# Clean output directories
clean:
	rm -rf build/* _site/* run.log change-report.txt

# Run all steps as GitHub Actions would
github-actions-test: clean all check test-site

format:
	$(RUN_CMD) ruff format .

lint:
	$(RUN_CMD) ruff check --fix .
	
pre-commit:
	$(RUN_CMD) pre-commit run --all-files
	
# Run all code quality checks
check: lint format pre-commit
