import logging
from typing import List
from datetime import datetime, timedelta, date, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, func as sql_func, text

from app.schemas.dashboard import DashboardData, EquipoPorEstado
from app.models.equipo import Equipo
from app.models.mantenimiento import Mantenimiento
from app.models.licencia_software import LicenciaSoftware
from app.models.tipo_item_inventario import TipoItemInventario
from app.models.inventario_stock import InventarioStock
from app.models.estado_equipo import EstadoEquipo
from app.models.tipo_mantenimiento import TipoMantenimiento

from .equipo import equipo_service
# from .licencia_software import licencia_software_service
# from .mantenimiento import mantenimiento_service

logger = logging.getLogger(__name__)

class DashboardService:
    def get_summary(self, db: Session) -> DashboardData:
        logger.info("Obteniendo resumen de datos para el dashboard.")

        total_equipos = equipo_service.get_count(db)
        logger.debug(f"Total de equipos: {total_equipos}")

        equipos_estado_list: List[EquipoPorEstado] = []
        try:
            stmt_view = text("SELECT estado_id, estado_nombre, cantidad_equipos, estado_color FROM control_equipos.mv_equipos_estado ORDER BY estado_nombre")
            result_view = db.execute(stmt_view)
            equipos_estado_list = [EquipoPorEstado(**row._mapping) for row in result_view] # type: ignore
            logger.info("Equipos por estado obtenidos de la vista materializada.")
        except Exception as e_view:
            logger.warning(f"No se pudo usar la vista materializada 'mv_equipos_estado' ({e_view}). Calculando dinámicamente...")
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
            logger.info("Equipos por estado calculados dinámicamente.")
        logger.debug(f"Equipos por estado: {equipos_estado_list}")

        # Corrección aquí: datetime.now(timezone.utc)
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
        logger.debug(f"Mantenimientos próximos: {mantenimientos_proximos_count}")

        hoy_lic = date.today()
        fecha_limite_lic = hoy_lic + timedelta(days=30)
        stmt_lic_count = select(sql_func.count(LicenciaSoftware.id)).where(
            LicenciaSoftware.fecha_expiracion != None,
            LicenciaSoftware.fecha_expiracion >= hoy_lic,
            LicenciaSoftware.fecha_expiracion <= fecha_limite_lic
        )
        licencias_por_expirar_count = db.execute(stmt_lic_count).scalar_one_or_none() or 0
        logger.debug(f"Licencias por expirar: {licencias_por_expirar_count}")

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
        logger.debug(f"Items con bajo stock: {items_bajo_stock_count}")

        dashboard_data = DashboardData(
            total_equipos=total_equipos,
            equipos_por_estado=equipos_estado_list,
            mantenimientos_proximos_count=mantenimientos_proximos_count,
            licencias_por_expirar_count=licencias_por_expirar_count,
            items_bajo_stock_count=items_bajo_stock_count
        )
        logger.info("Resumen de dashboard generado exitosamente.")
        return dashboard_data

dashboard_service = DashboardService()
