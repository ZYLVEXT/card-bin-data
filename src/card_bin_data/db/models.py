"""SQLAlchemy persistence models for normalized BIN/IIN data."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import CardBinDataBase


class DataSourceModel(CardBinDataBase):
    """Upstream data source metadata used for attribution and import idempotency."""

    __tablename__ = "data_sources"
    __table_args__ = (UniqueConstraint("source_id", name="uq_data_sources_source_id"),)

    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    upstream_url: Mapped[str] = mapped_column(String(512), nullable=False)
    license: Mapped[str | None] = mapped_column(String(128), default=None)
    local_path: Mapped[str | None] = mapped_column(String(1024), default=None)

    record_sources: Mapped[list["BinRecordSourceModel"]] = relationship(
        back_populates="data_source",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class BinRecordModel(CardBinDataBase):
    """Normalized BIN/IIN record optimized for exact prefix and range lookup."""

    __tablename__ = "bin_records"
    __table_args__ = (
        # Narrow index for the latency-sensitive exact-prefix lookup.
        Index("ix_bin_records_iin_start", "iin_start"),
        # Range fallback matches an 8-digit prefix against the normalized fixed-width boundaries.
        Index("ix_bin_records_range_boundaries_8", "range_start_8", "range_end_8"),
    )

    iin_start: Mapped[str] = mapped_column(String(8), nullable=False)
    iin_end: Mapped[str | None] = mapped_column(String(8), default=None)
    range_start_8: Mapped[str | None] = mapped_column(String(8), default=None)
    range_end_8: Mapped[str | None] = mapped_column(String(8), default=None)
    number_length: Mapped[int | None] = mapped_column(Integer, default=None)
    luhn: Mapped[bool | None] = mapped_column(Boolean, default=None)
    scheme: Mapped[str | None] = mapped_column(String(64), default=None)
    product_brand: Mapped[str | None] = mapped_column(String(128), default=None)
    type: Mapped[str | None] = mapped_column(String(64), default=None)
    category: Mapped[str | None] = mapped_column(String(128), default=None)
    prepaid: Mapped[bool | None] = mapped_column(Boolean, default=None)
    country_alpha2: Mapped[str | None] = mapped_column(String(2), default=None)
    country_alpha3: Mapped[str | None] = mapped_column(String(3), default=None)
    country_name: Mapped[str | None] = mapped_column(String(255), default=None)
    issuer_name: Mapped[str | None] = mapped_column(String(255), default=None)
    issuer_phone: Mapped[str | None] = mapped_column(String(128), default=None)
    issuer_url: Mapped[str | None] = mapped_column(String(512), default=None)
    issuer_city: Mapped[str | None] = mapped_column(String(255), default=None)

    sources: Mapped[list["BinRecordSourceModel"]] = relationship(
        back_populates="bin_record",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class BinRecordSourceModel(CardBinDataBase):
    """Link one normalized BIN/IIN record to the source row that contributed data."""

    __tablename__ = "bin_record_sources"
    __table_args__ = (
        UniqueConstraint(
            "bin_record_id",
            "data_source_id",
            "source_row_key",
            name="uq_bin_record_sources_record_source_row",
        ),
        Index("ix_bin_record_sources_bin_record_id", "bin_record_id"),
    )

    bin_record_id: Mapped[int] = mapped_column(ForeignKey("bin_records.id", ondelete="CASCADE"), nullable=False)
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    source_row_key: Mapped[str] = mapped_column(String(255), nullable=False)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    raw_payload: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)

    bin_record: Mapped["BinRecordModel"] = relationship(back_populates="sources", lazy="joined")
    data_source: Mapped["DataSourceModel"] = relationship(back_populates="record_sources", lazy="joined")
