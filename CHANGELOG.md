# Changelog

What changed in the Authentication API, newest first.

## 1.1a1 — unreleased

Requires WebFluid `1.0.0rc1`.

### Routes only your phone app can call

`auth` now tells a request from your mobile app apart from everything else, and the routes that only
the app calls accept nothing else.

- Device routes (`/mobile`, `/mobile/challenge`, `/mobile/login`, `/mobile/keylog`,
  `/mobile/actions`, and the device side of the 2FA approval: `/users/2fa/mobile/pending`,
  `/approve`, `/deny`) require the `X-Client-Ident` header with the deployment's mobile secret and a
  platform user agent such as `myapp/1.0.0 (android; com.example.app)`. Anything else gets
  `401 INVALID_CLIENT` or `401 INVALID_USER_AGENT`.
- The user-agent check accepts a known shape instead of chasing a list of browsers and bots, so a
  new crawler or browser engine cannot slip through by an unknown name.
- The secret is compared in constant time, and a missing secret refuses every request instead of
  matching a missing header.
- The new query `auth_mobile:verify-client` applies the same check to any route outside `auth`; it
  answers `null` or the refusal code.

**Upgrade:** set `MOBILE_SECRET` in the `[auth]` section of the app config — `wf create app`
generates one — and have your app send it as `X-Client-Ident`. `auth` refuses to start without it
under `wf run`.

### The phone as an account's device

An account can bind one phone. The phone holds an X25519 and an Ed25519 key pair; `auth` only ever
sees the public halves.

- `POST /api/v1/mobile` binds the first device, `PUT /api/v1/mobile` replaces it — only from a
  session that signed in with a password or a provider, never from a device login — and
  `POST /api/v1/mobile/login` signs in with a challenge (`POST /api/v1/mobile/challenge`) signed
  by the device. Unknown accounts, accounts without a device and wrong signatures are
  indistinguishable.
- Every binding, replacement, recovery authority and browser key is a statement in the account's
  **key log** (`GET /api/v1/mobile/keylog`), signed by the device, the recovery key or — flagged —
  the host. `auth_keylog:state`, `:append` and `:unlink` let other Additives read and extend it.
- **Signed actions:** `auth_action:accept` verifies a `wf-action-v1` action signed by the device
  (account, target, committed parameters, sequence, chain, replay, validity window) and
  `auth_action:result` records what the host did with it (`GET /api/v1/mobile/actions`). With the
  `peering` Additive, key statements and actions are handed to `peering_record` every
  `AUTH_LEDGER_FLUSH_INTERVAL` seconds (`auth_ledger:flush`).
- `auth_user-encrypt` seals data so only the account's device can open it; `auth_verify-signature`
  checks a device signature; `auth_mobile:fingerprint` names the device in pushes.
- `auth_mobile:replaced` is emitted when an account moved to other device keys.

### The phone counts as second factor

Once an account has a device, every password or provider sign-in — in a browser or in an app on
another phone — has to be approved on it by number matching. The session carries no user until the
approval is complete, so every gate of every Additive answers `401 NOT_AUTHENTICATED` in the
meantime. The signing-in client follows the approval through `GET /api/v1/users/2fa/mobile` and
finishes with `/complete`, `/fallback` (TOTP, WebAuthn or a backup code instead) or `/cancel`; the
device is notified by the `auth_mobile:approval` push.

An Additive that runs its own second factor on the device takes the approval over with the
`auth_mobile:delegate` query and settles it through `auth_mobile:approval-state` and
`auth_mobile:resolve`.

`GET /users/me` answers `has_mobile`. A role that requires two-factor authentication is satisfied
by a phone, so clients no longer have to force TOTP or a security key on an account that already
has its phone as second factor — they recommend one as a fallback instead.

### Single sign-on from native apps

A native app signs in with a provider in the system browser instead of an embedded web view
(RFC 8252): `POST /api/v1/{provider}/app` starts the flow with a PKCE challenge and a redirect from
`AUTH_SSO_APP_REDIRECTS`, the callback hands the app a single-use code instead of signing the
browser in, and `POST /api/v1/{provider}/app/exchange` turns code and verifier into the app's
session. The flow is off while `AUTH_SSO_APP_REDIRECTS` is empty.

