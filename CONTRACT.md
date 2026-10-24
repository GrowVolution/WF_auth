# Authentication API — Contract

<!-- index -->
Read this file in parts. Each range is `first-last` as the file stands now — open one with the Read
tool's `offset`/`limit`, or `sed -n 'first,lastp'`.

- `100-114` **At a glance**
- `115-706` **API**
  - `122-127` Health
    - `124-127` GET /api/health
  - `128-141` Bootstrap
    - `133-136` GET /api/v1/dev/setup
    - `137-141` POST /api/v1/dev/setup
  - `142-352` Accounts & Sessions
    - `144-149` POST /api/v1/users/create
    - `150-153` POST /api/v1/users/login/available
    - `154-169` POST /api/v1/users/login
    - `170-173` GET /api/v1/users/logout
    - `174-194` Login gate
    - `195-215` Credential gate
    - `216-247` Mobile clients
    - `248-256` Session flags
    - `257-266` GET /api/v1/users/me/available
    - `267-300` GET /api/v1/users/me · PATCH /api/v1/users/me · DELETE /api/v1/users/me
    - `301-335` Verification
    - `336-344` Email confirmation
    - `345-352` Password reset
  - `353-391` OAuth providers
    - `365-391` Sign-in from a native app
  - `392-413` Personal JWT Tokens
  - `414-541` Two-Factor Authentication
    - `425-428` GET /api/v1/users/2fa
    - `429-441` TOTP
    - `442-449` WebAuthn / Passkeys
    - `450-459` Backup codes
    - `460-525` Mobile approval
    - `526-541` Delegated approvals
  - `542-660` Mobile devices
    - `554-559` POST /api/v1/mobile/challenge
    - `560-567` GET /api/v1/mobile
    - `568-575` GET /api/v1/mobile/keylog
    - `576-594` Key-log statements
    - `595-599` GET /api/v1/mobile/actions
    - `600-626` POST /api/v1/mobile
    - `627-641` PUT /api/v1/mobile
    - `642-660` POST /api/v1/mobile/login
  - `661-706` Administration
    - `666-677` Users — grant `users:read` / `users:write`
    - `678-695` Roles — grant `roles:read` / `roles:write`
    - `696-706` Permissions — grant `permissions:read` / `permissions:write`
- `707-1013` **Events / Queries**
  - `713-826` Triggers
    - `715-721` auth_user:created
    - `722-727` auth_user:confirmed
    - `728-743` user:role-update
    - `744-753` auth_send:confirm
    - `754-758` auth_send:reset
    - `759-795` auth_oauth:first-callback
    - `796-802` auth_token:expires
    - `803-817` auth_mobile:approval
    - `818-826` auth_mobile:replaced
  - `827-930` Provides
    - `834-847` auth_user-encrypt *(query)*
    - `848-859` auth_verify-signature *(query)*
    - `860-864` auth_keylog:state *(query)*
    - `865-872` auth_keylog:append *(query)*
    - `873-881` auth_keylog:unlink *(query)*
    - `882-889` auth_action:accept *(query)*
    - `890-894` auth_action:result *(query)*
    - `895-899` auth_ledger:flush *(query)*
    - `900-909` auth_mobile:verify-client *(query)*
    - `910-916` auth_mobile:fingerprint *(query)*
    - `917-922` auth_mobile:approval-state *(query)*
    - `923-930` auth_mobile:resolve *(query)*
  - `931-1013` Consumes
    - `933-963` auth_user:delete *(query, fan-out)*
    - `964-972` auth_delete:unconfirmed *(signal)*
    - `973-981` peering_integrity *(provider, only with `peering`)*
    - `982-989` auth_login:admit *(query, fan-out)*
    - `990-997` auth_credentials:admit *(query, fan-out)*
    - `998-1007` auth_mobile:delegate *(query)*
    - `1008-1013` auth_page:confirmation · auth_page:reset · auth_page:invalid *(queries)*
<!-- /index -->

The public integration surface of the `auth` additive: the REST API it exposes
and the event-bus contracts it emits and consumes.

`auth` is headless. All routes are served under the additive's API mount
(`<prefix>/api`), versioned under `/v1`. It has no frontend and registers no app
pages.

Terminology used throughout this document:

- **Signal** — a fire-and-forget event (`events.trigger` / `events.event`).
- **Query** — a request/response contract (`events.query` / `events.request`).
- **public** — declared with `internal=False`; also reachable by browser clients
  over the events websocket. **internal** contracts are server-side only but may
  still be consumed across additives.

## At a glance

|                  |                                                                                                                                                                                                                       |
|------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Mount            | REST under `/auth/api`, versioned `/v1`; no pages, no frontend                                                                                                                                                        |
| Requires         | WebFluid `>=1.0.0rc1`; extensions `scheduling`, `sqlalchemy`, `security`, `events`, `cache`, `jwt`                                                                                                                    |
| Gates            | session (`require_user` → verified email → `require_2fa`), admin `is_admin` + grant, **mobile client** (`X-Client-Ident` + platform user agent)                                                                       |
| Secret           | `MOBILE_SECRET` → `AUTH_MOBILE_SECRET` (`[auth]` in the app config, generated)                                                                                                                                        |
| Config           | `AUTH_2FA_*` (issuer, backup codes, WebAuthn RP), `AUTH_ADMIN_ROLE_REQUIRES_2FA`, `AUTH_PROVIDER_APP_REDIRECTS`, `AUTH_PROVIDER_APP_TTL`, `AUTH_JWT_MAX_DAYS`, `AUTH_TOKEN_EXPIRY_EVENT_DEADLINE`, `AUTH_LEDGER_FLUSH_INTERVAL` |
| Emits            | `auth_user:created`, `auth_user:confirmed`, `user:role-update`, `auth_send:confirm`, `auth_send:reset`, `auth_oauth:first-callback`, `auth_token:expires`, `auth_mobile:approval`, `auth_mobile:replaced`             |
| Provides         | `auth_mobile:verify-client`, `auth_user-encrypt`, `auth_verify-signature`, `auth_keylog:*`, `auth_action:*`, `auth_ledger:flush`, `auth_mobile:fingerprint`, `auth_mobile:approval-state`, `auth_mobile:resolve`      |
| Extension points | `auth_user:delete` (fan-out), `auth_login:admit` (fan-out), `auth_credentials:admit` (fan-out), `auth_mobile:delegate`, `auth_page:*`, `auth_delete:unconfirmed`                                                      |

