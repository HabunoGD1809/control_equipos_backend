import logging
import os
import io
import zipfile
import asyncio
from PIL import Image, UnidentifiedImageError
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
def validate_file_bytes(content: bytes, extension: str):
    if not content:
        raise HTTPException(422, "El archivo está vacío.")
    if extension == ".pdf":
        if not content.startswith(b"%PDF-"): raise HTTPException(415, "El contenido no corresponde a un PDF.")
    elif extension in {".jpg", ".jpeg", ".png", ".webp"}:
        try:
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"} or image.width * image.height > 16_000_000:
                    raise ValueError("Imagen inválida")
                image.verify()
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
            raise HTTPException(415, "Seleccione una imagen válida de hasta 16 megapíxeles.")
    elif extension in {".docx", ".xlsx"}:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                prefix = "word/" if extension == ".docx" else "xl/"
                if "[Content_Types].xml" not in archive.namelist() or not any(n.startswith(prefix) for n in archive.namelist()):
                    raise ValueError("Formato Office inválido")
                if sum(info.file_size for info in archive.infolist()) > 100 * 1024 * 1024:
                    raise ValueError("Archivo comprimido demasiado grande")
        except (zipfile.BadZipFile, ValueError): raise HTTPException(415, "El contenido no corresponde al formato Office seleccionado.")
    elif extension in {".doc", ".xls"}:
        if not content.startswith(bytes.fromhex("D0CF11E0A1B11AE1")): raise HTTPException(415, "El contenido no corresponde al formato Office seleccionado.")
    elif extension == ".txt":
        try: content.decode("utf-8")
        except UnicodeDecodeError: raise HTTPException(415, "El archivo de texto debe usar UTF-8.")
    else: raise HTTPException(415, "Formato de archivo no permitido.")


async def save_upload_file(upload_file: UploadFile) -> dict:
    if not upload_file or not upload_file.filename:
        raise HTTPException(400, "Seleccione un archivo con nombre.")
    filename = Path(upload_file.filename.replace("\\", "/")).name
    extension = Path(filename).suffix.lower()
    mime_types = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".doc": "application/msword", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".xls": "application/vnd.ms-excel", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".txt": "text/plain"}
    try:
        content = await upload_file.read(settings.MAX_FILE_SIZE_BYTES + 1)
        if len(content) > settings.MAX_FILE_SIZE_BYTES: raise HTTPException(413, "El archivo supera el tamaño permitido.")
        validate_file_bytes(content, extension)
        relative_path = f"{uuid.uuid4()}{extension}"
        destination = UPLOAD_DIR / relative_path
        await asyncio.to_thread(destination.write_bytes, content)
        return {"file_path": relative_path, "filename": filename, "mime_type": mime_types[extension], "size": len(content)}
    finally: await upload_file.close()


async def delete_uploaded_file(file_path_relative: Optional[str]):
    """
    Elimina un archivo del directorio de uploads de forma segura y asíncrona.
    """
    if not file_path_relative:
        logger.warning("Se intentó eliminar un archivo con una ruta nula o vacía.")
        return

    full_path = (UPLOAD_DIR / file_path_relative).resolve()
    if full_path.parent != UPLOAD_DIR.resolve():
        raise ValueError("Ruta de archivo inválida.")
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


# ==========================================
# FUNCIONES DE AVATARES (Híbrido S3/Local)
# ==========================================
async def upload_avatar(upload_file: UploadFile, user_id: str) -> str:
    try:
        content = await upload_file.read(2 * 1024 * 1024 + 1)
        if len(content) > 2 * 1024 * 1024: raise HTTPException(413, "El avatar debe pesar menos de 2 MB.")
        extension = Path(upload_file.filename or "").suffix.lower()
        if extension not in {".png", ".jpg", ".jpeg", ".webp"}: raise HTTPException(415, "Use una imagen PNG, JPG o WEBP.")
        validate_file_bytes(content, extension)
        with Image.open(io.BytesIO(content)) as image:
            image = image.convert("RGB"); image.thumbnail((512,512))
            normalized = io.BytesIO(); image.save(normalized, "JPEG", quality=90)
        filename = f"user_{uuid.UUID(str(user_id))}.jpg"
        client = get_s3_client()
        if client:
            try:
                await asyncio.to_thread(client.upload_fileobj, io.BytesIO(normalized.getvalue()), settings.AWS_BUCKET_NAME,
                    f"avatars/{filename}", ExtraArgs={"ContentType": "image/jpeg"})
            finally:
                await asyncio.to_thread(client.close)
        else:
            await asyncio.to_thread((AVATARS_DIR / filename).write_bytes, normalized.getvalue())
        return f"/api/v1/usuarios/avatar/{filename}"
    finally: await upload_file.close()


def read_cloud_avatar(filename: str) -> Optional[bytes]:
    """Return a bounded private photo through the authenticated application route."""
    client = get_s3_client()
    if not client:
        return None
    try:
        try:
            response = client.get_object(Bucket=settings.AWS_BUCKET_NAME, Key=f"avatars/{filename}")
        except Exception as error:
            code = getattr(error, 'response', {}).get('Error', {}).get('Code')
            if code in {'NoSuchKey', '404', 'NotFound'}:
                return None  # Older local photos remain available after enabling S3.
            raise HTTPException(503, 'No se pudo consultar la foto en el almacenamiento configurado.') from error
        body = response['Body']
        try:
            content = body.read(2 * 1024 * 1024 + 1)
        finally:
            body.close()
        if len(content) > 2 * 1024 * 1024:
            raise HTTPException(413, 'La foto almacenada supera el tamaño permitido.')
        validate_file_bytes(content, Path(filename).suffix.lower())
        return content
    finally:
        client.close()
