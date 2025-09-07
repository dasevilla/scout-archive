# Scout Requirements Archive

A project to archive Scouts BSA merit badge requirements and Cub Scout adventures.

Goals:

- Have machine-readable versions of merit badges and Cub Scout adventures with their requirements
- Ability to review the history of requirements as they evolve via git commits
- A simple static site of all merit badges and adventures deployed to GitHub pages

## Usage

### Merit Badges

Create the merit badge archive:

```shell
make archive
```

Validate the merit badge archive:

```shell
make validate
```

Generate the merit badge index file:

```shell
make index
```

Generate merit badge change report:

```shell
make report
```

### Cub Scout Adventures

Create the Cub Scout adventures archive:

```shell
make archive-cub-adventures
```

Clean only Cub Scout adventures output:

```shell
make clean-cub-adventures
```

Validate the Cub Scout adventures archive:

```shell
make validate-cub-adventures
```

Generate the Cub Scout adventures index file:

```shell
make index-cub-adventures
```

Generate Cub Scout adventures change report:

```shell
make report-cub-adventures
```

### Combined Operations

Run the entire merit badge archiving process (archive, index, validate, and report):

```shell
make all
```

Run both merit badges and Cub Scout adventures archiving:

```shell
make all-with-cub-adventures
```

Run code quality checks:

```shell
make check
```

## Output Format

The project generates two types of files for each merit badge and Cub Scout adventure:

1. **JSON files**: Structured data including name, overview, requirements, activities, etc.
2. **Markdown files**: Human-readable format of the requirements

### Merit Badges
- Stored in `build/merit-badges/`
- Include Eagle-required status, PDF links, and shop URLs
- Images stored in `build/merit-badges/images/`

### Cub Scout Adventures
- Organized by rank in `build/cub-scout-adventures/{rank}/`
- Include adventure type (Required/Elective), category, and detailed activities
- Activities include location, energy level, supply requirements, and prep time
- Images stored in `build/cub-scout-adventures/{rank}/images/`

## Historical Change Tracking

Changes to requirements are tracked and preserved using Git's version control:

1. **Individual Files**: Each merit badge and adventure is stored as separate JSON and Markdown files
2. **Git History**: Changes are committed only when requirements actually differ
3. **Detailed Commit Messages**: Commit messages include which items were added, removed, or modified
4. **Web Interface**: A GitHub Pages site provides access to current requirements with links to Git history

## Website

The project automatically deploys a simple website to GitHub Pages that includes:

- An index of all available merit badges and Cub Scout adventures
- Individual pages for each item with full requirements
- Links to original scouting.org pages and resources
- Images for each badge and adventure

## Automated Archive

The project includes GitHub Actions workflows that:

1. Run archive process automatically on a schedule
2. Generate structured comparison reports between archive runs
3. Commit changes to the repository with detailed commit messages
4. Deploy an updated website to GitHub Pages

You can also manually trigger these workflows from the GitHub Actions tab.

## Troubleshooting

### Manual Intervention

In case of failures:

1. Use the workflow_dispatch trigger to manually run the archiver
2. Check the GitHub Actions logs for detailed error information
3. Run the validation steps to identify specific issues:
     ```shell
     make validate
     make validate-cub-adventures
     ```
4. Run the archivers locally to debug issues:
     ```shell
     make archive
     make archive-cub-adventures
     ```
