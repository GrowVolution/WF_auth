from ...services import keylog, actions, outbox


def _int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


async def state_query(data: dict) -> dict:
    user_id = (data or {}).get("user_id")
    if not _int(user_id): raise TypeError("Expected { user_id: int }.")
    state = await keylog.anchors(user_id)
    return {
        "account": state["account"], "seq": state["seq"], "head": state["head"], "device": state["device"],
        "recovery": state["recovery"], "browsers": state["browsers"], "broken": state["broken"]
    }


async def append_query(data: dict) -> dict:
    user_id, envelope = (data or {}).get("user_id"), (data or {}).get("envelope")
    if not _int(user_id) or not isinstance(envelope, dict):
        raise TypeError("Expected { user_id: int, envelope: dict }.")
    try:
        if (data or {}).get("dry_run"):
            state = await keylog.anchors(user_id)
            nxt, flags = keylog.evaluate(state, envelope)
            return { "ok": True, "seq": nxt["seq"], "hash": nxt["head"], "flags": flags, "dry_run": True }
        result = await keylog.append(user_id, envelope)
    except keylog.KeylogError as exc:
        return { "ok": False, "code": exc.code }
    return { "ok": True, "seq": result["seq"], "hash": result["hash"], "flags": result["flags"] }


async def accept_query(data: dict) -> dict:
    user_id = (data or {}).get("user_id")
    envelope, name = (data or {}).get("envelope"), (data or {}).get("action")
    target, params = (data or {}).get("target"), (data or {}).get("params")
    if not _int(user_id) or not isinstance(name, str) or not isinstance(target, str) or not isinstance(params, dict):
        raise TypeError("Expected { user_id: int, envelope: dict, action: str, target: str, params: dict }.")
    try:
        accepted = await actions.accept(user_id, envelope, name, target, params)
    except actions.ActionError as exc:
        return { "ok": False, "code": exc.code }
    return { "ok": True, **accepted }


async def result_query(data: dict) -> bool:
    row_id, result = (data or {}).get("id"), (data or {}).get("result")
    if not _int(row_id) or not isinstance(result, dict): raise TypeError("Expected { id: int, result: dict }.")
    await actions.result(row_id, result)
    return True


async def flush_query(_) -> int:
    return await outbox.flush()
