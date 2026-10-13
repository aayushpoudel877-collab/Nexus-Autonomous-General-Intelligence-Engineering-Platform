# Security

## Reporting a vulnerability

Do not publish exploit details, credentials, tokens, private keys, or personal data in public issues or pull requests.

If GitHub private vulnerability reporting is enabled for this repository, use the repository's **Security → Advisories → Report a vulnerability** workflow. If it is not enabled, contact the repository maintainers privately through a verified channel rather than posting sensitive details publicly.

Before production deployment, the repository owner should enable private vulnerability reporting and publish a monitored security contact. Reports should include the affected commit, impact, and minimal reproduction steps without including real secrets or user data.

## Deployment checklist

- Set a unique, high-entropy NEXUS_SECRET_KEY; never use the development default in production.
- Configure explicit NEXUS_ALLOWED_HOSTS and CORS_ORIGINS values.
- Terminate TLS at a trusted proxy and enable HTTPS-only deployment.
- Keep database, artifact, runtime, and secret-provider credentials out of source control and logs.
- Keep sandbox launch disabled until the isolated runtime, resource limits, egress policy, and artifact verification are configured and tested.
- Treat passing CI as a code-quality signal, not as a complete security assessment or proof that all external integrations are configured.
