"""ORM mapping for ``registered_services``."""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aspire_tool.database.sqlalchemy.base import Base


class ServiceRow(Base):
    """Single ORM model for the registry table (inherits ``Base`` only)."""

    __tablename__ = "registered_services"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    workdir_relative: Mapped[str] = mapped_column(String(1024), nullable=False)
    command: Mapped[str] = mapped_column(String(1024), nullable=False)
    args_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    health_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    health_target: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_start_with_home: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    env_json: Mapped[str | None] = mapped_column(Text, nullable=True)
