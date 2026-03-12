import logging
import os
from typing import Optional
import uuid
from pathlib import Path
from fastapi import UploadFile, HTTPException, status
import aiofiles
import aiofiles.os

from app.core.config import settings

logger = logging.getLogger(__name__)

# ==========================================
# CONFIGURACIÓN LOCAL
# ==========================================
UPLOAD_DIR = Path(settings.UPLOADS_DIRECTORY)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

AVATARS_DIR = UPLOAD_DIR / "avatars"
AVATARS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
}

# ==========================================
# CONFIGURACIÓN NUBE (S3 / MinIO) - Opcional
# ==========================================
try:
    import boto3 as boto3  # type: ignore[import-untyped]
    from botocore.exceptions import NoCredentialsError  # type: ignore[import-untyped]
    S3_AVAILABLE = True
    logger.debug("boto3 disponible. Soporte S3/MinIO activado.")
except ImportError:
    boto3 = None  # type: ignore[assignment]
    NoCredentialsError = Exception  # type: ignore[assignment, misc]
    S3_AVAILABLE = False
    logger.info("boto3 no instalado. Almacenamiento en nube S3/MinIO no disponible. Usando almacenamiento local.")


def get_s3_client():
    """Retorna cliente S3 si está configurado, de lo contrario None."""
    if not S3_AVAILABLE or boto3 is None:
        return None
    if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_BUCKET_NAME:
        logger.debug("Credenciales S3 no configuradas. Usando almacenamiento local.")
        return None

    logger.debug(f"Creando cliente S3 para bucket '{settings.AWS_BUCKET_NAME}' en región '{settings.AWS_REGION}'.")
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
        endpoint_url=settings.AWS_ENDPOINT_URL
    )


