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

### GET /api/v1/users/logout

Ends the current session.

### GET /api/v1/users/me/available

Session probe. Answers `{ "available": bool }` for *any* caller — it resolves the
session without gating it, so a client can tell "signed in" from "signed out"
before it knows whether the account is fully activated. **This is the endpoint a
client should use to decide between a login screen and an account screen.**

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
  — sign in through an external provider.
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
(signals `auth` emits), **Provides** (queries `auth` answers — none), and
**Consumes** (signals it subscribes to and queries it requests).

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

### auth_token:expires

Emitted by the scheduled token watcher for each token nearing expiry, before
expired tokens are purged. Payload:
`{ username, email, token, exp, iat }`. Offered for a notifier to subscribe to;
no additive consumes it today.

## Provides

`auth` registers no query handlers. Its identity data is reached through the
REST API.

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
- **Raise to abort.** An exception propagates out of the request, so the account
  row survives and the deletion can be retried; handlers that already committed
  are not rolled back, which is why a handler should be idempotent.

Answer with a JSON-shaped dict; `auth` ignores the value and it exists for
logging and tests.

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
