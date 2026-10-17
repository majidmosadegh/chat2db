# chat2db

**Ask your database questions in natural language.**

chat2db is an early-stage project exploring AI-assisted SQL generation and database chat. It started as an independent experiment about a year ago, without LangChain as the core architecture. The code is now being prepared for community development because the original creator cannot actively lead development at the moment.

**The project is looking for contributors and potential maintainers.** If you are interested in improving the implementation, reviewing its architecture, or helping guide its future, you are welcome to get involved.

> **Status: experimental.** This repository has not yet been independently audited or verified as production-ready. Features and setup instructions below describe the intended/current codebase and should be validated before use.

## What it explores

- Chat-based interaction with databases and AI-assisted SQL generation.
- A backend built with Python and FastAPI.
- A Next.js frontend.
- LLM integration code for OpenAI-compatible use, vLLM, Ollama, and custom HTTP providers.
- Database connector code for PostgreSQL, MySQL, and SQL Server.
- Schema context, data-dictionary, relationship, and use-case generation workflows.

These capabilities have not all been independently validated in this release. Please check the implementation and report discrepancies rather than assuming every feature is complete.

## Why this project?

Many people understand the question they want to ask of their data but do not know how to write the SQL. chat2db explores how AI can help translate a natural-language question into a query, use database context, and make the resulting SQL easier to inspect and improve.

The project did not begin with LangChain as its architectural foundation. That is part of its history, not a permanent constraint: contributors are welcome to evaluate the current design and propose changes based on real requirements.

## Current status and roadmap

The project is early-stage and needs community review. Initial areas where help would be valuable:

- Document the actual architecture and supported database/LLM combinations.
- Make setup reproducible across operating systems.
- Add or repair automated tests and CI.
- Review SQL generation, query execution permissions, and destructive-query protections.
- Review secret handling and encryption-key management before any production use.
- Improve the chat UX, examples, and developer documentation.
- Help establish a roadmap and take on long-term maintainer responsibilities.

These are areas to investigate, not claims that the work is already complete.

## Getting started

The existing repository includes a Python backend, a Next.js frontend, and Windows-oriented startup scripts. Setup instructions and scripts may be stale, so validate them against the current code.

### Prerequisites

- Python (see backend dependencies for the version actually required).
- Node.js and npm (see `frontend/package.json` for the supported version).
- Git.
- An LLM provider and API credentials if you choose a hosted model; local providers may require separate setup.

### Configuration

1. Copy `.env.example` to an untracked `.env` (or export the variables in your shell).
2. Generate `CHAT2DB_ENCRYPTION_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

3. Copy `frontend/.env.example` to `frontend/.env.local` if you need a non-default backend URL.
4. Read [docs/ENCRYPTION_KEY.md](docs/ENCRYPTION_KEY.md) before rotating keys on an existing installation.

### Manual development setup

Backend:

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# ensure CHAT2DB_ENCRYPTION_KEY is set
python main.py
```

Frontend, in a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Expected local defaults are backend `http://localhost:8000` and frontend `http://localhost:3000`. Validate against the current code. Never put real secrets in committed files.

### Tests

```bash
cd backend
pip install -r requirements.txt pytest
# ensure CHAT2DB_ENCRYPTION_KEY is set
pytest tests/security -q
```

```bash
cd frontend
npm ci
npm run build
```

CI runs security tests, Gitleaks, and the frontend build on pull requests.

## Security warning

**Do not connect this project to a production database or sensitive data until the code has been reviewed.** AI-generated SQL is untrusted input. Use least-privilege database credentials, prefer read-only access for exploration, and verify queries before execution.

Treat any encryption key or credential that was previously present in Git history as compromised. Generate a new Fernet key for every deployment and re-enter stored credentials after rotation. See [docs/ENCRYPTION_KEY.md](docs/ENCRYPTION_KEY.md).

Please report security vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## Contributing

You can help by reproducing issues, improving docs, adding tests, reviewing the architecture, or taking responsibility for a subsystem.

1. Read [CONTRIBUTING.md](CONTRIBUTING.md).
2. Search existing issues before opening a new one.
3. For substantial changes, discuss the proposal in an issue first.
4. Submit focused pull requests with tests or a clear description of what you verified.

The original creator has limited time to lead development right now. People interested in becoming core contributors or maintainers are especially welcome.

## License

Released under the [MIT License](LICENSE). Copyright (c) 2026 Majid Mosadeq.

## Project links

- [Issues](https://github.com/majidmosadegh/chat2db/issues)
- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
