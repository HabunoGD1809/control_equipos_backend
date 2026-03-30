"""normalizacion_marcas_y_departamentos

Revision ID: ea2eec0480b6
Revises: ce69340be793
Create Date: 2026-03-26 17:28:10.051769

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ea2eec0480b6'
down_revision: Union[str, None] = 'ce69340be793'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Crear las nuevas tablas maestras
    op.create_table('departamentos',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('nombre', sa.String(length=150), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_departamentos')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_departamentos_nombre'), 'departamentos', ['nombre'], unique=True, schema='control_equipos')

    op.create_table('marcas',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_marcas')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_marcas_nombre'), 'marcas', ['nombre'], unique=True, schema='control_equipos')

    # 2. Agregar las columnas ForeignKey a las tablas existentes
    op.add_column('equipos', sa.Column('marca_id', sa.UUID(), nullable=True), schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_equipos_marca_id'), 'equipos', ['marca_id'], unique=False, schema='control_equipos')
    op.create_foreign_key(op.f('fk_equipos_marca_id_marcas'), 'equipos', 'marcas', ['marca_id'], ['id'], source_schema='control_equipos', referent_schema='control_equipos', ondelete='SET NULL')

    op.add_column('software_catalogo', sa.Column('marca_id', sa.UUID(), nullable=True), schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_software_catalogo_marca_id'), 'software_catalogo', ['marca_id'], unique=False, schema='control_equipos')
    op.create_foreign_key(op.f('fk_software_catalogo_marca_id_marcas'), 'software_catalogo', 'marcas', ['marca_id'], ['id'], source_schema='control_equipos', referent_schema='control_equipos', ondelete='SET NULL')

    op.add_column('tipos_item_inventario', sa.Column('marca_id', sa.UUID(), nullable=True), schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_tipos_item_inventario_marca_id'), 'tipos_item_inventario', ['marca_id'], unique=False, schema='control_equipos')
    op.create_foreign_key(op.f('fk_tipos_item_inventario_marca_id_marcas'), 'tipos_item_inventario', 'marcas', ['marca_id'], ['id'], source_schema='control_equipos', referent_schema='control_equipos', ondelete='SET NULL')

    op.add_column('ubicaciones', sa.Column('departamento_id', sa.UUID(), nullable=True), schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_ubicaciones_departamento_id'), 'ubicaciones', ['departamento_id'], unique=False, schema='control_equipos')
    op.create_foreign_key(op.f('fk_ubicaciones_departamento_id_departamentos'), 'ubicaciones', 'departamentos', ['departamento_id'], ['id'], source_schema='control_equipos', referent_schema='control_equipos', ondelete='SET NULL')

    op.add_column('usuarios', sa.Column('departamento_id', sa.UUID(), nullable=True), schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_usuarios_departamento_id'), 'usuarios', ['departamento_id'], unique=False, schema='control_equipos')
    op.create_foreign_key(op.f('fk_usuarios_departamento_id_departamentos'), 'usuarios', 'departamentos', ['departamento_id'], ['id'], source_schema='control_equipos', referent_schema='control_equipos', ondelete='SET NULL')

    # 3. Eliminar las columnas de texto antiguas
    op.drop_column('equipos', 'marca', schema='control_equipos')
    op.drop_column('software_catalogo', 'fabricante', schema='control_equipos')
    op.drop_column('tipos_item_inventario', 'marca', schema='control_equipos')
    op.drop_column('ubicaciones', 'departamento', schema='control_equipos')

    # 4. Actualizar el trigger de búsqueda de equipos
    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.actualizar_busqueda_equipo()
    RETURNS TRIGGER AS $$
    DECLARE
        v_ubicacion_nombre TEXT := '';
        v_marca_nombre TEXT := '';
    BEGIN
        IF NEW.ubicacion_id IS NOT NULL THEN
            SELECT nombre INTO v_ubicacion_nombre FROM control_equipos.ubicaciones WHERE id = NEW.ubicacion_id;
        END IF;

        IF NEW.marca_id IS NOT NULL THEN
            SELECT nombre INTO v_marca_nombre FROM control_equipos.marcas WHERE id = NEW.marca_id;
        END IF;

        NEW.texto_busqueda =
            setweight(to_tsvector('spanish', COALESCE(NEW.nombre, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.numero_serie, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.codigo_interno, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(v_marca_nombre, '')), 'B') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.modelo, '')), 'B') ||
            setweight(to_tsvector('spanish', COALESCE(v_ubicacion_nombre, '')), 'C') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.centro_costo, '')), 'C') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.notas, '')), 'D');

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Recrear las columnas de texto antiguas
    op.add_column('ubicaciones', sa.Column('departamento', sa.TEXT(), autoincrement=False, nullable=True), schema='control_equipos')
    op.add_column('tipos_item_inventario', sa.Column('marca', sa.TEXT(), autoincrement=False, nullable=True), schema='control_equipos')
    op.add_column('software_catalogo', sa.Column('fabricante', sa.TEXT(), autoincrement=False, nullable=True), schema='control_equipos')
    op.add_column('equipos', sa.Column('marca', sa.TEXT(), autoincrement=False, nullable=True), schema='control_equipos')

    # 2. Eliminar llaves foráneas y columnas ID
    op.drop_constraint(op.f('fk_usuarios_departamento_id_departamentos'), 'usuarios', schema='control_equipos', type_='foreignkey')
    op.drop_index(op.f('ix_control_equipos_usuarios_departamento_id'), table_name='usuarios', schema='control_equipos')
    op.drop_column('usuarios', 'departamento_id', schema='control_equipos')

    op.drop_constraint(op.f('fk_ubicaciones_departamento_id_departamentos'), 'ubicaciones', schema='control_equipos', type_='foreignkey')
    op.drop_index(op.f('ix_control_equipos_ubicaciones_departamento_id'), table_name='ubicaciones', schema='control_equipos')
    op.drop_column('ubicaciones', 'departamento_id', schema='control_equipos')

    op.drop_constraint(op.f('fk_tipos_item_inventario_marca_id_marcas'), 'tipos_item_inventario', schema='control_equipos', type_='foreignkey')
    op.drop_index(op.f('ix_control_equipos_tipos_item_inventario_marca_id'), table_name='tipos_item_inventario', schema='control_equipos')
    op.drop_column('tipos_item_inventario', 'marca_id', schema='control_equipos')

    op.drop_constraint(op.f('fk_software_catalogo_marca_id_marcas'), 'software_catalogo', schema='control_equipos', type_='foreignkey')
    op.drop_index(op.f('ix_control_equipos_software_catalogo_marca_id'), table_name='software_catalogo', schema='control_equipos')
    op.drop_column('software_catalogo', 'marca_id', schema='control_equipos')

    op.drop_constraint(op.f('fk_equipos_marca_id_marcas'), 'equipos', schema='control_equipos', type_='foreignkey')
    op.drop_index(op.f('ix_control_equipos_equipos_marca_id'), table_name='equipos', schema='control_equipos')
    op.drop_column('equipos', 'marca_id', schema='control_equipos')

    # 3. Eliminar las tablas maestras
    op.drop_index(op.f('ix_control_equipos_marcas_nombre'), table_name='marcas', schema='control_equipos')
    op.drop_table('marcas', schema='control_equipos')
    op.drop_index(op.f('ix_control_equipos_departamentos_nombre'), table_name='departamentos', schema='control_equipos')
    op.drop_table('departamentos', schema='control_equipos')

    # 4. Revertir el trigger a su estado original
    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.actualizar_busqueda_equipo()
    RETURNS TRIGGER AS $$
    DECLARE
        v_ubicacion_nombre TEXT := '';
    BEGIN
        IF NEW.ubicacion_id IS NOT NULL THEN
            SELECT nombre INTO v_ubicacion_nombre FROM control_equipos.ubicaciones WHERE id = NEW.ubicacion_id;
        END IF;

        NEW.texto_busqueda =
            setweight(to_tsvector('spanish', COALESCE(NEW.nombre, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.numero_serie, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.codigo_interno, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.marca, '')), 'B') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.modelo, '')), 'B') ||
            setweight(to_tsvector('spanish', COALESCE(v_ubicacion_nombre, '')), 'C') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.centro_costo, '')), 'C') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.notas, '')), 'D');

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
