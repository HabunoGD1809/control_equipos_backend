"""Bounded, extensible technical metadata shared by equipment create/update."""
import ipaddress
import re
import unicodedata
from enum import Enum
from typing import Annotated
from pydantic import AfterValidator, StrictStr


class TipoActivoEnum(str, Enum):
    EQUIPO = "Equipo"
    SERVIDOR = "Servidor"
    RED = "Red"
    IMPRESORA = "Impresora"
    UPS = "UPS"
    ALMACENAMIENTO = "Almacenamiento"
    PERIFERICO = "Periférico"
    OTRO = "Otro"


def validar_ficha(value: dict[str, str]) -> dict[str, str]:
    if len(value) > 20:
        raise ValueError("La ficha técnica admite hasta 20 campos.")
    result = {}
    for key, item in value.items():
        key, item = key.strip(), item.strip()
        if not key or len(key) > 40 or len(item) > 500 or key in result:
            raise ValueError("Cada campo debe tener un nombre único de hasta 40 caracteres y un valor de hasta 500.")
        normalized = "".join(c for c in unicodedata.normalize("NFD", key.lower()) if not unicodedata.combining(c))
        if any(word in normalized for word in ("password", "contrasena", "secret", "token")):
            raise ValueError("Las credenciales no deben almacenarse en la ficha técnica.")
        if key == "direccion_ip" and item:
            try:
                ipaddress.ip_address(item)
            except ValueError:
                raise ValueError("La dirección IP debe ser IPv4 o IPv6 válida.") from None
        if key == "direccion_mac" and item and not re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}|(?:[0-9a-fA-F]{2}-){5}[0-9a-fA-F]{2}", item):
            raise ValueError("La dirección MAC debe tener seis pares hexadecimales.")
        if item:
            result[key] = item
    return result


FichaTecnica = Annotated[dict[StrictStr, StrictStr], AfterValidator(validar_ficha)]
