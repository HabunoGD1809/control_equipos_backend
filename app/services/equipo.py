import logging
import csv
import io
import json
import re
from itertools import islice
from datetime import datetime
from typing import Optional, List, Union, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, text, or_, Text
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.models.equipo import Equipo
from app.models.estado_equipo import EstadoEquipo
from app.models.proveedor import Proveedor
from app.models.ubicacion import Ubicacion
from app.models.marca import Marca
from app.models.movimiento import Movimiento
from app.models.reserva_equipo import ReservaEquipo
from app.models.documentacion import Documentacion
from app.models.mantenimiento import Mantenimiento
from app.models.asignacion_licencia import AsignacionLicencia
from app.models.equipo_componente import EquipoComponente
from app.schemas.equipo import EquipoCreate, EquipoUpdate, EquipoSearchResult, GlobalSearchResult
from app.services.ubicacion import ubicacion_service

from .base_service import BaseService
from .asset_custody import lock_topology
from .estado_equipo import estado_equipo_service
from .proveedor import proveedor_service

logger = logging.getLogger(__name__)
SERIAL_NUMBER_REGEX_DB_FORMAT = r"^[A-Za-z0-9][A-Za-z0-9._/ :+\-]{0,99}$"

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

    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100, q=None, estado_id=None, proveedor_id=None, ubicacion_id=None, ubicacion_actual=None) -> List[Equipo]:
        statement = select(self.model)
        if q and q.strip():
            pattern = '%' + q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
            statement = statement.where(or_(self.model.nombre.ilike(pattern), self.model.numero_serie.ilike(pattern), self.model.codigo_interno.ilike(pattern), self.model.modelo.ilike(pattern), self.model.tipo_activo.ilike(pattern), self.model.especificaciones_tecnicas.cast(Text).ilike(pattern)))
        for field, value in [(self.model.estado_id, estado_id), (self.model.proveedor_id, proveedor_id), (self.model.ubicacion_id, ubicacion_id)]:
            if value: statement = statement.where(field == value)
        if ubicacion_actual:
            try: statement = statement.where(self.model.ubicacion_id == UUID(ubicacion_actual))
            except ValueError:
                statement = statement.join(self.model.ubicacion).where(Ubicacion.nombre.ilike('%' + ubicacion_actual.replace('%', '\\%').replace('_', '\\_') + '%'))
        statement = statement.order_by(self.model.nombre, self.model.id).offset(skip).limit(limit)
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
        if not re.fullmatch(SERIAL_NUMBER_REGEX_DB_FORMAT, numero_serie):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
        lock_topology(db)
        db.query(Equipo).filter(Equipo.id == equipo_id).with_for_update().populate_existing().one()
        if "empleado_asignado_id" in update_data and update_data["empleado_asignado_id"] != db_obj.empleado_asignado_id:
            raise HTTPException(409, "Asigna o libera el custodio mediante Movimientos para conservar la trazabilidad de la entrega.")
        custody_changes = any(key in update_data and update_data[key] != getattr(db_obj, key) for key in ["estado_id", "ubicacion_id", "empleado_asignado_id"])
        linked_component = db.scalar(select(EquipoComponente.id).where((EquipoComponente.equipo_padre_id == equipo_id) | (EquipoComponente.equipo_componente_id == equipo_id)).limit(1))
        grouped_history = db.scalar(select(Movimiento.id).where(Movimiento.componentes_origen.has_key(str(equipo_id))).limit(1))
        if custody_changes and (linked_component or grouped_history or db_obj.empleado_asignado_id or db.scalar(select(Movimiento.id).where(Movimiento.equipo_id == equipo_id).limit(1)) or db.scalar(select(ReservaEquipo.id).where(ReservaEquipo.equipo_id == equipo_id, ReservaEquipo.estado == "En Curso").limit(1))):
            raise HTTPException(409, "Registre un movimiento o una devolución para cambiar la custodia, ubicación o estado de este activo.")

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

    def remove(self, db: Session, *, id):
        lock_topology(db)
        equipo = self.get_or_404(db, id=id)
        if db.scalar(select(Movimiento.id).where(Movimiento.componentes_origen.has_key(str(id))).limit(1)):
            raise HTTPException(409, "Este activo tiene movimientos como componente. Registre una baja para conservar su historial.")
        if equipo.empleado_asignado_id:
            raise HTTPException(409, "El equipo tiene un custodio asignado. Registre su devolución o baja.")
        for model in [Movimiento, ReservaEquipo, Documentacion, Mantenimiento, AsignacionLicencia]:
            if db.scalar(select(model.id).where(model.equipo_id == id).limit(1)):
                raise HTTPException(409, "El equipo tiene historial. Registre una baja para conservar la trazabilidad.")
        if db.scalar(select(EquipoComponente.id).where((EquipoComponente.equipo_padre_id == id) | (EquipoComponente.equipo_componente_id == id)).limit(1)):
            raise HTTPException(409, "Desvincule los componentes del activo antes de eliminarlo.")
        return super().remove(db, id=id)

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
        csv_content = csv_content.lstrip('\ufeff')
        header = csv_content.splitlines()[0] if csv_content.strip() else ''
        reader = csv.DictReader(io.StringIO(csv_content), delimiter=';' if header.count(';') > header.count(',') else ',', strict=True)
        try:
            fields = [name.strip().lower() for name in (reader.fieldnames or [])]
        except csv.Error:
            raise HTTPException(400, 'El encabezado del CSV no tiene un formato válido.')
        supported = {'nombre', 'numero_serie', 'estado', 'proveedor', 'ubicacion_actual', 'marca', 'modelo', 'tipo_activo', 'codigo_interno', 'fecha_adquisicion', 'fecha_puesta_marcha', 'fecha_garantia_expiracion', 'valor_adquisicion', 'centro_costo', 'notas', 'especificaciones_tecnicas'}
        if not {'nombre', 'numero_serie'}.issubset(fields):
            raise HTTPException(400, 'El CSV debe contener las columnas nombre y numero_serie.')
        if len(fields) != len(set(fields)):
            raise HTTPException(400, 'El CSV contiene columnas repetidas.')
        unknown = [field for field in fields if field not in supported and not field.startswith('tecnico.')]
        if unknown:
            raise HTTPException(400, 'Columnas no admitidas: ' + ', '.join(unknown) + '. La asignación de custodios se registra desde Movimientos.')
        reader.fieldnames = fields
        try:
            rows = list(islice(reader, 5001))
        except csv.Error:
            raise HTTPException(400, 'El CSV contiene comillas o campos inválidos; revise el formato del archivo.')
        if not rows:
            raise HTTPException(400, 'El CSV no contiene filas para importar.')
        if len(rows) > 5000:
            raise HTTPException(400, 'Cada archivo admite hasta 5000 equipos. Divida el inventario en varios archivos.')
        
        estados = db.query(EstadoEquipo).all()
        estado_map = {e.nombre.strip().lower(): e.id for e in estados}
        from app.core.equipment_states import EquipmentStateCode
        estado_disponible_id = next((state.id for state in estados if state.codigo == EquipmentStateCode.AVAILABLE), None)

        proveedores = db.query(Proveedor).all()
        proveedor_map = {p.nombre.strip().lower(): p.id for p in proveedores}
        
        ubicaciones = db.query(Ubicacion).all()
        ubicacion_map = {u.nombre.strip().lower(): u.id for u in ubicaciones}

        marcas = {m.nombre.strip().lower(): m.id for m in db.scalars(select(Marca))}
        resultados = {"total_procesados": 0, "insertados": 0, "errores": []}

        for i, row in enumerate(rows, start=2):
            resultados["total_procesados"] += 1
            numero_serie = ""
            
            try:
                if None in row or any(value is None for value in row.values()):
                    raise HTTPException(422, 'La cantidad de celdas no coincide con el encabezado.')
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

                for supplied, mapping, label in [(estado_str,estado_map,"estado"),(proveedor_str,proveedor_map,"proveedor"),(ubicacion_str,ubicacion_map,"ubicación"),(row.get("marca", "").strip().lower(),marcas,"marca")]:
                    if supplied and supplied not in mapping:
                        raise HTTPException(422, f"El catálogo de {label} no contiene '{supplied}'.")
                technical = json.loads(row.get('especificaciones_tecnicas', '').strip() or '{}')
                if not isinstance(technical, dict):
                    raise HTTPException(422, 'La ficha técnica debe ser un objeto de campos y valores de texto.')
                for key, value in row.items():
                    if key.startswith('tecnico.') and value.strip():
                        name = key.removeprefix('tecnico.').strip()
                        if name in technical:
                            raise HTTPException(422, f'El campo técnico {name} aparece dos veces.')
                        technical[name] = value.strip()
                extra = {key: row[key].strip() for key in ('tipo_activo', 'codigo_interno', 'fecha_adquisicion', 'fecha_puesta_marcha', 'fecha_garantia_expiracion', 'valor_adquisicion', 'centro_costo', 'notas') if row.get(key, '').strip()}
                equipment_in = EquipoCreate(**extra, nombre=nombre, numero_serie=numero_serie, ubicacion_id=ubicacion_id, marca_id=marcas.get(row.get('marca', '').strip().lower()), modelo=row.get('modelo', '').strip() or None, estado_id=estado_id, proveedor_id=proveedor_id, especificaciones_tecnicas=technical)

                with db.begin_nested():
                    self.create(db, obj_in=equipment_in)
                    db.flush() 
                    
                resultados["insertados"] += 1

            except IntegrityError as e:
                resultados["errores"].append(f"Fila {i}: Número de serie '{numero_serie}' ya registrado o inválido.")
            except HTTPException as e:
                resultados["errores"].append(f"Fila {i}: {e.detail}")
            except ValidationError as e:
                details = '; '.join('.'.join(map(str, error['loc'])) + ': ' + error['msg'] for error in e.errors())
                resultados['errores'].append(f'Fila {i}: {details}')
            except json.JSONDecodeError:
                resultados['errores'].append(f'Fila {i}: especificaciones_tecnicas debe contener JSON válido.')
            except Exception:
                logger.exception("Error en la fila %s de la importación", i)
                resultados["errores"].append(f"Fila {i}: Datos inválidos; revise los campos y catálogos.")

        return resultados

equipo_service = EquipoService(Equipo)