---

# API

Authentication for most routes is a session cookie established at login. Admin
routes additionally require the caller to be an administrator **and** hold a
named permission grant. Selected routes are rate-limited or CSRF-protected as
noted.

## Health

### GET /api/health

Liveness probe. Returns `{ "status": "ok", "timestamp": <iso8601> }`. No auth.

## Bootstrap

One-time initial setup, only available in debug builds before any user or role
exists.

### GET /api/v1/dev/setup

Returns `{ "available": bool }` — whether initial setup can still run.

### POST /api/v1/dev/setup

Creates the first administrator account and its role.
Request: `InitialSetup` (`admin_user: CreateUser`, `admin_role: RoleSchema`).

## Accounts & Sessions

### POST /api/v1/users/create

Registers a new user (rate-limited 10/hour). Request: `CreateUser` (`username`,
`email`, `password`, `roles`). On success signs the caller in and emits
`auth_user:created`. Subject to the *Login gate* (method `register`).

### POST /api/v1/users/login/available

Checks whether a given identity can sign in and by which method.

### POST /api/v1/users/login

Signs a user in (rate-limited 10/minute). Request: `LoginUser` (`username`,
`password`). Establishes the session; may require a second factor (see 2FA).
Subject to the *Login gate* (method `password`). An unknown account and a wrong
password take the same time and answer the same `401 INVALID_CREDENTIALS`: for an
unknown account the password is verified against a decoy hash. An account that
only signs in through a provider answers `400 PROVIDER_ONLY`.

For an account with a mobile device the password alone establishes **nothing**:
the answer is `{ "status": "mobile_2fa", "delegated": false, "number": <10–99>,
"expires": <seconds>, "fallback": bool }` instead of `{ "status": "ok" }`, and the
session only holds the open approval — see *Mobile approval* below. When another
additive took over the approval (see *Delegated approvals*), the answer carries
`"delegated": true` and the approval's id as `approval` instead of a number.

### GET /api/v1/users/logout

Ends the current session.

### Login gate

Every route that would establish a session from credentials first asks the
fan-out query `auth_login:admit` (see *Consumes*) with
`{ "method": <method>, "provider": <name, provider methods only> }`:

| Method     | Route                                                                            |
|------------|----------------------------------------------------------------------------------|
| `password` | `POST /api/v1/users/login`                                                       |
| `register` | `POST /api/v1/users/create`                                                      |
| `setup`    | `POST /api/v1/dev/setup`                                                         |
| `provider` | `GET /api/v1/{provider}/login` and its callback, unless they carry an app ticket |
| `app-provider` | `POST /api/v1/{provider}/app` and `POST /api/v1/{provider}/app/exchange`     |
| `device`   | `POST /api/v1/mobile/login`                                                      |

A handler answers `null` (or `true`) to admit, or a refusal code
(`^[A-Z][A-Z0-9_]{2,63}$`), which `auth` answers as `403 <code>`; any other
answer refuses with `403 LOGIN_NOT_ADMITTED`. A handler that raises refuses the
sign-in with `503 LOGIN_GATE_FAILED`. Handlers run inside the request, so they
can inspect it. Without a handler nothing changes.

### Credential gate

Every route that changes a credential of the signed-in account first asks the
fan-out query `auth_credentials:admit` (see *Consumes*) with
`{ "credential": <credential>, "user_id": <int> }`:

| Credential     | Route                                                                                                                                    |
|----------------|------------------------------------------------------------------------------------------------------------------------------------------|
| `password`     | `PATCH /api/v1/users/me` with `new_password`                                                                                             |
| `totp`         | `POST /api/v1/users/2fa/totp`, `DELETE /api/v1/users/2fa/totp`, and `POST /api/v1/users/2fa/totp/verify` while the secret is unconfirmed |
| `webauthn`     | `POST /api/v1/users/2fa/webauthn/register`, `POST …/webauthn/register/verify`, `DELETE /api/v1/users/2fa/webauthn`                       |
| `backup_codes` | `POST /api/v1/users/2fa/backup`, `DELETE /api/v1/users/2fa/backup`                                                                       |

Checking a second factor (a confirmed TOTP, a WebAuthn assertion, a backup code)
changes nothing and is not gated. The gate runs before the current password or
the submitted code is checked, after the 2FA routes' own `401 TWO_FA_REQUIRED`
for an unverified session. Answers follow the login
gate: `null` (or `true`) admits, a refusal code is answered as `403 <code>`, any
other answer as `403 CREDENTIAL_NOT_ADMITTED`, and a handler that raises refuses
the change with `503 CREDENTIAL_GATE_FAILED`. Without a handler nothing changes.

### Mobile clients

Routes that only an app on the account's phone calls are restricted to **mobile
clients**. A mobile client sends two headers:

- `X-Client-Ident` with the deployment's `AUTH_MOBILE_SECRET` (environment
  `MOBILE_SECRET` in the `[auth]` section of the app config; `wf create app`
  generates it). `auth` refuses to start without it under `wf run`.
- `User-Agent` in product form with the platform first:
  `<product>/<version> (<android|ios>[; <detail>])`, for example
  `myapp/1.0.0 (android; com.example.app)`. Browsers, crawlers, monitors and
  generic HTTP libraries do not identify like this.

Anything else is answered `401 INVALID_CLIENT` (missing or wrong secret) or
`401 INVALID_USER_AGENT`. The secret is compared in constant time. It ships inside
the app binary, so it keeps foreign apps and casual scripts off a deployment; it
is not a cryptographic guarantee — every sensitive device route additionally
requires the device's signature.

| Route                                            | Why it is mobile-only                 |
|--------------------------------------------------|---------------------------------------|
| `POST /api/v1/mobile/challenge`                  | starts a device registration or login |
| `GET` / `POST` / `PUT /api/v1/mobile`            | reads or binds the device keys        |
| `GET /api/v1/mobile/keylog`, `/mobile/actions`   | the device's own trust data           |
| `POST /api/v1/mobile/login`                      | device sign-in                        |
| `GET /api/v1/users/2fa/mobile/pending`           | the device asks for its open approval |
| `POST /api/v1/users/2fa/mobile/approve`, `/deny` | the device settles an approval        |

