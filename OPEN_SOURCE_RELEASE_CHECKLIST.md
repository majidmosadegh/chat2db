# Open-source release checklist

Status recorded from the release engineering run. Do not invent completed results.

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
- [ ] Operators must rotate any previously exposed Fernet key and re-enter stored credentials (operational; not automatable in git).

## History cleanup

- [x] Backup original refs before rewrite (`D:\tmp\chat2db-original-refs-backup`).
- [x] Removed sensitive historical paths from rewritten refs (`backend/api/encryption_key.txt`, `frontend/.env.production`, historical `security.py` / `database.py`).
- [x] Gitleaks clean on rewritten history (`no leaks found`, 27 commits scanned).
- [x] Path/pattern verification on rewritten history (`HITS 0`).
- [x] `main` aligned to cleaned application history (same tip as `master`).
- [x] Push rewritten refs with force-with-lease (main+master -> 3ce2a40); verified on fresh clone.
- [ ] Set GitHub default branch to `main`.
- [x] Repository visibility set to public after verification.

## Verification command results (this run)

```text
gitleaks git . --redact
-> no leaks found (exit 0)

pytest tests/security -q   # backend/, CHAT2DB_ENCRYPTION_KEY set
-> 6 passed (exit 0)

Independent local clone of rewritten main:
-> gitleaks no leaks found; pytest 6 passed
```

Frontend `npm run build` succeeded on the pre-rewrite security tip that includes restored `frontend/lib/*`.

## Known limitations (honest)

- No full multi-user authz model for public internet exposure.
- Many legacy backend tests are exploratory and are not part of the release gate.
- AI-generated SQL remains untrusted input even with read-only guards.
- Previously exposed credentials must be rotated by operators; treat them as compromised.
