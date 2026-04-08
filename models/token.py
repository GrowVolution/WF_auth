from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from webfluid.core.ext import db


class ExpiredToken(db.Model):
    __tablename__ = "expired_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now()
    )

    def __init__(self, token: str): self.token = token
