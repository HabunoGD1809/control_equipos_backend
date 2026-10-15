"""Printable equipment and receipt documents using the shared report identity."""
import json
from datetime import date, datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core import permissions as perms
from app.core.security import user_has_permissions
from app.models.equipo_componente import EquipoComponente
from app.models.movimiento import Movimiento
from app.models.documentacion import Documentacion
from app.models.mantenimiento import Mantenimiento
from app.models.equipo import Equipo
from app.models.asignacion_licencia import AsignacionLicencia
from app.services.report_export import CompanyPDF, company_identity, write_pdf_table, display


def value_text(value):
    if value is None or value == "":
        return "No registrado"
    if isinstance(value, datetime):
        return display(value)
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return display(value)


def section(pdf, title, fields):
    if pdf.will_page_break(30):
        pdf.add_page()
    pdf.set_font("Report", "B", 10)
    pdf.set_text_color(0, 127, 134)
    pdf.multi_cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Report", "", 9)
    pdf.set_text_color(23, 50, 77)
    write_pdf_table(pdf, ["Campo", "Información"], [{"Campo": key, "Información": value_text(value)} for key, value in fields], [30, 70], line_height=4.2, padding=1.1)
    pdf.ln(4)


def equipment_document(db, equipo, user):
    pdf = CompanyPDF(company_identity(db), "Ficha del activo", f"Código: {equipo.codigo_interno or equipo.numero_serie}", orientation="P")
    pdf.add_page()
    section(pdf, "Identificación", [
        ("Nombre", equipo.nombre), ("Tipo de activo", equipo.tipo_activo),
        ("Código interno", equipo.codigo_interno), ("Número de serie", equipo.numero_serie),
        ("Marca", getattr(equipo.marca_rel, "nombre", None)), ("Modelo", equipo.modelo),
        ("Estado", equipo.estado.nombre),
    ])
    custodio = equipo.empleado_asignado
    section(pdf, "Ubicación y custodia", [
        ("Ubicación actual", getattr(equipo.ubicacion, "nombre", None)),
        ("Custodio asignado", custodio.nombre_completo if custodio else "Sin asignación"),
        ("Cargo", custodio.cargo if custodio else None),
        ("Departamento", getattr(custodio.departamento_rel, "nombre", None) if custodio else None),
        ("Centro de costo", equipo.centro_costo),
    ])
    section(pdf, "Adquisición y garantía", [
        ("Proveedor", getattr(equipo.proveedor, "nombre", None)),
        ("Adquisición", equipo.fecha_adquisicion), ("Puesta en marcha", equipo.fecha_puesta_marcha),
        ("Fin de garantía", equipo.fecha_garantia_expiracion), ("Valor de adquisición", equipo.valor_adquisicion),
    ])
    section(pdf, "Ficha técnica", [(key.replace('_', ' ').capitalize(), value) for key, value in (equipo.especificaciones_tecnicas or {}).items()] or [("Especificaciones", "Sin especificaciones registradas")])
    relations = list(db.scalars(select(EquipoComponente).where((EquipoComponente.equipo_padre_id == equipo.id) | (EquipoComponente.equipo_componente_id == equipo.id)).options(selectinload(EquipoComponente.equipo_padre), selectinload(EquipoComponente.equipo_componente)).order_by(EquipoComponente.created_at, EquipoComponente.id)))
    fields = []
    for relation in relations:
        is_parent = relation.equipo_padre_id == equipo.id
        other = relation.equipo_componente if is_parent else relation.equipo_padre
        fields.append(("Componente" if is_parent else "Parte de", f"{other.nombre} | Serie: {other.numero_serie} | {relation.tipo_relacion}"))
    section(pdf, "Conjunto y relaciones", fields or [("Vínculos", "Sin componentes ni equipos asociados")])
    if user_has_permissions(user, {perms.PERM_VER_LICENCIAS}):
        assignments = list(db.scalars(select(AsignacionLicencia).where(AsignacionLicencia.equipo_id == equipo.id).order_by(AsignacionLicencia.fecha_asignacion.desc(), AsignacionLicencia.id.desc())))
        section(pdf, "Licencias asignadas", [(assignment.licencia.software_info.nombre, f"Asignada: {value_text(assignment.fecha_asignacion)} | Expira: {value_text(assignment.licencia.fecha_expiracion)} | Instalada: {'Sí' if assignment.instalado else 'No'}") for assignment in assignments] or [("Software", "Sin licencias asignadas")])
    if user_has_permissions(user, {perms.PERM_VER_MOVIMIENTOS}):
        history = list(db.scalars(select(Movimiento).where((Movimiento.equipo_id == equipo.id) | Movimiento.componentes_origen.has_key(str(equipo.id))).order_by(Movimiento.fecha_hora.desc(), Movimiento.id.desc()).limit(10)))
        section(pdf, "Últimos movimientos (hasta 10)", [(value_text(m.fecha_hora), f"{m.tipo_movimiento} | {m.estado}\nCustodio: {getattr(m.empleado_destino, 'nombre_completo', 'Sin asignación')}\nRegistró: {getattr(m.usuario_registrador, 'nombre_usuario', 'Sistema')} | Autorizó: {getattr(m.usuario_autorizador, 'nombre_usuario', 'No registrado')}\nReceptor registrado: {m.recibido_por or 'Sin recepción confirmada'} | Confirmó: {getattr(m.usuario_confirmador, 'nombre_usuario', 'No registrado')}") for m in history] or [("Historial", "Sin movimientos registrados")])
    for permission, model, title, render in [
        (perms.PERM_VER_DOCUMENTOS, Documentacion, "Documentación vinculada (hasta 10)", lambda d: f"{d.titulo} | {d.estado}"),
        (perms.PERM_VER_MANTENIMIENTOS, Mantenimiento, "Mantenimientos recientes (hasta 10)", lambda m: f"{value_text(m.fecha_programada)} | {m.estado}"),
    ]:
        if user_has_permissions(user, {permission}):
            recent = model.fecha_subida if model is Documentacion else model.created_at
            rows = list(db.scalars(select(model).where(model.equipo_id == equipo.id).order_by(recent.desc(), model.id.desc()).limit(10)))
            section(pdf, title, [(str(index), render(row)) for index, row in enumerate(rows, 1)] or [("Registros", "Sin registros vinculados")])
    section(pdf, "Observaciones y control", [("Notas", equipo.notas), ("Alta", equipo.created_at), ("Última actualización", equipo.updated_at), ("Documento generado por", user.nombre_usuario)])
    return bytes(pdf.output())


