# Credential Rotation Runbook

## Purpose and safety boundary

Use this runbook after a suspected disclosure or during scheduled rotation.
Rotation changes live systems and requires an approved maintenance window,
current backups, named operator/reviewer, and a rollback owner. This repository
change does not rotate any credential.

Rotate first. Optional Git-history cleanup happens only afterward under a
separate destructive-change approval; rewriting history does not invalidate a
credential that has already escaped.

## Preparation

1. Record the incident/change ticket, affected environments, start time, and
   credential owners.
2. Verify a restorable PostgreSQL backup and record its checksum and location.
3. Capture current service health and the deployed image digest.
4. Create replacement values in the approved secret manager. Never paste them
   into chat, tickets, shell history, logs, or Git.
5. Identify every consumer before revoking the old value.

## Rotation order

### PostgreSQL

Create a replacement database role/password with the same least privileges,
update `POSTGRES_PASSWORD` and `DATABASE_URL`, restart consumers, validate API,
worker, beat, and listener queries, then revoke the old role/password. Roll back
by restoring the prior secret only while it remains valid.

### Redis and Celery

Set a new Redis password during a controlled restart, update `REDIS_PASSWORD`,
`REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` for every process,
then validate ping, queue publish/consume, scheduled tasks, and revocation
lookups. Do not run mixed passwords longer than the maintenance window.

### Administrator password

Set a unique password of at least 12 characters through the approved admin
recovery path, revoke existing admin sessions/tokens, verify login and 2FA, and
record only the secret-manager reference.

### JWT secret

Changing `SECRET_KEY` invalidates all platform, customer, and sales JWTs.
Schedule a coordinated backend/worker/listener restart, force all users to log
in again, and verify rejected old tokens plus accepted new tokens.

### Session encryption key

Inventory encrypted Telegram session files before changing
`SESSION_ENCRYPTION_KEY`. Decrypt/re-encrypt through an audited offline
migration with backup copies and a sampled login verification. Never discard
the old key until every file is migrated and the rollback window closes.

### Payment provider

Rotate the NowPayments IPN secret and any payment API credentials at the
provider, update the secret manager and `NOWPAYMENTS_IPN_SECRET`, then send a
signed test notification and verify idempotent settlement. Revoke the old
provider credential after verification.

### LLM providers

Rotate OpenAI, DeepSeek, Google/Vertex, and other configured provider keys in
their respective consoles. Update all API, worker, and listener consumers;
verify one non-sensitive health request per enabled provider; then revoke old
keys and review provider audit logs for abuse.

### Telegram API and session credentials

Rotate Telegram API id/hash only with an account re-authentication plan.
Individually revoke and recreate compromised `.session`/TData credentials,
verify the intended phone/account mapping, and keep files out of Git and logs.

### TLS private keys

Generate a new private key and certificate through the approved CA workflow,
deploy atomically, validate hostname/chain/expiry from an external client, then
revoke the old certificate where supported. Never reuse a disclosed key.

## File ownership and permissions

Run read-only checks before changing permissions:

```bash
find backend -maxdepth 2 -type f \( -name '.env' -o -name '*.session' \) -printf '%m %u:%g %p\n'
find ssl -maxdepth 1 -type f -name '*.key' -printf '%m %u:%g %p\n'
```

Secret files must be owned by the deployment service account and group, with
mode `0600`. Apply `chown`/`chmod` only to individually reviewed absolute paths;
never use a recursive command over the repository or home directory.

## Verification and evidence

- Run `scripts/check_tracked_secrets.sh` and the release preflight.
- Verify API login, customer login, sales login, WebSocket rejection/acceptance,
  one Celery task, one listener heartbeat, and one payment test notification.
- Confirm old credentials fail after revocation.
- Attach timestamps, secret-manager version identifiers, image digest, command
  exit codes, and reviewer sign-off to the incident/change ticket.
- Monitor authentication failures, payment errors, queue depth, and provider
  audit logs through the rollback window.

## Optional history cleanup

Only after every exposed credential is revoked may a separately approved plan
rewrite Git history. It must enumerate exact paths/patterns, create a recovery
mirror, coordinate force-push and clone invalidation, and document the new
commit roots. History cleanup is destructive and is not part of this runbook's
normal rotation execution.
