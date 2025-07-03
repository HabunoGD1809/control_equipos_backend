import logging
import os
from pathlib import Path
from typing import Any, List, Optional
from uuid import UUID as PyUUID
import shutil

from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile, Form, Request 
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.api import deps
from app.schemas.documentacion import (
    Documentacion,
    DocumentacionCreateInternal,
    DocumentacionUpdate,
    DocumentacionVerify,
)
from app.schemas.common import Msg
from app.services.documentacion import documentacion_service
from app.models.usuario import Usuario as UsuarioModel
from app.core.storage import save_upload_file, delete_uploaded_file, UPLOAD_DIR # Import UPLOAD_DIR
from app.core.config import settings
from app.services.equipo import equipo_service

logger = logging.getLogger(__name__)
router = APIRouter()

PERM_SUBIR_DOCUMENTOS = "subir_documentos"
PERM_VER_DOCUMENTOS = "ver_documentos"
PERM_EDITAR_DOCUMENTOS = "editar_documentos"
PERM_VERIFICAR_DOCUMENTOS = "verificar_documentos"
PERM_ELIMINAR_DOCUMENTOS = "eliminar_documentos"


@router.post("/",
             response_model=Documentacion,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([PERM_SUBIR_DOCUMENTOS]))],
             summary="Subir Archivo y Crear registro de Documentación",
             response_description="El registro de documentación creado.")
async def create_documentacion_with_upload(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
    titulo: str = Form(...),
    tipo_documento_id: PyUUID = Form(...),
    descripcion: Optional[str] = Form(None),
    equipo_id: Optional[PyUUID] = Form(None),
    mantenimiento_id: Optional[PyUUID] = Form(None),
    licencia_id: Optional[PyUUID] = Form(None),
    file: UploadFile = File(..., description="Archivo a subir"),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' subiendo documento '{file.filename}' con título '{titulo}'.")
    
    # 1. Validar tamaño usando el header Content-Length ANTES de procesar
    content_length = request.headers.get('content-length')
    if content_length is None:
        raise HTTPException(
            status_code=status.HTTP_411_LENGTH_REQUIRED,
            detail="Header 'Content-Length' es requerido."
        )
    if int(content_length) > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El payload de la petición es demasiado grande. El límite es {settings.MAX_FILE_SIZE_BYTES // 1024 // 1024} MB."
        )
    
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo debe tener un nombre.")

    if equipo_id is None and mantenimiento_id is None and licencia_id is None:
        logger.warning("Intento de subir documento sin asociación a Equipo, Mantenimiento o Licencia.")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El documento debe estar asociado al menos a un Equipo, Mantenimiento o Licencia.")

    saved_file_info = None
    destination_path_for_log = None # Para logging en caso de error
    try:
        saved_file_info = await save_upload_file(upload_file=file)
        # Construir la ruta completa para el log, si es necesario
        destination_path_for_log = UPLOAD_DIR / saved_file_info["file_path"]
        logger.info(f"Archivo '{saved_file_info['filename']}' guardado temporalmente en '{destination_path_for_log}' (ruta relativa DB: '{saved_file_info['file_path']}')")

        doc_in_internal = DocumentacionCreateInternal(
            titulo=titulo,
            descripcion=descripcion,
            tipo_documento_id=tipo_documento_id,
            equipo_id=equipo_id,
            mantenimiento_id=mantenimiento_id,
            licencia_id=licencia_id,
            enlace=saved_file_info["file_path"], # Usar 'enlace' como en el modelo
            nombre_archivo=saved_file_info["filename"],
            mime_type=saved_file_info["mime_type"],
            tamano_bytes=saved_file_info["size"],
            subido_por=current_user.id
        )

        documento = documentacion_service.create(db=db, obj_in=doc_in_internal)
        db.commit()
        db.refresh(documento)
        
        logger.info(f"Registro de documentación ID {documento.id} para archivo '{documento.nombre_archivo}' creado exitosamente.")
        return documento

    except HTTPException as http_exc:
        logger.error(f"Error HTTP ({http_exc.status_code}) al procesar subida de documento: {http_exc.detail}")
        if saved_file_info and saved_file_info.get("file_path"): # Verificar que file_path exista
            logger.warning(f"Intentando revertir guardado de archivo '{destination_path_for_log or saved_file_info['file_path']}' debido a error HTTP.")
            await delete_uploaded_file(saved_file_info['file_path'])
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error de integridad al crear registro de documentación: {getattr(e, 'orig', e)}", exc_info=True)
        if saved_file_info and saved_file_info.get("file_path"):
            logger.warning(f"Intentando revertir guardado de archivo '{destination_path_for_log or saved_file_info['file_path']}' debido a error de integridad en DB.")
            await delete_uploaded_file(saved_file_info['file_path'])
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al crear el registro de documentación.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado durante la subida de documento: {e}", exc_info=True)
        # Corrección en el log de error: usar destination_path_for_log si está disponible
        path_to_log_delete = "desconocido"
        if saved_file_info and saved_file_info.get("file_path"):
             path_to_log_delete = str(destination_path_for_log or saved_file_info['file_path'])
             logger.warning(f"Intentando revertir guardado de archivo '{path_to_log_delete}' debido a error inesperado.")
             await delete_uploaded_file(saved_file_info['file_path'])
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al procesar la subida del documento.")


@router.get("/",
            response_model=List[Documentacion],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_DOCUMENTOS]))],
            summary="Listar Registros de Documentación",
            response_description="Una lista de registros de documentación, opcionalmente filtrada.")
