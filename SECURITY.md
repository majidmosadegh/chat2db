# Security Policy

## Status

chat2db is experimental and is not currently recommended for production databases or sensitive data.

## Reporting a vulnerability

Please do not publish exploitable vulnerability details in a public issue. Contact the repository owner privately through GitHub Security Advisories (preferred) or by messaging the repository owner on GitHub to coordinate a responsible disclosure. Include the affected component, impact, and reproduction steps, while avoiding real customer data or live credentials.

Do not invent or use alternate contact channels that are not listed here.

## Safe-use guidance

- Never commit API keys, database credentials, encryption keys, production environment files, logs, or database dumps.
- Configure secrets through environment variables. See `.env.example` and [docs/ENCRYPTION_KEY.md](docs/ENCRYPTION_KEY.md).
- Use least-privilege credentials and preferably read-only database access when exploring data.
- Treat AI-generated SQL as untrusted and inspect it before execution.
- Do not expose the application to untrusted networks without a security review.
- If a secret is committed, revoke or rotate it; deleting it from the latest commit is not sufficient.

## Known security model limits

- The application does not yet ship a complete multi-user authentication and authorization model for untrusted internet exposure.
- SQL execution paths enforce read-only validation, but AI-generated SQL should still be reviewed.
- Previously exposed encryption material must be treated as compromised; rotate keys and re-enter stored credentials. See [docs/ENCRYPTION_KEY.md](docs/ENCRYPTION_KEY.md).
