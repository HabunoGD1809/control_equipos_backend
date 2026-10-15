"""Idempotent system catalogs. No people, assets or access credentials are seeded."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core import permissions
from app.core.equipment_states import EquipmentStateCode
from app.models import Permiso, Rol, EstadoEquipo, TipoDocumento, TipoMantenimiento, Ubicacion, Empresa

DEFAULT_STATES = [
    (EquipmentStateCode.AVAILABLE, "Disponible", "Listo para asignación o uso", True, False, False, "#4CAF50"),
    (EquipmentStateCode.IN_USE, "En Uso", "Asignado a un empleado o ubicación", True, False, False, "#2196F3"),
    (EquipmentStateCode.ON_LOAN, "Prestado", "Entregado temporalmente; requiere devolución", False, False, False, "#FF9800"),
    (EquipmentStateCode.MAINTENANCE, "En Mantenimiento", "Mantenimiento en curso", False, False, False, "#FFC107"),
    (None, "En Reparación", "En servicio técnico externo", False, False, False, "#FF5722"),
    (None, "Averiado", "Requiere diagnóstico o reparación", False, True, False, "#F44336"),
    (None, "En Cuarentena", "Bajo evaluación antes de su uso", False, True, False, "#9E9E9E"),
    (None, "Reservado", "Apartado para un uso específico", False, True, False, "#607D8B"),
    (None, "En Tránsito", "En traslado entre ubicaciones", False, False, False, "#795548"),
    (None, "Extraviado", "Ubicación pendiente de investigación", False, True, False, "#000000"),
    (EquipmentStateCode.RETIRED, "Dado de Baja", "Retirado definitivamente del servicio", False, True, True, "#E0E0E0"),
]
DEFAULT_DOCUMENT_TYPES = [
    ("Factura Compra", "Comprobante de adquisición", True, ["pdf", "jpg", "png"]),
    ("Manual Usuario", "Instrucciones de operación", False, ["pdf", "docx"]),
    ("Manual Servicio", "Instrucciones técnicas de reparación", False, ["pdf"]),
    ("Ficha Técnica", "Especificaciones del fabricante", True, ["pdf"]),
    ("Garantía", "Documento de cobertura de garantía", True, ["pdf", "jpg", "png"]),
    ("Certificado Calibración", "Resultado de calibración", True, ["pdf"]),
    ("Reporte Mantenimiento", "Informe del servicio realizado", False, ["pdf", "docx"]),
    ("Póliza Seguro", "Cobertura de seguro del equipo", True, ["pdf"]),
    ("Fotografía", "Imagen del equipo", False, ["jpg", "png", "webp"]),
    ("Acta de Entrega/Recepción", "Evidencia de entrega o devolución", True, ["pdf"]),
    ("Informe de Baja", "Justificación de retiro del activo", True, ["pdf"]),
]
DEFAULT_MAINTENANCE_TYPES = [
    ("Preventivo Básico Trimestral", "Limpieza, inspección y ajustes", 90, False, True),
    ("Preventivo Completo Semestral", "Revisión y pruebas de funcionamiento", 180, True, True),
    ("Preventivo Anual", "Revisión según fabricante", 365, True, True),
    ("Correctivo Menor", "Reparación de una falla simple", None, True, False),
    ("Correctivo Mayor", "Reparación de una falla compleja", None, True, False),
    ("Calibración Anual", "Verificación y ajuste de precisión", 365, True, True),
    ("Actualización Firmware/Software", "Actualización de versiones", None, True, False),
    ("Inspección de Seguridad", "Verificación de condiciones de seguridad", 120, True, True),
]


def seed_system_catalogs(db: Session) -> Rol:
    """Insert missing essentials while preserving catalog customizations and IDs."""
    names = sorted({value for name, value in vars(permissions).items() if name.startswith("PERM_") and isinstance(value, str)})
    existing = set(db.scalars(select(Permiso.nombre)))
    db.add_all(Permiso(nombre=name, descripcion=name.replace("_", " ").capitalize()) for name in names if name not in existing)
    db.flush()
    role = db.scalar(select(Rol).where(Rol.nombre == permissions.ADMIN_ROLE_NAME))
    if not role:
        role = Rol(nombre=permissions.ADMIN_ROLE_NAME, descripcion="Administración completa del sistema")
        db.add(role)
    role.permisos = list(db.scalars(select(Permiso).where(Permiso.nombre.in_(names))))
    state_catalog_empty = not db.scalar(select(EstadoEquipo.id).limit(1))
    for code, name, description, movable, authorization, final, color in DEFAULT_STATES:
        if not code and not state_catalog_empty:
            continue
        condition = EstadoEquipo.codigo == code if code else EstadoEquipo.nombre == name
        if not db.scalar(select(EstadoEquipo.id).where(condition)):
            db.add(EstadoEquipo(codigo=code, nombre=name, descripcion=description, permite_movimientos=movable, requiere_autorizacion=authorization, es_estado_final=final, color_hex=color))
    if not db.scalar(select(TipoDocumento.id).limit(1)):
        db.add_all(TipoDocumento(nombre=name, descripcion=description, requiere_verificacion=verification, formato_permitido=formats) for name, description, verification, formats in DEFAULT_DOCUMENT_TYPES)
    if not db.scalar(select(TipoMantenimiento.id).limit(1)):
        db.add_all(TipoMantenimiento(nombre=name, descripcion=description, periodicidad_dias=period, requiere_documentacion=documentation, es_preventivo=preventive) for name, description, period, documentation, preventive in DEFAULT_MAINTENANCE_TYPES)
    if not db.scalar(select(Ubicacion.id)):
        db.add(Ubicacion(nombre="Almacén de informática", is_active=True))
    if not db.get(Empresa, 1):
        db.add(Empresa(id=1, nombre="ControlEquipos"))
    db.flush()
    return role