def receipt_document(db, movimiento, user):
    pdf = CompanyPDF(company_identity(db), "Acuse de recepción" if movimiento.estado == "Completado" else "Constancia de movimiento", f"Movimiento: {movimiento.id}", orientation="P")
    pdf.add_page()
    equipo = movimiento.equipo
    section(pdf, "Activo y entrega", [("Equipo", equipo.nombre), ("Código / serie", f"{equipo.codigo_interno or 'Sin código'} / {equipo.numero_serie}"), ("Tipo", movimiento.tipo_movimiento), ("Estado", movimiento.estado), ("Origen", getattr(movimiento.ubicacion_origen, "nombre", None)), ("Destino", getattr(movimiento.ubicacion_destino, "nombre", None)), ("Propósito", movimiento.proposito), ("Fecha de movimiento", movimiento.fecha_hora), ("Retorno previsto", movimiento.fecha_prevista_retorno), ("Retorno registrado", movimiento.fecha_retorno)])
    recipient_label = "Recibió físicamente" if movimiento.fecha_recepcion else "Receptor registrado (histórico)"
    section(pdf, "Personas y confirmación", [("Custodio asignado", getattr(movimiento.empleado_destino, "nombre_completo", None)), (recipient_label, movimiento.recibido_por), ("Entidad externa", movimiento.entidad_receptora), ("Registró la entrega", getattr(movimiento.usuario_registrador, "nombre_usuario", None)), ("Autorizó", getattr(movimiento.usuario_autorizador, "nombre_usuario", None)), ("Registró la decisión", getattr(movimiento.usuario_confirmador, "nombre_usuario", None)), ("Fecha de decisión", movimiento.fecha_recepcion)])
    components = []
    for identifier, saved in (movimiento.componentes_origen or {}).items():
        from uuid import UUID
        item = db.get(Equipo, UUID(identifier))
        name = saved.get('nombre') or getattr(item, 'nombre', 'Activo histórico')
        serial = saved.get('numero_serie') or getattr(item, 'numero_serie', identifier)
        components.append(("Componente", f"{name} | Serie: {serial}"))
    section(pdf, "Activos del conjunto", [("Activo principal", f"{equipo.nombre} | {equipo.numero_serie}")] + components)
    section(pdf, "Observaciones", [("Registro", movimiento.observaciones)])
    if movimiento.estado == "Completado":
        if pdf.will_page_break(24):
            pdf.add_page()
        pdf.set_font("Report", "", 9)
        pdf.ln(6)
        pdf.cell(pdf.epw / 2, 7, "Firma de quien entrega: __________________")
        pdf.cell(pdf.epw / 2, 7, "Firma de quien recibe: __________________", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Report", "", 8)
        pdf.multi_cell(0, 6, "Registro del sistema. Las firmas, cuando correspondan, se recaban al entregar y recibir.")
    return bytes(pdf.output())
