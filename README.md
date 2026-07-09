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

- **Account lifecycle** — registration, email confirmation, and cleanup of
  accounts that are never confirmed.
- **Sessions** — sign-in and sign-out backed by the framework's security
  extension.
- **Password reset** — request and completion flows.
- **Two-factor authentication** — time-based one-time passwords (TOTP) with QR
  provisioning, and WebAuthn/passkey registration and login.
- **Token issuance** — JSON Web Tokens for programmatic access, plus a scheduled
  watcher that keeps revoked tokens out of circulation.
- **Administrative endpoints** — the API surface for managing users, roles, and
  permissions.

Everything is exposed under the additive's `/api` prefix and versioned under
`/v1`.

---

## Requirements

`auth` relies on a set of framework extensions and refuses to enable if any are
missing:

`scheduling` · `sqlalchemy` · `security` · `events` · `cache` · `jwt`

It targets WebFluid `1.0.0a2` and installs a few Python packages for its security
features (`pyotp`, `segno`, `webauthn`, and `pydantic[email]`).

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

See the [Ocean Licensing page](https://ocean.webfluid.dev/licensing) for the
ecosystem-wide licensing overview.
