from webfluid.core.ext import db
from webfluid.extensions.security.models import User as SecurityUser
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship, backref


def _unique_name(name: str) -> str:
    from .. import additive
    return additive.unique_name(name)


class MobileSecurity(db.Model):
    __tablename__ = _unique_name("mobile_security")

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[int] = mapped_column(ForeignKey(
        SecurityUser.id, ondelete="CASCADE"
    ), unique=True)

    enc_pubkey: Mapped[str]
    sig_pubkey: Mapped[str]

    owner: Mapped[SecurityUser] = relationship(
        backref=backref(
            _unique_name("mobile_security"),
            cascade="all, delete-orphan",
            uselist=False
        ),
        lazy="raise_on_sql"
    )

    def __init__(self, uid: int, enc_pubkey: str, sig_pubkey: str):
        self.uid = uid
        self.enc_pubkey = enc_pubkey
        self.sig_pubkey = sig_pubkey