def read_documentacion(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    equipo_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de equipo asociado"),
    mantenimiento_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de mantenimiento asociado"),
    licencia_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de licencia asociada"),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando documentación.")
    if equipo_id:
        documentos = documentacion_service.get_multi_by_equipo(db, equipo_id=equipo_id, skip=skip, limit=limit)
    elif mantenimiento_id:
        documentos = documentacion_service.get_multi_by_mantenimiento(db, mantenimiento_id=mantenimiento_id, skip=skip, limit=limit)
    elif licencia_id:
        documentos = documentacion_service.get_multi_by_licencia(db, licencia_id=licencia_id, skip=skip, limit=limit)
    else:
        documentos = documentacion_service.get_multi(db, skip=skip, limit=limit)
    return documentos

@router.get("/{doc_id}",
            response_model=Documentacion,
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_DOCUMENTOS]))],
            summary="Obtener Documentación por ID",
            response_description="Información detallada del registro de documentación.")
def read_documentacion_by_id(
    doc_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitando documentación ID: {doc_id}.")
    documento = documentacion_service.get_or_404(db, id=doc_id)
    return documento

@router.put("/{doc_id}",
            response_model=Documentacion,
            dependencies=[Depends(deps.PermissionChecker([PERM_EDITAR_DOCUMENTOS]))],
            summary="Actualizar Metadatos de Documentación",
            response_description="Registro de documentación con metadatos actualizados.")
def update_documentacion_metadata(
    *,
    db: Session = Depends(deps.get_db),
    doc_id: PyUUID,
    doc_in: DocumentacionUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' actualizando metadatos de documentación ID: {doc_id} con datos: {doc_in.model_dump(exclude_unset=True)}")
    db_doc = documentacion_service.get_or_404(db, id=doc_id)
    
    # La validación de si el equipo_id existe ya no es necesaria aquí porque DocumentacionUpdate no lo incluye.
    # if doc_in.equipo_id and doc_in.equipo_id != db_doc.equipo_id:
    #     if not deps.is_valid_uuid(str(doc_in.equipo_id)) or not equipo_service.get(db, id=doc_in.equipo_id):
    #          raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Equipo con ID {doc_in.equipo_id} no encontrado.")
    
    try:
        updated_doc = documentacion_service.update(db=db, db_obj=db_doc, obj_in=doc_in)
        db.commit()
        db.refresh(updated_doc)
        logger.info(f"Metadatos de documentación ID {doc_id} ('{updated_doc.titulo}') actualizados exitosamente.")
        return updated_doc
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al actualizar metadatos de doc ID {doc_id}: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error de integridad al actualizar metadatos de doc ID {doc_id}: {getattr(e, 'orig', e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al actualizar los metadatos.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando metadatos de doc ID {doc_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar los metadatos.")


@router.post("/{doc_id}/verificar",
             response_model=Documentacion,
             dependencies=[Depends(deps.PermissionChecker([PERM_VERIFICAR_DOCUMENTOS]))],
             summary="Verificar o Rechazar Documentación",
             response_description="El registro de documentación con el estado de verificación actualizado.")
def verify_documentacion_status(
    *,
    db: Session = Depends(deps.get_db),
    doc_id: PyUUID,
    verify_in: DocumentacionVerify,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' actualizando estado de verificación para doc ID {doc_id} a '{verify_in.estado}'.")
    db_doc = documentacion_service.get_or_404(db, id=doc_id)
    
    try:
        verified_doc = documentacion_service.verify_document(
            db=db,
            db_obj=db_doc,
            verify_data=verify_in,
            verificado_por_usuario=current_user
        )
        db.commit()
        db.refresh(verified_doc)
        logger.info(f"Estado de verificación para doc ID {doc_id} actualizado a '{verified_doc.estado}' por '{current_user.nombre_usuario}'.")
        return verified_doc
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado al verificar doc ID {doc_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al actualizar el estado de verificación.")


@router.delete("/{doc_id}",
               response_model=Msg,
               dependencies=[Depends(deps.PermissionChecker([PERM_ELIMINAR_DOCUMENTOS]))],
               status_code=status.HTTP_200_OK,
               summary="Eliminar Registro de Documentación y Archivo Físico",
               response_description="Mensaje de confirmación.")
async def delete_documentacion(
    *,
    db: Session = Depends(deps.get_db),
    doc_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.warning(f"Usuario '{current_user.nombre_usuario}' intentando eliminar documentación ID: {doc_id}.")
    doc = documentacion_service.get_or_404(db, id=doc_id)
    
    file_path_relative = doc.enlace
    file_delete_attempted = False
    file_actually_deleted = False
    file_was_not_found = False

    try:
        documentacion_service.remove(db=db, id=doc_id)
        db.commit()
        logger.info(f"Registro de documentación '{doc.titulo}' (ID: {doc_id}) eliminado de la BD.")
        
        if file_path_relative:
            file_delete_attempted = True
            try:
                # Modificar delete_uploaded_file para que quizás devuelva un status o usar try-except aquí
                await delete_uploaded_file(file_path_relative)
                logger.info(f"Archivo físico '{file_path_relative}' eliminado correctamente para doc ID {doc_id}.")
                file_actually_deleted = True
            except FileNotFoundError:
                logger.warning(f"Archivo físico '{file_path_relative}' no encontrado para doc ID {doc_id} durante la eliminación.")
                file_was_not_found = True # Marcar que no se encontró
            except Exception as file_err:
                logger.error(f"Error CRÍTICO al eliminar archivo físico '{file_path_relative}' para doc ID {doc_id} DESPUÉS de borrar el registro DB: {file_err}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"El registro de documentación fue eliminado, pero ocurrió un error al eliminar el archivo físico asociado '{doc.nombre_archivo}'. Contacte al administrador."
                )
        else:
            logger.info(f"Registro de documentación '{doc.titulo}' (ID: {doc_id}) no tenía archivo físico asociado para eliminar.")

        msg = f"Registro de documentación '{doc.titulo}' eliminado."
        if file_delete_attempted:
            if file_actually_deleted:
                msg += " Archivo asociado también eliminado."
            elif file_was_not_found:
                msg += " Archivo asociado no encontrado en disco (puede haber sido borrado previamente)."
        
        return {"msg": msg}

    except HTTPException as http_exc:
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error de integridad al eliminar doc ID {doc_id}: {getattr(e, 'orig', e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se pudo eliminar el registro de documentación debido a referencias existentes.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando documentación ID {doc_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al eliminar la documentación.")


@router.get("/equipo/{equipo_id}",
            response_model=List[Documentacion],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_DOCUMENTOS]))],
            summary="Listar Documentos de un Equipo",
            )
def read_documentacion_by_equipo(
    equipo_id: PyUUID,
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando documentos del equipo ID: {equipo_id}.")
    documentos = documentacion_service.get_multi_by_equipo(db, equipo_id=equipo_id, skip=skip, limit=limit)
    return documentos

@router.get("/mantenimiento/{mantenimiento_id}",
            response_model=List[Documentacion],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_DOCUMENTOS]))],
            summary="Listar Documentos de un Mantenimiento",
            )
def read_documentacion_by_mantenimiento(
    mantenimiento_id: PyUUID,
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando documentos del mantenimiento ID: {mantenimiento_id}.")
    documentos = documentacion_service.get_multi_by_mantenimiento(db, mantenimiento_id=mantenimiento_id, skip=skip, limit=limit)
    return documentos

@router.get("/licencia/{licencia_id}",
            response_model=List[Documentacion],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_DOCUMENTOS]))],
            summary="Listar Documentos de una Licencia",
            )
def read_documentacion_by_licencia(
    licencia_id: PyUUID,
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando documentos de la licencia ID: {licencia_id}.")
    documentos = documentacion_service.get_multi_by_licencia(db, licencia_id=licencia_id, skip=skip, limit=limit)
    return documentos
