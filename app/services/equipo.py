import logging
import csv
import io
import re
from datetime import datetime
from typing import Optional, List, Union, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.equipo import Equipo
from app.models.estado_equipo import EstadoEquipo
from app.models.proveedor import Proveedor
from app.models.ubicacion import Ubicacion
from app.schemas.equipo import EquipoCreate, EquipoUpdate, EquipoSearchResult, GlobalSearchResult
from app.services.ubicacion import ubicacion_service

from .base_service import BaseService
from .estado_equipo import estado_equipo_service
from .proveedor import proveedor_service

logger = logging.getLogger(__name__)
SERIAL_NUMBER_REGEX_DB_FORMAT = r"^[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+$"

class EquipoService(BaseService[Equipo, EquipoCreate, EquipoUpdate]):

    def _apply_load_options_for_equipo(self, statement):
        return statement.options(
            selectinload(Equipo.estado),
            selectinload(Equipo.proveedor),
            selectinload(Equipo.ubicacion)
        )

    # --- HELPER PARA NO ROMPER EL FRONTEND ---
    def _map_to_read(self, db_obj: Equipo) -> Equipo:
        """Inyecta el nombre de la ubicación en una propiedad virtual para el Schema Read"""
        if db_obj and db_obj.ubicacion:
            setattr(db_obj, 'ubicacion_actual', db_obj.ubicacion.nombre)
        elif db_obj:
             setattr(db_obj, 'ubicacion_actual', None)
        return db_obj

    def get(self, db: Session, id: Any) -> Optional[Equipo]:
        statement = select(self.model).where(self.model.id == id)
        statement = self._apply_load_options_for_equipo(statement)
        result = db.execute(statement).scalar_one_or_none()
        return self._map_to_read(result) if result else None

    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Equipo]:
        statement = select(self.model).order_by(self.model.nombre).offset(skip).limit(limit)
        statement = self._apply_load_options_for_equipo(statement)
        results = list(db.execute(statement).scalars().all())
        return [self._map_to_read(r) for r in results]

    def get_by_serie(self, db: Session, *, numero_serie: str) -> Optional[Equipo]:
        statement = select(self.model).where(self.model.numero_serie == numero_serie)
        statement = self._apply_load_options_for_equipo(statement)
        result = db.execute(statement).scalar_one_or_none()
        return self._map_to_read(result) if result else None

    def get_by_codigo_interno(self, db: Session, *, codigo_interno: str) -> Optional[Equipo]:
        if not codigo_interno:
            return None
        statement = select(self.model).where(self.model.codigo_interno == codigo_interno)
        statement = self._apply_load_options_for_equipo(statement)
        result = db.execute(statement).scalar_one_or_none()
        return self._map_to_read(result) if result else None

    def _validate_numero_serie_format(self, numero_serie: str):
        if not re.match(SERIAL_NUMBER_REGEX_DB_FORMAT, numero_serie):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"El formato del número de serie '{numero_serie}' no es válido."
            )

    def create(self, db: Session, *, obj_in: EquipoCreate) -> Equipo:
        self._validate_numero_serie_format(obj_in.numero_serie)

        if self.get_by_serie(db, numero_serie=obj_in.numero_serie):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Número de serie ya registrado.")
        
        if obj_in.codigo_interno and self.get_by_codigo_interno(db, codigo_interno=obj_in.codigo_interno):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Código interno ya registrado.")

        if not estado_equipo_service.get(db, id=obj_in.estado_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estado de equipo no encontrado.")

        if obj_in.proveedor_id and not proveedor_service.get(db, id=obj_in.proveedor_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado.")
            
        if obj_in.ubicacion_id and not ubicacion_service.get(db, id=obj_in.ubicacion_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ubicación no encontrada.")

        db_obj = super().create(db, obj_in=obj_in)
        return self._map_to_read(db_obj)

    def update(self, db: Session, *, db_obj: Equipo, obj_in: Union[EquipoUpdate, Dict[str, Any]]) -> Equipo:
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        equipo_id = db_obj.id

        if "numero_serie" in update_data and update_data["numero_serie"] != db_obj.numero_serie:
            self._validate_numero_serie_format(update_data["numero_serie"])
            existing = self.get_by_serie(db, numero_serie=update_data["numero_serie"])
            if existing and existing.id != equipo_id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Número de serie ya registrado.")
        
        if "codigo_interno" in update_data and update_data["codigo_interno"] != db_obj.codigo_interno:
            if update_data["codigo_interno"]:
                existing = self.get_by_codigo_interno(db, codigo_interno=update_data["codigo_interno"])
                if existing and existing.id != equipo_id:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Código interno ya registrado.")

        if "estado_id" in update_data and update_data["estado_id"] != db_obj.estado_id:
             if not estado_equipo_service.get(db, id=update_data["estado_id"]):
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estado de equipo no encontrado.")

        if "proveedor_id" in update_data and update_data["proveedor_id"] != db_obj.proveedor_id:
            if update_data["proveedor_id"] is not None and not proveedor_service.get(db, id=update_data["proveedor_id"]):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado.")
                
        if "ubicacion_id" in update_data and update_data["ubicacion_id"] != db_obj.ubicacion_id:
            if update_data["ubicacion_id"] is not None and not ubicacion_service.get(db, id=update_data["ubicacion_id"]):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ubicación no encontrada.")

        updated_obj = super().update(db, db_obj=db_obj, obj_in=update_data)
        return self._map_to_read(updated_obj)

    def search(self, db: Session, *, termino: str) -> List[EquipoSearchResult]:
        if not termino or not termino.strip():
            return []
        stmt = text("SELECT * FROM control_equipos.buscar_equipos(:termino)")
        result = db.execute(stmt, {"termino": termino})
        return [EquipoSearchResult.model_validate(row._asdict()) for row in result]

    def search_global(self, db: Session, *, termino: str) -> List[GlobalSearchResult]:
        if not termino or not termino.strip():
            return []
        stmt = text("SELECT * FROM control_equipos.busqueda_global(:termino)")
        result = db.execute(stmt, {"termino": termino})
        return [GlobalSearchResult.model_validate(row._asdict()) for row in result]

    def bulk_upload_from_csv(self, db: Session, csv_content: str) -> dict:
        reader = csv.DictReader(io.StringIO(csv_content))
        
        estados = db.query(EstadoEquipo).all()
        estado_map = {e.nombre.strip().lower(): e.id for e in estados}
        estado_disponible_id = estado_map.get('disponible', estados[0].id if estados else None)

        proveedores = db.query(Proveedor).all()
        proveedor_map = {p.nombre.strip().lower(): p.id for p in proveedores}
        
        ubicaciones = db.query(Ubicacion).all()
        ubicacion_map = {u.nombre.strip().lower(): u.id for u in ubicaciones}

        resultados = {"total_procesados": 0, "insertados": 0, "errores": []}

        for i, row in enumerate(reader, start=2): 
            resultados["total_procesados"] += 1
            numero_serie = ""
            
            try:
                nombre = row.get("nombre", "").strip()
                numero_serie = row.get("numero_serie", "").strip()
                
                if not nombre or not numero_serie:
                    resultados["errores"].append(f"Fila {i}: Faltan campos obligatorios (nombre, numero_serie).")
                    continue

                estado_str = row.get("estado", "").strip().lower()
                estado_id = estado_map.get(estado_str, estado_disponible_id)

                proveedor_str = row.get("proveedor", "").strip().lower()
                proveedor_id = proveedor_map.get(proveedor_str) if proveedor_str else None
                
                ubicacion_str = row.get("ubicacion_actual", "").strip().lower()
                ubicacion_id = ubicacion_map.get(ubicacion_str) if ubicacion_str else None

                nuevo_equipo = Equipo(
                    nombre=nombre,
                    numero_serie=numero_serie,
                    ubicacion_id=ubicacion_id,
                    marca=row.get("marca", "").strip() or None,
                    modelo=row.get("modelo", "").strip() or None,
                    estado_id=estado_id,
                    proveedor_id=proveedor_id
                )

                with db.begin_nested():
                    db.add(nuevo_equipo)
                    db.flush() 
                    
                resultados["insertados"] += 1

            except IntegrityError as e:
                resultados["errores"].append(f"Fila {i}: Número de serie '{numero_serie}' ya registrado o inválido.")
            except Exception as e:
                resultados["errores"].append(f"Fila {i}: Error inesperado - {str(e)}")

        return resultados

equipo_service = EquipoService(Equipo)
