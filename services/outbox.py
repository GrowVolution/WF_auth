from webfluid.core.ext import db, events
from webfluid.utils.logging import factory as log_factory
from sqlalchemy import select
import asyncio, json

from ..models.keylog import KeyStatement, ActionLog
from ..models.mobile import MobileSecurity
from . import actions, keylog

RECORD = "peering_record"
_lock: asyncio.Lock | None = None


def _guard() -> asyncio.Lock:
    global _lock
    if _lock is None: _lock = asyncio.Lock()
    return _lock


async def _record(kind: str, body: dict, subject: str, ref: str) -> int | None:
    try:
        answer = await events.request(RECORD, { "kind": kind, "source": "auth", "body": body,
                                               "subject": subject, "ref": ref })
    except ValueError as exc:
        if str(exc) == f"Query '{RECORD}' does not exist.": return None
        log_factory.warning(f"[auth] Recording {ref} in the peering ledger failed: {exc}")
        return None
    except Exception as exc:
        log_factory.exception(exc, f"[auth] Recording {ref} in the peering ledger failed.")
        return None
    return answer.get("seq") if isinstance(answer, dict) else None


async def flush(limit: int = 200) -> int:
    if _guard().locked(): return 0
    async with _guard():
        recorded = 0
        async with db.async_executor(model=KeyStatement) as e:
            result = await e.exec(select(KeyStatement).where(KeyStatement.ledger_seq.is_(None))
                                  .order_by(KeyStatement.id).limit(limit))
            statements = list(result.all())
        for row in statements:
            body = { "protocol": keylog.PROTOCOL, "statement": json.loads(row.statement),
                     "signatures": { "subject": row.subject_sig, "authority": row.authority_sig } }
            seq = await _record("auth:keylog", body, row.account, f"auth:keylog:{row.account}:{row.seq}")
            if seq is None: break
            async with db.async_executor(model=KeyStatement) as e:
                found = await e.exec(select(KeyStatement).where(KeyStatement.id == row.id))
                target = found.first()
                if target: target.ledger_seq = seq
            recorded += 1

        async with db.async_executor(model=ActionLog) as e:
            result = await e.exec(select(ActionLog).where(ActionLog.ledger_seq.is_(None))
                                  .order_by(ActionLog.id).limit(limit))
            rows = list(result.all())
        for row in rows:
            if not await _statements_recorded(row.uid): break
            seq = await _record("auth:action", actions.envelope(row), row.account, f"auth:action:{row.account}:{row.action_id}")
            if seq is None: break
            async with db.async_executor(model=ActionLog) as e:
                found = await e.exec(select(ActionLog).where(ActionLog.id == row.id))
                target = found.first()
                if target: target.ledger_seq = seq
            recorded += 1
        return recorded


async def _statements_recorded(uid: int) -> bool:
    async with db.async_executor(model=KeyStatement) as e:
        result = await e.exec(select(KeyStatement.id).where(KeyStatement.uid == uid, KeyStatement.ledger_seq.is_(None)).limit(1))
        return result.first() is None


async def import_all() -> int:
    async with db.async_executor(model=MobileSecurity) as e:
        result = await e.exec(select(MobileSecurity.uid))
        uids = list(result.all())
    imported = 0
    for uid in uids:
        if await keylog.import_legacy(uid): imported += 1
    if imported: log_factory.log(f"[auth] Imported {imported} existing device binding(s) into the key log as legacy.")
    return imported