Other additives apply the same check to their own app-only routes through the
query `auth_mobile:verify-client` (see *Provides*), so a deployment has one mobile
secret and one definition of a mobile client.

### Session flags

The session cookie carries `user_id` and `2fa_verified` (framework) and, for a
session opened by the account's device or on its behalf, `mobile: true`. Such a
session cannot replace the device keys (`PUT /api/v1/mobile` answers
`403 REAUTHENTICATION_REQUIRED`) and deletes the account only with a signed
action. `auth` sets it on `POST /api/v1/mobile/login`; another additive that opens
a session on the device's behalf sets it as well.

### GET /api/v1/users/me/available

Session probe. Answers `{ "available": bool, "mobile_2fa": bool }` for *any*
caller — it resolves the session without gating it, so a client can tell "signed
in" from "signed out" before it knows whether the account is fully activated.
`mobile_2fa` is `true` while the session waits for a mobile approval, which is how
a client finds its way back to the number after a provider sign-in or a reload.
**This is the endpoint a client should use to decide between a login screen and
an account screen.**

### GET /api/v1/users/me · PATCH /api/v1/users/me · DELETE /api/v1/users/me

Reads, updates, or deletes the authenticated user. All three sit behind the full
`require_2fa` chain, so an account that is not fully activated is answered with
`401 EMAIL_NOT_VERIFIED` or `401 TWO_FA_REQUIRED` — see *Verification* below for
how a client walks the caller out of those states.

`GET` responds with `UserResponse`: `id`, `username`, `email`,
`pending_email`, `email_verified`, `roles` (`name`, `permissions`,
`requires_2fa`), `is_admin`, `has_2fa` (a confirmed TOTP or a WebAuthn
credential) and `has_mobile` (the account has a mobile device). A role's
`requires_2fa` is satisfied by **either** — the device is a second factor — so a
client that enforces the role should ask for TOTP or WebAuthn only when both are
`false`, and may recommend one as a fallback when only `has_mobile` is `true`.
`PATCH` accepts `UpdateUser` (`username`,
`current_password`, `new_password`; rate-limited 10/minute) — **the email address
is not part of it**; the address lifecycle belongs to `/verification/email`. A
`new_password` passes the *Credential gate* first.
`DELETE` fans out `auth_user:delete` before removing the row and answers
`500 DELETION_INCOMPLETE`, keeping the account, when a handler answers `None`.
From a session carrying the `mobile` flag, `DELETE` requires a signed action
`auth:account.delete` on target `auth:account` in the header `X-WF-Action`
(`401 ACTION_SIGNATURE_REQUIRED`, `400 INVALID_ACTION`, `401` with the
verification code).

Once every handler succeeded, `auth` retires the account before the row is
removed: every live personal token is revoked (its id stays on the revocation
list until it would have expired), and a key log that anchors anything is closed
with a host statement `device.revoke` carrying `reset: true`. The log of the
pseudonymous handle therefore stays continuous, and a new account that is given
the same id later (SQLite reuses the highest id in a `users` table created before
WebFluid `1.0.0rc1`, which creates it with `AUTOINCREMENT`) starts without device,
recovery key, browsers or links of its predecessor.

### Verification

The activation surface. Every route here is gated at `require_user` — the lowest
rung of the chain — and applies its own checks inside, so an account that has not
passed the email or 2FA gates can still complete its activation. Where an
operation is as sensitive as a fully authenticated one, the handler escalates to
the equivalent of `require_2fa` internally.

- **GET /api/v1/verification/email** — the state of the caller's email address.
  Answers `{ "email": <address|null>, "verified": bool }` while verification is
  outstanding, and `{ "email": null, "verified": true }` once it is done: the
  address is disclosed only while a client needs it to render the activation
  step. A client distinguishes "no address on file" (`email: null`,
  `verified: false`) from "address awaiting confirmation" (`email` set,
  `verified: false`).
- **POST /api/v1/verification/email** — sets or changes the address
  (`SetEmail`, rate-limited 6/hour). On an account with **no verified address**
  this runs at `require_user`, which is what makes the address recoverable after
  a provider sign-in that carried none. On an account **with** a verified
  address this is a change of an established credential and escalates
  internally: `401 EMAIL_NOT_VERIFIED` / `401 TWO_FA_REQUIRED` apply exactly as
  they would on `require_2fa`. Posting the address the account already holds
  cancels a pending change (`type: "CANCELLED"`).
  Emits `auth_send:confirm`; answers `{ "status": "ok", "type": ... }` with
  `REGISTRATION`, `CHANGE`, `CANCELLED`, or `VERIFIED`.
- **POST /api/v1/verification/email/resend** — resends the pending confirmation
  (rate-limited 2/hour). Gated at `require_user`; escalates internally for a
  `CHANGE`, stays at `require_user` for a `REGISTRATION`, because a registration
  resend is by definition reachable only from an unactivated account.

`VERIFIED` is answered when **no** `auth_send:confirm` handler is registered: an
application with no confirmation channel cannot demand a confirmation, so the
address is accepted and marked verified rather than locking the account behind a
gate nothing can open. The same fallback applies to registration.

### Email confirmation

- **GET /api/v1/users/confirm** — confirms an email from a `?token=`. Renders the
  confirmation/invalid page (supplied by a page-provider additive, see
  `auth_page:*`) or returns `{ "status": "ok" }`.
  Emits `auth_user:confirmed` on the first successful verification. A token
  issued for an email *change* carries the new address and is accepted only
  while that address is still the pending one.

### Password reset

- **POST /api/v1/users/reset/request** — starts a reset for an email
  (rate-limited 2/hour). Request: `ResetRequest`. Emits `auth_send:reset`.
- **GET /api/v1/users/reset** — renders the reset page from a `?token=`.
- **POST /api/v1/users/reset** — sets the new password (rate-limited 10/hour).
  Request: `ResetPassword`. CSRF-protected.

## OAuth providers

Provider-driven sign-in and account linking. `{provider}` selects the OAuth
provider.

- **GET /api/v1/{provider}/login** and **GET|POST /api/v1/{provider}/login/callback**
  — sign in through an external provider. For an existing account with a mobile
  device the callback opens a mobile approval instead of a session, exactly like
  the password login.
