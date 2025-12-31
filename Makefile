.PHONY: all all-with-cub-adventures archive-merit-badges archive-merit-badges-url archive-cub-adventures archive-cub-adventures-url index-merit-badges index-cub-adventures validate-merit-badges validate-cub-adventures report-merit-badges report-cub-adventures clean clean-cub-adventures build-website format lint pre-commit check

RUN_CMD=uv run

# Default target - runs a complete merit badges archiving process
all: archive-merit-badges index-merit-badges validate-merit-badges report-merit-badges

# Run cub scout adventure archive process
all-cub-adventures: archive-cub-adventures index-cub-adventures validate-cub-adventures report-cub-adventures

# Create required directories
dirs:
	mkdir -p build/merit-badges/files build/merit-badges/images build/cub-scout-adventures

# Run the merit badge archiver
archive-merit-badges: dirs
	cd src && $(RUN_CMD) python -m scrapy crawl merit_badges \
		--set MERIT_BADGE_OUTPUT_DIR=../build/merit-badges \
		--set FILES_STORE=../build/merit-badges/files \
		--set IMAGES_STORE=../build/merit-badges/images \
		--output ../build/merit-badges.jsonl \
		--logfile ../run.log

# Run the cub adventures archiver
archive-cub-adventures: dirs
	cd src && $(RUN_CMD) python -m scrapy crawl cub_scout_adventures \
		--set CUB_ADVENTURE_OUTPUT_DIR=../build/cub-scout-adventures \
		--set IMAGES_STORE=../build/cub-scout-adventures \
		--output ../build/cub-scout-adventures.jsonl \
		--logfile ../run-cub-adventures.log

# Archive a specific URL for testing
archive-merit-badges-url: dirs
	cd src && $(RUN_CMD) python -m scrapy crawl merit_badges \
		-a url=$(URL) \
		--set MERIT_BADGE_OUTPUT_DIR=../build/merit-badges \
		--set FILES_STORE=../build/merit-badges/files \
		--set IMAGES_STORE=../build/merit-badges/images \
		--output ../build/merit-badges-test.jsonl \
		--logfile ../run-test.log

# Archive a specific cub adventure URL for testing
archive-cub-adventures-url: dirs
	cd src && $(RUN_CMD) python -m scrapy parse --spider cub_scout_adventures --callback parse_adventure --pipelines "$(URL)" \
		-a url=$(URL) \
		--set CUB_ADVENTURE_OUTPUT_DIR=../build/cub-scout-adventures \
		--set IMAGES_STORE=../build/cub-scout-adventures \
		--output ../build/cub-scout-adventures-test.jsonl \
		--logfile ../run-cub-adventures-test.log

# Generate the merit badges index file
index-merit-badges:
	$(RUN_CMD) python src/scripts/make-merit-badges-index-file.py build/merit-badges

# Generate the cub adventures index file
index-cub-adventures:
	$(RUN_CMD) python src/scripts/make-cub-adventures-index-file.py build/cub-scout-adventures

# Validate the merit badges archive results
validate-merit-badges:
	$(RUN_CMD) python src/scripts/validate-merit-badges-archive.py build/merit-badges

# Validate the cub adventures archive results
validate-cub-adventures:
	$(RUN_CMD) python src/scripts/validate-cub-adventures-archive.py build/cub-scout-adventures

# Generate a merit badges change report
report-merit-badges:
	$(RUN_CMD) python src/scripts/generate-merit-badges-change-report.py > merit-badges-change-report.txt
	cat merit-badges-change-report.txt

# Generate a cub adventures change report
report-cub-adventures:
	$(RUN_CMD) python src/scripts/generate-cub-adventures-change-report.py > cub-adventures-change-report.txt
	cat cub-adventures-change-report.txt

# Build website with proper structure
build-website:
	$(RUN_CMD) python src/scripts/build-website.py

# Clean output directories
clean:
	rm -rf build/* _site/* run.log run-cub-adventures.log merit-badges-change-report.txt cub-adventures-change-report.txt

# Clean only cub adventures output
clean-cub-adventures:
	rm -rf build/cub-scout-adventures/* build/cub-scout-adventures.jsonl run-cub-adventures.log cub-adventures-change-report.txt

# Run all steps as GitHub Actions would
github-actions-test: clean all check build-website

format:
	$(RUN_CMD) ruff format .

lint:
	$(RUN_CMD) ruff check --fix .
	
pre-commit:
	$(RUN_CMD) pre-commit run --all-files
	
# Run all code quality checks
check: lint format pre-commit
