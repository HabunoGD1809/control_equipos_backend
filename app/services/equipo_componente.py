import logging # Importar logging
from typing import Optional, List, Union, Dict, Any # Union, Dict, Any no se usan aquí pero están por si se añaden más métodos
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select, delete # delete no se usa directamente aquí
from fastapi import HTTPException, status

# Importar modelos y schemas
from app.models.equipo_componente import EquipoComponente
# from app.models.equipo import Equipo # Usado a través de equipo_service
from app.schemas.equipo_componente import EquipoComponenteCreate, EquipoComponenteUpdate

# Importar la clase base y otros servicios necesarios
from .base_service import BaseService # BaseService ya está modificado
from .equipo import equipo_service # Para validar IDs de equipo

logger = logging.getLogger(__name__) # Configurar logger

class EquipoComponenteService(BaseService[EquipoComponente, EquipoComponenteCreate, EquipoComponenteUpdate]):
    """
    Servicio para gestionar las relaciones de componentes entre equipos.
    Las operaciones CUD (Create, Update, Delete) heredadas o propias
    NO realizan commit. El commit debe ser manejado en la capa de la ruta.
    """

    def get_relation(
        self,
        db: Session,
        *,
        padre_id: UUID,
        componente_id: UUID,
        tipo: str
    ) -> Optional[EquipoComponente]:
        """Busca una relación específica por padre, componente y tipo."""
        logger.debug(f"Buscando relación: Padre ID {padre_id}, Componente ID {componente_id}, Tipo '{tipo}'")
        statement = select(self.model).where(
            self.model.equipo_padre_id == padre_id,
            self.model.equipo_componente_id == componente_id,
            self.model.tipo_relacion == tipo
        )
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def create(self, db: Session, *, obj_in: EquipoComponenteCreate) -> EquipoComponente:
        """
        Crea una nueva relación de componente, validando IDs y restricciones.
        NO realiza db.commit().
        """
        logger.debug(f"Intentando crear relación de componente: Padre ID {obj_in.equipo_padre_id}, Componente ID {obj_in.equipo_componente_id}, Tipo '{obj_in.tipo_relacion}'")

        if obj_in.equipo_padre_id == obj_in.equipo_componente_id:
            logger.warning("Intento de crear relación de componente cíclica (padre == componente).")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un equipo no puede ser componente de sí mismo."
            )

        padre = equipo_service.get(db, id=obj_in.equipo_padre_id)
        if not padre:
            logger.error(f"Equipo padre con ID {obj_in.equipo_padre_id} no encontrado al crear relación de componente.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Equipo padre con ID {obj_in.equipo_padre_id} no encontrado."
            )

        componente = equipo_service.get(db, id=obj_in.equipo_componente_id)
        if not componente:
             logger.error(f"Equipo componente con ID {obj_in.equipo_componente_id} no encontrado al crear relación.")
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Equipo componente con ID {obj_in.equipo_componente_id} no encontrado."
            )

        existing_relation = self.get_relation(
            db,
            padre_id=obj_in.equipo_padre_id,
            componente_id=obj_in.equipo_componente_id,
            tipo=obj_in.tipo_relacion
        )
        if existing_relation:
             logger.warning(f"Intento de crear relación de componente duplicada: Padre {obj_in.equipo_padre_id}, Componente {obj_in.equipo_componente_id}, Tipo '{obj_in.tipo_relacion}'.")
             raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe una relación de tipo '{obj_in.tipo_relacion}' entre el equipo padre (ID: {padre.nombre}) y el componente (ID: {componente.nombre})."
            )

        # Llamar al método base para crear. super().create() ya no hace commit.
        db_relation = super().create(db, obj_in=obj_in)
        logger.info(f"Relación de componente (Padre: {padre.nombre}, Componente: {componente.nombre}, Tipo: '{db_relation.tipo_relacion}') preparada para ser creada.")
        return db_relation

    # El método update es heredado de BaseService. Si se necesita lógica específica
    # (ej. no permitir cambiar equipo_padre_id o equipo_componente_id), se debería sobreescribir.
    # def update(self, db: Session, *, db_obj: EquipoComponente, obj_in: EquipoComponenteUpdate) -> EquipoComponente:
    #     logger.debug(f"Actualizando relación de componente ID {db_obj.id}")
    #     # Validaciones específicas si es necesario...
    #     # Por ejemplo, no permitir cambiar los IDs de padre o componente:
    #     update_data = obj_in.model_dump(exclude_unset=True)
    #     if "equipo_padre_id" in update_data and update_data["equipo_padre_id"] != db_obj.equipo_padre_id:
    #         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se puede cambiar el equipo padre de una relación existente.")
    #     if "equipo_componente_id" in update_data and update_data["equipo_componente_id"] != db_obj.equipo_componente_id:
    #         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se puede cambiar el equipo componente de una relación existente.")
    #
    #     updated_obj = super().update(db, db_obj=db_obj, obj_in=obj_in) # No hace commit
    #     logger.info(f"Relación de componente ID {updated_obj.id} preparada para ser actualizada.")
    #     return updated_obj


    def get_componentes_by_padre(self, db: Session, *, equipo_padre_id: UUID) -> List[EquipoComponente]:
        """Obtiene todas las relaciones donde el equipo es el padre, ordenadas por fecha de creación."""
        logger.debug(f"Obteniendo componentes para el equipo padre ID: {equipo_padre_id}")
        statement = select(self.model).where(self.model.equipo_padre_id == equipo_padre_id).order_by(self.model.created_at) # type: ignore[attr-defined]
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_padres_by_componente(self, db: Session, *, equipo_componente_id: UUID) -> List[EquipoComponente]:
        """Obtiene todas las relaciones donde el equipo es el componente, ordenadas por fecha de creación."""
        logger.debug(f"Obteniendo padres para el equipo componente ID: {equipo_componente_id}")
        statement = select(self.model).where(self.model.equipo_componente_id == equipo_componente_id).order_by(self.model.created_at) # type: ignore[attr-defined]
        result = db.execute(statement)
        return list(result.scalars().all())

    def remove_relation(self, db: Session, *, id: UUID) -> EquipoComponente:
         """
         Elimina una relación de componente por su ID.
         NO realiza db.commit(). Llama a super().remove() que tampoco lo hace.
         """
         logger.debug(f"Intentando eliminar relación de componente ID: {id}")
         # super().remove() incluye get_or_404 y db.delete()
         deleted_obj = super().remove(db=db, id=id)
         logger.warning(f"Relación de componente ID {id} (Padre ID: {deleted_obj.equipo_padre_id}, Componente ID: {deleted_obj.equipo_componente_id}) preparada para ser eliminada.")
         return deleted_obj

equipo_componente_service = EquipoComponenteService(EquipoComponente)
