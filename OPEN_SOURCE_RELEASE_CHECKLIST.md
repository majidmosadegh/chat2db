# Open-source release checklist

This checklist is intentionally conservative. Do not switch this repository to public until every release blocker is resolved and verified.

## Confirmed blockers

- [x] Add MIT license file to the application branch.
- [x] Add contributor and security guidance to the application branch.
- [x] Remove the committed encryption-key file from the current application tree.
- [x] Change encryption setup to require `CHAT2DB_ENCRYPTION_KEY` from the environment instead of silently recreating a fixed key.
- [x] Add ignore rules for local environment files, the encryption-key file, and common database backups.
- [x] Remove the hard-coded password fallback from `backend/db/security.py`; decryption now requires `CHAT2DB_ENCRYPTION_KEY` and fails closed.
- [ ] Rotate the previously exposed Fernet key and any credential that may have been exposed through the hard-coded fallback. Treat them as compromised; do not reuse them for new installations.
- [ ] Decide how existing locally stored encrypted database credentials will be migrated or re-entered before rotating the key in any existing installation.
- [ ] Rewrite Git history on every branch and tag to remove the previously committed encryption key and review/remove any sensitive configuration. Removing a file in a new commit does not remove it from earlier commits.
- [ ] Scan every branch, tag, commit, and repository object for credentials, tokens, private URLs, personal data, database files, logs, and backups. Revoke/rotate any credential that may have been exposed.
- [ ] Verify that the history-cleanup result no longer contains the key or other secrets, using a fresh clone and automated secret scanning.
- [ ] Run the app from a clean clone using documented environment variables; verify backend startup, frontend startup, and core chat/SQL flows.
- [ ] Run available tests and record known failures or missing coverage honestly.
- [ ] Review SQL execution permissions, destructive query protections, authentication/authorization, logging, CORS, API-key decryption behavior, and secret handling. Do not connect to production data during this review.
- [ ] Ensure no private or customer data, proprietary material owned by others, or files without redistribution rights are included.
- [ ] Check that README, setup scripts, dependency versions, and links match the actual code.
- [ ] Confirm the MIT license is on the intended public default branch and its copyright holder/year are correct.
- [ ] Resolve the branch layout: `main` and `master` currently have unrelated histories, and `main` does not contain the application code. Choose a canonical branch and verify GitHub's default-branch setting before release.
- [ ] Add repository description and relevant Topics, then enable Issues and Discussions as appropriate.
- [ ] Only after all blockers pass, change repository visibility from private to public and verify the public clone, README rendering, license, and links.

## Important key-handling note

The old key was committed to Git history and must be considered compromised even after the current file is deleted. The new application code expects a valid Fernet key in `CHAT2DB_ENCRYPTION_KEY`. Generate one for each deployment/installation and store it in a secret manager or untracked environment configuration.

Changing the key makes previously encrypted values unreadable unless they are migrated or re-entered using a controlled process. Do not overwrite an existing deployment's key without first planning that migration.

## History cleanup guidance

Perform history rewriting in a controlled local clone, after making a secure backup. Use a history-rewriting tool such as `git filter-repo` to remove the key file and any other sensitive historical files from every branch and tag, then force-push the cleaned refs. Coordinate this carefully because it changes commit IDs. A new deletion commit alone is not sufficient.

Do not put the old key value in issues, documentation, commits, or release notes.
