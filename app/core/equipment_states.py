"""Stable identifiers for operational rules; visible names belong to the catalog."""
from enum import Enum


class EquipmentStateCode(str, Enum):
    AVAILABLE = "disponible"
    IN_USE = "en_uso"
    ON_LOAN = "prestado"
    MAINTENANCE = "en_mantenimiento"
    RETIRED = "dado_de_baja"


SYSTEM_STATE_CODES = frozenset(state.value for state in EquipmentStateCode)
