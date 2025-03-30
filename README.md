# Scout Requirements Archive

A project to archive Scouts BSA merit badge requirements.

Goals:

- Have machine-readable versions of merit badges and their requirements
- Ability to review the history of the merit badge requirements as they evolve via git commits
- A simple static site of all the merit badges deployed to GitHub pages

## Usage

Create the archive:

```shell
make archive
```

Validate the archive:

```shell
make validate
```

Generate the index file:

```shell
make index
```

Generate change report:

```shell
make report
```

Run the entire archiving process (archive, index, validate, and report):

```shell
make all
```

Run code quality checks:

```shell
make check
```

## Output Format

The project generates two types of files for each merit badge:

1. **JSON files**: Structured data including badge name, overview, requirements, etc.
2. **Markdown files**: Human-readable format of the badge requirements

## Historical Change Tracking

Changes to merit badge requirements are tracked and preserved using Git's version control:

1. **Individual Badge Files**: Each merit badge is stored as separate JSON and Markdown files
2. **Git History**: Changes are committed only when badge requirements actually differ
3. **Detailed Commit Messages**: Commit messages include which badges were added, removed, or modified
4. **Web Interface**: A GitHub Pages site provides access to current badge requirements with links to Git history

## Website

The project automatically deploys a simple website to GitHub Pages that includes:

- An index of all available merit badges
- Individual pages for each merit badge with full requirements
- Links to original scouting.org pages and PDF files
- Images for each badge

## Automated Archiving

The project includes GitHub Actions workflows that:

1. Run the archiver automatically on a schedule
2. Generate structured comparison reports between archive runs
3. Commit changes to the repository with detailed commit messages
4. Deploy an updated website to GitHub Pages

You can also manually trigger these workflows from the GitHub Actions tab.

## Troubleshooting

### Manual Intervention

In case of failures:

1. Use the workflow_dispatch trigger to manually run the archiver
2. Check the GitHub Actions logs for detailed error information
3. Run the validation step to identify specific issues:
     ```shell
     make validate
     ```
4. Run the archiver locally to debug issues:
     ```shell
     make archive
     ```
