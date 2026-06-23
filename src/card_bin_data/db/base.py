"""Isolated declarative base for card_bin_data persistence models.

Binding the models to a dedicated ``__bind_key__`` keeps their tables in a
private ``MetaData`` instead of advanced_alchemy's shared ``orm_registry``
metadata. A host application that embeds card_bin_data therefore never has the
BIN/IIN tables injected into its own default metadata as an import side effect:
to generate Alembic migrations for them, the host opts in explicitly by adding
``card_bin_data.db.metadata`` to its ``target_metadata``.
"""

from advanced_alchemy.base import BigIntAuditBase


class CardBinDataBase(BigIntAuditBase):
    """BigInt + audit declarative base scoped to the card_bin_data bind key."""

    __abstract__ = True
    __bind_key__ = "card_bin_data"
