# Security Policy

This repository is public-safe by design. Production secrets, access tokens, database dumps, browser profiles, logs and runtime state must stay outside git and only on the target servers or secret managers.

## What must never be committed

- `.env` and `.env.*` files with real values
- API keys, OAuth tokens, Telegram bot tokens, payment provider keys
- database dumps, SQLite files, Redis dumps
- browser profiles, cookies, session storage
- production IPs, SSH commands with real hosts, admin passwords
- customer data, resumes, personal documents, chat exports

## Configuration pattern

Use `.env.example` and docs with placeholders only. Real values are injected at deploy time through server-local environment files, CI secrets or a secrets manager.

## Reporting

If you find a secret in this repository, do not open a public issue with the value. Contact the repository owner privately and include only the path and type of secret.
