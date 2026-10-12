from webfluid.core.ext import db
from sqlalchemy import select
from datetime import datetime, UTC
import hashlib, json, re, time

from .canonical import canonical_text, digest, CanonicalError
from .crypto import b64encode, b64decode, verify, valid_keys, sig_key, enc_key
from ..models.keylog import KeyStatement
from ..models.mobile import MobileSecurity

PROTOCOL = "wf-keylog-v1"
SUBJECT_CONTEXT = "wf-keylog-v1:subject"
AUTHORITY_CONTEXT = "wf-keylog-v1:authority"
GENESIS = "0" * 64
TYPES = ("device.bind", "device.revoke", "recovery.set", "browser.bind", "browser.revoke")
SIGNED_AUTHORITIES = ("self", "device", "recovery")
CLOCK_SKEW = 1800

_HANDLE = re.compile(r"^a1\.[A-Za-z0-9_-]{22}$")


class KeylogError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def now_ts() -> str:
    return datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


_origin = { "value": "http://localhost:8000" }


def configure(base_url: str):
    text = (base_url or "").strip().lower()
    while text.endswith("/"): text = text[:-1]
    _origin["value"] = text or _origin["value"]


def origin() -> str:
    return _origin["value"]


def handle(user_id: int) -> str:
    raw = f"wf-account-v1\n{origin()}\n{int(user_id)}".encode("utf-8")
    return "a1." + b64encode(hashlib.sha256(raw).digest()[:16])


def fingerprint(sig_pubkey: str) -> str:
    return b64encode(hashlib.sha256(b64decode(sig_pubkey)).digest()[:16])


def _valid_sig(text) -> bool:
    try:
        sig_key(text)
        return True
    except (ValueError, TypeError): return False


def _valid_enc(text) -> bool:
    try:
        enc_key(text)
        return True
    except (ValueError, TypeError): return False


def signed(context: str, statement: dict, key: str | None, signature: str | None) -> bool:
    if not key or not signature: return False
    return verify(key, f"{context}\n{canonical_text(statement)}", signature)


def empty(account: str) -> dict:
    return { "account": account, "seq": 0, "head": GENESIS, "device": None, "recovery": None,
             "browsers": [], "broken": False }


def anchored(state: dict) -> bool:
    return state["device"] is not None or state["recovery"] is not None


