# Known limitations

- Production readiness is not implied by a passing build. Curriculum coverage, Khmer glossary review, staging evidence, security sign-off, and pilot outcomes remain release gates.
- The root production Compose file intentionally has no TLS proxy or backup scheduler. Deploy it behind a managed ingress/TLS layer and use managed backups or a separately tested backup job.
- The admin service is optional in Compose (`--profile admin`) and needs its own operational authentication/configuration review before public exposure.
- The current repository has historical scripts and phase/audit files that refer to removed services. They are preserved for audit history and must not be used to deploy; see `ARCHIVED_PHASE_AUDITS.md`.
- Current automation verifies source builds and tests. It does not replace a real staging load test, device matrix, teacher review, or rollback drill.
