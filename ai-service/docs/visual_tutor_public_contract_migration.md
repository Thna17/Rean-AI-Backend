# Visual Tutor public turn contract migration

The student-facing turn contract is schema version `1`. The Flutter app sends
`public_contract_version: 1`; the TypeScript gateway injects the same value and
rejects any response that is not the compact envelope.

The historical full turn payload is a temporary development-only diagnostic
path. It requires both a trusted internal-service request and
`X-Visual-Tutor-Api-Compatibility-Version: 0`. Staging and production ignore
that compatibility request and always return the compact contract.

Before removing compatibility version `0`:

1. Keep the Python, TypeScript, and Flutter contract tests green for one
   release cycle after all supported clients use schema version `1`.
2. Confirm gateway metrics show no compatibility-version requests outside test
   environments.
3. Remove the compatibility header handling, legacy Flutter turn parsing, and
   legacy-only test fixtures together in the next major API release.
4. Retain persisted full responses server-side only for audit/replay migration;
   never re-expose them to a student client.