# ==========================================
# FUNCIONES LOCALES (Documentos)
# ==========================================
async def save_upload_file(upload_file: UploadFile) -> dict:
    """
    Guarda un archivo subido localmente y devuelve metadatos. (Usado por Documentos)
    """
    if not upload_file or not upload_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se envió ningún archivo o el archivo no tiene nombre."
        )

    size = upload_file.size
    if size is None:
        raise HTTPException(
            status_code=status.HTTP_411_LENGTH_REQUIRED,
            detail="No se pudo determinar el tamaño del archivo. Header 'Content-Length' requerido."
        )

    if size > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo excede el tamaño máximo permitido ({settings.MAX_FILE_SIZE_BYTES / 1024 / 1024:.1f} MB).",
        )

    mime_type = upload_file.content_type
    if mime_type not in ALLOWED_MIME_TYPES:
        logger.warning(f"Intento de subir archivo con tipo MIME no permitido: '{mime_type}'. Archivo: '{upload_file.filename}'.")
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de archivo '{mime_type}' no permitido. Permitidos: {', '.join(ALLOWED_MIME_TYPES)}",
        )

    file_extension = Path(upload_file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    relative_path = Path(unique_filename)
    destination_path = UPLOAD_DIR / relative_path

    logger.debug(f"Guardando archivo '{upload_file.filename}' ({size} bytes) como '{unique_filename}' en '{UPLOAD_DIR}'.")
    try:
        async with aiofiles.open(destination_path, "wb") as out_file:
            while content := await upload_file.read(1024 * 1024):
                await out_file.write(content)
        logger.info(f"Archivo '{upload_file.filename}' guardado exitosamente como '{unique_filename}' en '{UPLOAD_DIR}'.")
    except Exception as e:
        logger.error(f"Error al guardar el archivo '{unique_filename}': {e}", exc_info=True)
        if await aiofiles.os.path.exists(destination_path):
            await aiofiles.os.remove(destination_path)
            logger.warning(f"Archivo parcial '{unique_filename}' eliminado tras error de escritura.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo guardar el archivo en el servidor."
        )
    finally:
        await upload_file.close()

    return {
        "file_path": str(relative_path),
        "filename": upload_file.filename,
        "mime_type": mime_type,
        "size": size,
    }


async def delete_uploaded_file(file_path_relative: Optional[str]):
    """
    Elimina un archivo del directorio de uploads de forma segura y asíncrona.
    """
    if not file_path_relative:
        logger.warning("Se intentó eliminar un archivo con una ruta nula o vacía.")
        return

    full_path = UPLOAD_DIR / file_path_relative
    logger.debug(f"Intentando eliminar archivo: '{full_path}'.")
    try:
        if await aiofiles.os.path.isfile(full_path):
            await aiofiles.os.remove(full_path)
            logger.info(f"Archivo '{full_path}' eliminado exitosamente.")
        else:
            logger.warning(f"Intento de eliminar archivo no encontrado en disco: '{full_path}' (puede haber sido borrado previamente o no es un archivo).")
            raise FileNotFoundError(f"Archivo físico no encontrado en la ruta: {full_path}")
    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error inesperado al intentar eliminar el archivo '{file_path_relative}': {e}", exc_info=True)
        raise


def get_file_url(relative_path: Optional[str]) -> Optional[str]:
    """Genera una URL para acceder al archivo servido estáticamente."""
    if not relative_path:
        return None
    return f"/static/uploads/{relative_path}"


# ==========================================
# FUNCIONES DE AVATARES (Híbrido S3/Local)
# ==========================================
async def upload_avatar(upload_file: UploadFile, user_id: str) -> str:
    """
    Sube un avatar. Intenta usar S3 primero, si no hay configuración lo hace localmente.
    Siempre fuerza el nombre del archivo a `user_{id}.ext` para sobrescribir el anterior
    y ahorrar espacio sin acumular archivos huérfanos.
    """
    if not upload_file.filename:
        raise ValueError("El archivo de avatar no tiene nombre.")

    extension = upload_file.filename.split(".")[-1].lower()
    if extension not in ["jpg", "jpeg", "png", "webp"]:
        logger.warning(f"Formato de avatar rechazado: '.{extension}' para usuario ID '{user_id}'.")
        raise ValueError("Formato de imagen no permitido. Use JPG, PNG o WEBP.")

    file_name = f"user_{user_id}.{extension}"
    logger.info(f"Iniciando subida de avatar para usuario ID '{user_id}'. Archivo: '{file_name}'.")

    # 1. INTENTO DE NUBE (S3 / MinIO)
    s3_client = get_s3_client()
    if s3_client:
        try:
            s3_path = f"avatars/{file_name}"
            bucket = settings.AWS_BUCKET_NAME or ""  # ← guard para Pylance
            region = settings.AWS_REGION or ""        # ← guard para Pylance
            logger.debug(f"Subiendo avatar a S3: bucket='{bucket}', path='{s3_path}'.")
            s3_client.upload_fileobj(
                upload_file.file,
                bucket,
                s3_path,
                ExtraArgs={'ContentType': upload_file.content_type, 'ACL': 'public-read'}
            )
            if settings.AWS_ENDPOINT_URL:
                url = f"{settings.AWS_ENDPOINT_URL}/{bucket}/{s3_path}"
            else:
                url = f"https://{bucket}.s3.{region}.amazonaws.com/{s3_path}"
            logger.info(f"Avatar para usuario ID '{user_id}' subido exitosamente a S3. URL base: '{url}'.")
            return url
        except Exception as e:
            logger.error(f"Fallo al subir avatar a S3 para usuario ID '{user_id}'. Cayendo a almacenamiento local. Error: {e}", exc_info=True)

    # 2. FALLBACK LOCAL
    destination_path = AVATARS_DIR / file_name
    upload_file.file.seek(0)  # Resetear puntero por si S3 lo movió
    logger.debug(f"Guardando avatar localmente en '{destination_path}'.")

    try:
        async with aiofiles.open(destination_path, "wb") as out_file:
            while content := await upload_file.read(1024 * 1024):
                await out_file.write(content)

        url = f"/static/uploads/avatars/{file_name}"
        logger.info(f"Avatar para usuario ID '{user_id}' guardado localmente. URL: '{url}'.")
        return url
    except Exception as e:
        logger.error(f"Error guardando avatar local para usuario ID '{user_id}': {e}", exc_info=True)
        raise Exception("Error al guardar la foto de perfil en el servidor.")
    finally:
        await upload_file.close()
