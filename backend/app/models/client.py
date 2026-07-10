from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.artifact import Artifact
    from app.models.project import Project


class Client(BaseEntity):
    __tablename__ = "clients"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    projects: Mapped[list[Project]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )
    artifacts: Mapped[list[Artifact]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )
