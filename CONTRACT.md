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

### GET /api/v1/users/me · GET /api/v1/users/me/available · PATCH /api/v1/users/me · DELETE /api/v1/users/me

Reads, probes, updates, or deletes the authenticated user.
`GET` responds with `UserResponse`; `PATCH` accepts `UpdateUser`.

### Email confirmation

- **GET /api/v1/users/confirm** — confirms an email from a `?token=`. Renders the
  confirmation/invalid page (supplied by a page-provider additive, see
  `auth_page:*`) or returns `{ "status": "ok" }`.
  Emits `auth_user:confirmed` on success.
- **POST /api/v1/users/confirm/resend** — resends the confirmation mail
  (rate-limited 2/hour). Emits `auth_send:confirm`.

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
`{ type: "REGISTRATION" | "CHANGE", username, email, link, [locale] }`.
Handled by a subscribing mail provider.

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

### auth_delete:unconfirmed *(signal)*

Subscribed handler that deletes accounts left unconfirmed past a deadline.
The signal is triggered on a daily schedule when email confirmation is in use; the
payload is the retention period in days (int). `auth` owns the deletion logic and
exposes this as an inbound extension point — it does not schedule the signal
itself.

### auth_page:confirmation · auth_page:reset · auth_page:invalid *(queries)*

Requested while handling the confirmation and reset routes to obtain the HTML
page bodies. These are extension points `auth` defines but does not implement: a
page-provider additive answers them. Each returns rendered HTML; a missing
provider raises `ValueError`, which `auth` treats as "no page available".