### Gates for other Additives

- **Login gate:** every route that would establish a session from credentials first asks the
  fan-out query `auth_login:admit` with the method (`password`, `register`, `setup`, `provider`,
  `app-sso`, `device`). A refusal code is answered as `403 <code>`.
- **Credential gate:** every route that changes the password or a second factor first asks
  `auth_credentials:admit`.
- Without a handler nothing changes.

### Account deletion

`auth_user:delete` is fanned out before an account row is deleted — by `DELETE /users/me`, by the
admin route and by the sweep of unconfirmed accounts — so every Additive can remove what it stores
against the account. `DELETE /users/me` answers `500 DELETION_INCOMPLETE` and keeps the account
when a handler fails.

A deleted account is retired first: its personal tokens are revoked, and a key log that anchors
anything is closed with a host statement carrying `reset: true`. A new account that SQLite later
gives the same id therefore starts without the device, keys or links of its predecessor.

### Email verification

- The email address left `PATCH /users/me`. `GET /api/v1/verification/email` reports its state,
  `POST /api/v1/verification/email` sets or changes it and `POST /api/v1/verification/email/resend`
  resends the confirmation. These routes are gated at the lowest rung (a session), so an account
  can finish its activation — for example after a provider sign-in that carried no address — and
  escalate internally where a change is as sensitive as a fully authenticated one.
- Without an `auth_send:confirm` handler an address is accepted as verified instead of locking the
  account behind a gate nothing can open.
- `auth_send:confirm` always carries the request's `locale`.
- A confirmation link issued for an address change only confirms that address, and only while it is
  still the pending one.

**Upgrade:** `POST /api/v1/users/confirm/resend` is replaced by
`POST /api/v1/verification/email/resend`; clients change the address through
`POST /api/v1/verification/email`.

### Hardening

- Rate limits on every route that takes a secret: registration, login, setup, password reset,
  `PATCH /users/me`, TOTP, WebAuthn and backup-code verification, and the mobile routes.
- Ten failed TOTP or backup-code verifications of an account within 15 minutes answer
  `429 TOO_MANY_ATTEMPTS`, whatever address they come from.
- A TOTP code is accepted once; a code of the same or an earlier time step is refused.
- An unknown account and a wrong password take the same time and answer the same
  `401 INVALID_CREDENTIALS`; a provider-only account answers `400 PROVIDER_ONLY`.
- A session that has not passed its second factor can no longer enrol another one once the account
  holds a factor.
- Personal tokens: names are 1–64 characters and unique among the live tokens, the payload may only
  carry `permissions`, the lifetime is bounded by `AUTH_JWT_MAX_DAYS` (365). Renaming or revoking a
  token another account owns answers `400 UNKNOWN_TOKEN`.

### Fixes

- Token revocation warming runs after registration setup and propagates database failures.
  Missing tables or unavailable storage must not silently leave revoked tokens usable. Apply
  migrations before enabling authentication. Tests import the token models before creating their
  disposable database schema.

### Signals

- `user:role-update` is emitted by the server, after the change is committed, for every admin
  route that changes what a user is granted — once per affected user.
- `auth_oauth:first-callback` is emitted when a provider sign-in created an account, with the
  provider's claims normalised to stable field names (`first_name`, `last_name`, `roles`, …).

### Integrity

With the `peering` Additive, `auth` reports the hash of the `static/js/utils.js` it serves through
`peering_integrity`.

## 1.0b1

Requires WebFluid `1.0.0b1` or later.

- Every route opens its own database session and loads the relations it reads up front, as
  WebFluid `1.0.0b1` requires.
- Role member counts and permission role counts are counted in the database instead of loading
  every member.
- The guards against removing your own admin role await the admin check.
- Renaming and revoking a personal token compare the owner by account id.

## 1.0a1

The first version. Requires WebFluid `1.0.0a2`.

- Registration, email confirmation with removal of accounts that stay unconfirmed, password reset,
  sessions, and OAuth sign-in and linking.
- Two-factor authentication with TOTP, WebAuthn/passkeys and backup codes.
- Personal JWTs with a nightly watcher that keeps revoked tokens out of circulation.
- Admin endpoints for users, roles and permissions.