def evaluate(state: dict, envelope: dict, allow_host: bool = False, stored: bool = False) -> tuple[dict, list[dict]]:
    statement = (envelope or {}).get("statement")
    signatures = (envelope or {}).get("signatures") or {}
    if (envelope or {}).get("protocol") != PROTOCOL or not isinstance(statement, dict):
        raise KeylogError("INVALID_KEYLOG")
    expected = { "v", "account", "seq", "prev", "type", "authority", "keys", "ts" }
    if not expected <= set(statement) <= expected | { "reset" } or statement.get("v") != 1:
        raise KeylogError("INVALID_KEYLOG")
    if statement["account"] != state["account"] or not _HANDLE.match(str(statement["account"])):
        raise KeylogError("ACCOUNT_MISMATCH")
    if state["broken"]: raise KeylogError("KEYLOG_BROKEN")
    if statement["seq"] != state["seq"] + 1 or statement["prev"] != state["head"]:
        raise KeylogError("KEYLOG_CONFLICT")
    if not isinstance(statement["ts"], int) or isinstance(statement["ts"], bool):
        raise KeylogError("INVALID_KEYLOG")
    if not stored and abs(statement["ts"] - int(time.time())) > CLOCK_SKEW:
        raise KeylogError("KEYLOG_CLOCK")
    kind, authority, keys = statement["type"], statement["authority"], statement["keys"]
    if kind not in TYPES or not isinstance(keys, dict): raise KeylogError("INVALID_KEYLOG")
    if "reset" in statement and not isinstance(statement["reset"], bool): raise KeylogError("INVALID_KEYLOG")
    try: own = digest(statement)
    except CanonicalError: raise KeylogError("INVALID_KEYLOG")

    subject = None
    if kind == "device.bind":
        if set(keys) != { "sig", "enc" } or not _valid_sig(keys["sig"]) or not _valid_enc(keys["enc"]):
            raise KeylogError("INVALID_KEY")
        subject = keys["sig"]
    elif kind == "recovery.set":
        if set(keys) != { "recovery" } or not _valid_sig(keys["recovery"]): raise KeylogError("INVALID_KEY")
        subject = keys["recovery"]
    elif kind == "browser.bind":
        if set(keys) != { "enc" } or not _valid_enc(keys["enc"]): raise KeylogError("INVALID_KEY")
        if state["device"] is not None: raise KeylogError("MOBILE_ENROLLED")
    elif kind == "browser.revoke":
        if set(keys) != { "enc" } or keys["enc"] not in state["browsers"]: raise KeylogError("UNKNOWN_BROWSER_KEY")
    elif kind == "device.revoke":
        if state["device"] is None: raise KeylogError("NOTHING_TO_REVOKE")

    flags = []
    if subject is not None:
        if signatures.get("subject"):
            if not signed(SUBJECT_CONTEXT, statement, subject, signatures.get("subject")):
                raise KeylogError("INVALID_SIGNATURE")
        elif authority in ("host", "legacy"):
            flags.append({ "code": "NO_PROOF_OF_POSSESSION", "severity": "normal" })
        else:
            raise KeylogError("INVALID_SIGNATURE")

    if authority == "self":
        if anchored(state) or kind in ("device.revoke", "browser.revoke"): raise KeylogError("AUTHORITY_REQUIRED")
    elif authority == "device":
        if not signed(AUTHORITY_CONTEXT, statement, (state["device"] or {}).get("sig"), signatures.get("authority")):
            raise KeylogError("INVALID_AUTHORITY")
    elif authority == "recovery":
        if not signed(AUTHORITY_CONTEXT, statement, state["recovery"], signatures.get("authority")):
            raise KeylogError("INVALID_AUTHORITY")
    elif authority == "host":
        if not allow_host: raise KeylogError("AUTHORITY_REQUIRED")
        if anchored(state):
            flags.append({ "code": "HOST_ASSERTED_RESET" if statement.get("reset") else "HOST_ASSERTED_KEY_CHANGE",
                           "severity": "high" if statement.get("reset") else "critical" })
        else:
            flags.append({ "code": "HOST_ASSERTED_BINDING", "severity": "normal" })
    elif authority == "legacy":
        if not allow_host or statement["seq"] != 1 or kind != "device.bind": raise KeylogError("AUTHORITY_REQUIRED")
        flags.append({ "code": "LEGACY_IMPORT", "severity": "normal" })
    else:
        raise KeylogError("INVALID_KEYLOG")

    nxt = dict(state, seq=statement["seq"], head=own, browsers=list(state["browsers"]))
    if statement.get("reset") and authority == "host":
        nxt["recovery"] = None
        nxt["browsers"] = []
    if kind == "device.bind":
        if state["device"] is None or state["device"]["sig"] != keys["sig"]:
            if authority in ("recovery", "host"): nxt["browsers"] = []
        nxt["device"] = { "sig": keys["sig"], "enc": keys["enc"] }
    elif kind == "device.revoke":
        nxt["device"] = None
    elif kind == "recovery.set":
        nxt["recovery"] = keys["recovery"]
    elif kind == "browser.bind":
        if keys["enc"] not in nxt["browsers"]: nxt["browsers"].append(keys["enc"])
    elif kind == "browser.revoke":
        nxt["browsers"] = [key for key in nxt["browsers"] if key != keys["enc"]]
    return nxt, flags


def _envelope(row: KeyStatement) -> dict:
    return {
        "protocol": PROTOCOL,
        "statement": json.loads(row.statement),
        "signatures": { "subject": row.subject_sig, "authority": row.authority_sig }
    }


