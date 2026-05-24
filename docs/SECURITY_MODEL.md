# Security model

The system is designed around a human-in-the-loop workflow.

## Safe by default

- generation creates drafts, not external sends
- Telegram is used for review and alerts
- browser automation requires explicit configuration
- secrets are loaded from local environment files
- real candidate profiles are private deployment data

## Public repository rules

Only examples and placeholders are committed. Real browser profiles, databases, logs, resumes and tokens stay on the server.
