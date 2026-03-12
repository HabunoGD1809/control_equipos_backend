import logging
from typing import Dict, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_

from app.worker import celery_app
from app.db.session import SessionLocal
from app.models.notificacion import Notificacion
from app.models.movimiento import Movimiento
from app.models.usuario import Usuario
from app.models.rol import Rol

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.send_email_notification")
def task_send_email_notification(recipient_email: str, subject: str, content: str) -> str:
    """
    Tarea Celery para enviar una notificación por correo electrónico.
    """
    logger.info(f"Iniciando tarea: Enviar email a {recipient_email}, Asunto: {subject}")
    try:
        print(f"--- SIMULACIÓN EMAIL ---")
        print(f"Para: {recipient_email}")
        print(f"Asunto: {subject}")
        print(f"Contenido: {content}")
        print(f"--- FIN SIMULACIÓN ---")
        logger.info(f"Tarea completada: Email (simulado) enviado a {recipient_email}.")
        return f"Email enviado a {recipient_email}"
    except Exception as e:
        logger.error(f"Error en tarea send_email_notification para {recipient_email}: {e}", exc_info=True)
        return f"Error al enviar email: {e}"


# --- PREVENCIÓN DE DESASTRES (ALERTAS AUTOMÁTICAS) ---
@celery_app.task(name="tasks.check_overdue_loans")
def task_check_overdue_loans() -> str:
    """
    Se ejecuta diariamente. Busca movimientos de 'Salida Temporal' 
    cuya fecha de retorno ya pasó y el equipo aún no se ha devuelto.
    Notifica a los administradores.
    """
    logger.info("Iniciando tarea: Revisión de Préstamos Vencidos")
    db = SessionLocal()
    
    try:
        ahora = datetime.now(timezone.utc)
        
        # 1. Buscar préstamos vencidos (En Uso / Pendiente y fecha pasada)
        statement = select(Movimiento).where(
            and_(
                Movimiento.tipo_movimiento == 'Salida Temporal',
                Movimiento.estado.in_(['En Proceso', 'Completado']),
                Movimiento.fecha_prevista_retorno < ahora,
                Movimiento.fecha_retorno.is_(None)
            )
        )
        prestamos_vencidos = db.execute(statement).scalars().all()
        
        if not prestamos_vencidos:
            logger.info("No se encontraron préstamos vencidos hoy.")
            return "No hay préstamos vencidos."

        # 2. Buscar a los administradores a quienes notificar
        admins = db.execute(
            select(Usuario).join(Rol).where(Rol.nombre == 'admin')
        ).scalars().all()
        
        # 3. Generar notificaciones
        for mov in prestamos_vencidos:
            if mov.fecha_prevista_retorno is None:
                logger.warning(f"Movimiento ID {mov.id} no tiene fecha_prevista_retorno, omitiendo.")
                continue

            dias_retraso = (ahora - mov.fecha_prevista_retorno).days
            mensaje = f"ALERTA: El equipo '{mov.equipo.nombre}' prestado a '{mov.destino}' tiene {dias_retraso} días de retraso."
            
            for admin in admins:
                # Verificamos si ya le enviamos esta alerta recientemente para no spammear
                ya_notificado = db.execute(
                    select(Notificacion).where(
                        and_(
                            Notificacion.usuario_id == admin.id,
                            Notificacion.referencia_id == mov.id,
                            Notificacion.created_at > (ahora - timedelta(days=1))
                        )
                    )
                ).scalar_one_or_none()
                
                if not ya_notificado:
                    notif = Notificacion(
                        usuario_id=admin.id,
                        mensaje=mensaje,
                        tipo="alerta",
                        urgencia=2,
                        referencia_id=mov.id,
                        referencia_tabla="movimientos"
                    )
                    db.add(notif)
                    
        db.commit()
        logger.info(f"Tarea completada: {len(prestamos_vencidos)} equipos vencidos notificados.")
        return f"Notificaciones generadas para {len(prestamos_vencidos)} equipos."
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error en tarea check_overdue_loans: {e}", exc_info=True)
        return f"Error: {e}"
    finally:
        db.close()
