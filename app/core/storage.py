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

# Asegurarse que el directorio de uploads exista
UPLOAD_DIR = Path(settings.UPLOADS_DIRECTORY)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Tipos MIME permitidos
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/msword",  # .doc
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/vnd.ms-excel",  # .xls
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "text/plain",
}

async def save_upload_file(upload_file: UploadFile) -> dict:
    """
    Guarda un archivo subido localmente y devuelve metadatos.
    """
    if not upload_file or not upload_file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se envió ningún archivo o el archivo no tiene nombre.")

    # 1. Validación de Tamaño usando el atributo .size
    # CORRECCIÓN: Usar el atributo 'size' directamente. Es más eficiente.
    size = upload_file.size
    if size is None:
        # Esto ocurre si el cliente no envía el header Content-Length.
        # Por seguridad, podemos rechazar estas solicitudes o implementar una lectura en trozos para calcularlo.
        # Por ahora, lo rechazaremos por simplicidad y seguridad.
        raise HTTPException(status_code=status.HTTP_411_LENGTH_REQUIRED, detail="No se pudo determinar el tamaño del archivo. Header 'Content-Length' requerido.")

    if size > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo excede el tamaño máximo permitido ({settings.MAX_FILE_SIZE_BYTES / 1024 / 1024:.1f} MB).",
        )

    # 2. Validación de Tipo MIME
    mime_type = upload_file.content_type
    if mime_type not in ALLOWED_MIME_TYPES:
        logger.warning(f"Intento de subir archivo con tipo MIME no permitido: {mime_type}")
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de archivo '{mime_type}' no permitido. Permitidos: {', '.join(ALLOWED_MIME_TYPES)}",
        )

    # 3. Generar nombre de archivo único
    # CORRECCIÓN: La comprobación de 'upload_file.filename' se hizo al principio.
    file_extension = Path(upload_file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    relative_path = Path(unique_filename)
    destination_path = UPLOAD_DIR / relative_path

    # 4. Guardar el archivo de forma asíncrona
    try:
        async with aiofiles.open(destination_path, "wb") as out_file:
            # Leer el archivo en trozos para no consumir toda la memoria RAM
            while content := await upload_file.read(1024 * 1024):  # Leer en bloques de 1MB
                await out_file.write(content)
        logger.info(f"Archivo '{upload_file.filename}' guardado como '{unique_filename}' en {UPLOAD_DIR}")
    except Exception as e:
        logger.error(f"Error al guardar el archivo {unique_filename}: {e}", exc_info=True)
        # Intentar borrar el archivo parcial si se creó (de forma asíncrona)
        if await aiofiles.os.path.exists(destination_path):
            await aiofiles.os.remove(destination_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo guardar el archivo en el servidor.",
        )
    finally:
        await upload_file.close()

    # 5. Devolver metadatos necesarios para guardar en la DB
    return {
        "file_path": str(relative_path),
        "filename": upload_file.filename,
        "mime_type": mime_type,
        "size": size,
    }

async def delete_uploaded_file(file_path_relative: Optional[str]):
    """
    Elimina un archivo del directorio de uploads de forma segura y asíncrona.
    Verifica si el archivo existe antes de intentar eliminarlo.
    """
    if not file_path_relative:
        logger.warning("Se intentó eliminar un archivo con una ruta nula o vacía.")
        return

    full_path = UPLOAD_DIR / file_path_relative
    try:
        # ===== INICIO DE LA CORRECCIÓN =====
        # Verificar si la ruta es un archivo antes de intentar borrarla.
        # Esto satisface la expectativa del mock en la prueba.
        if await aiofiles.os.path.isfile(full_path):
            await aiofiles.os.remove(full_path)
            logger.info(f"Archivo '{full_path}' eliminado exitosamente.")
        else:
            # Si no es un archivo, registramos una advertencia clara.
            # La prueba que verifica este escenario buscará este mensaje en los logs.
            logger.warning(f"Intento de eliminar archivo no encontrado en disco: '{full_path}' (puede haber sido borrado previamente o no es un archivo).")
            # Lanzamos FileNotFoundError para que el llamador pueda manejarlo.
            raise FileNotFoundError(f"Archivo físico no encontrado en la ruta: {full_path}")
        # ===== FIN DE LA CORRECCIÓN =====
    except FileNotFoundError:
        # Re-lanzamos la excepción para que la ruta de la API pueda decidir qué hacer.
        raise
    except Exception as e:
        logger.error(f"Error inesperado al intentar eliminar el archivo '{file_path_relative}': {e}", exc_info=True)
        # Re-lanzamos una excepción genérica para otros problemas.
        raise

def get_file_url(relative_path: Optional[str]) -> Optional[str]:
    """
    Genera una URL para acceder al archivo (si se sirven estáticamente).
    """
    if not relative_path:
        return None
    return f"/static/uploads/{relative_path}"