- **GET /api/v1/{provider}/connect** and **GET|POST /api/v1/{provider}/connect/callback**
  — link a provider to the signed-in account.

### Sign-in from a native app

A native app never shows the provider in an embedded web view (RFC 8252): it opens
the sign-in in the system browser and receives a single-use code on a private-use
redirect it registered, bound to a PKCE verifier only the app holds (RFC 7636).
The browser itself is never signed in.

- **POST /api/v1/{provider}/app** — `ProviderAppStart` (`redirect`, `challenge`;
  rate-limited 10/minute). `challenge` is the base64url SHA-256 of the app's
  verifier (43 characters). `redirect` must be listed exactly in
  `AUTH_PROVIDER_APP_REDIRECTS` (default `[]`, which turns the flow off). Answers
  `{ "ticket", "url", "expires" }`; the ticket lives `AUTH_PROVIDER_APP_TTL` seconds
  (600). `400 PROVIDER_APP_DISABLED`, `400 INVALID_REDIRECT`,
  `400 INVALID_CODE_CHALLENGE`, `400 UNKNOWN_PROVIDER`.
- **GET /api/v1/{provider}/login?device=mobile&app=<ticket>** — the `url` the app
  opens in the system browser. `400 PROVIDER_APP_EXPIRED` for an unknown or expired
  ticket. After the provider, the callback does not sign the browser in: it
  consumes the ticket, issues a code that is valid for 120 seconds and redirects
  (`303`) to `<redirect>?code=…&ticket=…`.
- **POST /api/v1/{provider}/app/exchange** — `ProviderAppExchange` (`code`,
  `verifier`; rate-limited 20/minute), sent by the app's own HTTP client. The code
  is consumed before it is checked, so a wrong verifier burns it; the SHA-256 of
  `verifier` must equal the challenge (`400 INVALID_CODE` otherwise). On success
  the app's session is signed in exactly like a password login — including the
  mobile approval of an account that already has a device
  (`{ "status": "mobile_2fa", … }`).

## Personal JWT Tokens

Programmatic-access tokens for the authenticated user. These endpoints back a
personal-token management UI.

- **POST /api/v1/users/jwt** — issue a token. Request: `CreateToken`
  (`name`, `payload`, optional `expires`). `name` is trimmed and must be 1–64
  characters (`400 INVALID_TOKEN_NAME`) and unique among the user's live tokens
  (`400 TOKEN_EXISTS`). `payload` may only carry `permissions`, a list of at most
  256 grant strings of up to 128 characters (`400 INVALID_TOKEN_PAYLOAD`); `sub`
  and `jti` are set by the server. `expires` is the lifetime in days, 1 to
  `AUTH_JWT_MAX_DAYS` (365), defaulting to `JWT_EXPIRY_DAYS`
  (`400 INVALID_EXPIRY`). Answers `{ "token" }`.
- **GET /api/v1/users/jwts** — list the user's live tokens as
  `[{ "name", "exp", "iat" }]`.
- **GET /api/v1/users/jwt/metadata** — issuance metadata for the token UI.
- **PATCH /api/v1/users/jwt** — rename a token (`UpdateToken`: `iat`, `name`).
  `iat` identifies one of the caller's live tokens; anything else — another
  user's token, a revoked one, an unparsable value — is `400 UNKNOWN_TOKEN`.
- **DELETE /api/v1/users/jwt** — revoke one of the caller's live tokens
  (`UpdateToken`: `iat`), with the same `400 UNKNOWN_TOKEN`.

## Two-Factor Authentication

Enrolling a factor is gated at `require_user` so a fresh account can set up 2FA
before it has verified its email — but every route that **adds** a factor, or
hands out credentials for one, escalates internally: once the account already
holds a second factor, the session must have passed it (`401 TWO_FA_REQUIRED`).
The challenge routes (`.../verify`, `.../webauthn/verify`, backup-code verify)
stay at `require_user`, since passing them is what marks the session verified.
Removing a factor requires a session that has passed 2FA, but not a verified
email.

### GET /api/v1/users/2fa

Returns the user's configured second factors.

### TOTP

- **POST /api/v1/users/2fa/totp** — begin TOTP setup (`TOTPSetupResponse`:
  `secret`, `uri`, `qr`).
- **POST /api/v1/users/2fa/totp/verify** — confirm setup / verify a code
  (`TOTPVerify`; rate-limited 10/minute). A code is accepted once: a code of the
  same or an earlier time step is refused as `401 INVALID_OTP`.
- **DELETE /api/v1/users/2fa/totp** — remove TOTP.

Ten failed TOTP or backup-code verifications of an account within 15 minutes
answer `429 TOO_MANY_ATTEMPTS` until the window passes, whatever address they
come from; a successful verification resets the counter.

### WebAuthn / Passkeys

- **POST /api/v1/users/2fa/webauthn/register** → **/register/verify** — register a
  credential (`WebAuthnRegister`).
- **POST /api/v1/users/2fa/webauthn/verify** → **/verify/complete** — authenticate
  with a credential (`WebAuthnVerify`; the completion is rate-limited 20/minute).
- **DELETE /api/v1/users/2fa/webauthn** — remove a credential (`WebAuthnDelete`).

### Backup codes

- **POST /api/v1/users/2fa/backup** — (re)generate codes (`BackupCodesResponse`).
- **POST /api/v1/users/2fa/backup/verify** — consume a code (`BackupCodeVerify`;
  rate-limited 10/minute, counted per account as above).
- **DELETE /api/v1/users/2fa/backup** — remove backup codes.

`GET /api/v1/users/2fa` also answers `mobile: bool` — whether the account has a
mobile device.

### Mobile approval

Once an account has a mobile device (see *Mobile devices*), the device **is** its
second factor, ranked above TOTP and WebAuthn: every password or provider sign-in
— in a browser or in an app on another phone — has to be approved on it. The
other factors remain as the **fallback** for when the device is not at hand.

The approval works by number matching. The sign-in shows a number from 10 to 99;
the device is asked to approve the sign-in, and the user has to type that number
into it. The device signs the number with its signing key, so neither an attacker
nor a careless tap can approve a sign-in the user is not looking at.

Until an approval is complete the session carries **no user** — only the open
approval. Every gate of every additive therefore answers
`401 NOT_AUTHENTICATED` in the meantime, without any of them knowing about mobile
approvals. An approval expires after 120 seconds.

