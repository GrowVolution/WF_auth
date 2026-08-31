# Authentication API

> A WebFluid additive — login, sessions, and two-factor security.

The `auth` additive is a self-contained authentication foundation for WebFluid
applications. It provides the account, session, and identity primitives an
application needs to sign people in and keep their accounts secure. It is a
headless additive: it exposes a JSON API and background jobs, but ships no
frontend of its own.

---

## Why it exists

Almost every application needs the same authentication core — creating accounts,
confirming email addresses, signing users in and out, resetting passwords,
second-factor verification, and issuing tokens. `auth` implements that core once,
as a self-contained additive, so any WebFluid app can adopt a complete and
consistent auth story by enabling it.

It deliberately stops at authentication and identity. Profiles, settings, admin
dashboards, and token-management UIs are intentionally out of scope — they are
meant to be layered on top separately, which keeps `auth` small, focused, and
reusable in any application.

---

## What it provides

- **Account lifecycle** — registration, email confirmation, account deletion,
  and cleanup of accounts that are never confirmed.
- **Sessions** — sign-in and sign-out backed by the framework's security
  extension.
- **Password reset** — request and completion flows.
- **Account activation** — a dedicated verification surface that lets a client
  walk an account from "signed in" to "fully activated" without ever being
  locked out by the very gates it is trying to satisfy.
- **Two-factor authentication** — time-based one-time passwords (TOTP) with QR
  provisioning, and WebAuthn/passkey registration and login.
- **Token issuance** — JSON Web Tokens for programmatic access, plus a scheduled
  watcher that keeps revoked tokens out of circulation.
- **Administrative endpoints** — the API surface for managing users, roles, and
  permissions.

Everything is exposed under the additive's `/api` prefix and versioned under
`/v1`.

---

## Activation without a lockout

Authentication is a chain: a session, then a verified email address, then a
second factor. Each rung is a gate, and a route sitting on the top rung answers
`401` for anything below it. That is correct — but it means the routes an account
needs in order to *climb* the chain cannot themselves sit on top of it, or an
account with no verified address could never add one.

`auth` resolves that by splitting the two concerns. Routes that act on an
established account stay on the full chain. Routes that exist to activate an
account — `/api/v1/verification/*` and the 2FA enrolment routes — are gated at
the session rung and perform the remaining checks **inside** the handler, so each
operation carries exactly the authority it needs:

- setting a first email address, or verifying it, needs only a session;
- changing an address that is already verified is a change of an established
  credential, and is held to the same bar as any fully authenticated route;
- adding a second factor to an account that already has one requires a session
  that has passed the existing factor.

The result is that a client never has to guess: `GET /api/v1/users/me/available`
says whether anyone is signed in, `GET /api/v1/users/me` says with its `401`
*which* rung is missing, and `/api/v1/verification/email` says what to render for
the email step — disclosing the address only while it is actually needed.

---

## Cleaning up after an account

Deleting an account removes far more than the rows `auth` owns. Before it deletes
anything, `auth` fans out the `auth_user:delete` query carrying nothing but the
account id, and waits for every subscriber to finish. Any additive that stores
data against an account registers a handler and removes its own — including the
artefacts no database cascade reaches: files on disk, remote objects, rows behind
association tables. `auth` neither knows nor cares who listens; if nobody does,
the deletion simply proceeds.

---

## Requirements

`auth` relies on a set of framework extensions and refuses to enable if any are
missing:

`scheduling` · `sqlalchemy` · `security` · `events` · `cache` · `jwt`

It targets WebFluid `1.0.0b1` or newer and installs a few Python packages for its
security features (`pyotp`, `segno`, `webauthn`, and `pydantic[email]`).

---

## Position in the ecosystem

`auth` is a foundational additive: it has no additive dependencies of its own and
can be enabled on its own. It is designed as a base for richer account features to
build on — through the API and event contracts it exposes — but it never depends
on those features in return. Enabling `auth` pulls in nothing beyond the framework
extensions it requires.

If you are building a WebFluid application that needs accounts and sign-in, this
is the additive to start from.

---

## License

The Authentication API is maintained by **GrowVolution e.V.** and released under the
**GNU General Public License v3 (GPL v3)**.
