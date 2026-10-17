# Encryption key configuration and rotation

chat2db encrypts stored database passwords and LLM API keys with Fernet.
The key must be supplied through the environment variable `CHAT2DB_ENCRYPTION_KEY`.

## Fresh installation

1. Generate a key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

2. Put it in an untracked environment file or secret manager. See `.env.example`.
3. Start the backend. Startup fails closed if the variable is missing or not a valid Fernet key.

## Existing installation / key rotation

Changing `CHAT2DB_ENCRYPTION_KEY` makes previously encrypted values unreadable.
There is no silent automatic migration that re-encrypts old ciphertext under a new key.

Safe procedure:

1. Keep the old key available until every stored credential has been re-entered or migrated.
2. For each database connection and LLM API key in the UI (or metadata store), re-enter the secret while the new key is configured so it is encrypted with the new key.
3. Only after every credential works under the new key, discard the old key.
4. Treat any previously committed or shared Fernet key as compromised. Do not reuse it.

If the old key is lost, encrypted credentials cannot be recovered. Re-enter them.

## Release note

An encryption key file was previously present in Git history and must be treated as compromised.
Rotate keys and re-enter stored credentials for any installation that may have used that key.