Routes for the signing-in client (the session of the sign-in):

- **GET /api/v1/users/2fa/mobile** — the approval's state (rate-limited
  120/minute): `{ "pending": false }` without one, otherwise
  `{ "pending": true, "state", "number", "fallback", "delegated", "expires" }`
  with `state` one of `pending`, `approved`, `denied`, `cancelled`, `used` — or
  `{ "pending": true, "state": "expired" }`. A delegated approval has no number
  and carries its id as `approval`, so a client finds its way back to the
  delegate's flow after a reload. Poll it while waiting.
- **POST /api/v1/users/2fa/mobile/complete** — turns an approved approval into
  the session, marked as having passed the second factor, and sets the CSRF
  cookie (rate-limited 20/minute). `409 MOBILE_APPROVAL_PENDING` while it is
  still open, `401 MOBILE_APPROVAL_DENIED` or `401 MOBILE_APPROVAL_EXPIRED`
  otherwise.
- **POST /api/v1/users/2fa/mobile/fallback** — gives up on the device and opens
  an ordinary session that still has to pass TOTP, WebAuthn or a backup code
  (rate-limited 10/minute). Only offered — `fallback: true` — when the account
  has one of them, or when the delegate declared the approval skippable;
  `400 TWO_FA_NOT_SETUP` otherwise.
- **POST /api/v1/users/2fa/mobile/cancel** — abandons the sign-in and clears the
  session.

Routes for the device:

- **GET /api/v1/users/2fa/mobile/pending** — the open approval of the account,
  `{ "approval": <id>|null, "expires" }`. Gated at `require_2fa`; a device asks
  after it signed in or came back to the foreground, since the push below only
  reaches a running app.
- **POST /api/v1/users/2fa/mobile/approve** (`MobileApproval`: `user_id`,
  `approval`, `number`, `signature`; rate-limited 30/minute) — no session needed,
  the device signs

  ```text
  auth_mobile:approve
  <user_id>
  <approval>
  <number>
  ```

  A wrong number answers `400 WRONG_NUMBER`; the third wrong number denies the
  approval (`409 MOBILE_APPROVAL_DENIED`).
- **POST /api/v1/users/2fa/mobile/deny** (`MobileDenial`: `user_id`, `approval`,
  `signature`; rate-limited 30/minute) — rejects the sign-in, signed
  `auth_mobile:deny` / `<user_id>` / `<approval>`.

`409 MOBILE_APPROVAL_UNAVAILABLE` for an approval that is no longer open or
delegated, and `401 INVALID_SIGNATURE` for a signature of anything but the
account's device.

### Delegated approvals

An additive that runs a second factor of its own on the account's device can take
the approval over by registering the singleton query `auth_mobile:delegate` (see
*Consumes*). `auth` then still opens the approval and holds the session in it —
every rule above about the session carrying no user applies unchanged — but it
neither picks a number nor pushes `auth_mobile:approval`, and the approval never
shows up in `GET /api/v1/users/2fa/mobile/pending`. The device routes `approve`
and `deny` answer `409 MOBILE_APPROVAL_UNAVAILABLE` for it.

The delegate drives the approval through the `auth_mobile:approval-state` and
`auth_mobile:resolve` queries (see *Provides*); the signing-in client completes,
falls back or cancels through the same routes as above. Without a delegate, or
when the delegate fails or answers anything but a dict, `auth` uses its own
number matching.

## Mobile devices

A mobile app can bind one device to an account and sign in with it afterwards.
The device holds two key pairs; `auth` only ever sees the public halves. An
account has **at most one** device. A device is never removed on its own — it can
only be *replaced*, and only by a session that signed in the traditional way.

Keys and signatures are base64url without padding: `enc_pubkey` is a raw X25519
public key (32 bytes), `sig_pubkey` a raw Ed25519 public key (32 bytes), and a
signature is a raw Ed25519 signature (64 bytes) over the UTF-8 message lines
listed below, joined with `\n`.

### POST /api/v1/mobile/challenge

Issues a single-use challenge (rate-limited 30/minute). No auth. Answers
`{ "challenge": <43 chars>, "expires": 120 }`. A challenge is consumed by the
first request that presents it, whether that request succeeds or not.

### GET /api/v1/mobile

The verification endpoint. Gated at `require_2fa`. Answers
`{ "enrolled": bool, "enc_pubkey": str|null, "sig_pubkey": str|null, "account",
"keylog": { "seq", "head", "broken", "recovery": bool } }` for the caller's
account, so a client can compare the server's copy — and the key-log head — with
its own.

### GET /api/v1/mobile/keylog

Gated at `require_2fa`. Answers `{ account, origin, state, consistent,
statements }`: the pseudonymous account handle, the origin it is derived from,
the replayed anchors (`seq`, `head`, `device`, `recovery`, `browsers`, `links`,
`broken`), whether the stored device matches the log, and every statement with
its stored verification flags.

### Key-log statements

| Type             | Keys          | Authority                                    | Effect                                                                             |
|------------------|---------------|----------------------------------------------|------------------------------------------------------------------------------------|
| `device.bind`    | `sig`, `enc`  | `self` (first), `device`, `recovery`, `host` | binds the device; a new device under `recovery` or `host` drops browsers and links |
| `device.revoke`  | `sig` or none | `device`, `recovery`, `host`                 | removes the device and every link                                                  |
| `recovery.set`   | `recovery`    | `self` (first), `device`, `recovery`         | anchors the recovery authority                                                     |
| `browser.bind`   | `enc`         | `self` (first), `recovery`                   | binds a browser vault (accounts without a device)                                  |
| `browser.revoke` | `enc`         | `device`, `recovery`                         | removes a browser vault                                                            |
| `browser.link`   | `enc`         | `device`, `recovery`                         | links a browser to the account's device                                            |
| `browser.unlink` | `enc`         | `device`, `recovery`, `host`                 | releases a linked browser                                                          |

A host statement is recorded with a flag: `HOST_ASSERTED_BINDING` (normal) on an
unanchored account, `HOST_ASSERTED_KEY_CHANGE` (critical) or, with `reset: true`,
`HOST_ASSERTED_RESET` (high) on an anchored one, `HOST_ASSERTED_UNLINK` (normal)
for a released link and `HOST_ASSERTED_LINK` (critical) for a link nobody signed.
`auth` itself writes host statements only for device bindings without a proof
and for releasing links; it never accepts a host link through its API.

