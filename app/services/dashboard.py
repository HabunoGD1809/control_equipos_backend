import logging
from typing import List
from datetime import datetime, timedelta, date, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, func as sql_func, text

from app.schemas.dashboard import DashboardData, EquipoPorEstado, MovimientoReciente
from app.models.equipo import Equipo
from app.models.mantenimiento import Mantenimiento
from app.models.licencia_software import LicenciaSoftware
from app.models.tipo_item_inventario import TipoItemInventario
from app.models.inventario_stock import InventarioStock
from app.models.estado_equipo import EstadoEquipo
from app.models.tipo_mantenimiento import TipoMantenimiento

from app.models.reserva_equipo import ReservaEquipo
from app.models.documentacion import Documentacion
from app.models.movimiento import Movimiento
from app.models.usuario import Usuario

from .equipo import equipo_service

logger = logging.getLogger(__name__)

class DashboardService:
    def get_summary(self, db: Session) -> DashboardData:
        logger.info("Obteniendo resumen de datos para el dashboard.")

        total_equipos = equipo_service.get_count(db)

        equipos_estado_list: List[EquipoPorEstado] = []
        try:
            stmt_view = text("SELECT estado_id, estado_nombre, cantidad_equipos, estado_color FROM control_equipos.mv_equipos_estado ORDER BY estado_nombre")
            result_view = db.execute(stmt_view)
            equipos_estado_list = [EquipoPorEstado(**row._mapping) for row in result_view] # type: ignore
        except Exception as e_view:
            logger.warning(f"No se pudo usar la vista materializada 'mv_equipos_estado'. Calculando dinámicamente...")
            stmt_query = (
                select(
                    EstadoEquipo.id.label("estado_id"),
                    EstadoEquipo.nombre.label("estado_nombre"),
                    sql_func.count(Equipo.id).label("cantidad_equipos"),
                    EstadoEquipo.color_hex.label("estado_color")
                )
                .outerjoin(Equipo, EstadoEquipo.id == Equipo.estado_id)
                .group_by(EstadoEquipo.id, EstadoEquipo.nombre, EstadoEquipo.color_hex)
                .order_by(EstadoEquipo.nombre)
            )
            result_query = db.execute(stmt_query)
            equipos_estado_list = [EquipoPorEstado(**row._mapping) for row in result_query] # type: ignore

        fecha_limite_mant = datetime.now(timezone.utc) + timedelta(days=30)
        stmt_mant_count = (
            select(sql_func.count(Mantenimiento.id))
            .join(Mantenimiento.tipo_mantenimiento) # type: ignore[attr-defined]
             .where(
                Mantenimiento.estado.in_(['Programado', 'Pendiente Aprobacion', 'Requiere Piezas', 'Pausado']),
                sql_func.coalesce(Mantenimiento.fecha_proximo_mantenimiento, Mantenimiento.fecha_programada) <= fecha_limite_mant,
                (
                    (TipoMantenimiento.es_preventivo == True) | (Mantenimiento.fecha_proximo_mantenimiento != None)
                )
            )
        )
        mantenimientos_proximos_count = db.execute(stmt_mant_count).scalar_one_or_none() or 0

        hoy_lic = date.today()
        fecha_limite_lic = hoy_lic + timedelta(days=30)
        stmt_lic_count = select(sql_func.count(LicenciaSoftware.id)).where(
            LicenciaSoftware.fecha_expiracion != None,
            LicenciaSoftware.fecha_expiracion >= hoy_lic,
            LicenciaSoftware.fecha_expiracion <= fecha_limite_lic
        )
        licencias_por_expirar_count = db.execute(stmt_lic_count).scalar_one_or_none() or 0

        subquery_stock = (
            select(
                InventarioStock.tipo_item_id,
                sql_func.sum(InventarioStock.cantidad_actual).label("stock_total")
            )
            .group_by(InventarioStock.tipo_item_id)
            .subquery('sq_stock_total_por_item')
        )
        stmt_low_stock_count = (
            select(sql_func.count(TipoItemInventario.id))
            .join(subquery_stock, TipoItemInventario.id == subquery_stock.c.tipo_item_id)
            .where(subquery_stock.c.stock_total <= TipoItemInventario.stock_minimo)
        )
        items_bajo_stock_count = db.execute(stmt_low_stock_count).scalar_one_or_none() or 0
        
        # 1. Reservas Pendientes
        stmt_reservas = select(sql_func.count(ReservaEquipo.id)).where(ReservaEquipo.estado == 'Pendiente Aprobacion')
        reservas_pendientes_count = db.execute(stmt_reservas).scalar_one_or_none() or 0

        # 2. Documentos Pendientes de Verificación
        stmt_docs = select(sql_func.count(Documentacion.id)).where(Documentacion.estado == 'Pendiente')
        documentos_pendientes_count = db.execute(stmt_docs).scalar_one_or_none() or 0

        # 3. Movimientos Recientes (Últimos 5)
        stmt_movs = (
            select(
                Movimiento.id,
                Equipo.nombre.label("equipo_nombre"),
                Movimiento.tipo_movimiento,
                Movimiento.fecha_hora,
                Usuario.nombre_usuario.label("usuario_nombre")
            )
            .join(Equipo, Movimiento.equipo_id == Equipo.id)
            .outerjoin(Usuario, Movimiento.usuario_id == Usuario.id)
            .order_by(Movimiento.fecha_hora.desc())
            .limit(5)
        )
        result_movs = db.execute(stmt_movs)
        movimientos_recientes = [MovimientoReciente(**row._mapping) for row in result_movs] # type: ignore

        stmt_valor_activos = select(sql_func.sum(Equipo.valor_adquisicion))
        total_valor_calc = db.execute(stmt_valor_activos).scalar_one_or_none() or 0

        # --- CONSTRUCCIÓN DE LA RESPUESTA ---
        dashboard_data = DashboardData(
            total_equipos=total_equipos,
            total_valor_activos=float(total_valor_calc), # 👇 Agregado aquí
            equipos_por_estado=equipos_estado_list,
            mantenimientos_proximos_count=mantenimientos_proximos_count,
            licencias_por_expirar_count=licencias_por_expirar_count,
            items_bajo_stock_count=items_bajo_stock_count,
            reservas_pendientes_count=reservas_pendientes_count,
            documentos_pendientes_count=documentos_pendientes_count,
            movimientos_recientes=movimientos_recientes
        )
        
        logger.info("Resumen de dashboard engordado generado exitosamente.")
        return dashboard_data

dashboard_service = DashboardService()
