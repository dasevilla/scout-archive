---
name: Archiver Failure
about: Issue created automatically when the archiver workflow fails
title: 'Archiver Job Failed: {{ date | date("YYYY-MM-DD") }}'
labels: bug, automation
assignees: dasevilla
---

## Archiver Failure Report

The scheduled archiving job failed on {{ date | date("YYYY-MM-DD") }}.

### Possible Causes

1. **Website Structure Changes**: The website may have updated its structure, causing our selectors to fail
2. **Validation Failures**: The archive quality checks failed because:
   - Not enough merit badges were found
   - Required badges are missing
   - Requirements data is incomplete
3. **Network Issues**: There might have been temporary connectivity problems
4. **Permission Issues**: GitHub Actions may have had insufficient permissions to commit changes

### Debugging Steps

1. Check the [action logs]({{ env.GITHUB_SERVER_URL }}/{{ env.GITHUB_REPOSITORY }}/actions/runs/{{ env.GITHUB_RUN_ID }}) for specific error messages
2. Run the archiver locally to test:
   ```shell
   make archive
   make validate
   ```
3. Check if the website structure has changed
4. Verify GitHub permissions are set correctly

### Recent Changes

[View recent commits]({{ env.GITHUB_SERVER_URL }}/{{ env.GITHUB_REPOSITORY }}/commits/main)
