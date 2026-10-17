# Security Policy

## Status

chat2db is experimental and is not currently recommended for production databases or sensitive data. The repository is being prepared for public release; secret handling and Git history must be reviewed before that release.

## Reporting a vulnerability

Please do not publish exploitable vulnerability details in a public issue. Contact the repository owner privately through GitHub to coordinate a responsible disclosure. Include the affected component, impact, and reproduction steps, while avoiding real customer data or live credentials.

## Safe-use guidance

- Never commit API keys, database credentials, encryption keys, production environment files, logs, or database dumps.
- Use least-privilege credentials and preferably read-only database access when exploring data.
- Treat AI-generated SQL as untrusted and inspect it before execution.
- Do not expose the application to untrusted networks without a security review.
- If a secret is committed, revoke or rotate it; deleting it from the latest commit is not sufficient.
