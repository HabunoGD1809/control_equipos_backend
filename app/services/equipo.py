import logging
from typing import Optional, List, Union, Dict, Any
from uuid import UUID
import re # Importar re para validación de formato de N/S si se decide hacer en el servicio

from sqlalchemy.orm import Session, selectinload # Añadir selectinload
from sqlalchemy import select, text
from fastapi import HTTPException, status

# Importar modelos y schemas
from app.models.equipo import Equipo
from app.models.estado_equipo import EstadoEquipo # Para type hint
from app.models.proveedor import Proveedor # Para type hint
from app.schemas.equipo import EquipoCreate, EquipoUpdate, EquipoSearchResult, GlobalSearchResult

# Importar la clase base y otros servicios necesarios
from .base_service import BaseService
from .estado_equipo import estado_equipo_service
from .proveedor import proveedor_service

logger = logging.getLogger(__name__)

# Expresión regular para el formato de número de serie (debe coincidir con la constraint de la BD)
# La constraint en structureControlEquipos.sql es: '^[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+$'
# Ejemplo: ABC-1234-XYZ5
# Aquí definimos uno un poco más flexible para el ejemplo, pero idealmente sería idéntico.
# Este regex es una aproximación, la validación final la hará la BD.
# SERIAL_NUMBER_REGEX = r"^[A-Za-z0-9]+(-[A-Za-z0-9]+){2,}$" # Ejemplo: X-Y-Z o X-Y-Z-123
# Usaremos el que está en la BD como referencia.
SERIAL_NUMBER_REGEX_DB_FORMAT = r"^[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+$"


