import logging
from typing import Any, List, Optional
from uuid import UUID as PyUUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from pathlib import Path
from fastapi.responses import FileResponse
from app.core.backup import create_system_backup, BACKUP_DIR, ROOT

from app.api import deps
from app.schemas.backup_log import BackupLog as BackupLogSchema
from app.services.backup_log import backup_log_service
from app.models.usuario import Usuario as UsuarioModel
from app.models.backup_log import BackupLog as BackupLogModel

from app.core import permissions as perms
from app.db.session import SessionLocal, engine

logger = logging.getLogger(__name__)

router = APIRouter()

def run_backup_script(user_name: str):
    started = datetime.now(timezone.utc)
    with SessionLocal() as db:
        log = BackupLogModel(backup_status="En Proceso", backup_type="Manual DB + archivos", notes=f"Solicitado por: {user_name}")
        db.add(log); db.commit(); db.refresh(log)
        lock_connection = engine.connect()
        locked = False
        try:
            locked = bool(lock_connection.execute(text("SELECT pg_try_advisory_lock(hashtext('control_equipos.manual_backup'))")).scalar())
            if not locked:
                log.backup_status = "Fallido"
                log.error_message = "Ya hay un respaldo en ejecución. Espere a que termine antes de volver a intentarlo."
                db.commit()
                return
            path = create_system_backup()
            log.backup_status = "Completado"
            log.file_path = str(path)
            log.duration = datetime.now(timezone.utc) - started
            db.commit()
        except Exception:
            logger.exception("Falló el respaldo manual")
            db.rollback()
            log.backup_status = "Fallido"
            log.error_message = "No se pudo crear el respaldo. Revise las herramientas de PostgreSQL, el espacio disponible y el registro del servidor."
            log.duration = datetime.now(timezone.utc) - started
            db.commit()

        finally:
            try:
                if locked:
                    lock_connection.execute(text("SELECT pg_advisory_unlock(hashtext('control_equipos.manual_backup'))"))
            finally:
                lock_connection.close()


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
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La fecha de fin debe ser posterior a la fecha de inicio para el filtro.")

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


@router.get("/{backup_id}/download", dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_SISTEMA]))])
def download_backup(backup_id: PyUUID, db: Session = Depends(deps.get_db), current_user: UsuarioModel = Depends(deps.get_current_active_user)):
    log = db.get(BackupLogModel, backup_id)
    if not log or log.backup_status not in {"Completado", "Success"} or not log.file_path:
        raise HTTPException(404, "El respaldo no está disponible.")
    path = Path(log.file_path)
    if not path.is_absolute(): path = ROOT / path
    path = path.resolve()
    if path.parent != BACKUP_DIR.resolve() or path.suffix.lower() not in {".zip", ".dump", ".backup"} or not path.is_file():
        raise HTTPException(404, "El archivo de respaldo no está disponible.")
    return FileResponse(path, filename=path.name, media_type="application/octet-stream", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
