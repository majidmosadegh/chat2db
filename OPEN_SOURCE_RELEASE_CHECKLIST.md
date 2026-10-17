# Open-source release checklist

This checklist records release hardening status. Do not invent completed results.

## Application security (working tree)

- [x] MIT `LICENSE` on the application branch (Copyright (c) 2026 Majid Mosadeq).
- [x] `CONTRIBUTING.md` and `SECURITY.md` present.
- [x] Encryption key required from `CHAT2DB_ENCRYPTION_KEY`; fail closed when missing/invalid.
- [x] Password and API-key decryption fail closed (no plaintext / hard-coded fallback).
- [x] `DirectDatabaseConnector.execute_query` validates read-only SQL before execution.
- [x] `.env.example` and `frontend/.env.example` with placeholders only.
- [x] `.gitignore` covers env files, key files, databases, logs, build output.
- [x] Encryption rotation / re-entry documented in `docs/ENCRYPTION_KEY.md`.
- [x] Security unit tests under `backend/tests/security/`.
- [x] CI workflow for security tests, Gitleaks, and frontend build.
- [ ] Operators must rotate any previously exposed Fernet key and re-enter stored credentials (operational; not automatable here).

## History cleanup

- [ ] Backup original refs before rewrite.
- [ ] Remove sensitive historical paths from every affected ref (`backend/api/encryption_key.txt`, `frontend/.env.production`, historical unsafe `security.py` / `database.py`).
- [ ] Gitleaks clean on rewritten history.
- [ ] Path/pattern verification on rewritten history.
- [ ] Align `main` to the cleaned application history (replace unrelated docs-only `main`).
- [ ] Push rewritten refs only after verification; keep private until gates pass.
- [ ] Set GitHub default branch to `main`.
- [ ] Set repository visibility to public only after the above pass.

## Verification commands (record real results during release)

```text
gitleaks git . --redact
pytest tests/security -q   # from backend/, with CHAT2DB_ENCRYPTION_KEY set
npm ci && npm run build    # from frontend/
```

## Known limitations (honest)

- No full multi-user authz model for public internet exposure.
- Many legacy backend tests are exploratory and are not part of the release gate.
- AI-generated SQL remains untrusted input even with read-only guards.
