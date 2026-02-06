# Security

## Reporting vulnerabilities

If you discover a security vulnerability, please report it responsibly by opening a private issue or contacting the maintainer directly. Do not open a public issue for security vulnerabilities.

## Security model

This system runs AI agents with significant filesystem and network access. The security model assumes:

- **Trusted network.** Agents communicate over a local network. Services like AgentChat have no authentication by default.
- **Trusted operator.** The human who sets up the system has full control. Agents run as the operator's user.
- **Defense in depth is the operator's responsibility.** The system does not enforce firewalls, service isolation, or least-privilege by default. See `onboarding/PERMISSIONS.md` for a hardening checklist.

## What's NOT in this repo

- API keys, tokens, or credentials of any kind
- SSH private keys
- Personal information (real IPs, usernames, Telegram IDs)
- Database files or runtime state

## Recommendations

- Run a firewall (`ufw`) and only expose ports you need
- Use separate user accounts for agents in production
- Rotate API tokens regularly
- Don't expose AgentChat or the OpenClaw gateway to the internet without authentication
