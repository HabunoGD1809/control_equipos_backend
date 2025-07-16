"""
Creacion inicial de toda la base de datos (Versión Completa y Corregida)

Revision ID: 4aa970dc2c24
Revises:
Create Date: 2025-07-14 19:48:42.532476

Descripción:
Este script de migración contiene la estructura completa y los datos iniciales
de la base de datos, replicando fielmente los archivos structureControlEquipos.sql
y datosControlEquipos.sql.

Correcciones clave:
1.  Se invoca la función `gestionar_particiones_audit_log()` para crear la
    partición de auditoría inicial, evitando el error crítico en los tests.
2.  Se han reemplazado los datos de sembrado (seed data) para que coincidan
    exactamente con los datos de `datosControlEquipos.sql`, asegurando que
    todos los roles, permisos y catálogos necesarios existan desde el principio.
3.  Se ha verificado el orden lógico de creación de todos los objetos de la BD.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4aa970dc2c24'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Ejecuta todos los comandos para construir la base de datos desde cero.
    """
    # === PASO 1: LÓGICA PRE-TABLAS (Schema y Extensiones) ===
    op.execute("CREATE SCHEMA IF NOT EXISTS control_equipos;")
    op.execute("SET search_path TO control_equipos, public;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;")

    # === PASO 2: CREACIÓN DE TABLAS (Autogenerado por Alembic) ===
    # Esta sección define la estructura de las tablas usando el ORM de SQLAlchemy.
    op.create_table('audit_log',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('audit_timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('table_name', sa.Text(), nullable=False),
        sa.Column('operation', sa.Text(), nullable=False),
        sa.Column('old_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('username', sa.Text(), server_default=sa.text('current_user'), nullable=True),
        sa.Column('app_user_id', sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint('audit_timestamp', 'id', name=op.f('pk_audit_log')),
        schema='control_equipos',
        postgresql_partition_by='RANGE (audit_timestamp)'
    )
    op.create_table('backup_logs',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('backup_timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('backup_status', sa.Text(), nullable=True),
        sa.Column('backup_type', sa.Text(), nullable=True),
        sa.Column('duration', sa.Interval(), nullable=True),
        sa.Column('file_path', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_backup_logs')),
        schema='control_equipos'
    )
    op.create_table('estados_equipo',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('nombre', sa.Text(), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('permite_movimientos', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('requiere_autorizacion', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('es_estado_final', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('color_hex', sa.Text(), nullable=True),
        sa.Column('icono', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_estados_equipo')),
        sa.UniqueConstraint('nombre', name=op.f('uq_estados_equipo_nombre')),
        schema='control_equipos'
    )
    op.create_table('permisos',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('nombre', sa.Text(), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_permisos')),
        sa.UniqueConstraint('nombre', name=op.f('uq_permisos_nombre')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_permisos_nombre'), 'permisos', ['nombre'], unique=True, schema='control_equipos')
    op.create_table('proveedores',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('nombre', sa.Text(), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('contacto', sa.Text(), nullable=True),
        sa.Column('direccion', sa.Text(), nullable=True),
        sa.Column('sitio_web', sa.Text(), nullable=True),
        sa.Column('rnc', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_proveedores')),
        sa.UniqueConstraint('nombre', name=op.f('uq_proveedores_nombre')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_proveedores_nombre'), 'proveedores', ['nombre'], unique=True, schema='control_equipos')
    op.create_table('roles',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('nombre', sa.Text(), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_roles')),
        sa.UniqueConstraint('nombre', name=op.f('uq_roles_nombre')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_roles_nombre'), 'roles', ['nombre'], unique=True, schema='control_equipos')
    op.create_table('software_catalogo',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('nombre', sa.Text(), nullable=False),
        sa.Column('version', sa.Text(), nullable=True),
        sa.Column('fabricante', sa.Text(), nullable=True),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('categoria', sa.Text(), nullable=True),
        sa.Column('tipo_licencia', sa.Text(), nullable=False),
        sa.Column('metrica_licenciamiento', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint("metrica_licenciamiento IN ('Por Dispositivo', 'Por Usuario Nominal', 'Por Usuario Concurrente', 'Por Core', 'Por Servidor', 'Gratuita', 'Otra')", name='software_catalogo_metrica_licenciamiento_check'),
        sa.CheckConstraint("tipo_licencia IN ('Perpetua', 'Suscripción Anual', 'Suscripción Mensual', 'OEM', 'Freeware', 'Open Source', 'Otra')", name='software_catalogo_tipo_licencia_check'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_software_catalogo')),
        sa.UniqueConstraint('nombre', 'version', name='uq_software_nombre_version'),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_software_catalogo_fabricante'), 'software_catalogo', ['fabricante'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_software_catalogo_nombre'), 'software_catalogo', ['nombre'], unique=False, schema='control_equipos')
    op.create_table('tipos_documento',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('nombre', sa.Text(), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('requiere_verificacion', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('formato_permitido', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tipos_documento')),
        sa.UniqueConstraint('nombre', name=op.f('uq_tipos_documento_nombre')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_tipos_documento_nombre'), 'tipos_documento', ['nombre'], unique=True, schema='control_equipos')
    op.create_table('tipos_mantenimiento',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('nombre', sa.Text(), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('periodicidad_dias', sa.Integer(), nullable=True),
        sa.Column('requiere_documentacion', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('es_preventivo', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint('periodicidad_dias IS NULL OR periodicidad_dias > 0', name='tipos_mantenimiento_periodicidad_dias_check'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tipos_mantenimiento')),
        sa.UniqueConstraint('nombre', name=op.f('uq_tipos_mantenimiento_nombre')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_tipos_mantenimiento_nombre'), 'tipos_mantenimiento', ['nombre'], unique=True, schema='control_equipos')
    op.create_table('equipos',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('nombre', sa.Text(), nullable=False),
        sa.Column('numero_serie', sa.Text(), nullable=False),
        sa.Column('codigo_interno', sa.Text(), nullable=True),
        sa.Column('estado_id', sa.UUID(), nullable=False),
        sa.Column('ubicacion_actual', sa.Text(), nullable=True),
        sa.Column('marca', sa.Text(), nullable=True),
        sa.Column('modelo', sa.Text(), nullable=True),
        sa.Column('fecha_adquisicion', sa.Date(), nullable=True),
        sa.Column('fecha_puesta_marcha', sa.Date(), nullable=True),
        sa.Column('fecha_garantia_expiracion', sa.Date(), nullable=True),
        sa.Column('valor_adquisicion', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('proveedor_id', sa.UUID(), nullable=True),
        sa.Column('centro_costo', sa.Text(), nullable=True),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('texto_busqueda', postgresql.TSVECTOR(), nullable=True),
        sa.CheckConstraint('fecha_adquisicion IS NULL OR fecha_adquisicion <= CURRENT_DATE', name='check_fecha_adq'),
        sa.CheckConstraint('fecha_puesta_marcha IS NULL OR fecha_adquisicion IS NULL OR fecha_puesta_marcha >= fecha_adquisicion', name='check_fechas_logicas'),
        sa.CheckConstraint("numero_serie ~ '^[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+$'", name='check_numero_serie_format'),
        sa.CheckConstraint('valor_adquisicion IS NULL OR valor_adquisicion >= 0', name='check_valor_adq'),
        sa.ForeignKeyConstraint(['estado_id'], ['control_equipos.estados_equipo.id'], name=op.f('fk_equipos_estado_id_estados_equipo'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['proveedor_id'], ['control_equipos.proveedores.id'], name=op.f('fk_equipos_proveedor_id_proveedores'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_equipos')),
        sa.UniqueConstraint('codigo_interno', name=op.f('uq_equipos_codigo_interno')),
        sa.UniqueConstraint('numero_serie', name=op.f('uq_equipos_numero_serie')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_equipos_centro_costo'), 'equipos', ['centro_costo'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_equipos_codigo_interno'), 'equipos', ['codigo_interno'], unique=True, schema='control_equipos', postgresql_where=sa.text('codigo_interno IS NOT NULL'))
    op.create_index(op.f('ix_control_equipos_equipos_estado_id'), 'equipos', ['estado_id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_equipos_marca'), 'equipos', ['marca'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_equipos_modelo'), 'equipos', ['modelo'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_equipos_nombre'), 'equipos', ['nombre'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_equipos_numero_serie'), 'equipos', ['numero_serie'], unique=True, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_equipos_proveedor_id'), 'equipos', ['proveedor_id'], unique=False, schema='control_equipos')
    op.create_index('idx_equipos_texto_busqueda', 'equipos', ['texto_busqueda'], unique=False, schema='control_equipos', postgresql_using='gin')
    op.create_table('licencias_software',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('software_catalogo_id', sa.UUID(), nullable=False),
        sa.Column('clave_producto', sa.Text(), nullable=True),
        sa.Column('fecha_adquisicion', sa.Date(), nullable=False),
        sa.Column('fecha_expiracion', sa.Date(), nullable=True),
        sa.Column('proveedor_id', sa.UUID(), nullable=True),
        sa.Column('costo_adquisicion', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('numero_orden_compra', sa.Text(), nullable=True),
        sa.Column('cantidad_total', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('cantidad_disponible', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint('cantidad_disponible <= cantidad_total', name='check_disponible_no_mayor_total'),
        sa.CheckConstraint('fecha_expiracion IS NULL OR fecha_adquisicion IS NULL OR fecha_expiracion > fecha_adquisicion', name='check_expiracion_logica'),
        sa.ForeignKeyConstraint(['proveedor_id'], ['control_equipos.proveedores.id'], name=op.f('fk_licencias_software_proveedor_id_proveedores'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['software_catalogo_id'], ['control_equipos.software_catalogo.id'], name=op.f('fk_licencias_software_software_catalogo_id_software_catalogo'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_licencias_software')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_licencias_software_fecha_expiracion'), 'licencias_software', ['fecha_expiracion'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_licencias_software_proveedor_id'), 'licencias_software', ['proveedor_id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_licencias_software_software_catalogo_id'), 'licencias_software', ['software_catalogo_id'], unique=False, schema='control_equipos')
    op.create_index('idx_licencias_software_clave_producto', 'licencias_software', ['clave_producto'], unique=False, schema='control_equipos', postgresql_where=sa.text('clave_producto IS NOT NULL'))
    op.create_table('tipos_item_inventario',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('nombre', sa.Text(), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('categoria', sa.Text(), nullable=False),
        sa.Column('unidad_medida', sa.Text(), server_default=sa.text("'Unidad'"), nullable=False),
        sa.Column('marca', sa.Text(), nullable=True),
        sa.Column('modelo', sa.Text(), nullable=True),
        sa.Column('sku', sa.Text(), nullable=True),
        sa.Column('codigo_barras', sa.Text(), nullable=True),
        sa.Column('modelos_equipo_compatibles', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('proveedor_preferido_id', sa.UUID(), nullable=True),
        sa.Column('stock_minimo', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('perecedero', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint("categoria IN ('Consumible', 'Parte Repuesto', 'Accesorio', 'Otro')", name='tipos_item_inventario_categoria_check'),
        sa.CheckConstraint('stock_minimo >= 0', name='tipos_item_inventario_stock_minimo_check'),
        sa.ForeignKeyConstraint(['proveedor_preferido_id'], ['control_equipos.proveedores.id'], name=op.f('fk_tipos_item_inventario_proveedor_preferido_id_proveedores'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tipos_item_inventario')),
        sa.UniqueConstraint('codigo_barras', name=op.f('uq_tipos_item_inventario_codigo_barras')),
        sa.UniqueConstraint('nombre', name=op.f('uq_tipos_item_inventario_nombre')),
        sa.UniqueConstraint('sku', name=op.f('uq_tipos_item_inventario_sku')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_tipos_item_inventario_categoria'), 'tipos_item_inventario', ['categoria'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_tipos_item_inventario_codigo_barras'), 'tipos_item_inventario', ['codigo_barras'], unique=True, schema='control_equipos', postgresql_where=sa.text('codigo_barras IS NOT NULL'))
    op.create_index(op.f('ix_control_equipos_tipos_item_inventario_nombre'), 'tipos_item_inventario', ['nombre'], unique=True, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_tipos_item_inventario_sku'), 'tipos_item_inventario', ['sku'], unique=True, schema='control_equipos', postgresql_where=sa.text('sku IS NOT NULL'))
    op.create_table('usuarios',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('nombre_usuario', sa.Text(), nullable=False),
        sa.Column('contrasena', sa.Text(), nullable=False),
        sa.Column('rol_id', sa.UUID(), nullable=False),
        sa.Column('email', sa.Text(), nullable=True),
        sa.Column('token_temporal', sa.UUID(), nullable=True),
        sa.Column('token_expiracion', sa.DateTime(timezone=True), nullable=True),
        sa.Column('intentos_fallidos', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('bloqueado', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('ultimo_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('requiere_cambio_contrasena', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.CheckConstraint("email IS NULL OR email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'", name='check_email_format'),
        sa.ForeignKeyConstraint(['rol_id'], ['control_equipos.roles.id'], name=op.f('fk_usuarios_rol_id_roles'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_usuarios')),
        sa.UniqueConstraint('email', name=op.f('uq_usuarios_email')),
        sa.UniqueConstraint('nombre_usuario', name=op.f('uq_usuarios_nombre_usuario')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_usuarios_email'), 'usuarios', ['email'], unique=True, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_usuarios_nombre_usuario'), 'usuarios', ['nombre_usuario'], unique=True, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_usuarios_rol_id'), 'usuarios', ['rol_id'], unique=False, schema='control_equipos')
    op.create_table('equipo_componentes',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('equipo_padre_id', sa.UUID(), nullable=False),
        sa.Column('equipo_componente_id', sa.UUID(), nullable=False),
        sa.Column('tipo_relacion', sa.Text(), server_default=sa.text("'componente'"), nullable=True),
        sa.Column('cantidad', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint('cantidad > 0', name='equipo_componentes_cantidad_check'),
        sa.CheckConstraint('equipo_padre_id <> equipo_componente_id', name='check_no_self_component'),
        sa.CheckConstraint("tipo_relacion IN ('componente', 'conectado_a', 'parte_de', 'accesorio')", name='equipo_componentes_tipo_relacion_check'),
        sa.ForeignKeyConstraint(['equipo_componente_id'], ['control_equipos.equipos.id'], name=op.f('fk_equipo_componentes_equipo_componente_id_equipos'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['equipo_padre_id'], ['control_equipos.equipos.id'], name=op.f('fk_equipo_componentes_equipo_padre_id_equipos'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_equipo_componentes')),
        sa.UniqueConstraint('equipo_padre_id', 'equipo_componente_id', 'tipo_relacion', name='uq_componente'),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_equipo_componentes_equipo_componente_id'), 'equipo_componentes', ['equipo_componente_id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_equipo_componentes_equipo_padre_id'), 'equipo_componentes', ['equipo_padre_id'], unique=False, schema='control_equipos')
    op.create_table('inventario_stock',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tipo_item_id', sa.UUID(), nullable=False),
        sa.Column('ubicacion', sa.Text(), server_default=sa.text("'Almacén Principal'"), nullable=False),
        sa.Column('lote', sa.Text(), server_default=sa.text("'N/A'"), nullable=False),
        sa.Column('fecha_caducidad', sa.Date(), nullable=True),
        sa.Column('cantidad_actual', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('costo_promedio_ponderado', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('ultima_actualizacion', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint('cantidad_actual >= 0', name='inventario_stock_cantidad_actual_check'),
        sa.ForeignKeyConstraint(['tipo_item_id'], ['control_equipos.tipos_item_inventario.id'], name=op.f('fk_inventario_stock_tipo_item_id_tipos_item_inventario'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_inventario_stock')),
        sa.UniqueConstraint('tipo_item_id', 'ubicacion', 'lote', name='uq_item_ubicacion_lote'),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_inventario_stock_fecha_caducidad'), 'inventario_stock', ['fecha_caducidad'], unique=False, schema='control_equipos', postgresql_where=sa.text('fecha_caducidad IS NOT NULL'))
    op.create_index(op.f('ix_control_equipos_inventario_stock_tipo_item_id'), 'inventario_stock', ['tipo_item_id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_inventario_stock_ubicacion'), 'inventario_stock', ['ubicacion'], unique=False, schema='control_equipos')
    op.create_table('login_logs',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('usuario_id', sa.UUID(), nullable=True),
        sa.Column('nombre_usuario_intento', sa.Text(), nullable=True),
        sa.Column('intento', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('exito', sa.Boolean(), nullable=True),
        sa.Column('ip_origen', sa.Text(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('motivo_fallo', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['usuario_id'], ['control_equipos.usuarios.id'], name=op.f('fk_login_logs_usuario_id_usuarios'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_login_logs')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_login_logs_intento'), 'login_logs', ['intento'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_login_logs_ip_origen'), 'login_logs', ['ip_origen'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_login_logs_usuario_id'), 'login_logs', ['usuario_id'], unique=False, schema='control_equipos')
    op.create_index('idx_login_logs_exito_intento', 'login_logs', ['exito', 'intento'], unique=False, schema='control_equipos')
    op.create_table('mantenimiento',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('equipo_id', sa.UUID(), nullable=False),
        sa.Column('tipo_mantenimiento_id', sa.UUID(), nullable=False),
        sa.Column('fecha_programada', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fecha_inicio', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fecha_finalizacion', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fecha_proximo_mantenimiento', sa.DateTime(timezone=True), nullable=True),
        sa.Column('costo_estimado', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('costo_real', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('tecnico_responsable', sa.Text(), nullable=False),
        sa.Column('proveedor_servicio_id', sa.UUID(), nullable=True),
        sa.Column('estado', sa.Text(), server_default=sa.text("'Programado'"), nullable=True),
        sa.Column('prioridad', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('texto_busqueda', postgresql.TSVECTOR(), nullable=True),
        sa.CheckConstraint('costo_real IS NULL OR costo_real >= 0', name='mantenimiento_costo_real_check'),
        sa.CheckConstraint("estado IN ('Programado', 'En Proceso', 'Completado', 'Cancelado', 'Pendiente Aprobacion', 'Requiere Piezas', 'Pausado')", name='mantenimiento_estado_check'),
        sa.ForeignKeyConstraint(['equipo_id'], ['control_equipos.equipos.id'], name=op.f('fk_mantenimiento_equipo_id_equipos'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['proveedor_servicio_id'], ['control_equipos.proveedores.id'], name=op.f('fk_mantenimiento_proveedor_servicio_id_proveedores'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tipo_mantenimiento_id'], ['control_equipos.tipos_mantenimiento.id'], name=op.f('fk_mantenimiento_tipo_mantenimiento_id_tipos_mantenimiento'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_mantenimiento')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_mantenimiento_equipo_id'), 'mantenimiento', ['equipo_id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_mantenimiento_estado'), 'mantenimiento', ['estado'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_mantenimiento_proveedor_servicio_id'), 'mantenimiento', ['proveedor_servicio_id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_mantenimiento_tipo_mantenimiento_id'), 'mantenimiento', ['tipo_mantenimiento_id'], unique=False, schema='control_equipos')
    op.create_index('idx_mantenimiento_fecha_finalizacion', 'mantenimiento', ['fecha_finalizacion'], unique=False, schema='control_equipos', postgresql_where=sa.text('fecha_finalizacion IS NOT NULL'))
    op.create_index('idx_mantenimiento_fecha_inicio', 'mantenimiento', ['fecha_inicio'], unique=False, schema='control_equipos', postgresql_where=sa.text('fecha_inicio IS NOT NULL'))
    op.create_index('idx_mantenimiento_fecha_programada', 'mantenimiento', ['fecha_programada'], unique=False, schema='control_equipos', postgresql_where=sa.text('fecha_programada IS NOT NULL'))
    op.create_index('idx_mantenimiento_fecha_proximo', 'mantenimiento', ['fecha_proximo_mantenimiento'], unique=False, schema='control_equipos', postgresql_where=sa.text('fecha_proximo_mantenimiento IS NOT NULL'))
    op.create_index('idx_mantenimiento_prioridad', 'mantenimiento', ['prioridad'], unique=False, schema='control_equipos')
    op.create_index('idx_mantenimiento_texto_busqueda', 'mantenimiento', ['texto_busqueda'], unique=False, schema='control_equipos', postgresql_using='gin')
    op.create_table('movimientos',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('equipo_id', sa.UUID(), nullable=False),
        sa.Column('usuario_id', sa.UUID(), nullable=True),
        sa.Column('tipo_movimiento', sa.Text(), nullable=False),
        sa.Column('fecha_hora', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('fecha_prevista_retorno', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fecha_retorno', sa.DateTime(timezone=True), nullable=True),
        sa.Column('origen', sa.Text(), nullable=True),
        sa.Column('destino', sa.Text(), nullable=True),
        sa.Column('proposito', sa.Text(), nullable=True),
        sa.Column('autorizado_por', sa.UUID(), nullable=True),
        sa.Column('recibido_por', sa.Text(), nullable=True),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('estado', sa.Text(), server_default=sa.text("'Completado'"), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint("(tipo_movimiento LIKE '%Asignacion%' AND origen IS NOT NULL AND destino IS NOT NULL) OR (tipo_movimiento NOT LIKE '%Asignacion%')", name='check_origen_destino_asignacion'),
        sa.CheckConstraint("(tipo_movimiento = 'Entrada' AND origen IS NOT NULL) OR (tipo_movimiento <> 'Entrada')", name='check_origen_entrada'),
        sa.CheckConstraint("(tipo_movimiento = 'Salida Temporal' AND fecha_prevista_retorno IS NOT NULL) OR (tipo_movimiento <> 'Salida Temporal')", name='check_retorno_salida_temporal'),
        sa.CheckConstraint("estado IN ('Pendiente', 'Autorizado', 'En Proceso', 'Completado', 'Cancelado', 'Rechazado')", name='movimientos_estado_check'),
        sa.CheckConstraint("tipo_movimiento IN ('Salida Temporal', 'Salida Definitiva', 'Entrada', 'Asignacion Interna', 'Transferencia Bodega')", name='movimientos_tipo_movimiento_check'),
        sa.ForeignKeyConstraint(['autorizado_por'], ['control_equipos.usuarios.id'], name=op.f('fk_movimientos_autorizado_por_usuarios'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['equipo_id'], ['control_equipos.equipos.id'], name=op.f('fk_movimientos_equipo_id_equipos'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['control_equipos.usuarios.id'], name=op.f('fk_movimientos_usuario_id_usuarios'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_movimientos')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_movimientos_autorizado_por'), 'movimientos', ['autorizado_por'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_movimientos_equipo_id'), 'movimientos', ['equipo_id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_movimientos_estado'), 'movimientos', ['estado'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_movimientos_fecha_hora'), 'movimientos', ['fecha_hora'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_movimientos_tipo_movimiento'), 'movimientos', ['tipo_movimiento'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_movimientos_usuario_id'), 'movimientos', ['usuario_id'], unique=False, schema='control_equipos')
    op.create_table('notificaciones',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('usuario_id', sa.UUID(), nullable=False),
        sa.Column('mensaje', sa.Text(), nullable=False),
        sa.Column('leido', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('fecha_leido', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tipo', sa.Text(), nullable=True),
        sa.Column('urgencia', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('referencia_id', sa.UUID(), nullable=True),
        sa.Column('referencia_tabla', sa.Text(), nullable=True),
        sa.CheckConstraint("tipo IN ('info', 'alerta', 'error', 'mantenimiento', 'reserva', 'sistema')", name='notificaciones_tipo_check'),
        sa.ForeignKeyConstraint(['usuario_id'], ['control_equipos.usuarios.id'], name=op.f('fk_notificaciones_usuario_id_usuarios'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_notificaciones')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_notificaciones_created_at'), 'notificaciones', ['created_at'], unique=False, schema='control_equipos')
    op.create_index('idx_notificaciones_usuario_id_leido_urgencia', 'notificaciones', ['usuario_id', 'leido', 'urgencia', 'created_at'], unique=False, schema='control_equipos')
    op.create_table('reservas_equipo',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('equipo_id', sa.UUID(), nullable=False),
        sa.Column('usuario_solicitante_id', sa.UUID(), nullable=False),
        sa.Column('fecha_hora_inicio', sa.DateTime(timezone=True), nullable=False),
        sa.Column('fecha_hora_fin', sa.DateTime(timezone=True), nullable=False),
        sa.Column('proposito', sa.Text(), nullable=True),
        sa.Column('estado', sa.Text(), server_default=sa.text("'Confirmada'"), nullable=False),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.Column('notas_administrador', sa.Text(), nullable=True),
        sa.Column('notas_devolucion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('aprobado_por_id', sa.UUID(), nullable=True),
        sa.Column('fecha_aprobacion', sa.DateTime(timezone=True), nullable=True),
        sa.Column('check_in_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('check_out_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('fecha_hora_fin > fecha_hora_inicio', name='check_fechas_reserva'),
        sa.CheckConstraint("estado IN ('Confirmada', 'Pendiente Aprobacion', 'Cancelada', 'Cancelada por Usuario', 'Cancelada por Gestor', 'Rechazada', 'Finalizada', 'En Curso')", name='reservas_equipo_estado_check'),
        sa.ForeignKeyConstraint(['aprobado_por_id'], ['control_equipos.usuarios.id'], name=op.f('fk_reservas_equipo_aprobado_por_id_usuarios'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['equipo_id'], ['control_equipos.equipos.id'], name=op.f('fk_reservas_equipo_equipo_id_equipos'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_solicitante_id'], ['control_equipos.usuarios.id'], name=op.f('fk_reservas_equipo_usuario_solicitante_id_usuarios'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_reservas_equipo')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_reservas_equipo_equipo_id'), 'reservas_equipo', ['equipo_id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_reservas_equipo_estado'), 'reservas_equipo', ['estado'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_reservas_equipo_usuario_solicitante_id'), 'reservas_equipo', ['usuario_solicitante_id'], unique=False, schema='control_equipos')
    op.create_index('idx_reservas_equipo_rango_gist', 'reservas_equipo', ['equipo_id', sa.text("tstzrange(fecha_hora_inicio, fecha_hora_fin, '()')")], unique=False, schema='control_equipos', postgresql_using='gist')
    op.create_index('idx_reservas_fechas', 'reservas_equipo', ['fecha_hora_inicio', 'fecha_hora_fin'], unique=False, schema='control_equipos')
    op.create_table('roles_permisos',
        sa.Column('rol_id', sa.UUID(), nullable=False),
        sa.Column('permiso_id', sa.UUID(), nullable=False),
        sa.Column('otorgado_por', sa.UUID(), nullable=True),
        sa.Column('fecha_otorgamiento', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['otorgado_por'], ['control_equipos.usuarios.id'], name=op.f('fk_roles_permisos_otorgado_por_usuarios'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['permiso_id'], ['control_equipos.permisos.id'], name=op.f('fk_roles_permisos_permiso_id_permisos'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rol_id'], ['control_equipos.roles.id'], name=op.f('fk_roles_permisos_rol_id_roles'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('rol_id', 'permiso_id', name=op.f('pk_roles_permisos')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_roles_permisos_permiso_id'), 'roles_permisos', ['permiso_id'], unique=False, schema='control_equipos')
    op.create_table('asignaciones_licencia',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('licencia_id', sa.UUID(), nullable=False),
        sa.Column('equipo_id', sa.UUID(), nullable=True),
        sa.Column('usuario_id', sa.UUID(), nullable=True),
        sa.Column('fecha_asignacion', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('instalado', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.CheckConstraint('NOT (equipo_id IS NOT NULL AND usuario_id IS NOT NULL)', name='check_asignacion_exclusiva'),
        sa.CheckConstraint('equipo_id IS NOT NULL OR usuario_id IS NOT NULL', name='check_asignacion_target'),
        sa.ForeignKeyConstraint(['equipo_id'], ['control_equipos.equipos.id'], name=op.f('fk_asignaciones_licencia_equipo_id_equipos'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['licencia_id'], ['control_equipos.licencias_software.id'], name=op.f('fk_asignaciones_licencia_licencia_id_licencias_software'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['control_equipos.usuarios.id'], name=op.f('fk_asignaciones_licencia_usuario_id_usuarios'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_asignaciones_licencia')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_asignaciones_licencia_equipo_id'), 'asignaciones_licencia', ['equipo_id'], unique=False, schema='control_equipos', postgresql_where=sa.text('equipo_id IS NOT NULL'))
    op.create_index(op.f('ix_control_equipos_asignaciones_licencia_licencia_id'), 'asignaciones_licencia', ['licencia_id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_asignaciones_licencia_usuario_id'), 'asignaciones_licencia', ['usuario_id'], unique=False, schema='control_equipos', postgresql_where=sa.text('usuario_id IS NOT NULL'))
    op.create_index('uq_asignacion_licencia_equipo', 'asignaciones_licencia', ['licencia_id', 'equipo_id'], unique=True, schema='control_equipos', postgresql_where=sa.text('equipo_id IS NOT NULL'))
    op.create_index('uq_asignacion_licencia_usuario', 'asignaciones_licencia', ['licencia_id', 'usuario_id'], unique=True, schema='control_equipos', postgresql_where=sa.text('usuario_id IS NOT NULL'))
    op.create_table('documentacion',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('equipo_id', sa.UUID(), nullable=True),
        sa.Column('mantenimiento_id', sa.UUID(), nullable=True),
        sa.Column('licencia_id', sa.UUID(), nullable=True),
        sa.Column('tipo_documento_id', sa.UUID(), nullable=False),
        sa.Column('titulo', sa.Text(), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('enlace', sa.Text(), nullable=False),
        sa.Column('nombre_archivo', sa.Text(), nullable=True),
        sa.Column('mime_type', sa.Text(), nullable=True),
        sa.Column('tamano_bytes', sa.BigInteger(), nullable=True),
        sa.Column('fecha_subida', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('subido_por', sa.UUID(), nullable=True),
        sa.Column('estado', sa.Text(), server_default=sa.text("'Pendiente'"), nullable=True),
        sa.Column('verificado_por', sa.UUID(), nullable=True),
        sa.Column('fecha_verificacion', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notas_verificacion', sa.Text(), nullable=True),
        sa.Column('texto_busqueda', postgresql.TSVECTOR(), nullable=True),
        sa.CheckConstraint("estado IN ('Pendiente', 'Verificado', 'Rechazado')", name='documentacion_estado_check'),
        sa.ForeignKeyConstraint(['equipo_id'], ['control_equipos.equipos.id'], name=op.f('fk_documentacion_equipo_id_equipos'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['licencia_id'], ['control_equipos.licencias_software.id'], name=op.f('fk_documentacion_licencia_id_licencias_software'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['mantenimiento_id'], ['control_equipos.mantenimiento.id'], name=op.f('fk_documentacion_mantenimiento_id_mantenimiento'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['subido_por'], ['control_equipos.usuarios.id'], name=op.f('fk_documentacion_subido_por_usuarios'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tipo_documento_id'], ['control_equipos.tipos_documento.id'], name=op.f('fk_documentacion_tipo_documento_id_tipos_documento'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['verificado_por'], ['control_equipos.usuarios.id'], name=op.f('fk_documentacion_verificado_por_usuarios'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_documentacion')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_documentacion_equipo_id'), 'documentacion', ['equipo_id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_documentacion_estado'), 'documentacion', ['estado'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_documentacion_subido_por'), 'documentacion', ['subido_por'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_documentacion_tipo_documento_id'), 'documentacion', ['tipo_documento_id'], unique=False, schema='control_equipos')
    op.create_index('idx_documentacion_licencia_id', 'documentacion', ['licencia_id'], unique=False, schema='control_equipos', postgresql_where=sa.text('licencia_id IS NOT NULL'))
    op.create_index('idx_documentacion_mantenimiento_id', 'documentacion', ['mantenimiento_id'], unique=False, schema='control_equipos', postgresql_where=sa.text('mantenimiento_id IS NOT NULL'))
    op.create_index('idx_documentacion_texto_busqueda', 'documentacion', ['texto_busqueda'], unique=False, schema='control_equipos', postgresql_using='gin')
    op.create_index('idx_documentacion_titulo', 'documentacion', ['titulo'], unique=False, schema='control_equipos')
    op.create_table('inventario_movimientos',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tipo_item_id', sa.UUID(), nullable=False),
        sa.Column('tipo_movimiento', sa.Text(), nullable=False),
        sa.Column('cantidad', sa.Integer(), nullable=False),
        sa.Column('ubicacion_origen', sa.Text(), nullable=True),
        sa.Column('ubicacion_destino', sa.Text(), nullable=True),
        sa.Column('lote_origen', sa.Text(), server_default=sa.text("'N/A'"), nullable=True),
        sa.Column('lote_destino', sa.Text(), server_default=sa.text("'N/A'"), nullable=True),
        sa.Column('equipo_asociado_id', sa.UUID(), nullable=True),
        sa.Column('mantenimiento_id', sa.UUID(), nullable=True),
        sa.Column('usuario_id', sa.UUID(), nullable=True),
        sa.Column('fecha_hora', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('costo_unitario', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('motivo_ajuste', sa.Text(), nullable=True),
        sa.Column('referencia_externa', sa.Text(), nullable=True),
        sa.Column('referencia_transferencia', sa.UUID(), nullable=True),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.CheckConstraint('cantidad > 0', name='inventario_movimientos_cantidad_check'),
        sa.CheckConstraint("tipo_movimiento IN ('Entrada Compra', 'Salida Uso', 'Salida Descarte', 'Ajuste Positivo', 'Ajuste Negativo', 'Transferencia Salida', 'Transferencia Entrada', 'Devolucion Proveedor', 'Devolucion Interna')", name='inventario_movimientos_tipo_movimiento_check'),
        sa.ForeignKeyConstraint(['equipo_asociado_id'], ['control_equipos.equipos.id'], name=op.f('fk_inventario_movimientos_equipo_asociado_id_equipos'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['mantenimiento_id'], ['control_equipos.mantenimiento.id'], name=op.f('fk_inventario_movimientos_mantenimiento_id_mantenimiento'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tipo_item_id'], ['control_equipos.tipos_item_inventario.id'], name=op.f('fk_inventario_movimientos_tipo_item_id_tipos_item_inventario'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['usuario_id'], ['control_equipos.usuarios.id'], name=op.f('fk_inventario_movimientos_usuario_id_usuarios'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_inventario_movimientos')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_inventario_movimientos_equipo_asociado_id'), 'inventario_movimientos', ['equipo_asociado_id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_inventario_movimientos_fecha_hora'), 'inventario_movimientos', ['fecha_hora'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_inventario_movimientos_mantenimiento_id'), 'inventario_movimientos', ['mantenimiento_id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_inventario_movimientos_tipo_item_id'), 'inventario_movimientos', ['tipo_item_id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_inventario_movimientos_tipo_movimiento'), 'inventario_movimientos', ['tipo_movimiento'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_inventario_movimientos_usuario_id'), 'inventario_movimientos', ['usuario_id'], unique=False, schema='control_equipos')
    op.create_index('idx_inventario_movimientos_ref_transferencia', 'inventario_movimientos', ['referencia_transferencia'], unique=False, schema='control_equipos', postgresql_where=sa.text('referencia_transferencia IS NOT NULL'))
    # ### FIN DE COMANDOS AUTOGENERADOS POR ALEMBIC ###

    # === PASO 3: LÓGICA PERSONALIZADA (Funciones, Vistas, Triggers) ===
    # Aquí ejecutamos todo el SQL que Alembic no puede generar automáticamente.

    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.gestionar_particiones_audit_log()
    RETURNS VOID AS $$
    DECLARE
        v_current_partition_name TEXT;
        v_next_partition_name TEXT;
        v_from_date_current TEXT;
        v_to_date_current TEXT;
        v_from_date_next TEXT;
        v_to_date_next TEXT;
    BEGIN
        v_from_date_current := to_char(NOW(), 'YYYY-MM-01');
        v_to_date_current := to_char(NOW() + INTERVAL '1 month', 'YYYY-MM-01');
        v_current_partition_name := 'audit_log_y' || to_char(NOW(), 'YYYY') || 'm' || to_char(NOW(), 'MM');
        IF NOT EXISTS (SELECT FROM pg_class WHERE relname = v_current_partition_name) THEN
            EXECUTE format(
                'CREATE TABLE control_equipos.%I PARTITION OF control_equipos.audit_log FOR VALUES FROM (%L) TO (%L);',
                v_current_partition_name, v_from_date_current, v_to_date_current
            );
        END IF;
        v_from_date_next := to_char(NOW() + INTERVAL '1 month', 'YYYY-MM-01');
        v_to_date_next := to_char(NOW() + INTERVAL '2 months', 'YYYY-MM-01');
        v_next_partition_name := 'audit_log_y' || to_char(NOW() + INTERVAL '1 month', 'YYYY') || 'm' || to_char(NOW() + INTERVAL '1 month', 'MM');
        IF NOT EXISTS (SELECT FROM pg_class WHERE relname = v_next_partition_name) THEN
            EXECUTE format(
                'CREATE TABLE control_equipos.%I PARTITION OF control_equipos.audit_log FOR VALUES FROM (%L) TO (%L);',
                v_next_partition_name, v_from_date_next, v_to_date_next
            );
        END IF;
    END;
    $$ LANGUAGE plpgsql;
    """)

    # ---!!! CORRECCIÓN #1: EJECUTAR LA CREACIÓN DE PARTICIONES INICIALES !!!---
    # Este es el paso clave que faltaba y que causaba el error en los tests.
    op.execute("SELECT control_equipos.gestionar_particiones_audit_log();")

    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.audit_trigger_fn()
    RETURNS TRIGGER AS $$
    DECLARE
        v_app_user_id UUID;
    BEGIN
        BEGIN
            v_app_user_id := current_setting('myapp.current_user_id')::UUID;
        EXCEPTION WHEN OTHERS THEN
            v_app_user_id := NULL;
        END;

        IF TG_OP = 'INSERT' THEN
            INSERT INTO control_equipos.audit_log(table_name, operation, new_data, username, app_user_id)
            VALUES (TG_TABLE_NAME, TG_OP, to_jsonb(NEW), session_user, v_app_user_id);
            RETURN NEW;
        ELSIF TG_OP = 'UPDATE' THEN
            IF OLD IS DISTINCT FROM NEW THEN
                INSERT INTO control_equipos.audit_log(table_name, operation, old_data, new_data, username, app_user_id)
                VALUES (TG_TABLE_NAME, TG_OP, to_jsonb(OLD), to_jsonb(NEW), session_user, v_app_user_id);
            END IF;
            RETURN NEW;
        ELSIF TG_OP = 'DELETE' THEN
            INSERT INTO control_equipos.audit_log(table_name, operation, old_data, username, app_user_id)
            VALUES (TG_TABLE_NAME, TG_OP, to_jsonb(OLD), session_user, v_app_user_id);
            RETURN OLD;
        END IF;
        RETURN NULL;
    EXCEPTION
        WHEN OTHERS THEN
            RAISE EXCEPTION '[AUDIT_TRIGGER_FN] - FALLO CRÍTICO DE AUDITORÍA en tabla %: %. La transacción será revertida.', TG_TABLE_NAME, SQLERRM;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.set_audit_user(p_user_id UUID)
    RETURNS VOID AS $$
    BEGIN
        EXECUTE format('SET LOCAL myapp.current_user_id = %L', p_user_id::text);
    EXCEPTION
        WHEN OTHERS THEN
            RAISE EXCEPTION '[SET_AUDIT_USER] - FALLO CRÍTICO al establecer el usuario para auditoría: %. La transacción será revertida.', SQLERRM;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.update_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at := NOW();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION actualizar_busqueda_equipo()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.texto_busqueda =
            setweight(to_tsvector('spanish', COALESCE(NEW.nombre, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.numero_serie, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.codigo_interno, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.marca, '')), 'B') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.modelo, '')), 'B') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.ubicacion_actual, '')), 'C') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.centro_costo, '')), 'C') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.notas, '')), 'D');
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION actualizar_busqueda_documento()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.texto_busqueda =
            setweight(to_tsvector('spanish', COALESCE(NEW.titulo, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.descripcion, '')), 'B') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.nombre_archivo, '')), 'C');
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION actualizar_busqueda_mantenimiento()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.texto_busqueda =
            setweight(to_tsvector('spanish', COALESCE(NEW.tecnico_responsable, '')), 'B') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.observaciones, '')), 'C');
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION actualizar_fecha_proximo_mantenimiento()
    RETURNS TRIGGER AS $$
    DECLARE
        v_periodicidad INTEGER;
        v_fecha_base TIMESTAMPTZ;
    BEGIN
        IF NEW.estado = 'Completado' AND (OLD.estado IS DISTINCT FROM 'Completado' OR TG_OP = 'INSERT') THEN
            SELECT tm.periodicidad_dias INTO v_periodicidad
            FROM control_equipos.tipos_mantenimiento tm
            WHERE tm.id = NEW.tipo_mantenimiento_id AND tm.es_preventivo = TRUE;

            IF FOUND AND v_periodicidad IS NOT NULL THEN
                v_fecha_base := COALESCE(NEW.fecha_finalizacion, NEW.fecha_inicio, NEW.fecha_programada);
                IF v_fecha_base IS NOT NULL THEN
                    NEW.fecha_proximo_mantenimiento := v_fecha_base + (v_periodicidad || ' days')::INTERVAL;
                ELSE
                    NEW.fecha_proximo_mantenimiento := NULL;
                END IF;
            ELSE
                 NEW.fecha_proximo_mantenimiento := NULL;
            END IF;
        ELSIF OLD.estado = 'Completado' AND NEW.estado <> 'Completado' THEN
            NEW.fecha_proximo_mantenimiento := NULL;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.actualizar_inventario_stock_fn()
    RETURNS TRIGGER AS $$
    DECLARE
        v_cantidad_origen_actual INTEGER;
        v_costo_promedio_origen DECIMAL(12, 4);
        v_costo_promedio_destino DECIMAL(12, 4);
        v_cantidad_destino_actual INTEGER;
        v_lote_origen_busqueda TEXT;
        v_lote_destino_busqueda TEXT;
    BEGIN
        v_lote_origen_busqueda := COALESCE(NEW.lote_origen, 'N/A');
        v_lote_destino_busqueda := COALESCE(NEW.lote_destino, 'N/A');

        IF NEW.ubicacion_origen IS NOT NULL THEN
            SELECT cantidad_actual, costo_promedio_ponderado
            INTO v_cantidad_origen_actual, v_costo_promedio_origen
            FROM control_equipos.inventario_stock
            WHERE tipo_item_id = NEW.tipo_item_id
              AND ubicacion = NEW.ubicacion_origen
              AND lote = v_lote_origen_busqueda
            FOR UPDATE;

            IF NOT FOUND OR v_cantidad_origen_actual < NEW.cantidad THEN
                RAISE EXCEPTION 'Stock insuficiente en origen: Item ID %, Ubicación %, Lote %, Cantidad requerida %, Cantidad actual %',
                               NEW.tipo_item_id, NEW.ubicacion_origen, v_lote_origen_busqueda, NEW.cantidad, COALESCE(v_cantidad_origen_actual, 0);
            END IF;

            UPDATE control_equipos.inventario_stock
            SET cantidad_actual = cantidad_actual - NEW.cantidad,
                ultima_actualizacion = NOW()
            WHERE tipo_item_id = NEW.tipo_item_id
              AND ubicacion = NEW.ubicacion_origen
              AND lote = v_lote_origen_busqueda;
        END IF;

        IF NEW.ubicacion_destino IS NOT NULL THEN
            SELECT cantidad_actual, costo_promedio_ponderado
            INTO v_cantidad_destino_actual, v_costo_promedio_destino
            FROM control_equipos.inventario_stock
            WHERE tipo_item_id = NEW.tipo_item_id
              AND ubicacion = NEW.ubicacion_destino
              AND lote = v_lote_destino_busqueda
            FOR UPDATE;

            IF FOUND AND v_cantidad_destino_actual > 0 AND COALESCE(v_costo_promedio_destino, 0) > 0 AND NEW.costo_unitario IS NOT NULL THEN
                v_costo_promedio_destino := ((v_cantidad_destino_actual * v_costo_promedio_destino) + (NEW.cantidad * NEW.costo_unitario)) / (v_cantidad_destino_actual + NEW.cantidad);
            ELSE
                v_costo_promedio_destino := NEW.costo_unitario;
            END IF;

            INSERT INTO control_equipos.inventario_stock (tipo_item_id, ubicacion, lote, cantidad_actual, costo_promedio_ponderado, ultima_actualizacion)
            VALUES (
                NEW.tipo_item_id,
                NEW.ubicacion_destino,
                v_lote_destino_busqueda,
                NEW.cantidad,
                v_costo_promedio_destino,
                NOW()
            )
            ON CONFLICT (tipo_item_id, ubicacion, lote) DO UPDATE
            SET cantidad_actual = inventario_stock.cantidad_actual + EXCLUDED.cantidad_actual,
                costo_promedio_ponderado = EXCLUDED.costo_promedio_ponderado,
                ultima_actualizacion = NOW();
        END IF;

        RETURN NEW;
    EXCEPTION
        WHEN raise_exception THEN RAISE;
        WHEN OTHERS THEN
            RAISE WARNING '[ACTUALIZAR_STOCK_FN] - Error inesperado en Trigger para Item ID %: %', NEW.tipo_item_id, SQLERRM;
            RAISE EXCEPTION 'Error al actualizar stock: %', SQLERRM;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION actualizar_licencia_disponible_fn()
    RETURNS TRIGGER AS $$
    DECLARE
        v_licencia_id UUID;
        v_change INTEGER;
    BEGIN
        IF TG_OP = 'INSERT' THEN
            v_licencia_id := NEW.licencia_id;
            v_change := -1;
        ELSIF TG_OP = 'DELETE' THEN
            v_licencia_id := OLD.licencia_id;
            v_change := 1;
        ELSE
            RETURN NEW;
        END IF;

        UPDATE control_equipos.licencias_software
        SET cantidad_disponible = cantidad_disponible + v_change,
            updated_at = NOW()
        WHERE id = v_licencia_id;

        IF (SELECT cantidad_disponible FROM control_equipos.licencias_software WHERE id = v_licencia_id) < 0 THEN
            RAISE EXCEPTION 'Error de consistencia: Cantidad disponible de licencia no puede ser negativa (Licencia ID: %)', v_licencia_id;
        END IF;

        IF TG_OP = 'INSERT' THEN RETURN NEW; ELSE RETURN OLD; END IF;
    END;
    $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.registrar_movimiento_equipo(
        p_equipo_id UUID,
        p_usuario_id UUID,
        p_tipo_movimiento TEXT,
        p_origen TEXT DEFAULT NULL,
        p_destino TEXT DEFAULT NULL,
        p_proposito TEXT DEFAULT NULL,
        p_fecha_prevista_retorno TIMESTAMPTZ DEFAULT NULL,
        p_recibido_por TEXT DEFAULT NULL,
        p_observaciones TEXT DEFAULT NULL,
        p_autorizado_por UUID DEFAULT NULL
    ) RETURNS UUID AS $$
    DECLARE
        v_movimiento_id UUID;
        v_estado_equipo RECORD;
        v_estado_final_id UUID;
        v_ubicacion_final TEXT;
        v_current_user_has_auth_perm BOOLEAN;
    BEGIN
        SELECT ee.nombre, ee.permite_movimientos, ee.requiere_autorizacion, e.ubicacion_actual, e.estado_id
        INTO v_estado_equipo
        FROM control_equipos.equipos e
        JOIN control_equipos.estados_equipo ee ON e.estado_id = ee.id
        WHERE e.id = p_equipo_id
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Equipo no encontrado (ID: %)', p_equipo_id;
        END IF;

        -- ## ANÁLISIS Y CORRECCIÓN: Lógica de validación reordenada ##
        -- 1. Primero, la validación más general: ¿el estado permite movimientos?
        IF NOT v_estado_equipo.permite_movimientos THEN
            RAISE EXCEPTION 'El equipo con estado "%" no permite movimientos actualmente.', v_estado_equipo.nombre;
        END IF;

        -- 2. Segundo, la validación de autorización.
        -- Si el estado requiere autorización, verificamos si el usuario que autoriza tiene el permiso necesario.
        IF v_estado_equipo.requiere_autorizacion THEN
            IF p_autorizado_por IS NULL THEN
                 RAISE EXCEPTION 'Este movimiento requiere autorización previa.';
            END IF;
            
            SELECT EXISTS (
                SELECT 1 FROM control_equipos.usuarios u
                JOIN control_equipos.roles r ON u.rol_id = r.id
                JOIN control_equipos.roles_permisos rp ON r.id = rp.rol_id
                JOIN control_equipos.permisos p ON rp.permiso_id = p.id
                WHERE u.id = p_autorizado_por AND p.nombre = 'autorizar_movimientos'
            ) INTO v_current_user_has_auth_perm;

            IF NOT v_current_user_has_auth_perm THEN
                RAISE EXCEPTION 'El usuario que autoriza no tiene el permiso ''autorizar_movimientos''.';
            END IF;
        END IF;
        
        -- 3. Finalmente, las validaciones específicas por tipo de movimiento.
        IF p_tipo_movimiento = 'Asignacion Interna' AND v_estado_equipo.nombre <> 'Disponible' THEN
            RAISE EXCEPTION 'Solo se pueden asignar equipos que están en estado "Disponible". Estado actual: "%".', v_estado_equipo.nombre;
        END IF;

        -- El resto de la lógica de la función...
        CASE p_tipo_movimiento
            WHEN 'Salida Temporal' THEN
                SELECT id INTO v_estado_final_id FROM control_equipos.estados_equipo WHERE nombre = 'Prestado';
                v_ubicacion_final := p_destino;
                p_origen := COALESCE(p_origen, v_estado_equipo.ubicacion_actual);
            WHEN 'Salida Definitiva' THEN
                SELECT id INTO v_estado_final_id FROM control_equipos.estados_equipo WHERE nombre = 'Dado de Baja';
                v_ubicacion_final := p_destino;
                p_origen := COALESCE(p_origen, v_estado_equipo.ubicacion_actual);
            WHEN 'Entrada' THEN
                SELECT id INTO v_estado_final_id FROM control_equipos.estados_equipo WHERE nombre = 'Disponible';
                v_ubicacion_final := 'Almacén Principal';
                p_destino := v_ubicacion_final;
            WHEN 'Asignacion Interna' THEN
                SELECT id INTO v_estado_final_id FROM control_equipos.estados_equipo WHERE nombre = 'En Uso';
                v_ubicacion_final := p_destino;
                p_origen := COALESCE(p_origen, v_estado_equipo.ubicacion_actual);
            WHEN 'Transferencia Bodega' THEN
                v_estado_final_id := v_estado_equipo.estado_id;
                v_ubicacion_final := p_destino;
                p_origen := COALESCE(p_origen, v_estado_equipo.ubicacion_actual);
            ELSE
                RAISE EXCEPTION 'Tipo de movimiento no válido: %', p_tipo_movimiento;
        END CASE;

        INSERT INTO control_equipos.movimientos (equipo_id, usuario_id, tipo_movimiento, origen, destino, proposito, fecha_prevista_retorno, recibido_por, observaciones, autorizado_por, estado)
        VALUES (p_equipo_id, p_usuario_id, p_tipo_movimiento, p_origen, p_destino, p_proposito, p_fecha_prevista_retorno, p_recibido_por, p_observaciones, p_autorizado_por, 'Completado')
        RETURNING id INTO v_movimiento_id;

        UPDATE control_equipos.equipos SET estado_id = v_estado_final_id, ubicacion_actual = v_ubicacion_final, updated_at = NOW() WHERE id = p_equipo_id;

        RETURN v_movimiento_id;
    EXCEPTION
        WHEN raise_exception THEN RAISE;
        WHEN OTHERS THEN RAISE EXCEPTION 'Error inesperado al registrar movimiento: %', SQLERRM;
    END;
    $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
    CREATE OR REPLACE FUNCTION buscar_equipos(termino TEXT)
    RETURNS TABLE (
        id UUID,
        nombre TEXT,
        numero_serie TEXT,
        marca TEXT,
        modelo TEXT,
        ubicacion_actual TEXT,
        estado_nombre TEXT,
        relevancia FLOAT4
    ) AS $$
    DECLARE
        query_term TEXT;
    BEGIN
        -- Convertir término en expresión TSQuery para búsqueda de prefijos
        query_term := string_agg(lexeme || ':*', ' & ' ORDER BY positions)
                    FROM unnest(to_tsvector('spanish', termino));

        IF query_term IS NULL OR query_term = '' THEN
            query_term := termino;
        END IF;

        RETURN QUERY
        SELECT
            e.id,
            e.nombre,
            e.numero_serie,
            e.marca,
            e.modelo,
            e.ubicacion_actual,
            ee.nombre AS estado_nombre,
            ts_rank_cd(e.texto_busqueda, to_tsquery('spanish', query_term)) AS relevancia
        FROM control_equipos.equipos e
        LEFT JOIN control_equipos.estados_equipo ee ON e.estado_id = ee.id
        WHERE e.texto_busqueda @@ to_tsquery('spanish', query_term)
        ORDER BY relevancia DESC, e.nombre ASC;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION busqueda_global(termino TEXT)
    RETURNS TABLE (
        tipo TEXT,
        id UUID,
        titulo TEXT,
        descripcion TEXT,
        relevancia FLOAT4,
        metadata JSONB
    ) AS $$
    DECLARE
        query_term TEXT;
    BEGIN
        query_term := string_agg(lexeme || ':*', ' & ' ORDER BY positions)
                    FROM unnest(to_tsvector('spanish', termino));

        IF query_term IS NULL OR query_term = '' THEN
            query_term := termino;
        END IF;

        RETURN QUERY
        SELECT
            'equipo' AS tipo,
            e.id,
            e.nombre AS titulo,
            'Serie: ' || e.numero_serie || ' | Marca: ' || COALESCE(e.marca, 'N/A') || ' | Modelo: ' || COALESCE(e.modelo, 'N/A') AS descripcion,
            ts_rank_cd(e.texto_busqueda, to_tsquery('spanish', query_term)) AS relevancia,
            jsonb_build_object(
                'numero_serie', e.numero_serie,
                'marca', e.marca,
                'modelo', e.modelo,
                'ubicacion', e.ubicacion_actual,
                'estado_id', e.estado_id
            ) AS metadata
        FROM control_equipos.equipos e
        WHERE e.texto_busqueda @@ to_tsquery('spanish', query_term)

        UNION ALL

        SELECT
            'documento',
            d.id,
            d.titulo,
            COALESCE(d.descripcion, 'Sin descripción'),
            ts_rank_cd(d.texto_busqueda, to_tsquery('spanish', query_term)),
            jsonb_build_object(
                'equipo_id', d.equipo_id,
                'tipo_documento_id', d.tipo_documento_id,
                'nombre_archivo', d.nombre_archivo,
                'enlace', d.enlace
            )
        FROM control_equipos.documentacion d
        WHERE d.texto_busqueda @@ to_tsquery('spanish', query_term)

        UNION ALL

        SELECT
            'mantenimiento',
            m.id,
            'Mantenimiento ID: ' || m.id::TEXT,
            'Técnico: ' || m.tecnico_responsable || ' | Obs: ' || COALESCE(m.observaciones, 'N/A'),
            ts_rank_cd(m.texto_busqueda, to_tsquery('spanish', query_term)),
            jsonb_build_object(
                'equipo_id', m.equipo_id,
                'tipo_mantenimiento_id', m.tipo_mantenimiento_id,
                'tecnico', m.tecnico_responsable,
                'fecha_programada', m.fecha_programada,
                'estado', m.estado
            )
        FROM control_equipos.mantenimiento m
        WHERE m.texto_busqueda @@ to_tsquery('spanish', query_term)

        ORDER BY relevancia DESC, tipo ASC, titulo ASC;
    END;
    $$ LANGUAGE plpgsql;
    """)
        
    # === PASO 4: CREACIÓN DE TRIGGERS (dependen de las funciones anteriores) ===
    op.execute("""
    CREATE TRIGGER trg_update_usuario_updated_at
        BEFORE UPDATE ON control_equipos.usuarios
        FOR EACH ROW
        WHEN (OLD IS DISTINCT FROM NEW)
        EXECUTE FUNCTION update_updated_at();
    """)
    op.execute("""
    CREATE TRIGGER trg_update_proveedores_updated_at
        BEFORE UPDATE ON control_equipos.proveedores
        FOR EACH ROW
        WHEN (OLD IS DISTINCT FROM NEW)
        EXECUTE FUNCTION update_updated_at();
    """)
    op.execute("""
    CREATE TRIGGER trg_update_equipo_updated_at
        BEFORE UPDATE ON control_equipos.equipos
        FOR EACH ROW
        WHEN (OLD IS DISTINCT FROM NEW)
        EXECUTE FUNCTION update_updated_at();
    """)
    op.execute("""
    CREATE TRIGGER trg_equipos_texto_busqueda
        BEFORE INSERT OR UPDATE ON equipos
        FOR EACH ROW
        EXECUTE FUNCTION actualizar_busqueda_equipo();
    """)
    op.execute("""
    CREATE TRIGGER trg_documentacion_texto_busqueda
        BEFORE INSERT OR UPDATE ON documentacion
        FOR EACH ROW
        EXECUTE FUNCTION actualizar_busqueda_documento();
    """)
    op.execute("""
    CREATE TRIGGER trg_mantenimiento_texto_busqueda
        BEFORE INSERT OR UPDATE ON mantenimiento
        FOR EACH ROW
        EXECUTE FUNCTION actualizar_busqueda_mantenimiento();
    """)
    op.execute("""
    CREATE TRIGGER trg_update_mantenimiento_updated_at
        BEFORE UPDATE ON control_equipos.mantenimiento
        FOR EACH ROW
        WHEN (OLD IS DISTINCT FROM NEW)
        EXECUTE FUNCTION update_updated_at();
    """)
    op.execute("""
    CREATE TRIGGER trg_actualizar_fecha_proximo_mantenimiento
        BEFORE INSERT OR UPDATE ON mantenimiento
        FOR EACH ROW
        EXECUTE FUNCTION actualizar_fecha_proximo_mantenimiento();
    """)
    op.execute("""
    CREATE TRIGGER trg_update_tipos_item_inv_updated_at
        BEFORE UPDATE ON tipos_item_inventario
        FOR EACH ROW WHEN (OLD IS DISTINCT FROM NEW)
        EXECUTE FUNCTION update_updated_at();
    """)
    op.execute("""
    CREATE TRIGGER trg_actualizar_inventario_stock
        AFTER INSERT ON control_equipos.inventario_movimientos
        FOR EACH ROW
        EXECUTE FUNCTION actualizar_inventario_stock_fn();
    """)
    op.execute("""
    CREATE TRIGGER trg_update_software_catalogo_updated_at
        BEFORE UPDATE ON software_catalogo
        FOR EACH ROW WHEN (OLD IS DISTINCT FROM NEW)
        EXECUTE FUNCTION update_updated_at();
    """)
    op.execute("""
    CREATE TRIGGER trg_update_licencias_software_updated_at
        BEFORE UPDATE ON licencias_software
        FOR EACH ROW WHEN (OLD IS DISTINCT FROM NEW)
        EXECUTE FUNCTION update_updated_at();
    """)
    op.execute("""
    CREATE TRIGGER trg_actualizar_licencia_disponible
        AFTER INSERT OR DELETE ON asignaciones_licencia
        FOR EACH ROW
        EXECUTE FUNCTION actualizar_licencia_disponible_fn();
    """)
    op.execute("""
    CREATE TRIGGER trg_update_reserva_equipo_updated_at
        BEFORE UPDATE ON control_equipos.reservas_equipo
        FOR EACH ROW
        WHEN (OLD IS DISTINCT FROM NEW)
        EXECUTE FUNCTION update_updated_at();
    """)

    # Trigger de auditoría global (se aplica a todas las tablas al final)
    op.execute("""
    DO $$
    DECLARE
        t_name TEXT;
    BEGIN
        FOR t_name IN (
            SELECT table_name
            FROM information_schema.tables
            WHERE
                table_schema = 'control_equipos'
                AND table_name NOT LIKE 'audit_log%'
                AND table_name NOT LIKE 'mv_%'
                AND table_name NOT LIKE 'backup_log%'
                AND table_name <> 'alembic_version'
                AND table_type = 'BASE TABLE'
        )
        LOOP
            EXECUTE format(
                'CREATE TRIGGER %I_audit_trigger
                 AFTER INSERT OR UPDATE OR DELETE
                 ON control_equipos.%I
                 FOR EACH ROW
                 EXECUTE FUNCTION audit_trigger_fn();',
                t_name, t_name
            );
        END LOOP;
    END $$;
    """)

    # === PASO 5: DATOS INICIALES (SEED DATA) ===
    # ---!!! CORRECCIÓN #2: DATOS DE SEMBRADO FIELES AL SQL ORIGINAL !!!---

    # -- Permisos --
    permisos_table = sa.table('permisos', sa.column('nombre', sa.String), sa.column('descripcion', sa.Text))
    op.bulk_insert(permisos_table, [
        {'nombre': 'ver_dashboard', 'descripcion': 'Acceso al dashboard principal'},
        {'nombre': 'ver_equipos', 'descripcion': 'Visualizar lista y detalles de equipos'},
        {'nombre': 'crear_equipos', 'descripcion': 'Registrar nuevos equipos'},
        {'nombre': 'editar_equipos', 'descripcion': 'Modificar información de equipos existentes'},
        {'nombre': 'eliminar_equipos', 'descripcion': 'Eliminar equipos del sistema'},
        {'nombre': 'gestionar_componentes', 'descripcion': 'Añadir/quitar componentes a equipos'},
        {'nombre': 'ver_movimientos', 'descripcion': 'Visualizar historial de movimientos de equipos'},
        {'nombre': 'registrar_movimientos', 'descripcion': 'Registrar salidas, entradas, asignaciones de equipos'},
        {'nombre': 'editar_movimientos', 'descripcion': 'Editar campos de un movimiento ya registrado'},
        {'nombre': 'autorizar_movimientos', 'descripcion': 'Autorizar movimientos de equipos que lo requieran'},
        {'nombre': 'cancelar_movimientos', 'descripcion': 'Cancelar movimientos de equipos pendientes'},
        {'nombre': 'ver_mantenimientos', 'descripcion': 'Visualizar historial y mantenimientos programados'},
        {'nombre': 'programar_mantenimientos', 'descripcion': 'Crear nuevos registros de mantenimiento'},
        {'nombre': 'editar_mantenimientos', 'descripcion': 'Modificar registros de mantenimiento'},
        {'nombre': 'eliminar_mantenimientos', 'descripcion': 'Eliminar registros de mantenimiento'},
        {'nombre': 'ver_documentos', 'descripcion': 'Visualizar documentos asociados'},
        {'nombre': 'subir_documentos', 'descripcion': 'Subir nuevos documentos'},
        {'nombre': 'editar_documentos', 'descripcion': 'Editar metadatos de documentos'},
        {'nombre': 'verificar_documentos', 'descripcion': 'Marcar documentos como verificados/rechazados'},
        {'nombre': 'eliminar_documentos', 'descripcion': 'Eliminar documentos'},
        {'nombre': 'ver_inventario', 'descripcion': 'Consultar stock de consumibles/partes'},
        {'nombre': 'administrar_inventario_tipos', 'descripcion': 'Gestionar catálogo de tipos de items de inventario'},
        {'nombre': 'administrar_inventario_stock', 'descripcion': 'Registrar movimientos de inventario y ajustar stock'},
        {'nombre': 'ver_licencias', 'descripcion': 'Consultar licencias de software y sus asignaciones'},
        {'nombre': 'administrar_licencias', 'descripcion': 'Gestionar licencias de software adquiridas'},
        {'nombre': 'asignar_licencias', 'descripcion': 'Asignar/desasignar licencias a equipos/usuarios'},
        {'nombre': 'administrar_software_catalogo', 'descripcion': 'Gestionar el catálogo de software'},
        {'nombre': 'ver_reservas', 'descripcion': 'Consultar calendario y detalles de reservas de equipos'},
        {'nombre': 'reservar_equipos', 'descripcion': 'Crear y cancelar reservas de equipos propias'},
        {'nombre': 'aprobar_reservas', 'descripcion': 'Aprobar o rechazar reservas de equipos pendientes'},
        {'nombre': 'administrar_usuarios', 'descripcion': 'Gestionar cuentas de usuario (crear, editar, bloquear)'},
        {'nombre': 'administrar_roles', 'descripcion': 'Gestionar roles y sus permisos asignados'},
        {'nombre': 'administrar_catalogos', 'descripcion': 'Gestionar catálogos generales (estados, tipos de doc/mant, etc.)'},
        {'nombre': 'generar_reportes', 'descripcion': 'Generar y descargar reportes del sistema'},
        {'nombre': 'ver_auditoria', 'descripcion': 'Consultar logs de auditoría del sistema'},
        {'nombre': 'configurar_sistema', 'descripcion': 'Modificar configuraciones generales del sistema'},
        {'nombre': 'administrar_sistema', 'descripcion': 'Administración completa del sistema (permiso global)'},
        {'nombre': 'ver_proveedores', 'descripcion': 'Consultar información de proveedores'}
    ])

    # -- Roles --
    roles_table = sa.table('roles', sa.column('nombre', sa.String), sa.column('descripcion', sa.Text))
    op.bulk_insert(roles_table, [
        {'nombre': 'admin', 'descripcion': 'Administrador con acceso total al sistema'},
        {'nombre': 'supervisor', 'descripcion': 'Supervisor con gestión operativa y de recursos'},
        {'nombre': 'auditor', 'descripcion': 'Auditor con permisos de solo lectura y consulta'},
        {'nombre': 'tecnico', 'descripcion': 'Técnico de Mantenimiento o Soporte'},
        {'nombre': 'usuario_regular', 'descripcion': 'Usuario Estándar para operaciones diarias y consulta'},
        {'nombre': 'tester', 'descripcion': 'Rol para pruebas funcionales y de sistema'}
    ])
    
    op.execute("""
        -- Permisos para Rol: admin (TODOS LOS PERMISOS)
        INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id)
        SELECT r.id, p.id
        FROM control_equipos.roles r, control_equipos.permisos p
        WHERE r.nombre = 'admin'
        ON CONFLICT (rol_id, permiso_id) DO NOTHING;
    """)

    op.execute("""
        -- Permisos para Rol: supervisor
        INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id)
        SELECT r.id, p.id
        FROM control_equipos.roles r, control_equipos.permisos p
        WHERE r.nombre = 'supervisor' AND p.nombre IN (
            'ver_dashboard',
            'ver_equipos', 'crear_equipos', 'editar_equipos', 'eliminar_equipos', 'gestionar_componentes',
            'ver_movimientos', 'registrar_movimientos', 'autorizar_movimientos', 'cancelar_movimientos', 'editar_movimientos',
            'ver_mantenimientos', 'programar_mantenimientos', 'editar_mantenimientos', 'eliminar_mantenimientos',
            'ver_documentos', 'subir_documentos', 'editar_documentos', 'verificar_documentos', 'eliminar_documentos',
            'ver_inventario', 'administrar_inventario_tipos', 'administrar_inventario_stock',
            'ver_licencias', 'administrar_licencias', 'asignar_licencias', 'administrar_software_catalogo',
            'ver_reservas', 'reservar_equipos', 'aprobar_reservas',
            'generar_reportes',
            'ver_proveedores',
            'administrar_catalogos',
            'administrar_usuarios'
        ) ON CONFLICT (rol_id, permiso_id) DO NOTHING;
    """)

    op.execute("""
        -- Permisos para Rol: auditor
        INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id)
        SELECT r.id, p.id
        FROM control_equipos.roles r, control_equipos.permisos p
        WHERE r.nombre = 'auditor' AND p.nombre IN (
            'ver_dashboard', 'ver_equipos', 'ver_movimientos', 'ver_mantenimientos',
            'ver_documentos', 'ver_inventario', 'ver_licencias', 'ver_reservas',
            'ver_proveedores', 'ver_auditoria', 'generar_reportes'
        ) ON CONFLICT (rol_id, permiso_id) DO NOTHING;
    """)

    op.execute("""
        -- Permisos para Rol: tecnico
        INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id)
        SELECT r.id, p.id
        FROM control_equipos.roles r, control_equipos.permisos p
        WHERE r.nombre = 'tecnico' AND p.nombre IN (
            'ver_dashboard', 'ver_equipos', 'gestionar_componentes', 'ver_movimientos',
            'registrar_movimientos', 'ver_mantenimientos', 'programar_mantenimientos',
            'editar_mantenimientos', 'ver_documentos', 'subir_documentos',
            'ver_inventario', 'ver_licencias', 'ver_reservas', 'ver_proveedores'
        ) ON CONFLICT (rol_id, permiso_id) DO NOTHING;
    """)

    op.execute("""
        -- Permisos para Rol: usuario_regular
        INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id)
        SELECT r.id, p.id
        FROM control_equipos.roles r, control_equipos.permisos p
        WHERE r.nombre = 'usuario_regular' AND p.nombre IN (
            'ver_dashboard', 'ver_equipos', 'ver_movimientos',
            'ver_mantenimientos', 'ver_documentos', 'subir_documentos',
            'ver_inventario', 'ver_licencias', 'ver_reservas',
            'reservar_equipos', 'ver_proveedores'
        ) ON CONFLICT (rol_id, permiso_id) DO NOTHING;
    """)

    op.execute("""
        -- Permisos para Rol: tester
        INSERT INTO control_equipos.roles_permisos (rol_id, permiso_id)
        SELECT r.id, p.id
        FROM control_equipos.roles r, control_equipos.permisos p
        WHERE r.nombre = 'tester' AND p.nombre IN (
            'ver_dashboard',
            'ver_equipos', 'crear_equipos', 'editar_equipos', 'eliminar_equipos',
            'gestionar_componentes',
            'ver_movimientos', 'registrar_movimientos', 'autorizar_movimientos', 'cancelar_movimientos',
            'ver_mantenimientos', 'programar_mantenimientos', 'editar_mantenimientos', 'eliminar_mantenimientos',
            'ver_documentos', 'subir_documentos', 'editar_documentos', 'verificar_documentos', 'eliminar_documentos',
            'ver_inventario', 'administrar_inventario_tipos', 'administrar_inventario_stock',
            'ver_licencias', 'administrar_licencias', 'asignar_licencias',
            'administrar_software_catalogo',
            'ver_reservas', 'reservar_equipos', 'aprobar_reservas',
            'ver_proveedores',
            'administrar_catalogos',
            'generar_reportes',
            'ver_auditoria'
        ) ON CONFLICT (rol_id, permiso_id) DO NOTHING;
    """)

    # -- Estados de Equipo --
    estados_equipo_table = sa.table('estados_equipo',
        sa.column('nombre', sa.String), sa.column('descripcion', sa.Text),
        sa.column('permite_movimientos', sa.Boolean), sa.column('requiere_autorizacion', sa.Boolean),
        sa.column('es_estado_final', sa.Boolean), sa.column('color_hex', sa.String)
    )
    op.bulk_insert(estados_equipo_table, [
        {'nombre': 'Disponible', 'descripcion': 'Listo para ser usado o asignado', 'permite_movimientos': True, 'requiere_autorizacion': False, 'es_estado_final': False, 'color_hex': '#4CAF50'},
        {'nombre': 'En Uso', 'descripcion': 'Asignado a un usuario o ubicación específica', 'permite_movimientos': True, 'requiere_autorizacion': False, 'es_estado_final': False, 'color_hex': '#2196F3'},
        {'nombre': 'Prestado', 'descripcion': 'Fuera de las instalaciones temporalmente', 'permite_movimientos': False, 'requiere_autorizacion': False, 'es_estado_final': False, 'color_hex': '#FF9800'},
        {'nombre': 'En Mantenimiento', 'descripcion': 'En proceso de mantenimiento preventivo/correctivo', 'permite_movimientos': False, 'requiere_autorizacion': False, 'es_estado_final': False, 'color_hex': '#FFC107'},
        {'nombre': 'En Reparación', 'descripcion': 'Enviado a servicio técnico externo', 'permite_movimientos': False, 'requiere_autorizacion': False, 'es_estado_final': False, 'color_hex': '#FF5722'},
        {'nombre': 'Averiado', 'descripcion': 'Requiere mantenimiento/reparación', 'permite_movimientos': False, 'requiere_autorizacion': True, 'es_estado_final': False, 'color_hex': '#F44336'},
        {'nombre': 'En Cuarentena', 'descripcion': 'Bajo evaluación o desinfección', 'permite_movimientos': False, 'requiere_autorizacion': True, 'es_estado_final': False, 'color_hex': '#9E9E9E'},
        {'nombre': 'Reservado', 'descripcion': 'Apartado para un uso futuro específico', 'permite_movimientos': False, 'requiere_autorizacion': True, 'es_estado_final': False, 'color_hex': '#607D8B'},
        {'nombre': 'En Tránsito', 'descripcion': 'Moviéndose entre ubicaciones', 'permite_movimientos': False, 'requiere_autorizacion': False, 'es_estado_final': False, 'color_hex': '#795548'},
        {'nombre': 'Extraviado', 'descripcion': 'Ubicación desconocida', 'permite_movimientos': False, 'requiere_autorizacion': True, 'es_estado_final': False, 'color_hex': '#000000'},
        {'nombre': 'Dado de Baja', 'descripcion': 'Retirado del servicio permanentemente', 'permite_movimientos': False, 'requiere_autorizacion': True, 'es_estado_final': True, 'color_hex': '#E0E0E0'}
    ])

    # -- Tipos de Documento --
    tipos_documento_table = sa.table('tipos_documento',
        sa.column('nombre', sa.String), sa.column('descripcion', sa.Text),
        sa.column('requiere_verificacion', sa.Boolean), sa.column('formato_permitido', postgresql.ARRAY(sa.String))
    )
    op.bulk_insert(tipos_documento_table, [
        {'nombre': 'Factura Compra', 'descripcion': 'Comprobante de adquisición', 'requiere_verificacion': True, 'formato_permitido': ['pdf', 'jpg', 'png', 'xml']},
        {'nombre': 'Manual Usuario', 'descripcion': 'Instrucciones de operación', 'requiere_verificacion': False, 'formato_permitido': ['pdf', 'docx']},
        {'nombre': 'Manual Servicio', 'descripcion': 'Instrucciones técnicas de reparación', 'requiere_verificacion': False, 'formato_permitido': ['pdf']},
        {'nombre': 'Ficha Técnica', 'descripcion': 'Especificaciones del fabricante', 'requiere_verificacion': True, 'formato_permitido': ['pdf']},
        {'nombre': 'Garantía', 'descripcion': 'Documento de cobertura de garantía', 'requiere_verificacion': True, 'formato_permitido': ['pdf', 'jpg']},
        {'nombre': 'Certificado Calibración', 'descripcion': 'Resultado de calibración periódica', 'requiere_verificacion': True, 'formato_permitido': ['pdf']},
        {'nombre': 'Reporte Mantenimiento', 'descripcion': 'Informe de servicio realizado', 'requiere_verificacion': False, 'formato_permitido': ['pdf', 'docx']},
        {'nombre': 'Póliza Seguro', 'descripcion': 'Cobertura de seguro del equipo', 'requiere_verificacion': True, 'formato_permitido': ['pdf']},
        {'nombre': 'Fotografía', 'descripcion': 'Imagen del equipo', 'requiere_verificacion': False, 'formato_permitido': ['jpg', 'png', 'webp']},
        {'nombre': 'Acta de Entrega/Recepción', 'descripcion': 'Documento de asignación/devolución a usuario', 'requiere_verificacion': True, 'formato_permitido': ['pdf']},
        {'nombre': 'Informe de Baja', 'descripcion': 'Documento que justifica la baja del activo', 'requiere_verificacion': True, 'formato_permitido': ['pdf']}
    ])

    # -- Tipos de Mantenimiento --
    tipos_mantenimiento_table = sa.table('tipos_mantenimiento',
        sa.column('nombre', sa.String), sa.column('descripcion', sa.Text), sa.column('periodicidad_dias', sa.Integer),
        sa.column('requiere_documentacion', sa.Boolean), sa.column('es_preventivo', sa.Boolean)
    )
    op.bulk_insert(tipos_mantenimiento_table, [
        {'nombre': 'Preventivo Básico Trimestral', 'descripcion': 'Limpieza, inspección visual, ajustes menores', 'periodicidad_dias': 90, 'requiere_documentacion': False, 'es_preventivo': True},
        {'nombre': 'Preventivo Completo Semestral', 'descripcion': 'Incluye cambio de filtros, lubricación, pruebas', 'periodicidad_dias': 180, 'requiere_documentacion': True, 'es_preventivo': True},
        {'nombre': 'Preventivo Anual', 'descripcion': 'Revisión profunda según fabricante', 'periodicidad_dias': 365, 'requiere_documentacion': True, 'es_preventivo': True},
        {'nombre': 'Correctivo Menor', 'descripcion': 'Reparación de falla simple', 'periodicidad_dias': None, 'requiere_documentacion': True, 'es_preventivo': False},
        {'nombre': 'Correctivo Mayor', 'descripcion': 'Reparación de falla compleja', 'periodicidad_dias': None, 'requiere_documentacion': True, 'es_preventivo': False},
        {'nombre': 'Calibración Anual', 'descripcion': 'Ajuste y verificación de precisión', 'periodicidad_dias': 365, 'requiere_documentacion': True, 'es_preventivo': True},
        {'nombre': 'Actualización Firmware/Software', 'descripcion': 'Instalación de nuevas versiones', 'periodicidad_dias': None, 'requiere_documentacion': True, 'es_preventivo': False},
        {'nombre': 'Inspección de Seguridad', 'descripcion': 'Verificación de normas de seguridad', 'periodicidad_dias': 120, 'requiere_documentacion': True, 'es_preventivo': True}
    ])

    # -- Proveedores --
    proveedores_table = sa.table('proveedores',
        sa.column('nombre', sa.String), sa.column('descripcion', sa.Text),
        sa.column('contacto', sa.Text), sa.column('rnc', sa.Text)
    )
    op.bulk_insert(proveedores_table, [
        {'nombre': 'Tech Solutions Inc.', 'descripcion': 'Equipos de cómputo y redes', 'contacto': 'ventas@techsolutions.com', 'rnc': '101000011'},
        {'nombre': 'Industrial Supply Co.', 'descripcion': 'Maquinaria y herramientas industriales', 'contacto': 'contacto@industrialsupply.com', 'rnc': '101000022'},
        {'nombre': 'MediCare Devices', 'descripcion': 'Equipamiento médico y de laboratorio', 'contacto': 'info@medicaredevices.com', 'rnc': '101000033'},
        {'nombre': 'Office Pro', 'descripcion': 'Mobiliario y suministros de oficina', 'contacto': 'sales@officepro.net', 'rnc': '101000044'}
    ])

    # === PASO 6: LÓGICA FINAL (Restricciones complejas, Vistas) ===
    op.execute("""
    ALTER TABLE control_equipos.reservas_equipo
    ADD CONSTRAINT reservas_equipo_solapamiento_excl
    EXCLUDE USING GIST (
        equipo_id WITH =,
        tstzrange(fecha_hora_inicio, fecha_hora_fin, '()') WITH &&
    ) WHERE (estado IN ('Confirmada', 'Pendiente Aprobacion', 'En Curso'));
    """)

    op.execute("""
    CREATE MATERIALIZED VIEW control_equipos.mv_equipos_estado AS
    SELECT
        ee.id AS estado_id,
        ee.nombre AS estado_nombre,
        ee.color_hex AS estado_color,
        COUNT(e.id) AS cantidad_equipos,
        SUM(CASE WHEN ee.permite_movimientos THEN 1 ELSE 0 END) AS cantidad_movibles,
        array_agg(e.id ORDER BY e.nombre) AS equipos_ids,
        array_agg(e.nombre ORDER BY e.nombre) AS equipos_nombres
    FROM
        control_equipos.estados_equipo ee
        LEFT JOIN control_equipos.equipos e ON e.estado_id = ee.id
    GROUP BY
        ee.id, ee.nombre, ee.color_hex
    ORDER BY
        ee.nombre
    WITH DATA;
    """)
    op.create_index('idx_mv_equipos_estado_id', 'mv_equipos_estado', ['estado_id'], unique=True, schema='control_equipos')

    op.execute("""
    CREATE MATERIALIZED VIEW control_equipos.mv_mantenimientos_proximos AS
    SELECT
        m.id AS mantenimiento_id,
        m.equipo_id,
        e.nombre AS equipo_nombre,
        e.numero_serie AS equipo_serie,
        e.ubicacion_actual AS equipo_ubicacion,
        tm.nombre AS tipo_mantenimiento_nombre,
        m.fecha_proximo_mantenimiento,
        m.estado AS mantenimiento_estado,
        (m.fecha_proximo_mantenimiento::DATE - CURRENT_DATE) AS dias_restantes
    FROM
        control_equipos.mantenimiento m
        JOIN control_equipos.equipos e ON m.equipo_id = e.id
        JOIN control_equipos.tipos_mantenimiento tm ON m.tipo_mantenimiento_id = tm.id
    WHERE
        m.fecha_proximo_mantenimiento IS NOT NULL
        AND m.fecha_proximo_mantenimiento BETWEEN NOW() AND NOW() + INTERVAL '30 days'
        AND m.estado NOT IN ('Completado', 'Cancelado')
    ORDER BY
        m.fecha_proximo_mantenimiento ASC
    WITH DATA;
    """)
    op.create_index('idx_mv_mantenimientos_proximos_fecha', 'mv_mantenimientos_proximos', ['fecha_proximo_mantenimiento'], unique=False, schema='control_equipos')
    op.create_index('idx_mv_mantenimientos_proximos_equipo', 'mv_mantenimientos_proximos', ['equipo_id'], unique=False, schema='control_equipos')


def downgrade() -> None:
    """
    Ejecuta todos los comandos para revertir la base de datos a un estado vacío.
    """
    # El orden de borrado es crucial: primero lo que depende de otros (vistas, triggers, funciones),
    # luego las tablas y finalmente el schema y extensiones.

    # === PASO 1 (INVERSO): BORRAR VISTAS, TRIGGERS Y FUNCIONES ===
    op.execute("DROP MATERIALIZED VIEW IF EXISTS control_equipos.mv_mantenimientos_proximos CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS control_equipos.mv_equipos_estado CASCADE;")

    op.execute("""
    DO $$
    DECLARE
        trigger_record RECORD;
    BEGIN
        FOR trigger_record IN (
            SELECT trigger_name, event_object_table
            FROM information_schema.triggers
            WHERE trigger_schema = 'control_equipos'
        )
        LOOP
            EXECUTE format('DROP TRIGGER IF EXISTS %I ON control_equipos.%I CASCADE;',
                           trigger_record.trigger_name, trigger_record.event_object_table);
        END LOOP;
    END $$;
    """)

    op.execute("DROP FUNCTION IF EXISTS control_equipos.registrar_movimiento_equipo(UUID, UUID, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ, TEXT, TEXT, UUID) CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS control_equipos.actualizar_licencia_disponible_fn() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS control_equipos.actualizar_inventario_stock_fn() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS control_equipos.actualizar_fecha_proximo_mantenimiento() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS control_equipos.actualizar_busqueda_mantenimiento() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS control_equipos.actualizar_busqueda_documento() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS control_equipos.actualizar_busqueda_equipo() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS control_equipos.update_updated_at() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS control_equipos.set_audit_user(UUID) CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS control_equipos.audit_trigger_fn() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS control_equipos.gestionar_particiones_audit_log() CASCADE;")

    # === PASO 2 (INVERSO): BORRAR TABLAS ===
    # Alembic genera esto en orden inverso a las dependencias de FK.
    op.drop_table('inventario_movimientos', schema='control_equipos')
    op.drop_table('documentacion', schema='control_equipos')
    op.drop_table('asignaciones_licencia', schema='control_equipos')
    op.drop_table('roles_permisos', schema='control_equipos')
    op.drop_table('reservas_equipo', schema='control_equipos')
    op.drop_table('notificaciones', schema='control_equipos')
    op.drop_table('movimientos', schema='control_equipos')
    op.drop_table('mantenimiento', schema='control_equipos')
    op.drop_table('login_logs', schema='control_equipos')
    op.drop_table('inventario_stock', schema='control_equipos')
    op.drop_table('equipo_componentes', schema='control_equipos')
    op.drop_table('usuarios', schema='control_equipos')
    op.drop_table('tipos_item_inventario', schema='control_equipos')
    op.drop_table('licencias_software', schema='control_equipos')
    op.drop_table('equipos', schema='control_equipos')
    op.drop_table('tipos_mantenimiento', schema='control_equipos')
    op.drop_table('tipos_documento', schema='control_equipos')
    op.drop_table('software_catalogo', schema='control_equipos')
    op.drop_table('roles', schema='control_equipos')
    op.drop_table('proveedores', schema='control_equipos')
    op.drop_table('permisos', schema='control_equipos')
    op.drop_table('estados_equipo', schema='control_equipos')
    op.drop_table('backup_logs', schema='control_equipos')
    op.drop_table('audit_log', schema='control_equipos')

    # === PASO 3 (INVERSO): BORRAR SCHEMA Y EXTENSIONES ===
    op.execute("DROP SCHEMA IF EXISTS control_equipos CASCADE;")
    op.execute("DROP EXTENSION IF EXISTS btree_gist;")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto;")
