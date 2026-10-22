# Authentication API

> A WebFluid Additive — accounts, sign-in, sessions and second factors, done once.

## Why

Every application needs the same authentication core, and every hand-written one gets the
dangerous details slightly differently wrong: timing of failed logins, replayed one-time codes,
second factors that a password-only session can enrol, tokens that never really expire. `auth` is
that core written once, reviewed in one place and hardened by every deployment that runs it. You
enable it instead of rebuilding it — and when a weakness is found, the fix reaches every
application with the next release.

It is headless on purpose: a JSON API, background jobs and event-bus contracts, and no pages of
its own.

## What you get

- Registration, email confirmation, password reset and cleanup of unconfirmed accounts
- Sessions with a clear activation path (session → verified email → second factor)
- TOTP, WebAuthn/passkeys and backup codes, with attempt limits and replay protection
- OAuth sign-in and linking, and native-app sign-in through the system browser (PKCE)
- Personal JWTs with bounded lifetime and permission-only payloads
- One phone per account as second factor, device login, number-matching approval, a key log
- Admin endpoints for users, roles and permissions
- A single definition of an *app client* that any route can apply (`auth_mobile:verify-client`)

## Install

```bash
wf ocean install -a auth --prefer-stable
```

Enable it in the app config: `WF_ADDITIVES = 1`, `auth = 1` under `[additives]`, and the
extensions `EXT_SCHEDULING`, `EXT_SQLALCHEMY`, `EXT_SECURITY`, `EXT_EVENTS`, `EXT_CACHE`,
`EXT_JWT`. `wf create app` asks for the one secret, `MOBILE_SECRET` — the value your mobile app is
built with.

## Configure

| Key                            | Default                   | What it decides                                     |
|--------------------------------|---------------------------|-----------------------------------------------------|
| `AUTH_2FA_ISSUER`              | `"WebFluid"`              | Name shown in authenticator apps                    |
| `AUTH_2FA_WEBAUTHN_RP_ID`      | `"localhost"`             | WebAuthn relying party — your domain in production  |
| `AUTH_2FA_WEBAUTHN_ORIGIN`     | `"http://localhost:8000"` | Origin passkeys are bound to                        |
| `AUTH_ADMIN_ROLE_REQUIRES_2FA` | `True`                    | Admin roles always ask for a second factor          |
| `AUTH_SSO_APP_REDIRECTS`       | `[]`                      | Redirects native apps may use for SSO (empty = off) |
| `AUTH_JWT_MAX_DAYS`            | `365`                     | Longest lifetime a personal token may have          |

All keys, routes, events and error codes are in [CONTRACT.md](CONTRACT.md).

## Works with

`auth` requires nothing but WebFluid `>=1.0.0rc1`.

## For developers and agents

- [CONTRACT.md](CONTRACT.md) — the complete integration surface
- [.agents/SKILL.md](.agents/SKILL.md) — what a coding agent needs to use it correctly
- [CHANGELOG.md](CHANGELOG.md) — what changed, version by version

## License

The Authentication API is maintained by **GrowVolution e.V.** and released under the
**GNU General Public License v3 (GPL v3)**.

## Guide

[DOCS.md](DOCS.md) explains setup, operation and troubleshooting.
