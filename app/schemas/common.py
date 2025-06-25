from pydantic import BaseModel

class Msg(BaseModel):
    """Schema genérico para mensajes de respuesta."""
    msg: str

# Podrías añadir aquí otros schemas comunes, como para paginación:
# class PaginatedResponse(BaseModel):
#     total: int
#     page: int
#     size: int
#     results: List[Any] # El tipo real dependerá de la respuesta
