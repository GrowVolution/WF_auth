from webfluid.core.ext import db
from webfluid.extensions.security.models import User
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime


def _unique_name(name: str) -> str:
    from .. import additive
    return additive.unique_name(name)


class Token(db.Model):
    __tablename__ = _unique_name("tokens")

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[int] = mapped_column(ForeignKey(
        User.id, ondelete="CASCADE"
    ))

    name: Mapped[str] = mapped_column(unique=True)
    exp: Mapped[datetime]
    iat: Mapped[datetime] = mapped_column(
        server_default=func.now()
    )

    owner: Mapped[User] = relationship(
        backref=_unique_name("tokens"),
        lazy="selectin"
    )

    def __init__(self, uid: int, name: str, exp: datetime):
        self.uid = uid
        self.name = name
        self.exp = exp
