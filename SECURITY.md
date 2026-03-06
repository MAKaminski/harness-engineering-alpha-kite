# Security Policy

## Supported Versions

Security updates are applied to the current main branch.

| Version | Supported |
| ------- | --------- |
| main    | yes       |
| < 1.0   | no        |

## Reporting a Vulnerability

Do not report vulnerabilities in public issues or PRs.

Use GitHub Security Advisories (Security -> Advisories -> Report a vulnerability) or a private maintainer channel.

Include:

1. Impact summary and affected area (`symphony`, `apps/api`, or `apps/web`)
2. Reproduction steps or PoC
3. Affected commits/versions
4. Suggested mitigation if available

## Trading Stack Security Notes

- Secrets must be environment variables only (`SUPABASE_SERVICE_ROLE_KEY`, `POLYGON_API_KEY`, `SCHWAB_ACCESS_TOKEN`, `LINEAR_API_KEY`, deploy tokens).
- Never expose service-role or trading API credentials in frontend bundles.
- `POST /orders/{user_id}` is gated behind `SCHWAB_ENABLE_ORDER_PLACEMENT=true`.
- Use `PROVIDER_MODE=mock` in local or CI environments without live credentials.
- Apply least-privilege database policies (see `apps/api/sql/supabase_schema.sql`) for multi-tenant tables.
- Treat Camelot ingestion inputs as untrusted data; validate schema before production usage.

## Symphony Operational Security

- Workspace roots must remain isolated and writable only by trusted users.
- Hooks in `WORKFLOW.md` execute as shell commands with Symphony privileges.
- Keep dashboard/API access restricted to trusted networks.
