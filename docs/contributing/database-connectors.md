# Contributing database connectors

**Status:** contribution contract and roadmap guidance  
**Product:** Chat2DB — open-source AI database assistant / natural-language-to-SQL explorer

Expanding database support is a planned part of Chat2DB’s evolution. This document separates what exists today from what is planned, and describes how to propose or implement a connector without overstating maturity.

## Current support (audit summary)

Code and UI were inspected for connector types. **Presence in code or a dropdown is not the same as CI-verified connectivity.**

### Implemented (code present)

| Database | Where it appears | Maturity notes |
| --- | --- | --- |
| PostgreSQL | `DirectDatabaseConnector`, `engine_factory`, `/database` UI | Implementation present; not covered by CI against a live Postgres |
| MySQL | Same | Implementation present; not covered by CI against a live MySQL |
| SQL Server | Same (+ pymssql/aioodbc paths) | Implementation present; host ODBC/driver setup often required; not covered by CI against a live SQL Server |

CI currently gates security unit tests, Gitleaks, and the frontend build—not live multi-database integration suites.

### Planned (intent to evaluate)

Candidates for evaluation as the adapter surface matures (no delivery dates implied):

- SQLite (file-based demos and local experiments)
- MariaDB (often close to MySQL paths; still needs explicit validation)
- Oracle Database
- Snowflake
- BigQuery
- DuckDB
- Other warehouse / analytical engines requested by contributors

Treat this list as a backlog for discussion, not a promise of support.

### Community proposals

Open an issue to propose a database when you can speak to:

- Demand (who needs it and why)
- Technical feasibility (Python drivers, async story, schema introspection)
- Maintainer willingness (who will own tests and breakage)

## Expected connector contract

A healthy connector contribution should cover at least:

1. **Connection configuration** — host/port/user/password/database (or equivalent), validated in API and UI.
2. **Secure credential handling** — reuse existing encryption (`CHAT2DB_ENCRYPTION_KEY`); never log secrets.
3. **Connect / disconnect lifecycle** — clear errors on failure.
4. **Schema introspection** — enough metadata for Chat2DB context (tables/columns/types as applicable).
5. **Safe query execution** — integrate with read-only validation (`validate_sql` / `validate_read_only_sql` or successor); reject destructive statements.
6. **Sampling helpers** (optional but useful) — limited `SELECT` samples for dictionary/AI features.
7. **Tests** — unit tests for URL/build/validation; integration tests when credentials/services are available in CI or documented local recipes.
8. **Documentation** — README/matrix update, driver prerequisites, known limitations.
9. **CI impact** — do not weaken security gates; add jobs only when they are reliable.

Primary code touchpoints today (subject to refactor):

- `backend/services/db_connector.py` — `DirectDatabaseConnector`
- `backend/db/connector.py` — chat-oriented `DatabaseConnector` + `execute_readonly`
- `backend/db/engine_factory.py` — SQLAlchemy async engines
- `backend/db/security.py` — SQL validation and password decryption
- `frontend/app/database/page.tsx` — connection UI options

Longer term, contributors may help extract a cleaner **database adapter interface** so new engines do not require large `if/elif` chains.

## Suggested contribution workflow

1. Open an issue: target database, drivers, scope (connect + schema + execute), and test plan.
2. Implement behind clear type keys (e.g. `postgresql`, `mysql`, `sqlserver`, …).
3. Wire UI option only when backend path exists.
4. Add tests and docs in the same PR when possible.
5. Update the compatibility tables in the root `README.md` with honest status labels.

## Status labels to use in docs/PRs

| Label | Meaning |
| --- | --- |
| Implemented (code) | Paths exist in the repository |
| Experimental | Wired but not broadly verified |
| CI-verified | Automated tests run against a real or containerized engine in CI |
| Planned | Intention to evaluate; not available yet |
| Proposed | Community request under discussion |

## Related

- Agentic architecture vision: [`../vision/agentic-architecture.md`](../vision/agentic-architecture.md)
- Security policy: [`../../SECURITY.md`](../../SECURITY.md)
- Contributing guide: [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md)
