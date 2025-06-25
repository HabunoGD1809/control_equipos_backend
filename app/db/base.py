from typing import Any, TypeVar

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention, schema="control_equipos")

class Base(DeclarativeBase):
    """
    Clase base para todos los modelos ORM de SQLAlchemy.
    """
    metadata = metadata
    # Ya no necesitas __table_args__ = {"schema": "control_equipos"} en cada modelo
    # si lo defines en MetaData.

    pass

ModelType = TypeVar("ModelType", bound=Base)
