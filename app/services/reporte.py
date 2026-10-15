from datetime import date, datetime, time, timedelta, timezone
from sqlalchemy import select, func, case, union_all
from sqlalchemy.orm import Session, selectinload, raiseload
from app.models import Equipo, Mantenimiento, Movimiento, AuditLog, InventarioMovimiento, InventarioStock, TipoItemInventario, Ubicacion, LicenciaSoftware, Usuario

MAX_ROWS = 50000

def label(obj, attribute="nombre"):
    return getattr(obj, attribute, "") if obj else ""

class ReporteService:
    def _range(self, statement, column, start, end):
        if start:
            statement = statement.where(column >= datetime.combine(start,time.min,tzinfo=timezone.utc))
        if end:
            statement = statement.where(column < datetime.combine(end+timedelta(days=1),time.min,tzinfo=timezone.utc))
        return statement

    def _rows(self, db, statement):
        rows=list(db.scalars(statement.limit(MAX_ROWS+1)).unique())
        if len(rows)>MAX_ROWS:
            raise ValueError("El reporte supera 50.000 registros. Seleccione un período más corto.")
        return rows

    def obtener_datos(self, db: Session, tipo_reporte: str, fecha_inicio: date | None, fecha_fin: date | None):
        start,end=fecha_inicio,fecha_fin
        if start and end and start>end:
            raise ValueError("La fecha inicial debe ser anterior o igual a la final.")
        if tipo_reporte=="equipos":
            stmt=self._range(select(Equipo).options(raiseload("*"),selectinload(Equipo.estado),selectinload(Equipo.ubicacion),selectinload(Equipo.marca_rel),selectinload(Equipo.empleado_asignado)).order_by(Equipo.nombre),Equipo.created_at,start,end)
            return [{"Código": e.codigo_interno or "Sin código", "Equipo":e.nombre,"Tipo":e.tipo_activo,"Serie":e.numero_serie,"Marca":label(e.marca_rel),"Modelo":e.modelo,"Estado":label(e.estado),"Ubicación":label(e.ubicacion),"Custodio":label(e.empleado_asignado,"nombre_completo"),"Ficha técnica":"; ".join(f"{key.replace('_', ' ')}: {value}" for key,value in (e.especificaciones_tecnicas or {}).items())} for e in self._rows(db,stmt)]
        if tipo_reporte=="mantenimientos":
            stmt=self._range(select(Mantenimiento).options(raiseload("*"),selectinload(Mantenimiento.equipo),selectinload(Mantenimiento.tecnico),selectinload(Mantenimiento.tipo_mantenimiento)).order_by(Mantenimiento.fecha_programada),func.coalesce(Mantenimiento.fecha_programada,Mantenimiento.created_at),start,end)
            return [{"Equipo":label(m.equipo),"Tipo":label(m.tipo_mantenimiento),"Programado":m.fecha_programada,"Inicio":m.fecha_inicio,"Finalización":m.fecha_finalizacion,"Técnico":label(m.tecnico,"nombre_completo"),"Costo estimado":m.costo_estimado,"Costo real":m.costo_real,"Estado":m.estado} for m in self._rows(db,stmt)]
        if tipo_reporte=="movimientos":
            stmt=self._range(select(Movimiento).options(raiseload("*"),selectinload(Movimiento.equipo),selectinload(Movimiento.usuario_registrador),selectinload(Movimiento.usuario_autorizador),selectinload(Movimiento.usuario_confirmador),selectinload(Movimiento.ubicacion_origen),selectinload(Movimiento.ubicacion_destino),selectinload(Movimiento.empleado_destino)).order_by(Movimiento.fecha_hora),Movimiento.fecha_hora,start,end)
            return [{"Equipo":label(m.equipo),"Serie":m.equipo.numero_serie,"Activos incluidos":1+len(m.componentes_origen or {}),"Tipo":m.tipo_movimiento,"Fecha":m.fecha_hora,"Origen":label(m.ubicacion_origen),"Destino":label(m.ubicacion_destino),"Custodio":label(m.empleado_destino,"nombre_completo"),"Retorno previsto":m.fecha_prevista_retorno,"Devuelto":m.fecha_retorno,"Estado":m.estado,"Registrado por":label(m.usuario_registrador,"nombre_usuario"),"Autorizado por":label(m.usuario_autorizador,"nombre_usuario"),"Recibió":m.recibido_por,"Entidad externa":m.entidad_receptora,"Registró acuse":label(m.usuario_confirmador,"nombre_usuario"),"Fecha de acuse":m.fecha_recepcion} for m in self._rows(db,stmt)]
        if tipo_reporte=="auditoria":
            stmt=self._range(select(AuditLog, Usuario.nombre_usuario).outerjoin(Usuario, AuditLog.app_user_id == Usuario.id).order_by(AuditLog.audit_timestamp.desc(), AuditLog.id.desc()),AuditLog.audit_timestamp,start,end)
            records = list(db.execute(stmt.limit(MAX_ROWS + 1)))
            if len(records) > MAX_ROWS:
                raise ValueError("El reporte supera 50.000 registros. Seleccione un período más corto.")
            return [{"Fecha":log.audit_timestamp,"Tabla":log.table_name,"Operación":log.operation,"Usuario":username or log.username or "Sistema"} for log, username in records]
        if tipo_reporte=="licencias":
            stmt=select(LicenciaSoftware).options(raiseload("*"),selectinload(LicenciaSoftware.software_info),selectinload(LicenciaSoftware.proveedor)).order_by(LicenciaSoftware.fecha_adquisicion)
            if start: stmt=stmt.where(LicenciaSoftware.fecha_adquisicion>=start)
            if end: stmt=stmt.where(LicenciaSoftware.fecha_adquisicion<=end)
            return [{"Software":label(l.software_info),"Adquirida":l.fecha_adquisicion,"Expira":l.fecha_expiracion,"Total":l.cantidad_total,"Disponibles":l.cantidad_disponible,"Asignadas":l.cantidad_total-l.cantidad_disponible,"Proveedor":label(l.proveedor),"Costo":l.costo_adquisicion} for l in self._rows(db,stmt)]
        if tipo_reporte=="inventario":
            return self._inventario(db,end)
        if tipo_reporte=="kardex":
            return self._kardex(db,start,end)
        raise ValueError("Tipo de reporte no soportado.")

    def _movements(self,db,start,end):
        stmt=self._range(select(InventarioMovimiento).options(raiseload("*"),selectinload(InventarioMovimiento.tipo_item),selectinload(InventarioMovimiento.origen),selectinload(InventarioMovimiento.destino),selectinload(InventarioMovimiento.usuario_registrador)).order_by(InventarioMovimiento.fecha_hora,InventarioMovimiento.id),InventarioMovimiento.fecha_hora,None,end)
        return self._rows(db,stmt)

    def _kardex(self,db,start,end):
        balances={}; output=[]
        for m in self._movements(db,start,end):
            inbound=m.tipo_movimiento in {"Entrada Compra","Entrada Abastecimiento","Ajuste Positivo","Transferencia Entrada","Devolucion Interna"}
            location=m.destino if inbound else m.origen
            batch=(m.lote_destino if inbound else m.lote_origen) or "N/A"
            key=(m.tipo_item_id, location.id if location else None, batch)
            balances[key]=balances.get(key,0)+(m.cantidad if inbound else -m.cantidad)
            if start and m.fecha_hora.date()<start: continue
            output.append({"Fecha":m.fecha_hora,"Ítem":label(m.tipo_item),"SKU":m.tipo_item.sku,"Color":m.tipo_item.color,"Ubicación":label(location),"Lote":batch,"Movimiento":m.tipo_movimiento,"Entrada":m.cantidad if inbound else 0,"Salida":0 if inbound else m.cantidad,"Saldo":balances[key],"Registrado por":label(m.usuario_registrador,"nombre_usuario"),"Procedencia":m.procedencia,"Entregado por":m.entregado_por,"Referencia":m.referencia_externa})
        return output

    def _inventario(self,db,end):
        # Historical balances at the selected closing date, including preceding entries.
        balances={}; details={}
        for m in self._movements(db,None,end):
            inbound=m.tipo_movimiento in {"Entrada Compra","Entrada Abastecimiento","Ajuste Positivo","Transferencia Entrada","Devolucion Interna"}
            location=m.destino if inbound else m.origen
            batch=(m.lote_destino if inbound else m.lote_origen) or "N/A"
            key=(m.tipo_item_id,location.id if location else None,batch)
            balances[key]=balances.get(key,0)+(m.cantidad if inbound else -m.cantidad)
            details[key]=(m.tipo_item,location,batch)
        rows=[]
        for key,quantity in balances.items():
            item,location,batch=details[key]
            rows.append({"Ítem":item.nombre,"SKU":item.sku,"Color":item.color,"Tecnología":item.tecnologia,"Modelos compatibles":", ".join(item.modelos_equipo_compatibles or []),"Ubicación":label(location),"Lote":batch,"Existencias":quantity,"Stock mínimo":item.stock_minimo,"Unidad":item.unidad_medida})
        return sorted(rows,key=lambda row:(row["Ítem"],row["Ubicación"],row["Lote"]))

reporte_service=ReporteService()
