from webfluid.core.ext import db
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
import json, re, time

from ..utils.canonical import canonical_text, digest, CanonicalError
from ..utils.crypto import verify, b64decode
from . import keylog
from ..models.keylog import ActionLog

PROTOCOL = "wf-action-v1"
CONTEXT = "wf-action-v1"
GENESIS = "0" * 64
MAX_LIFETIME = 900
CLOCK_SKEW = 300

_ID = re.compile(r"^[A-Za-z0-9_-]{22}$")
_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}:[a-z0-9][a-z0-9_.-]{0,63}$")
_TARGET = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}:[A-Za-z0-9_.:-]{1,128}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = { "v", "account", "device", "action", "target", "params", "id", "seq", "prev", "iat", "exp" }
HEADER = "X-WF-Action"
MAX_HEADER = 8192


def from_header(value: str | None) -> dict | None:
    if not value: return None
    if len(value) > MAX_HEADER: raise ActionError("INVALID_ACTION")
    try: data = json.loads(b64decode(value.strip()).decode("utf-8"))
    except (ValueError, UnicodeDecodeError): raise ActionError("INVALID_ACTION")
    if not isinstance(data, dict): raise ActionError("INVALID_ACTION")
    return { "protocol": PROTOCOL, "action": data.get("action"), "signature": data.get("signature") }


class ActionError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def shape(action) -> None:
    if not isinstance(action, dict) or set(action) != _FIELDS or action.get("v") != 1:
        raise ActionError("INVALID_ACTION")
    if not isinstance(action["action"], str) or not _NAME.match(action["action"]): raise ActionError("INVALID_ACTION")
    if not isinstance(action["target"], str) or not _TARGET.match(action["target"]): raise ActionError("INVALID_ACTION")
    if not isinstance(action["params"], dict): raise ActionError("INVALID_ACTION")
    if not isinstance(action["id"], str) or not _ID.match(action["id"]): raise ActionError("INVALID_ACTION")
    if not isinstance(action["prev"], str) or not _HEX.match(action["prev"]): raise ActionError("INVALID_ACTION")
    if not all(_int(action[key]) for key in ("seq", "iat", "exp")) or action["seq"] < 1:
        raise ActionError("INVALID_ACTION")
    if action["exp"] <= action["iat"] or action["exp"] - action["iat"] > MAX_LIFETIME:
        raise ActionError("INVALID_ACTION_LIFETIME")


async def last(account: str, device: str) -> tuple[int, str]:
    async with db.ensured_async_executor(model=ActionLog) as e:
        result = await e.exec(select(ActionLog).where(ActionLog.account == account, ActionLog.device == device)
                              .order_by(ActionLog.seq.desc()).limit(1))
        row = result.first()
        return (row.seq, row.hash) if row else (0, GENESIS)


async def accept(uid: int, envelope: dict, name: str, target: str, params: dict) -> dict:
    action = (envelope or {}).get("action")
    signature = (envelope or {}).get("signature")
    if (envelope or {}).get("protocol") != PROTOCOL: raise ActionError("ACTION_SIGNATURE_REQUIRED")
    shape(action)
    if not isinstance(signature, str): raise ActionError("ACTION_SIGNATURE_REQUIRED")

    state = await keylog.anchors(uid)
    if action["account"] != state["account"]: raise ActionError("ACCOUNT_MISMATCH")
    if state["broken"]: raise ActionError("KEYLOG_BROKEN")
    device = state["device"]
    if device is None: raise ActionError("MOBILE_NOT_ENROLLED")
    if action["device"] != keylog.fingerprint(device["sig"]): raise ActionError("FOREIGN_DEVICE_KEY")
    if not verify(device["sig"], f"{CONTEXT}\n{canonical_text(action)}", signature):
        raise ActionError("INVALID_ACTION_SIGNATURE")

    if action["action"] != name or action["target"] != target: raise ActionError("ACTION_MISMATCH")
    try:
        if canonical_text(action["params"]) != canonical_text(params): raise ActionError("ACTION_MISMATCH")
    except CanonicalError: raise ActionError("ACTION_MISMATCH")

    now = int(time.time())
    if now < action["iat"] - CLOCK_SKEW or now > action["exp"] + CLOCK_SKEW: raise ActionError("ACTION_EXPIRED")

    seq, head = await last(action["account"], action["device"])
    async with db.ensured_async_executor(model=ActionLog) as e:
        result = await e.exec(select(func.count(ActionLog.id)).where(
            ActionLog.account == action["account"], ActionLog.action_id == action["id"]
        ), scalars=False)
        if result.scalar(): raise ActionError("ACTION_REPLAY")
    if action["seq"] <= seq: raise ActionError("ACTION_REPLAY")
    if action["seq"] != seq + 1 or action["prev"] != head: raise ActionError("ACTION_OUT_OF_ORDER")

    value = digest(action)
    try:
        async with db.ensured_async_executor(model=ActionLog) as e:
            row = await e.insert(ActionLog(
                uid=uid, account=action["account"], device=action["device"], seq=action["seq"],
                action_id=action["id"], hash=value, name=action["action"], target=action["target"],
                content=canonical_text(action), signature=signature, created_at=keylog.now_ts()
            ), True)
    except IntegrityError:
        raise ActionError("ACTION_REPLAY")
    return { "id": row.id, "hash": value, "seq": action["seq"], "account": action["account"] }


async def result(row_id: int, data: dict):
    async with db.ensured_async_executor(model=ActionLog) as e:
        found = await e.exec(select(ActionLog).where(ActionLog.id == row_id))
        row = found.first()
        if row: row.result = canonical_text(data)


def envelope(row: ActionLog) -> dict:
    data = { "protocol": PROTOCOL, "action": json.loads(row.content), "signature": row.signature }
    if row.result: data["result"] = json.loads(row.result)
    return data


async def history(uid: int, limit: int = 500) -> list[dict]:
    async with db.ensured_async_executor(model=ActionLog) as e:
        found = await e.exec(select(ActionLog).where(ActionLog.uid == uid).order_by(ActionLog.id.desc()).limit(limit))
        return [dict(envelope(row), hash=row.hash, ledger_seq=row.ledger_seq, created_at=row.created_at)
                for row in found.all()]


def reduce(state: dict | None, params: dict) -> dict | None:
    if not isinstance(params, dict) or not ({ "set", "unset", "replace" } >= set(params)): return None
    if "set" not in params and "unset" not in params: return None
    values, removed = params.get("set") or {}, params.get("unset") or []
    if not isinstance(values, dict) or not isinstance(removed, list): return None
    current = {} if params.get("replace") or state is None else dict(state)
    current.update(values)
    for key in removed: current.pop(key, None)
    return current


async def heads(uid: int) -> dict:
    async with db.ensured_async_executor(model=ActionLog) as e:
        found = await e.exec(select(ActionLog).where(ActionLog.uid == uid).order_by(ActionLog.seq))
        devices = {}
        for row in found.all():
            devices[row.device] = { "seq": row.seq, "head": row.hash, "ledger_seq": row.ledger_seq }
        return devices
