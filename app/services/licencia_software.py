import logging
from typing import Optional, List, Union, Dict, Any
from uuid import UUID
from datetime import date, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import select, func as sql_func
from fastapi import HTTPException, status

from app.models.licencia_software import LicenciaSoftware
from app.models.asignacion_licencia import AsignacionLicencia
from app.schemas.licencia_software import LicenciaSoftwareCreate, LicenciaSoftwareUpdate
from .base_service import BaseService
from .software_catalogo import software_catalogo_service
from .proveedor import proveedor_service

logger = logging.getLogger(__name__)

class LicenciaSoftwareService(BaseService[LicenciaSoftware, LicenciaSoftwareCreate, LicenciaSoftwareUpdate]):
    """
    Servicio para gestionar las instancias de Licencias de Software adquiridas.
    Las operaciones CUD (Create, Update, Delete) NO realizan commit.
    El commit debe ser manejado en la capa de la ruta.
    """

    def get_by_clave_producto(self, db: Session, *, clave: str) -> Optional[LicenciaSoftware]:
        if not clave:
            return None
        logger.debug(f"Buscando licencia por clave de producto: '{clave}'")
        statement = select(self.model).where(self.model.clave_producto == clave)
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def create(self, db: Session, *, obj_in: LicenciaSoftwareCreate) -> LicenciaSoftware:
        logger.debug(f"Intentando crear licencia para SoftwareCatalogo ID: {obj_in.software_catalogo_id}, Clave: {obj_in.clave_producto}")

        software_info_db = software_catalogo_service.get(db, id=obj_in.software_catalogo_id)
        if not software_info_db:
            logger.error(f"SoftwareCatalogo con ID {obj_in.software_catalogo_id} no encontrado al crear licencia.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"SoftwareCatalogo con ID {obj_in.software_catalogo_id} no encontrado.")
        
        if obj_in.proveedor_id and not proveedor_service.get(db, id=obj_in.proveedor_id):
            logger.error(f"Proveedor con ID {obj_in.proveedor_id} no encontrado al crear licencia.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Proveedor con ID {obj_in.proveedor_id} no encontrado.")

        create_data = obj_in.model_dump()
        
        if create_data.get("cantidad_total", 0) < 0 :
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cantidad total no puede ser negativa.")

        create_data["cantidad_disponible"] = create_data.get("cantidad_total", 0)
        
        db_licencia = super().create(db, obj_in=LicenciaSoftwareCreate(**create_data))
        
        # Corrección: Acceder a través del objeto software_info_db que ya obtuvimos
        logger.info(f"Licencia para '{software_info_db.nombre}' (Clave: {db_licencia.clave_producto}) preparada para ser creada.")
        return db_licencia

    def update(
        self,
        db: Session,
        *,
        db_obj: LicenciaSoftware, # Licencia existente de la BD
        obj_in: Union[LicenciaSoftwareUpdate, Dict[str, Any]]
    ) -> LicenciaSoftware:
        """
        Actualiza una licencia, con validaciones especiales para cantidades.
        NO permite actualizar cantidad_disponible directamente (manejada por triggers/asignaciones).
        NO realiza db.commit(). Llama a super().update() que tampoco lo hace.
        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        lic_id = db_obj.id
        logger.debug(f"Intentando actualizar licencia ID {lic_id} con datos: {update_data}")

        if "proveedor_id" in update_data and update_data["proveedor_id"] != db_obj.proveedor_id: # type: ignore
            if update_data["proveedor_id"] is not None:
                if not proveedor_service.get(db, id=update_data["proveedor_id"]):
                    logger.error(f"Proveedor con ID {update_data['proveedor_id']} no encontrado al actualizar licencia {lic_id}.")
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Proveedor con ID {update_data['proveedor_id']} no encontrado.")

        if "cantidad_disponible" in update_data:
            logger.warning(f"Intento de actualizar 'cantidad_disponible' directamente para licencia ID {lic_id}. Ignorando.")
            del update_data["cantidad_disponible"]

        if "cantidad_total" in update_data:
            nueva_cantidad_total = update_data["cantidad_total"]
            if nueva_cantidad_total < 0:
                 raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cantidad total no puede ser negativa.")

            asignadas_stmt = select(sql_func.count(AsignacionLicencia.id)).where(AsignacionLicencia.licencia_id == lic_id) # type: ignore
            cantidad_asignada_actual = db.execute(asignadas_stmt).scalar_one_or_none() or 0

            if nueva_cantidad_total < cantidad_asignada_actual:
                logger.error(f"Nueva cantidad total ({nueva_cantidad_total}) para licencia ID {lic_id} es menor que la cantidad ya asignada ({cantidad_asignada_actual}).")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"La nueva cantidad total ({nueva_cantidad_total}) no puede ser menor que la cantidad ya asignada ({cantidad_asignada_actual})."
                )
        
        updated_db_licencia = super().update(db, db_obj=db_obj, obj_in=update_data)
        logger.info(f"Licencia ID {lic_id} preparada para ser actualizada.")
        return updated_db_licencia

    def get_multi_by_software(
        self, db: Session, *, software_catalogo_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[LicenciaSoftware]:
        """Obtiene todas las licencias para un software específico, ordenadas por fecha de adquisición descendente."""
        logger.debug(f"Listando licencias para SoftwareCatalogo ID: {software_catalogo_id} (skip: {skip}, limit: {limit}).")
        statement = (
            select(self.model)
            .where(self.model.software_catalogo_id == software_catalogo_id) # type: ignore
            .order_by(self.model.fecha_adquisicion.desc()) # type: ignore
            .offset(skip)
            .limit(limit)
        )
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_expiring_soon(
        self, db: Session, *, days_ahead: int = 30, skip: int = 0, limit: int = 100
    ) -> List[LicenciaSoftware]:
        """Obtiene licencias que expiran dentro de los próximos N días y que no han expirado ya."""
        logger.debug(f"Buscando licencias que expiran en los próximos {days_ahead} días (skip: {skip}, limit: {limit}).")
        if days_ahead < 0:
            days_ahead = 0
        
        hoy = date.today()
        fecha_limite = hoy + timedelta(days=days_ahead)
        
        statement = (
            select(self.model)
            .where(
                self.model.fecha_expiracion != None, # type: ignore
                self.model.fecha_expiracion >= hoy, # type: ignore
                self.model.fecha_expiracion <= fecha_limite # type: ignore
             )
            .order_by(self.model.fecha_expiracion.asc()) # type: ignore
            .offset(skip)
            .limit(limit)
         )
        result = db.execute(statement)
        return list(result.scalars().all())

    # El método remove es heredado de BaseService y ya no hace commit.
    # Si se necesitara lógica específica antes de eliminar una licencia (ej. verificar asignaciones activas),
    # se debería sobreescribir remove aquí.
    # La BD tiene un trigger `prevenir_eliminacion_licencia_asignada_fn` que ya maneja esto.

licencia_software_service = LicenciaSoftwareService(LicenciaSoftware)
