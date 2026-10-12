from webfluid.core.ext import db
from webfluid.extensions.security.models import User as SecurityUser
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional


def _unique_name(name: str) -> str:
    from .. import additive
    return additive.unique_name(name)


class KeyStatement(db.Model):
    __tablename__ = _unique_name("keylog")

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[int] = mapped_column(ForeignKey(SecurityUser.id, ondelete="CASCADE"), index=True)
    account: Mapped[str] = mapped_column(String(32), index=True)
    seq: Mapped[int]
    hash: Mapped[str] = mapped_column(String(64), unique=True)
    prev: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(32))
    authority: Mapped[str] = mapped_column(String(16))
    statement: Mapped[str] = mapped_column(Text)
    subject_sig: Mapped[Optional[str]] = mapped_column(String(128))
    authority_sig: Mapped[Optional[str]] = mapped_column(String(128))
    flags: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[str] = mapped_column(String(20))
    ledger_seq: Mapped[Optional[int]]

    __table_args__ = (UniqueConstraint("uid", "seq"),)

    def __init__(self, uid: int, account: str, seq: int, hash: str, prev: str, type: str, authority: str,
                 statement: str, subject_sig: Optional[str], authority_sig: Optional[str], flags: str,
                 created_at: str):
        self.uid = uid
        self.account = account
        self.seq = seq
        self.hash = hash
        self.prev = prev
        self.type = type
        self.authority = authority
        self.statement = statement
        self.subject_sig = subject_sig
        self.authority_sig = authority_sig
        self.flags = flags
        self.created_at = created_at


class ActionLog(db.Model):
    __tablename__ = _unique_name("actions")

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[int] = mapped_column(ForeignKey(SecurityUser.id, ondelete="CASCADE"), index=True)
    account: Mapped[str] = mapped_column(String(32), index=True)
    device: Mapped[str] = mapped_column(String(32))
    seq: Mapped[int]
    action_id: Mapped[str] = mapped_column(String(32))
    hash: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    target: Mapped[str] = mapped_column(String(160))
    content: Mapped[str] = mapped_column(Text)
    signature: Mapped[str] = mapped_column(String(128))
    result: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(20))
    ledger_seq: Mapped[Optional[int]]

    __table_args__ = (
        UniqueConstraint("account", "action_id"),
        UniqueConstraint("account", "device", "seq"),
    )

    def __init__(self, uid: int, account: str, device: str, seq: int, action_id: str, hash: str, name: str,
                 target: str, content: str, signature: str, created_at: str):
        self.uid = uid
        self.account = account
        self.device = device
        self.seq = seq
        self.action_id = action_id
        self.hash = hash
        self.name = name
        self.target = target
        self.content = content
        self.signature = signature
        self.created_at = created_at
