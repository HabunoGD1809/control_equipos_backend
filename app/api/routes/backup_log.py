import logging
import subprocess
import os
from typing import Any, List, Optional
from uuid import UUID as PyUUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.backup_log import BackupLog as BackupLogSchema
from app.services.backup_log import backup_log_service
from app.models.usuario import Usuario as UsuarioModel
from app.models.backup_log import BackupLog as BackupLogModel

from app.core import permissions as perms
from app.core.config import settings
from app.db.session import SessionLocal # Importante para la tarea en background

logger = logging.getLogger(__name__)

router = APIRouter()

def run_backup_script(user_name: str):
    """
    Ejecuta el backup real utilizando pg_dump mediante subprocess.
    Utiliza su propia sesión de BD porque se ejecuta en background.
    """
    db_bg: Optional[Session] = None
    try:
        db_bg = SessionLocal()
        logger.info(f"Iniciando backup manual solicitado por {user_name}")
        
        # 1. Preparar el directorio de backups
        backup_dir = "backups" 
        os.makedirs(backup_dir, exist_ok=True)
        
        # 2. Generar nombre de archivo único
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"db_backup_{timestamp}.backup"
        backup_file_path = os.path.join(backup_dir, backup_filename)
        
        # 3. Construir el comando pg_dump usando las propiedades de config.py
        command = [
            "pg_dump", 
            "-h", settings.POSTGRES_SERVER,
            "-p", str(settings.POSTGRES_PORT),
            "-U", settings.POSTGRES_USER,
            "-F", "c", # Formato custom (comprimido, ideal para restaurar con pg_restore)
            "-f", backup_file_path,
            settings.POSTGRES_DB
        ]
        
        # 4. Pasar la contraseña de forma segura mediante variables de entorno
        env = os.environ.copy()
        env["PGPASSWORD"] = settings.POSTGRES_PASSWORD
        
        # 5. Ejecutar el comando en el sistema operativo
        result = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
        
        # 6. Registrar el éxito en la base de datos
        nuevo_log = BackupLogModel(
            backup_status="Completado",
            backup_type="Manual DB",
            file_path=backup_file_path,
            notes=f"Ejecutado por: {user_name}"
        )
        db_bg.add(nuevo_log)
        db_bg.commit()
        logger.info(f"Backup completado exitosamente y guardado en {backup_file_path}.")

    except subprocess.CalledProcessError as e:
        logger.error(f"Error en pg_dump durante el backup manual: {e.stderr}")
        if db_bg:
            db_bg.rollback()
            log_fallido = BackupLogModel(
                backup_status="Fallido",
                backup_type="Manual DB",
                error_message=e.stderr[:500], 
                notes=f"Intento fallido de {user_name}"
            )
            db_bg.add(log_fallido)
            db_bg.commit()
            
    except Exception as e:
        logger.error(f"Error inesperado al ejecutar backup manual: {e}", exc_info=True)
        if db_bg:
            db_bg.rollback()
            log_fallido = BackupLogModel(
                backup_status="Fallido",
                backup_type="Manual DB",
                error_message=str(e)[:500],
                notes=f"Error inesperado. Intento fallido de {user_name}"
            )
            db_bg.add(log_fallido)
            db_bg.commit()
            
    finally:
        if db_bg:
            db_bg.close()

@router.post("/",
             response_model=dict,
             dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_SISTEMA]))],
             summary="Ejecutar Backup Manual",
             response_description="Confirmación del inicio del backup.")
def trigger_manual_backup(
    background_tasks: BackgroundTasks,
    current_user: UsuarioModel = Depends(deps.get_current_active_user)
) -> dict:
    """
    Inicia un proceso de copia de seguridad manual de la base de datos en segundo plano.
    Solo accesible para administradores del sistema.
    """
    # Importante: Solo pasamos valores simples (strings, ints) a la tarea de fondo, 
    # nunca pasamos la instancia `db` ni el objeto completo `current_user`
    background_tasks.add_task(run_backup_script, user_name=current_user.nombre_usuario)
    
    return {"status": "ok", "msg": "El proceso de backup ha iniciado en segundo plano."}

@router.get("/",
            response_model=List[BackupLogSchema],
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_SISTEMA]))],
            summary="Consultar Logs de Backup",
            response_description="Una lista de registros de operaciones de backup.")
def read_backup_logs(
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    backup_status: Optional[str] = Query(None, description="Filtrar por estado"),
    backup_type: Optional[str] = Query(None, description="Filtrar por tipo"),
    start_time: Optional[datetime] = Query(None, description="Fecha/hora mínima"),
    end_time: Optional[datetime] = Query(None, description="Fecha/hora máxima"),
) -> Any:
    """
    Obtiene una lista de registros del log de backups, permitiendo aplicar filtros.
    """
    if start_time and end_time and end_time <= start_time:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La fecha de fin debe ser posterior a la fecha de inicio para el filtro.")

    try:
        logs = backup_log_service.get_multi(
            db,
            skip=skip,
            limit=limit,
            backup_status=backup_status,
            backup_type=backup_type,
            start_time=start_time,
            end_time=end_time
        )
        return logs
    except Exception as e:
        logger.error(f"Error inesperado al consultar logs de backup: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno.")

@router.get("/{log_id}",
            response_model=BackupLogSchema,
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_SISTEMA]))],
            summary="Obtener Log de Backup por ID")
def read_backup_log_by_id(
    log_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Obtiene un log de backup específico por su ID."""
    log = backup_log_service.get(db, id=log_id)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Log de backup con ID {log_id} no encontrado.")
    return log
