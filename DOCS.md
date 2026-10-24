# Authentication API — Documentation

`auth` is the authentication core of an application: accounts, sign-in, sessions, second factors,
the phone as an account's device, personal tokens and the administrative API for users, roles and
permissions. It is **headless** — a JSON API, background jobs and event-bus contracts, no pages of
its own — so that any interface can sit on top of it and every interface gets the same rules. This
guide explains how an account becomes trustworthy step by step, what each factor does, which parts
other Additives can plug into, and what an operator configures. Every route, payload and error code
is in [CONTRACT.md](CONTRACT.md).

---

## How an account becomes trustworthy

An account moves up a ladder, and every route in the application is gated at one of its rungs:

1. **A session.** Registration or sign-in opens a session. Enough to finish activating the account,
   nothing more.
2. **A verified email.** The account confirms its address through a link. If the application has no
   way to send mail — nothing answers the confirmation request — the address is accepted as
   verified rather than locking the account behind a step nobody can complete.
3. **A passed second factor.** Once the account holds a second factor, a session has to pass it
   before it reaches anything that needs `require_2fa`, and before it can add or remove a factor.

The framework's gates (`require_user`, email verified, `require_2fa`, roles, permissions, admin)
correspond to these rungs. The routes that complete the activation itself sit at the lowest rung
and escalate internally where an operation is as sensitive as a fully authenticated one — changing
an already verified address asks for the second factor, for example.

---

## Signing in

**Password.** An unknown account and a wrong password take the same time and give the same answer,
so the response tells an attacker nothing about which accounts exist. Accounts created through a
provider and never given a password are told so.

**Providers (OAuth).** A person can sign in with a provider configured in the framework's
`SECURITY_OAUTH_CLIENTS`, and link providers to an existing account. The first provider sign-in
that creates an account is announced with the provider's claims normalised to stable field names,
so another Additive can prefill a profile.

**Native apps** never show a provider inside an embedded web view. They open the sign-in in the
system browser, receive a single-use code on a redirect they registered, and exchange it with a
PKCE verifier only the app holds. The redirects an app may use are listed in
`AUTH_PROVIDER_APP_REDIRECTS`; an empty list turns the flow off.

**The phone.** An app can bind one device to an account and sign in with it afterwards — see below.

Every route that would open a session from credentials first asks the **login gate**
(`auth_login:admit`): another Additive can refuse a sign-in method for its own reasons, with its own
error code. Every route that changes a credential asks the **credential gate**
(`auth_credentials:admit`) the same way. Without a handler, neither changes anything.

---

## Second factors

| Factor             | What it is                                                                                       |
|--------------------|--------------------------------------------------------------------------------------------------|
| TOTP               | an authenticator app; each code is accepted once, and after ten failed TOTP or backup-code checks within 15 minutes the account answers `429 TOO_MANY_ATTEMPTS` |
| WebAuthn / passkeys| a security key or platform passkey, bound to `AUTH_2FA_WEBAUTHN_RP_ID` and `…_ORIGIN`             |
| Backup codes       | `AUTH_2FA_BACKUP_CODE_COUNT` single-use codes of `AUTH_2FA_BACKUP_CODE_DIGITS` digits             |
| The phone          | ranked above all others once bound: every sign-in has to be approved on it                      |

**Approval on the phone** works by number matching: the signing-in screen shows a number from 10 to
99, and the person types it into the phone, which signs it with its device key. Neither an attacker
nor a careless tap can approve a sign-in the person is not looking at. Until the approval is
complete the session holds no user at all — every gate of every Additive answers
`401 NOT_AUTHENTICATED` without knowing anything about phones — and an approval expires after 120
seconds. The other factors remain the fallback for when the phone is not at hand.

An Additive can take over an approval and settle it its own way (`auth_mobile:delegate`).

---

## The phone as the account's device

An account has **at most one** device. It holds two key pairs — one for encryption, one for
signatures — and `auth` only ever sees the public halves. A device is never removed on its own; it
can only be replaced, and only by a session that signed in the traditional way, so a stolen phone
cannot lock its owner out. A session opened by the device itself cannot replace the device keys and
deletes the account only with a signed action.

Every change to an account's keys is a signed statement in the account's **key log**, and actions a
person signs on their phone are recorded with replay protection. With the `peering` Additive
enabled, both reach a public ledger that independent peers replay, so a key change the server makes
without the account's proof becomes visible.

**Mobile clients.** Routes only the app should call — device registration and sign-in, reading the
device's own trust data, settling approvals — accept only requests that carry the deployment's
`MOBILE_SECRET` in `X-Client-Ident` and identify with a product user agent such as
`myapp/1.0.0 (android; com.example.app)`. The secret ships inside the app binary: it keeps foreign
apps and casual scripts out, it is not a cryptographic guarantee, and every sensitive device route
additionally requires the device's signature. Other Additives apply the same check to their own
app-only routes through `auth_mobile:verify-client`, so a deployment has one definition of an app
client.

---

## Personal tokens

