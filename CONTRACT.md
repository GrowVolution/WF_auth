# Authentication API — Contract

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

Registers a new user. Request: `CreateUser` (`username`, `email`, `password`,
`roles`). On success signs the caller in and emits `auth_user:created`.

### POST /api/v1/users/login/available

Checks whether a given identity can sign in and by which method.

### POST /api/v1/users/login

Signs a user in. Request: `LoginUser` (`username`, `password`). Establishes the
session; may require a second factor (see 2FA).

For an account with a mobile device the password alone establishes **nothing**:
the answer is `{ "status": "mobile_2fa", "number": <10–99>, "expires": <seconds>,
"fallback": bool }` instead of `{ "status": "ok" }`, and the session only holds
the open approval — see *Mobile approval* below.

### GET /api/v1/users/logout

Ends the current session.

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

`GET` responds with `UserResponse`. `PATCH` accepts `UpdateUser` (`username`,
`current_password`, `new_password`) — **the email address is not part of it**;
the address lifecycle belongs to `/verification/email`. `DELETE` fans out
`auth_user:delete` before removing the row.

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
- **POST /api/v1/users/reset** — sets the new password. Request: `ResetPassword`.
  CSRF-protected.

## OAuth / SSO

Provider-driven sign-in and account linking. `{provider}` selects the OAuth
provider.

- **GET /api/v1/{provider}/login** and **GET|POST /api/v1/{provider}/login/callback**
  — sign in through an external provider. For an existing account with a mobile
  device the callback opens a mobile approval instead of a session, exactly like
  the password login.
- **GET /api/v1/{provider}/connect** and **GET|POST /api/v1/{provider}/connect/callback**
  — link a provider to the signed-in account.

## Personal JWT Tokens

Programmatic-access tokens for the authenticated user. These endpoints back a
personal-token management UI.

- **POST /api/v1/users/jwt** — issue a token. Request: `CreateToken`
  (`name`, `payload`, optional `expires`).
- **GET /api/v1/users/jwts** — list the user's tokens (`Tokens`).
- **GET /api/v1/users/jwt/metadata** — issuance metadata for the token UI.
- **PATCH /api/v1/users/jwt** — update a token (`UpdateToken`).
- **DELETE /api/v1/users/jwt** — revoke a token.

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
  (`TOTPVerify`).
- **DELETE /api/v1/users/2fa/totp** — remove TOTP.

### WebAuthn / Passkeys

- **POST /api/v1/users/2fa/webauthn/register** → **/register/verify** — register a
  credential (`WebAuthnRegister`).
- **POST /api/v1/users/2fa/webauthn/verify** → **/verify/complete** — authenticate
  with a credential (`WebAuthnVerify`).
- **DELETE /api/v1/users/2fa/webauthn** — remove a credential (`WebAuthnDelete`).

### Backup codes

- **POST /api/v1/users/2fa/backup** — (re)generate codes (`BackupCodesResponse`).
- **POST /api/v1/users/2fa/backup/verify** — consume a code (`BackupCodeVerify`).
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
  `{ "pending": true, "state", "number", "fallback", "expires" }` with `state`
  one of `pending`, `approved`, `denied`, `cancelled`, `used` — or
  `{ "pending": true, "state": "expired" }`. Poll it while waiting.
- **POST /api/v1/users/2fa/mobile/complete** — turns an approved approval into
  the session, marked as having passed the second factor, and sets the CSRF
  cookie (rate-limited 20/minute). `409 MOBILE_APPROVAL_PENDING` while it is
  still open, `401 MOBILE_APPROVAL_DENIED` or `401 MOBILE_APPROVAL_EXPIRED`
  otherwise.
- **POST /api/v1/users/2fa/mobile/fallback** — gives up on the device and opens
  an ordinary session that still has to pass TOTP, WebAuthn or a backup code
  (rate-limited 10/minute). Only offered — `fallback: true` — when the account
  has one of them; `400 TWO_FA_NOT_SETUP` otherwise.
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

`409 MOBILE_APPROVAL_UNAVAILABLE` for an approval that is no longer open and
`401 INVALID_SIGNATURE` for a signature of anything but the account's device.

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
`{ "enrolled": bool, "enc_pubkey": str|null, "sig_pubkey": str|null }` for the
caller's account, so a client can compare the server's copy with its own.

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

### PUT /api/v1/mobile

Registers or **replaces** the device (`MobileKeys`, same message, rate-limited
5/hour). Same gate as `POST`, and additionally refused with
`403 REAUTHENTICATION_REQUIRED` for a session that was itself opened by a device
login: only a traditional sign-in (password or provider, plus the second factor)
may move an account to other keys. This is how a client restores its own keys
after the server lost or mixed them up, and how a new device takes over after a
recovery. Answers `{ "status": "ok", "replaced": bool }`; when the keys actually
changed it triggers `auth_mobile:replaced`.

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
- **GET /api/v1/admin/users** (`users:read`) — list users (`AdminUserResponse[]`).
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
way round. The helper is `auth.api.utils.normalized_claims`.

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
holding its keys. Both are **internal** — server-side only, never reachable over
the events websocket.

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

### auth_page:confirmation · auth_page:reset · auth_page:invalid *(queries)*

Requested while handling the confirmation and reset routes to obtain the HTML
page bodies. These are extension points `auth` defines but does not implement: a
page-provider additive answers them. Each returns rendered HTML; a missing
provider raises `ValueError`, which `auth` treats as "no page available".