async def rows(uid: int) -> list[KeyStatement]:
    async with db.ensured_async_executor(model=KeyStatement) as e:
        result = await e.exec(select(KeyStatement).where(KeyStatement.uid == uid).order_by(KeyStatement.seq))
        return list(result.all())


async def history(uid: int) -> list[dict]:
    return [dict(_envelope(row), flags=json.loads(row.flags or "[]"), ledger_seq=row.ledger_seq)
            for row in await rows(uid)]


def replay(account: str, items: list[KeyStatement]) -> dict:
    state = empty(account)
    for row in items:
        try: state, _ = evaluate(state, _envelope(row), allow_host=True, stored=True)
        except KeylogError: return dict(state, broken=True)
    return state


async def import_legacy(uid: int) -> bool:
    async with db.ensured_async_executor(model=KeyStatement) as e:
        result = await e.exec(select(KeyStatement.id).where(KeyStatement.uid == uid).limit(1))
        if result.first() is not None: return False
        result = await e.exec(select(MobileSecurity).where(MobileSecurity.uid == uid))
        device = result.first()
        if device is None: return False
        statement = {
            "v": 1, "account": handle(uid), "seq": 1, "prev": GENESIS, "type": "device.bind",
            "authority": "legacy", "keys": { "sig": device.sig_pubkey, "enc": device.enc_pubkey },
            "ts": int(time.time())
        }
        await e.insert(KeyStatement(
            uid=uid, account=statement["account"], seq=1, hash=digest(statement), prev=GENESIS,
            type="device.bind", authority="legacy", statement=canonical_text(statement), subject_sig=None,
            authority_sig=None, flags=json.dumps([{ "code": "LEGACY_IMPORT", "severity": "normal" }]),
            created_at=now_ts()
        ))
        return True


async def anchors(uid: int) -> dict:
    await import_legacy(uid)
    return replay(handle(uid), await rows(uid))


async def append(uid: int, envelope: dict, allow_host: bool = False) -> dict:
    state = await anchors(uid)
    nxt, flags = evaluate(state, envelope, allow_host)
    statement = envelope["statement"]
    signatures = envelope.get("signatures") or {}
    async with db.ensured_async_executor(model=KeyStatement) as e:
        await e.insert(KeyStatement(
            uid=uid, account=statement["account"], seq=statement["seq"], hash=nxt["head"], prev=statement["prev"],
            type=statement["type"], authority=statement["authority"], statement=canonical_text(statement),
            subject_sig=signatures.get("subject"), authority_sig=signatures.get("authority"),
            flags=json.dumps(flags), created_at=now_ts()
        ), True)
        await _mirror(e, uid, nxt)
    return { "seq": nxt["seq"], "hash": nxt["head"], "flags": flags, "state": nxt }


async def _mirror(e, uid: int, state: dict):
    result = await e.exec(select(MobileSecurity).where(MobileSecurity.uid == uid))
    device = result.first()
    if state["device"] is None:
        if device is not None: await e.delete(device)
        return
    if device is None:
        await e.insert(MobileSecurity(uid, state["device"]["enc"], state["device"]["sig"]))
    else:
        device.enc_pubkey = state["device"]["enc"]
        device.sig_pubkey = state["device"]["sig"]


async def host_statement(uid: int, kind: str, keys: dict, reset: bool = False) -> dict:
    state = await anchors(uid)
    statement = {
        "v": 1, "account": state["account"], "seq": state["seq"] + 1, "prev": state["head"], "type": kind,
        "authority": "host", "keys": keys, "ts": int(time.time())
    }
    if reset: statement["reset"] = True
    return { "protocol": PROTOCOL, "statement": statement, "signatures": { "subject": None, "authority": None } }


async def consistent(uid: int) -> bool:
    state = await anchors(uid)
    async with db.ensured_async_executor(model=MobileSecurity) as e:
        result = await e.exec(select(MobileSecurity).where(MobileSecurity.uid == uid))
        device = result.first()
    if state["device"] is None: return device is None
    return device is not None and device.sig_pubkey == state["device"]["sig"] and device.enc_pubkey == state["device"]["enc"]