Signed-in accounts can issue JWTs for programmatic access: named, unique per account, valid for 1 up
to `AUTH_JWT_MAX_DAYS` days, carrying nothing but a list of grants. Revocation is recorded in the
cache until the token's natural expiry and warmed from the database on every start — run JWT against
Redis, and if `auth` cannot load token revocations, run the migrations and restart before
relying on a revocation. `AUTH_TOKEN_EXPIRY_EVENT_DEADLINE` days before a token expires, its owner
can be told through `auth_token:expires`.

---

## Administration

The admin API manages users, roles and permissions. Every route needs `is_admin`, and a personal
token additionally the matching grant (`users:*`, `roles:*`, `permissions:*`). With
`AUTH_ADMIN_ROLE_REQUIRES_2FA` on (the default) every administrator role is saved as requiring a
second factor. Every change that alters what someone is granted emits `user:role-update`, once per
affected account, after it is committed.

**The first administrator.** In a debug run, and only while no account and no role exist,
`POST /auth/api/v1/dev/setup` creates the first administrator together with its role.

**Deleting an account** asks every Additive that keeps data about it, through the fan-out
`auth_user:delete`, to remove that data in the same step.

---

## Installing and enabling

```bash
wf ocean install -a auth --prefer-stable
```

```ini
[extensions]
EXT_SCHEDULING = 1
EXT_SQLALCHEMY = 1
EXT_SECURITY = 1
EXT_EVENTS = 1
EXT_CACHE = 1
EXT_JWT = 1

[features]
WF_ADDITIVES = 1

[auth]
MOBILE_SECRET = <generated by wf create app>

[additives]
auth = 1
```

`wf create app` generates `MOBILE_SECRET`; the application refuses to start without it. Build your
mobile app with the same value.

---

## Configuration

| Key                                 | Default                    | What it changes                                              |
|-------------------------------------|----------------------------|--------------------------------------------------------------|
| `AUTH_2FA_ISSUER`                   | `"WebFluid"`               | the name authenticator apps show                             |
| `AUTH_2FA_BACKUP_CODE_COUNT`        | `10`                       | backup codes per set                                         |
| `AUTH_2FA_BACKUP_CODE_DIGITS`       | `8`                        | digits per backup code                                       |
| `AUTH_2FA_WEBAUTHN_RP_ID`           | `"localhost"`              | the WebAuthn relying party — **your domain in production**   |
| `AUTH_2FA_WEBAUTHN_RP_NAME`         | `"WebFluid"`               | the name passkey prompts show                                |
| `AUTH_2FA_WEBAUTHN_ORIGIN`          | `"http://localhost:8000"`  | the origin passkeys are bound to — **your origin in production** |
| `AUTH_ADMIN_ROLE_REQUIRES_2FA`      | `True`                     | administrator roles always require a second factor          |
| `AUTH_PROVIDER_APP_REDIRECTS`       | `[]`                       | redirects native apps may use for provider sign-in; empty = off |
| `AUTH_PROVIDER_APP_TTL`             | `600`                      | seconds a native-app sign-in may take                        |
| `AUTH_JWT_MAX_DAYS`                 | `365`                      | the longest lifetime of a personal token                     |
| `AUTH_TOKEN_EXPIRY_EVENT_DEADLINE`  | `5`                        | days before expiry at which owners are told                  |
| `AUTH_LEDGER_FLUSH_INTERVAL`        | `60`                       | seconds between flushes of the key-log outbox to the ledger  |

Passkeys registered against one relying party do not work against another: set the WebAuthn values
for production before the first person enrols one.

---

## Troubleshooting

| You see                                         | Because                                                                                     |
|-------------------------------------------------|---------------------------------------------------------------------------------------------|
| The app refuses to start: `Missing MOBILE_SECRET` | The `[auth]` section of the app config has no `MOBILE_SECRET`                             |
| Every route answers `401 NOT_AUTHENTICATED` after a password sign-in | The account has a phone; the sign-in waits for the approval on it      |
| `401 TWO_FA_REQUIRED`                           | The account holds a second factor that this session has not passed                          |
| `401 EMAIL_NOT_VERIFIED`                        | The address is not confirmed yet                                                            |
| App routes answer `401 INVALID_CLIENT` / `INVALID_USER_AGENT` | The app was built with another secret, or its user agent is not in product form |
| `403 LOGIN_NOT_ADMITTED` or another code        | An Additive's login gate refused the method                                                 |
| `503 LOGIN_GATE_FAILED`                         | A login gate handler raised — the sign-in is refused rather than waved through              |
| Passkeys fail in production                     | `AUTH_2FA_WEBAUTHN_RP_ID` / `…_ORIGIN` still point at localhost                             |
| Native provider sign-in is refused              | The app's redirect is not listed in `AUTH_PROVIDER_APP_REDIRECTS`                                |
| Auth cannot load token revocations    | Database access or tables are unavailable — restore access, run migrations and restart                         |

---

## Further reading

- [CONTRACT.md](CONTRACT.md) — every route, gate, signal, query, payload and error code
- [CHANGELOG.md](CHANGELOG.md) — what changed, release by release
- [.agents/SKILL.md](.agents/SKILL.md) — what a coding agent needs to use it correctly
