import logging
from typing import Optional, List, Union, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.documentacion import Documentacion
from app.models.usuario import Usuario
from app.schemas.documentacion import DocumentacionCreateInternal, DocumentacionUpdate, DocumentacionVerify
from .base_service import BaseService
from .tipo_documento import tipo_documento_service
from .equipo import equipo_service
from .mantenimiento import mantenimiento_service
from .licencia_software import licencia_software_service

logger = logging.getLogger(__name__)

class DocumentacionService(BaseService[Documentacion, DocumentacionCreateInternal, DocumentacionUpdate]):
    """
    Servicio para gestionar la Documentación asociada a otros objetos.
    Las operaciones CUD (Create, Update, Delete) y verify_document (que es una forma de update)
    NO realizan commit. El commit debe ser manejado en la capa de la ruta.
    """

    def create(self, db: Session, *, obj_in: DocumentacionCreateInternal) -> Documentacion:
        # Corrección en el log: usar obj_in.titulo o obj_in.nombre_archivo
        logger.debug(f"Intentando crear documentación: '{obj_in.titulo}' (Archivo: {obj_in.nombre_archivo}) para Tipo ID {obj_in.tipo_documento_id}")

        if not tipo_documento_service.get(db, id=obj_in.tipo_documento_id):
             logger.error(f"TipoDocumento con ID {obj_in.tipo_documento_id} no encontrado al crear documentación.")
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"TipoDocumento con ID {obj_in.tipo_documento_id} no encontrado.")

        if obj_in.equipo_id and not equipo_service.get(db, id=obj_in.equipo_id):
            logger.error(f"Equipo con ID {obj_in.equipo_id} no encontrado al crear documentación.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Equipo con ID {obj_in.equipo_id} no encontrado.")
        if obj_in.mantenimiento_id and not mantenimiento_service.get(db, id=obj_in.mantenimiento_id):
            logger.error(f"Mantenimiento con ID {obj_in.mantenimiento_id} no encontrado al crear documentación.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Mantenimiento con ID {obj_in.mantenimiento_id} no encontrado.")
        if obj_in.licencia_id and not licencia_software_service.get(db, id=obj_in.licencia_id):
             logger.error(f"Licencia con ID {obj_in.licencia_id} no encontrada al crear documentación.")
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Licencia con ID {obj_in.licencia_id} no encontrada.")

        if not obj_in.equipo_id and not obj_in.mantenimiento_id and not obj_in.licencia_id:
             logger.error("Intento de crear documentación sin asociación a Equipo, Mantenimiento o Licencia.")
             raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El documento debe estar asociado al menos a un Equipo, Mantenimiento o Licencia.")

        create_data = obj_in.model_dump()
        db_obj = self.model(**create_data)
        
        db.add(db_obj)
        # Corrección en el log: usar db_obj.titulo o db_obj.nombre_archivo
        logger.info(f"Documentación '{db_obj.titulo}' (Archivo: {db_obj.nombre_archivo}) preparada para ser creada (Enlace: {db_obj.enlace}).")
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: Documentacion,
        obj_in: Union[DocumentacionUpdate, Dict[str, Any]]
    ) -> Documentacion:
        """
        Actualiza metadatos de un registro de documentación (ej. nombre, descripción, tipo).
        NO realiza db.commit(). Llama a super().update() que tampoco lo hace.
        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        doc_id = db_obj.id
        logger.debug(f"Intentando actualizar metadatos de documentación ID {doc_id} con datos: {update_data}")

        if "tipo_documento_id" in update_data and update_data["tipo_documento_id"] != db_obj.tipo_documento_id: #type: ignore
            tipo_doc = tipo_documento_service.get(db, id=update_data["tipo_documento_id"])
            if not tipo_doc:
                logger.error(f"TipoDocumento con ID {update_data['tipo_documento_id']} no encontrado al actualizar documentación {doc_id}.")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"TipoDocumento con ID {update_data['tipo_documento_id']} no encontrado.")

        updated_db_obj = super().update(db, db_obj=db_obj, obj_in=update_data)
        # Corrección en el log: usar updated_db_obj.titulo
        logger.info(f"Metadatos de documentación ID {doc_id} ('{updated_db_obj.titulo}') preparados para ser actualizados.")
        return updated_db_obj


    def verify_document(
        self,
        db: Session,
        *,
        db_obj: Documentacion,
        verify_data: DocumentacionVerify,
        verificado_por_usuario: Usuario
    ) -> Documentacion:
        """
        Actualiza el estado de verificación de un documento.
        NO realiza db.commit().
        """
        doc_id = db_obj.id
        logger.debug(f"Intentando verificar/rechazar documentación ID {doc_id} a estado '{verify_data.estado}' por usuario '{verificado_por_usuario.nombre_usuario}'.")

        if db_obj.estado == verify_data.estado:
             if db_obj.notas_verificacion != verify_data.notas_verificacion:
                 logger.info(f"Actualizando solo notas de verificación para doc ID {doc_id} (estado sin cambios: '{db_obj.estado}').")
                 db_obj.notas_verificacion = verify_data.notas_verificacion
                 db_obj.verificado_por = verificado_por_usuario.id
                 db_obj.fecha_verificacion = datetime.now(timezone.utc)
                 db.add(db_obj)
             else:
                logger.info(f"Estado y notas de verificación sin cambios para doc ID {doc_id}.")
             return db_obj

        update_payload: Dict[str, Any] = {
            "estado": verify_data.estado,
            "notas_verificacion": verify_data.notas_verificacion,
            "verificado_por": verificado_por_usuario.id,
            "fecha_verificacion": datetime.now(timezone.utc)
        }
        
        logger.info(f"Cambiando estado de doc ID {doc_id} a '{verify_data.estado}' con notas: '{verify_data.notas_verificacion}'.")
        updated_db_obj = super().update(db, db_obj=db_obj, obj_in=update_payload)
        logger.info(f"Estado de verificación de documentación ID {doc_id} preparado para ser actualizado.")
        return updated_db_obj

    # --- Métodos GET con carga eager de relaciones ---
    def _apply_load_options(self, statement):
        """Aplica opciones de carga eager para las relaciones."""
        return statement.options(
            selectinload(self.model.equipo), #type: ignore
            selectinload(self.model.mantenimiento), #type: ignore
            selectinload(self.model.licencia), #type: ignore
            selectinload(self.model.tipo_documento), #type: ignore
            selectinload(self.model.subido_por_usuario), #type: ignore
            selectinload(self.model.verificado_por_usuario) #type: ignore
        )

    def get(self, db: Session, id: UUID) -> Optional[Documentacion]:
        """Sobrescribe get para cargar relaciones."""
        logger.debug(f"Obteniendo documentación ID: {id} con relaciones.")
        statement = select(self.model).where(self.model.id == id) #type: ignore
        statement = self._apply_load_options(statement)
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Documentacion]:
        """Sobrescribe get_multi para cargar relaciones, ordenado por fecha de subida descendente."""
        logger.debug(f"Listando documentación (skip: {skip}, limit: {limit}) con relaciones.")
        statement = select(self.model).order_by(self.model.fecha_subida.desc()).offset(skip).limit(limit) # type: ignore
        statement = self._apply_load_options(statement)
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_multi_by_equipo(self, db: Session, *, equipo_id: UUID, skip: int = 0, limit: int = 100) -> List[Documentacion]:
        logger.debug(f"Listando documentación para equipo ID: {equipo_id} (skip: {skip}, limit: {limit}).")
        statement = select(self.model).where(self.model.equipo_id == equipo_id).order_by(self.model.fecha_subida.desc()).offset(skip).limit(limit) # type: ignore
        statement = self._apply_load_options(statement)
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_multi_by_mantenimiento(self, db: Session, *, mantenimiento_id: UUID, skip: int = 0, limit: int = 100) -> List[Documentacion]:
        logger.debug(f"Listando documentación para mantenimiento ID: {mantenimiento_id} (skip: {skip}, limit: {limit}).")
        statement = select(self.model).where(self.model.mantenimiento_id == mantenimiento_id).order_by(self.model.fecha_subida.desc()).offset(skip).limit(limit) # type: ignore
        statement = self._apply_load_options(statement)
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_multi_by_licencia(self, db: Session, *, licencia_id: UUID, skip: int = 0, limit: int = 100) -> List[Documentacion]:
        logger.debug(f"Listando documentación para licencia ID: {licencia_id} (skip: {skip}, limit: {limit}).")
        statement = select(self.model).where(self.model.licencia_id == licencia_id).order_by(self.model.fecha_subida.desc()).offset(skip).limit(limit) # type: ignore
        statement = self._apply_load_options(statement)
        result = db.execute(statement)
        return list(result.scalars().all())
    
    # El método remove es heredado de BaseService y ya no hace commit.
    # Si se necesitara lógica específica antes de eliminar un documento (ej. borrar el archivo físico),
    # se debería sobreescribir remove aquí. El borrado del archivo físico usualmente se maneja en la ruta.

documentacion_service = DocumentacionService(Documentacion)