### GET /api/v1/mobile/actions

Gated at `require_2fa`. Answers `{ account, devices, recent }`: the head of every
device's action chain and the last 100 signed actions with their results.

### POST /api/v1/mobile

Registers the account's first device (`MobileKeys`: `enc_pubkey`, `sig_pubkey`,
`challenge`, `signature`; rate-limited 10/hour). Gated at `require_2fa` — a
session, a verified email, and a passed second factor when the account has one;
bearer tokens are not accepted. The device proves possession of its new signing
key by signing

```text
auth_mobile:register
<user_id>
<enc_pubkey>
<sig_pubkey>
<challenge>
```

`409 MOBILE_ALREADY_ENROLLED` when the account already has a device;
`400 INVALID_KEY`, `401 INVALID_CHALLENGE` and `401 INVALID_SIGNATURE` otherwise.

`MobileKeys` also takes `keylog`: the `device.bind` statement for the new keys,
signed by the keys themselves and by the authority `self` (first binding) or
`recovery` (the account's recovery key). Without it the server writes a
host-asserted statement. `400 KEYLOG_MISMATCH` when it binds other keys,
`400 AUTHORITY_NOT_ALLOWED`, `409 KEYLOG_CONFLICT` when the log moved on, and the
verification codes of the key log. Answers
`{ "status": "ok", "keylog": { "seq", "hash", "flags" } }`.

### PUT /api/v1/mobile

Registers or **replaces** the device (`MobileKeys`, same message, rate-limited
5/hour). Same gate as `POST`, and additionally refused with
`403 REAUTHENTICATION_REQUIRED` for a session that was itself opened by a device
login: only a traditional sign-in (password or provider, plus the second factor)
may move an account to other keys. This is how a client restores its own keys
after the server lost or mixed them up, and how a new device takes over after a
recovery. Answers `{ "status": "ok", "replaced": bool }`; when the keys actually
changed it triggers `auth_mobile:replaced`. Its `keylog` may be signed by the
authority `device` (the current phone) or `recovery`; without one the replacement
is recorded as host-asserted (`NO_PROOF_OF_POSSESSION`). Presenting the keys that
are already bound answers `replaced: false` and `restored: true` when the stored
device had drifted from the log and was restored from it.

### POST /api/v1/mobile/login

Signs in with the device (`MobileLogin`: `user_id`, `challenge`, `signature`;
rate-limited 20/minute). No auth. The device signs

```text
auth_mobile:login
<user_id>
<challenge>
```

On success the session is replaced exactly like a password login, marked as
having passed the second factor — the device was enrolled from a session that
had — and the CSRF cookie is set. `401 INVALID_CHALLENGE` for an unknown or spent
challenge; `401 MOBILE_AUTH_FAILED` for everything else. An unknown account, an
account without a device and a signature that does not match are deliberately
indistinguishable, so the route cannot be used to probe which accounts have a
device.

## Administration

Endpoints for managing users, roles, and permissions. Every route requires
`is_admin` plus the listed grant.

### Users — grant `users:read` / `users:write`

- **POST /api/v1/admin/users** (`users:write`) — create a user (`CreateUser`).
- **GET /api/v1/admin/users** (`users:read`) — list users (`AdminUserResponse[]`:
  `id`, `username`, `email`, `email_verified`, `is_admin`, `has_2fa`, `providers` — the sorted names
  of the OAuth providers linked to the account — and `roles`).
- **GET /api/v1/admin/users/{user_id}** (`users:read`) — one user
  (`AdminUserResponse`).
- **PATCH /api/v1/admin/users/{user_id}** (`users:write`) — update
  (`AdminUpdateUser`).
- **DELETE /api/v1/admin/users/{user_id}** (`users:write`) — delete.

### Roles — grant `roles:read` / `roles:write`

- **GET /api/v1/admin/config** (`roles:read`) — admin config
  (`AdminConfigResponse`).
- **GET /api/v1/admin/roles** (`roles:read`) — list roles (`AdminRoleResponse[]`).
- **POST /api/v1/admin/roles** (`roles:write`) — create (`AdminCreateRole`).
- **PATCH /api/v1/admin/roles/{role_id}** (`roles:write`) — update
  (`AdminUpdateRole`).
- **DELETE /api/v1/admin/roles/{role_id}** (`roles:write`) — delete.
- **POST /api/v1/admin/roles/{role_id}/permissions** (`roles:write`) — grant a
  permission (`AdminRolePermission`).
- **DELETE /api/v1/admin/roles/{role_id}/permissions/{permission_id}**
  (`roles:write`) — revoke.
- **POST /api/v1/admin/roles/{role_id}/users** (`roles:write`) — add a member
  (`AdminRoleMember`).
- **DELETE /api/v1/admin/roles/{role_id}/users/{user_id}** (`roles:write`) —
  remove a member.

### Permissions — grant `permissions:read` / `permissions:write`

- **GET /api/v1/admin/permissions** (`permissions:read`) — list
  (`AdminPermissionResponse[]`).
- **POST /api/v1/admin/permissions** (`permissions:write`) — create
  (`AdminCreatePermission`).
- **DELETE /api/v1/admin/permissions/{permission_id}** (`permissions:write`) —
  delete.

---

# Events / Queries

Event names are namespaced `auth_<name>`. This section splits into **Triggers**
(signals `auth` emits), **Provides** (queries `auth` answers), and **Consumes**
(signals it subscribes to and queries it requests).

## Triggers

### auth_user:created

Emitted right after a user registers through `POST /users/create`.
Payload: `{ type: "REGISTRATION", username, email, link }` (a confirmation link).
A subscribing handler is expected to send the confirmation email. Optional — if no
handler is registered the trigger is skipped with a warning.

### auth_user:confirmed

Public signal, declared with `create_signal`. Emitted when a user verifies their
email. Payload: `user_id` (int). Available to other additives and to browser
clients that want to react to a completed confirmation.

### user:role-update

Public signal, declared with `create_signal` under the shared ecosystem name (not
namespaced). Payload: `user_id` (int). Emitted after the change is committed,
once per affected user, whenever an *Administration* route changes what a user is
granted:

- `PATCH /admin/users/{user_id}` when the set of roles actually changes;
- `POST /admin/roles/{role_id}/users` and `DELETE …/users/{user_id}` — the member;
- `PATCH /admin/roles/{role_id}` when its name, `is_admin`, `requires_2fa` or
  permission set actually changes, `POST`/`DELETE …/permissions`, and
  `DELETE /admin/roles/{role_id}` — every member of the role;
- `DELETE /admin/permissions/{permission_id}` — every member of a role that held it.

Subscribers re-evaluate cached access decisions for that user.

### auth_send:confirm

Emitted to (re)send a confirmation email — on resend, on an email change, and on
admin-driven email changes. Payload:
`{ type: "REGISTRATION" | "CHANGE", username, email, link, locale }`.
`locale` is the request locale (the configured default for an admin-driven
change) and is `null` when Babel is not enabled; a mail provider should render in
it. Handled by a subscribing mail provider. If **no** handler is registered, the
address is accepted and marked verified instead — see *Verification*.

### auth_send:reset

Emitted to send a password-reset email. Payload: `{ username, email, link }`.
Handled by a subscribing mail provider.

### auth_oauth:first-callback

Internal signal. Emitted immediately after a provider sign-in has **created** a
new account — never on a repeat sign-in and never on
`/{provider}/connect/callback`, which links a provider to an account that
already exists. Payload:

```json
{
  "user_id": 42,
  "provider": "sso",
  "sub": "e2f1…",
  "claims": { "full_name": "…", "first_name": "…", "last_name": "…", "roles": ["…"] }
}
```

`claims` is the provider's userinfo response reduced to a stable shape: `auth`
reads the usual spellings of each claim (`name` / `full_name` / `display_name` /
`cn`, `given_name` / `firstName`, `family_name` / `surname` / `sn`, and so on)
and answers with the normalised field names

`full_name`, `first_name`, `last_name`, `middle_name`, `nickname`, `email`,
`picture`, `locale`, `timezone`, `phone`, `roles`

`roles` merges every role- and group-shaped claim — `roles`, `groups`,
`memberOf`, `authorities`, Keycloak's `realm_access.roles` and
`resource_access.*.roles` — into one de-duplicated list of strings. **Only keys
the provider actually supplied are present**; a consumer must treat every field
as optional. `full_name` is derived from first and last name only when both are
present and the provider sent no name of its own; `auth` never guesses the other
way round. The helper is `auth.utils.claims.normalized_claims`.

The signal exists so that other additives can pick up the profile data an OAuth
provider hands out once, at the only moment it is available. It is optional in
both directions: if nobody subscribes, `auth` skips the trigger silently, and a
subscriber must cope with an empty `claims` object.

### auth_token:expires

Emitted by the scheduled token watcher for each token nearing expiry, before
expired tokens are purged. Payload:
`{ username, email, token, exp, iat }`. Offered for a notifier to subscribe to;
no additive consumes it today.

### auth_mobile:approval

Public signal, the push of a mobile approval. Emitted when a sign-in opens an
approval and whenever its state changes. Payload:
`{ "device": <fingerprint>, "approval": <id>, "state": <state>, "expires": <s> }`.
`device` is base64url of the first 16 bytes of SHA-256 over the device's raw
`sig_pubkey`; a device recognises its own pushes by it, and nobody else can map it
to an account. The payload never contains the number — the user has to read it
off the sign-in. Event delivery is best-effort and only reaches a running app; a
device that comes back asks `GET /api/v1/users/2fa/mobile/pending`.

Like every public signal it can also be *triggered* by any socket client, so a
device treats it as a doorbell only: on a push for its fingerprint it asks
`GET /api/v1/users/2fa/mobile/pending` and shows what the server confirms.

### auth_mobile:replaced

Internal signal. Emitted by `PUT /api/v1/mobile` when an account's device keys
were actually replaced — not on a first registration and not when the same keys
are presented again. Payload: `{ "user_id": <int> }`. Optional in both
directions: `auth` skips the trigger silently when nobody subscribes. A mail
provider can use it to tell the account owner that the account moved to other
keys.

## Provides

`auth`'s identity data is reached through the REST API. The queries below exist
so that other additives can work with an account's mobile device without ever
holding its keys. All of them are **internal** — server-side only, never reachable
over the events websocket.

### auth_user-encrypt *(query)*

Encrypts data so that only the account's mobile device can read it. Payload:
`{ "user_id": <int>, "data": <base64url> }`. Answers the envelope as a string, or
`null` when the account has no device. A malformed payload raises `TypeError`.

The envelope is `x1.` followed by base64url of `epk ‖ nonce ‖ ciphertext ‖ tag`.
A fresh X25519 key pair is generated per call; its public half `epk` (32 bytes)
agrees a secret with the device's `enc_pubkey`, HKDF-SHA256 with salt
`epk ‖ enc_pubkey` and info `webfluid-mobile-x1` derives a 32-byte key, and the
data is sealed with AES-256-GCM under a random 12-byte `nonce` (16-byte tag, no
associated data). A device produces the same format when it encrypts to itself or
to another device, so every party can open what the others seal.

### auth_verify-signature *(query)*

Checks a signature made by the account's mobile device. Payload:
`{ "user_id": <int>, "message": <str>, "signature": <base64url> }`. Answers `true`
only when the account has a device and the Ed25519 signature over the UTF-8
message verifies against its `sig_pubkey`; `false` otherwise. A malformed payload
raises `TypeError`.

Prefix every message with a contract name of your own, one per purpose — as
`auth` does with `auth_mobile:login` and `auth_mobile:register` — so that a
signature made for one purpose can never be replayed into another.

### auth_keylog:state *(query)*

`{ "user_id": <int> }` → `{ account, seq, head, device, recovery, browsers, links,
broken }` — the replayed key-log anchors of the account.

### auth_keylog:append *(query)*

`{ "user_id": <int>, "envelope": { statement, subject, authority }, "dry_run": bool }`
→ `{ "ok": true, seq, hash, flags }` or `{ "ok": false, "code" }`. A dry run
checks the statement against the current head without storing it (used by
prepared recovery rotations). Statements whose timestamp is more than 30 minutes
off are rejected.

### auth_keylog:unlink *(query)*

`{ "user_id": <int>, "key": <x25519> }` → `{ "ok": true, seq, hash, flags }`,
`{ "ok": true, "seq": null }` when the key is not linked, or
`{ "ok": false, "code" }`. Appends the host statement `browser.unlink` for a
linked browser key — the one host statement a consumer can cause, because
releasing a link never grants anything. A link the account's device revokes
itself goes through `auth_keylog:append` with its own signature.

### auth_action:accept *(query)*

`{ "user_id", "envelope": { action, signature }, "action", "target", "params" }`
→ `{ "ok": true, "id", … }` or `{ "ok": false, "code" }`. Verifies a
`wf-action-v1` action against the account's current device: signature, account,
action and target, the committed `params`, sequence and chain, replay, validity
window.

### auth_action:result *(query)*

`{ "id": <int>, "result": { target, state, … } }` → `true`. Records the outcome of
an accepted action, so peers can check that the host applied what was signed.

### auth_ledger:flush *(query)*

Hands pending key statements and actions to `peering_record`; answers the number
flushed. Runs every `AUTH_LEDGER_FLUSH_INTERVAL` seconds (60) on its own.

### auth_mobile:verify-client *(query)*

Checks whether the **current request** comes from a mobile client as defined under
*Mobile clients*. The payload is ignored (send `null`); the request is taken from
the request context, so the query only means something inside a request. Answers
`null` for a mobile client, or the refusal code — `INVALID_CLIENT` or
`INVALID_USER_AGENT` — otherwise; outside a request it answers `INVALID_CLIENT`.
A consumer refuses with `401` and the code, which keeps every app-only route of
the application answering the same way.

### auth_mobile:fingerprint *(query)*

The fingerprint of the account's device, as carried by `auth_mobile:approval`.
Payload: `{ "user_id": <int> }`. Answers the fingerprint, or `null` when the
account has no device. Lets a delegate address pushes to the device the same way
`auth` does.

### auth_mobile:approval-state *(query)*

The state of an open approval. Payload: `{ "approval": <id> }`. Answers
`{ "user_id", "device", "state", "delegated", "expires" }` — `device` being the
fingerprint — or `null` for an unknown or expired approval.

### auth_mobile:resolve *(query)*

Settles a **delegated** approval. Payload:
`{ "approval": <id>, "user_id": <int>, "approved": bool }`. Moves the approval to
`approved` or `denied` and answers `true`; answers `false` when the approval is
unknown, expired, not delegated, not pending or belongs to another account. The
delegate must have verified the device's consent itself — `auth` trusts the call.

## Consumes

### auth_user:delete *(query, fan-out)*

Requested immediately **before** an account row is deleted — by
`DELETE /api/v1/users/me`, by `DELETE /api/v1/admin/users/{user_id}`, and by the
unconfirmed-account sweep. Payload: `{ "user_id": <int> }`. Nothing else crosses
the boundary; a handler that needs more looks it up itself.

`auth` never registers a handler for it — the query exists so that every additive
storing data against an account can remove it. Register with
`events.query("auth_user:delete", False)`; a missing producer is not an error,
`auth` skips the request when nobody answers.

Rules a handler must follow:

- **Open its own executor** (`db.async_executor(...)`, not the `ensured_` twin).
  Handlers are gathered concurrently and a shared `AsyncSession` breaks under
  concurrent use.
- **Delete only what the additive owns**, and remove the artefacts that no
  database cascade reaches — files on disk, remote objects, association rows
  behind a core statement.
- **Raise to abort.** During a request an exception propagates out of the
  request, so the account row survives and the deletion can be retried; handlers
  that already committed are not rolled back, which is why a handler should be
  idempotent.
- **Answer with a JSON-shaped dict.** Off-request — in the unconfirmed-account
  sweep — the framework swallows a handler's exception and answers `None` for
  it instead. `auth` reads that as a failed purge and **keeps the account**,
  logging the failure, so a broken handler delays a deletion rather than
  orphaning its data. A handler that answers `None` on purpose is therefore
  read as a failure.

### auth_delete:unconfirmed *(signal)*

Subscribed handler that deletes accounts left unconfirmed past a deadline.
The signal is triggered on a daily schedule when email confirmation is in use; the
payload is the retention period in days (int). `auth` owns the deletion logic and
exposes this as an inbound extension point — it does not schedule the signal
itself. Accounts are selected by `created_at` older than the deadline and each
one fans out `auth_user:delete` before it is removed.

### peering_integrity *(provider, only with `peering`)*

`auth` answers the collector of the `peering` Additive with one self-reported
record, `auth_utils_js`: the SHA-256 and size of `static/js/utils.js` — the
request and CSRF helpers every page loads as `window.wf.adt.auth` — its URL and
the Additive's version, provenance `unsigned`. Peers fetch the served file
themselves and compare it with the record; there is no reference repository for
it. Registered only when `peering` is enabled.

### auth_login:admit *(query, fan-out)*

Requested by every route of the *Login gate* before it establishes a session.
Payload: `{ "method", "provider"? }`; the request is available to the handler
through the request context. Register with `events.query("auth_login:admit", False)`
and answer `None` to admit or a refusal code to refuse. A missing handler admits
everything.

### auth_credentials:admit *(query, fan-out)*

Requested by every route of the *Credential gate* before it changes a credential.
Payload: `{ "credential", "user_id" }`; the request is available to the handler
through the request context. Register with
`events.query("auth_credentials:admit", False)` and answer `None` to admit or a
refusal code to refuse. A missing handler admits everything.

### auth_mobile:delegate *(query)*

Requested when a password or provider sign-in of an account with a mobile device
opens its approval. Payload: `{ "user_id": <int> }`. A singleton extension point:
an additive that answers it with a dict takes the approval over (see *Delegated
approvals*); `{ "skippable": true }` additionally allows the fallback for accounts
without TOTP, WebAuthn or backup codes. A missing handler is not an error: `auth`
then uses its own number matching, and does the same when the handler raises or
answers anything but a dict.

### auth_page:confirmation · auth_page:reset · auth_page:invalid *(queries)*

Requested while handling the confirmation and reset routes to obtain the HTML
page bodies. These are extension points `auth` defines but does not implement: a
page-provider additive answers them. Each returns rendered HTML; a missing
provider raises `ValueError`, which `auth` treats as "no page available".
