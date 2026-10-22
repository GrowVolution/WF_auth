---
name: additive-auth
description: Use the `auth` Additive of a WebFluid project for sign-in, sessions, email verification, password reset, TOTP/WebAuthn/backup codes, OAuth and native-app SSO, personal JWTs, mobile devices and their key log, and user/role/permission administration. Load it before writing any login, session, 2FA, token or account-admin code, before gating a route on a signed-in user or a phone app, and before adding a handler for an `auth_*` query or signal.
---

# auth — agent guide

<!-- index -->
This file is short enough to read whole; the ranges are for coming back to one section. Every file
it points to opens with an index of the same shape — read those first 30 lines, then only the ranges
the task needs.

- `24-32` **Do not build what it already does**
- `33-51` **Rules**
- `52-85` **Recipes**
- `86-93` **Verify**
- `94-175` **Contract map**
<!-- /index -->

`auth` is a headless identity core: JSON only, and the one place where accounts, sessions and
second factors live. Other code reaches it through its routes and its id-scoped queries. If a task
needs any of the things below, the answer is to call or extend `auth`, not to write it again.

## Do not build what it already does

- Registration, login, logout, email confirmation, password reset, unconfirmed-account cleanup.
- TOTP with QR provisioning, WebAuthn/passkeys, backup codes, attempt limits, replay protection.
- OAuth sign-in and linking; native-app SSO through the system browser with PKCE.
- Personal JWTs with bounded lifetime and grant-only payloads, revocation, expiry watcher.
- A mobile device per account, device login, number-matching approval, key log and signed actions.
- Admin CRUD for users, roles, permissions, with `user:role-update` fired on every change.

## Rules

1. **Gate routes with the framework guards, in this order of strength:** `require_user`
   (session), then verified email, then `require_2fa`. Activation routes stay low and escalate
   inside — never move a route that changes an established credential below `require_2fa`.
2. **App-only routes require a mobile client.** In your own Additive, ask
   `auth_mobile:verify-client` with `null` inside the request and answer `401` with the code it
   returns. Never invent a second secret or header.
3. **A role's `requires_2fa` is met by `has_2fa` or `has_mobile`.** Do not force TOTP on an
   account that has a phone; recommend it as a fallback.
4. **Sign every device message with its own purpose prefix** (`<your_id>_<purpose>`), the way
   `auth_mobile:login` does, and verify it through `auth_verify-signature`.
5. **Store data against an account only if you also answer `auth_user:delete`.** Open your own
   executor in the handler, delete only what you own, raise to abort, answer a dict.
6. **Gate sign-ins and credential changes through the fan-out queries** `auth_login:admit` and
   `auth_credentials:admit` instead of wrapping `auth`'s routes.
7. **Never import from `additives.auth`.** Use its REST API from clients and its queries from
   server code.

## Recipes

**Refuse non-app requests on a route of your own**

```python
from fastapi import Depends, HTTPException
from webfluid.core.ext import events


async def _mobile_client():
    try: code = await events.request("auth_mobile:verify-client", None)
    except ValueError: code = "INVALID_CLIENT"
    if code: raise HTTPException(status_code=401, detail=code)


MOBILE_CLIENT = [Depends(_mobile_client)]
```

Register with `router.post("/path", dependencies=MOBILE_CLIENT)(handler)`.

**Remove your rows when an account goes**

```python
events.query("auth_user:delete", False)(purge)

async def purge(data: dict) -> dict:
    async with db.async_executor(model=MyRow) as e:
        ...
    return {"status": "ok", "rows": count}
```

**Encrypt something only the user's phone can read:** `auth_user-encrypt` with
`{ user_id, data: <base64url> }` answers an `x1.` envelope, or `null` without a device.

## Verify

- `GET /auth/api/v1/users/me/available` tells signed in from signed out; `/users/me`'s `401`
  detail names the missing rung (`EMAIL_NOT_VERIFIED`, `TWO_FA_REQUIRED`).
- A mobile route called without the headers answers `401 INVALID_CLIENT`.
- The Additive's tests live in `tests/` (gitignored); run them with
  `python -m pytest -q -p no:cacheprovider` from that directory.

## Contract map

<!-- index ../CONTRACT.md -->
Sections of `../CONTRACT.md`, as that file stands now:

- `100-114` **At a glance**
- `115-704` **API**
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
  - `353-391` OAuth / SSO
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
  - `661-704` Administration
    - `666-675` Users — grant `users:read` / `users:write`
    - `676-693` Roles — grant `roles:read` / `roles:write`
    - `694-704` Permissions — grant `permissions:read` / `permissions:write`
- `705-1011` **Events / Queries**
  - `711-824` Triggers
    - `713-719` auth_user:created
    - `720-725` auth_user:confirmed
    - `726-741` user:role-update
    - `742-751` auth_send:confirm
    - `752-756` auth_send:reset
    - `757-793` auth_oauth:first-callback
    - `794-800` auth_token:expires
    - `801-815` auth_mobile:approval
    - `816-824` auth_mobile:replaced
  - `825-928` Provides
    - `832-845` auth_user-encrypt *(query)*
    - `846-857` auth_verify-signature *(query)*
    - `858-862` auth_keylog:state *(query)*
    - `863-870` auth_keylog:append *(query)*
    - `871-879` auth_keylog:unlink *(query)*
    - `880-887` auth_action:accept *(query)*
    - `888-892` auth_action:result *(query)*
    - `893-897` auth_ledger:flush *(query)*
    - `898-907` auth_mobile:verify-client *(query)*
    - `908-914` auth_mobile:fingerprint *(query)*
    - `915-920` auth_mobile:approval-state *(query)*
    - `921-928` auth_mobile:resolve *(query)*
  - `929-1011` Consumes
    - `931-961` auth_user:delete *(query, fan-out)*
    - `962-970` auth_delete:unconfirmed *(signal)*
    - `971-979` peering_integrity *(provider, only with `peering`)*
    - `980-987` auth_login:admit *(query, fan-out)*
    - `988-995` auth_credentials:admit *(query, fan-out)*
    - `996-1005` auth_mobile:delegate *(query)*
    - `1006-1011` auth_page:confirmation · auth_page:reset · auth_page:invalid *(queries)*
<!-- /index -->