class EquipoService(BaseService[Equipo, EquipoCreate, EquipoUpdate]):
    """
    Servicio para gestionar Equipos.
    Incluye validaciones y llamadas a funciones de búsqueda de la DB.
    Las operaciones CUD (Create, Update, Delete) heredadas de BaseService
    NO realizan commit. El commit debe ser manejado en la capa de la ruta.
    """

    def _apply_load_options_for_equipo(self, statement):
        """Aplica opciones de carga eager comunes para equipos."""
        return statement.options(
            selectinload(Equipo.estado),
            selectinload(Equipo.proveedor)
            # Añadir otras relaciones que se quieran cargar por defecto:
            # selectinload(Equipo.movimientos),
            # selectinload(Equipo.documentos),
            # selectinload(Equipo.mantenimientos),
        )

    def get(self, db: Session, id: Any) -> Optional[Equipo]:
        """Obtiene un equipo con sus relaciones principales cargadas."""
        statement = select(self.model).where(self.model.id == id) # type: ignore[attr-defined]
        statement = self._apply_load_options_for_equipo(statement)
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Equipo]:
        """Obtiene múltiples equipos con sus relaciones principales cargadas."""
        statement = select(self.model).order_by(self.model.nombre).offset(skip).limit(limit) # type: ignore[attr-defined]
        statement = self._apply_load_options_for_equipo(statement)
        result = db.execute(statement)
        return list(result.scalars().all())


    def get_by_serie(self, db: Session, *, numero_serie: str) -> Optional[Equipo]:
        """Obtiene un equipo por su número de serie."""
        statement = select(self.model).where(self.model.numero_serie == numero_serie) # type: ignore[attr-defined]
        statement = self._apply_load_options_for_equipo(statement) # Cargar relaciones también aquí
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def get_by_codigo_interno(self, db: Session, *, codigo_interno: str) -> Optional[Equipo]:
        """Obtiene un equipo por su código interno."""
        if not codigo_interno:
            return None
        statement = select(self.model).where(self.model.codigo_interno == codigo_interno) # type: ignore[attr-defined]
        statement = self._apply_load_options_for_equipo(statement)
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def _validate_numero_serie_format(self, numero_serie: str):
        """
        Valida el formato del número de serie contra la regex definida.
        Lanza HTTPException 422 si no coincide.
        Esta es una validación en la aplicación, la BD tiene su propia CHECK constraint.
        """
        if not re.match(SERIAL_NUMBER_REGEX_DB_FORMAT, numero_serie):
            logger.warning(f"Formato de número de serie inválido proporcionado: '{numero_serie}'")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"El formato del número de serie '{numero_serie}' no es válido. Debe ser similar a 'AAA-1111-BBB'."
            )

    def create(self, db: Session, *, obj_in: EquipoCreate) -> Equipo:
        """
        Crea un nuevo equipo, validando IDs relacionados y unicidad.
        NO realiza db.commit().
        """
        logger.debug(f"Intentando crear equipo con N/S: {obj_in.numero_serie}, Código Interno: {obj_in.codigo_interno}")
        
        self._validate_numero_serie_format(obj_in.numero_serie) # Validación de formato en la app

        existing_serie = self.get_by_serie(db, numero_serie=obj_in.numero_serie)
        if existing_serie:
            logger.warning(f"Intento de crear equipo con N/S duplicado: {obj_in.numero_serie}")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Número de serie ya registrado.")
        
        if obj_in.codigo_interno:
            existing_codigo = self.get_by_codigo_interno(db, codigo_interno=obj_in.codigo_interno)
            if existing_codigo:
                logger.warning(f"Intento de crear equipo con código interno duplicado: {obj_in.codigo_interno}")
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Código interno ya registrado.")

        if obj_in.estado_id:
            estado: Optional[EstadoEquipo] = estado_equipo_service.get(db, id=obj_in.estado_id) # type: ignore
            if not estado:
                logger.error(f"EstadoEquipo con ID {obj_in.estado_id} no encontrado al crear equipo.")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Estado de equipo con ID {obj_in.estado_id} no encontrado.")
        else:
            logger.error("Intento de crear equipo sin estado_id.")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El campo estado_id es obligatorio para el equipo.")

        if obj_in.proveedor_id:
            proveedor: Optional[Proveedor] = proveedor_service.get(db, id=obj_in.proveedor_id) # type: ignore
            if not proveedor:
                logger.error(f"Proveedor con ID {obj_in.proveedor_id} no encontrado al crear equipo.")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Proveedor con ID {obj_in.proveedor_id} no encontrado.")

        db_obj = super().create(db, obj_in=obj_in) # Llama al create de BaseService
        logger.info(f"Equipo '{db_obj.nombre}' (N/S: {db_obj.numero_serie}) preparado para ser creado.")
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: Equipo,
        obj_in: Union[EquipoUpdate, Dict[str, Any]]
    ) -> Equipo:
        """
        Actualiza un equipo existente, validando IDs y unicidad si cambian.
        NO realiza db.commit().
        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        equipo_id = db_obj.id
        logger.debug(f"Intentando actualizar equipo ID {equipo_id} con datos: {update_data}")

        if "numero_serie" in update_data and update_data["numero_serie"] != db_obj.numero_serie:
            self._validate_numero_serie_format(update_data["numero_serie"]) # Validación de formato en la app
            logger.debug(f"Validando nuevo N/S '{update_data['numero_serie']}' para equipo ID {equipo_id}")
            existing = self.get_by_serie(db, numero_serie=update_data["numero_serie"])
            if existing and existing.id != equipo_id:
                logger.warning(f"Conflicto de N/S al actualizar equipo ID {equipo_id}. N/S '{update_data['numero_serie']}' ya existe.")
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Número de serie ya registrado para otro equipo.")
        
        if "codigo_interno" in update_data and update_data["codigo_interno"] != db_obj.codigo_interno:
            if update_data["codigo_interno"]:
                logger.debug(f"Validando nuevo código interno '{update_data['codigo_interno']}' para equipo ID {equipo_id}")
                existing = self.get_by_codigo_interno(db, codigo_interno=update_data["codigo_interno"])
                if existing and existing.id != equipo_id:
                    logger.warning(f"Conflicto de código interno al actualizar equipo ID {equipo_id}. Código '{update_data['codigo_interno']}' ya existe.")
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Código interno ya registrado para otro equipo.")

        if "estado_id" in update_data and update_data["estado_id"] != db_obj.estado_id:
             logger.debug(f"Validando nuevo estado_id '{update_data['estado_id']}' para equipo ID {equipo_id}")
             estado: Optional[EstadoEquipo] = estado_equipo_service.get(db, id=update_data["estado_id"]) # type: ignore
             if not estado:
                 logger.error(f"EstadoEquipo con ID {update_data['estado_id']} no encontrado al actualizar equipo {equipo_id}.")
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Estado de equipo con ID {update_data['estado_id']} no encontrado.")

        if "proveedor_id" in update_data and update_data["proveedor_id"] != db_obj.proveedor_id:
            if update_data["proveedor_id"] is not None:
                logger.debug(f"Validando nuevo proveedor_id '{update_data['proveedor_id']}' para equipo ID {equipo_id}")
                proveedor: Optional[Proveedor] = proveedor_service.get(db, id=update_data["proveedor_id"]) # type: ignore
                if not proveedor:
                    logger.error(f"Proveedor con ID {update_data['proveedor_id']} no encontrado al actualizar equipo {equipo_id}.")
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Proveedor con ID {update_data['proveedor_id']} no encontrado.")
            else:
                logger.debug(f"Desasociando proveedor para equipo ID {equipo_id}.")

        updated_db_obj = super().update(db, db_obj=db_obj, obj_in=update_data)
        logger.info(f"Equipo ID {equipo_id} ('{updated_db_obj.nombre}') preparado para ser actualizado.")
        return updated_db_obj

    def search(self, db: Session, *, termino: str) -> List[EquipoSearchResult]:
        """
        Busca equipos usando la función de base de datos 'buscar_equipos'.
        """
        if not termino or not termino.strip():
            logger.debug("Término de búsqueda de equipos vacío, devolviendo lista vacía.")
            return []
        
        logger.debug(f"Buscando equipos con término: '{termino}'")
        # Asegurarse que el nombre de la función en el schema correcto sea invocado
        stmt = text("SELECT * FROM control_equipos.buscar_equipos(:termino)")
        try:
            result = db.execute(stmt, {"termino": termino})
            # Pydantic V2 model_validate
            search_results = [EquipoSearchResult.model_validate(row._asdict()) for row in result] # Corregido a _asdict() para NamedTuple
            logger.info(f"Búsqueda de equipos por '{termino}' encontró {len(search_results)} resultado(s).")
            return search_results
        except Exception as e:
            logger.error(f"Error durante la búsqueda de equipos con término '{termino}': {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error al realizar la búsqueda de equipos.")


    def search_global(self, db: Session, *, termino: str) -> List[GlobalSearchResult]:
        """
        Realiza una búsqueda global usando la función 'busqueda_global'.
        """
        if not termino or not termino.strip():
            logger.debug("Término de búsqueda global vacío, devolviendo lista vacía.")
            return []

        logger.debug(f"Buscando globalmente con término: '{termino}'")
        stmt = text("SELECT * FROM control_equipos.busqueda_global(:termino)")
        try:
            result = db.execute(stmt, {"termino": termino})
            search_results = [GlobalSearchResult.model_validate(row._asdict()) for row in result] # Corregido a _asdict()
            logger.info(f"Búsqueda global por '{termino}' encontró {len(search_results)} resultado(s).")
            return search_results
        except Exception as e:
            logger.error(f"Error durante la búsqueda global con término '{termino}': {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error al realizar la búsqueda global.")

    # El método remove es heredado de BaseService y ya no hace commit.
    # Si se necesitara lógica específica antes de eliminar un equipo (ej. verificar si está reservado,
    # tiene mantenimientos activos, etc.), se debería sobreescribir remove aquí.
            

equipo_service = EquipoService(Equipo)
