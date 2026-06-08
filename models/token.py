from webfluid.core.ext import db
from webfluid.extensions.security.models import User
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship, backref
from datetime import datetime, UTC


def _unique_name(name: str) -> str:
    from .. import additive
    return additive.unique_name(name)


class Token(db.Model):
    __tablename__ = _unique_name("tokens")

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[int] = mapped_column(ForeignKey(
        User.id, ondelete="CASCADE"
    ))

    name: Mapped[str]
    exp: Mapped[datetime]
    iat: Mapped[datetime]

    owner: Mapped[User] = relationship(
        backref=backref(_unique_name("tokens"), cascade="all, delete-orphan"),
        lazy="selectin"
    )

    def __init__(self, uid: int, name: str, exp: datetime):
        self.uid = uid
        self.name = name
        self.exp = exp
        self.iat = datetime.now(UTC)
