import io
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.api import deps
from app.core.config import settings
from app.models.empresa import Empresa
from app.schemas.empresa import EmpresaPublica, EmpresaRead, EmpresaUpdate

router = APIRouter()
LOGO_DIR = Path(settings.UPLOADS_DIRECTORY).resolve() / "branding"
admin = Depends(deps.PermissionChecker(["administrar_sistema", "configurar_sistema"]))


def get_empresa(db: Session):
    return db.get(Empresa, 1)


def serialize(empresa):
    data = {"nombre": "ControlEquipos", "identificacion": None, "direccion": None, "telefono": None, "email": None}
    if empresa:
        data.update({key: getattr(empresa, key) for key in data})
    data["logo_url"] = f"/api/proxy/empresa/publica/logo?v={empresa.logo_path}" if empresa and empresa.logo_path else None
    data["updated_at"] = empresa.updated_at if empresa else None
    return data


@router.get("/publica", response_model=EmpresaPublica)
def empresa_publica(db: Session = Depends(deps.get_db)):
    return serialize(get_empresa(db))


@router.get("/publica/logo", response_class=FileResponse)
def logo_publico(db: Session = Depends(deps.get_db)):
    empresa = get_empresa(db)
    if not empresa or not empresa.logo_path:
        raise HTTPException(404, "No hay logo configurado.")
    path = (LOGO_DIR / empresa.logo_path).resolve()
    if path.parent != LOGO_DIR or not path.is_file():
        raise HTTPException(404, "Logo no encontrado.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"})


@router.get("/", response_model=EmpresaRead, dependencies=[admin])
def leer_empresa(db: Session = Depends(deps.get_db)):
    return serialize(get_empresa(db))


@router.put("/", response_model=EmpresaRead, dependencies=[admin])
def actualizar_empresa(payload: EmpresaUpdate, db: Session = Depends(deps.get_db)):
    values = payload.model_dump()
    statement = insert(Empresa).values(id=1, **values)
    db.execute(statement.on_conflict_do_update(index_elements=[Empresa.id], set_={**values, "updated_at": func.now()}))
    db.commit()
    db.expire_all()
    return serialize(get_empresa(db))


@router.post("/logo", response_model=EmpresaRead, dependencies=[admin])
async def subir_logo(file: UploadFile = File(...), db: Session = Depends(deps.get_db)):
    content = await file.read(2 * 1024 * 1024 + 1)
    await file.close()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(413, "El logo debe pesar menos de 2 MB.")
    try:
        image = Image.open(io.BytesIO(content))
        if image.format not in {"PNG", "JPEG", "WEBP"} or image.width * image.height > 16_000_000:
            raise ValueError("Formato o dimensiones inválidas")
        image.load()
        image = image.convert("RGBA")
        image.thumbnail((1200, 1200))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(415, "Seleccione una imagen PNG, JPG o WEBP válida (máximo 16 megapíxeles).")
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4()}.png"
    path = LOGO_DIR / filename
    image.save(path, "PNG")
    old_path = None
    try:
        db.execute(insert(Empresa).values(id=1, nombre="ControlEquipos").on_conflict_do_nothing(index_elements=[Empresa.id]))
        empresa = db.scalar(select(Empresa).where(Empresa.id == 1).with_for_update())
        old_path = empresa.logo_path
        empresa.logo_path = filename
        empresa.updated_at = func.now()
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    if old_path and (LOGO_DIR / old_path).resolve().parent == LOGO_DIR:
        (LOGO_DIR / old_path).unlink(missing_ok=True)
    db.expire_all()
    return serialize(get_empresa(db))


@router.delete("/logo", response_model=EmpresaRead, dependencies=[admin])
def eliminar_logo(db: Session = Depends(deps.get_db)):
    empresa = db.query(Empresa).filter(Empresa.id == 1).with_for_update().first()
    if empresa:
        old_path = empresa.logo_path
        empresa.logo_path = None
        db.commit()
        if old_path and (LOGO_DIR / old_path).resolve().parent == LOGO_DIR:
            (LOGO_DIR / old_path).unlink(missing_ok=True)
    return serialize(empresa)
