"""Add tecnicos_mantenimiento table and relations

Revision ID: d74c0747cb81
Revises: b3735afa423c
Create Date: 2026-03-13 15:25:35.154692

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd74c0747cb81'
down_revision: Union[str, None] = 'b3735afa423c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Crear la nueva tabla de técnicos
    op.create_table(
        'tecnicos_mantenimiento',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('nombre_completo', sa.String(length=255), nullable=False),
        sa.Column('es_externo', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('proveedor_id', sa.UUID(), nullable=True),
        sa.Column('telefono_contacto', sa.String(length=50), nullable=True),
        sa.Column('email_contacto', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['proveedor_id'], ['control_equipos.proveedores.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_tecnicos_mantenimiento_proveedor_id'), 'tecnicos_mantenimiento', ['proveedor_id'], unique=False, schema='control_equipos')

    # 2. Agregar la nueva llave foránea a mantenimiento
    op.add_column('mantenimiento', sa.Column('tecnico_id', sa.UUID(), nullable=True), schema='control_equipos')
    op.create_foreign_key(
        op.f('fk_mantenimiento_tecnico_id_tecnicos_mantenimiento'), 
        'mantenimiento', 'tecnicos_mantenimiento', 
        ['tecnico_id'], ['id'], 
        source_schema='control_equipos', referent_schema='control_equipos', ondelete='RESTRICT'
    )
    op.create_index(op.f('ix_control_equipos_mantenimiento_tecnico_id'), 'mantenimiento', ['tecnico_id'], unique=False, schema='control_equipos')

    # 3. MIGRACIÓN DE DATOS (Salvar el historial)
    op.execute("""
        -- A) Insertar técnicos internos (los que no tenían proveedor_servicio_id)
        INSERT INTO control_equipos.tecnicos_mantenimiento (id, nombre_completo, es_externo, is_active)
        SELECT gen_random_uuid(), tecnico_responsable, false, true
        FROM control_equipos.mantenimiento
        WHERE proveedor_servicio_id IS NULL AND tecnico_responsable IS NOT NULL
        GROUP BY tecnico_responsable;

        -- B) Insertar técnicos externos (los que sí tenían proveedor_servicio_id)
        INSERT INTO control_equipos.tecnicos_mantenimiento (id, nombre_completo, es_externo, proveedor_id, is_active)
        SELECT gen_random_uuid(), tecnico_responsable, true, proveedor_servicio_id, true
        FROM control_equipos.mantenimiento
        WHERE proveedor_servicio_id IS NOT NULL AND tecnico_responsable IS NOT NULL
        GROUP BY tecnico_responsable, proveedor_servicio_id;

        -- C) Vincular los mantenimientos viejos con los nuevos IDs de técnico generados
        UPDATE control_equipos.mantenimiento m
        SET tecnico_id = tm.id
        FROM control_equipos.tecnicos_mantenimiento tm
        WHERE m.tecnico_responsable = tm.nombre_completo
          AND (m.proveedor_servicio_id = tm.proveedor_id OR (m.proveedor_servicio_id IS NULL AND tm.proveedor_id IS NULL));
    """)

    # 4. Hacer la nueva columna obligatoria (NOT NULL)
    op.alter_column('mantenimiento', 'tecnico_id', existing_type=sa.UUID(), nullable=False, schema='control_equipos')

    # 5. Eliminar las columnas viejas de forma segura
    op.execute("ALTER TABLE control_equipos.mantenimiento DROP CONSTRAINT IF EXISTS fk_mantenimiento_proveedor_servicio_id_proveedores;")
    op.drop_index('ix_control_equipos_mantenimiento_proveedor_servicio_id', table_name='mantenimiento', schema='control_equipos', if_exists=True)
    
    op.drop_column('mantenimiento', 'proveedor_servicio_id', schema='control_equipos')
    op.drop_column('mantenimiento', 'tecnico_responsable', schema='control_equipos')


def downgrade() -> None:
    """Downgrade schema."""
    pass
