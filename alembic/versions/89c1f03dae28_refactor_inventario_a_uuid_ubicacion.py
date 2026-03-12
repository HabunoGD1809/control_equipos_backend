"""Refactor inventario a UUID ubicacion

Revision ID: 89c1f03dae28
Revises: 2c65ae33746e
Create Date: 2026-03-12 16:29:47.726504

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '89c1f03dae28'
down_revision: Union[str, None] = '2c65ae33746e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # =========================================================================
    # INVENTARIO MOVIMIENTOS
    # =========================================================================
    # 1. Agregar las nuevas columnas UUID
    op.add_column('inventario_movimientos', sa.Column('ubicacion_origen_id', sa.UUID(), nullable=True), schema='control_equipos')
    op.add_column('inventario_movimientos', sa.Column('ubicacion_destino_id', sa.UUID(), nullable=True), schema='control_equipos')
    
    # 2. Crear las llaves foráneas
    op.create_foreign_key(op.f('fk_inventario_movimientos_ubicacion_origen_id_ubicaciones'), 'inventario_movimientos', 'ubicaciones', ['ubicacion_origen_id'], ['id'], source_schema='control_equipos', referent_schema='control_equipos', ondelete='SET NULL')
    op.create_foreign_key(op.f('fk_inventario_movimientos_ubicacion_destino_id_ubicaciones'), 'inventario_movimientos', 'ubicaciones', ['ubicacion_destino_id'], ['id'], source_schema='control_equipos', referent_schema='control_equipos', ondelete='SET NULL')
    
    # 3. Crear los índices
    op.create_index(op.f('ix_control_equipos_inventario_movimientos_ubicacion_destino_id'), 'inventario_movimientos', ['ubicacion_destino_id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_inventario_movimientos_ubicacion_origen_id'), 'inventario_movimientos', ['ubicacion_origen_id'], unique=False, schema='control_equipos')
    
    # 4. Eliminar las columnas viejas de texto
    op.drop_column('inventario_movimientos', 'ubicacion_destino', schema='control_equipos')
    op.drop_column('inventario_movimientos', 'ubicacion_origen', schema='control_equipos')

    # =========================================================================
    # INVENTARIO STOCK
    # =========================================================================
    # 1. Eliminar la restricción única y el índice viejo
    op.drop_constraint('uq_item_ubicacion_lote', 'inventario_stock', schema='control_equipos', type_='unique')
    op.drop_index(op.f('ix_control_equipos_inventario_stock_ubicacion'), table_name='inventario_stock', schema='control_equipos')
    
    # 2. Eliminar la columna de texto vieja. (Lo hacemos ANTES de crear la nueva para evitar conflictos de nullable).
    op.drop_column('inventario_stock', 'ubicacion', schema='control_equipos')

    # 3. Agregar la nueva columna UUID (permitimos nulos un milisegundo por si hay datos de prueba)
    op.add_column('inventario_stock', sa.Column('ubicacion_id', sa.UUID(), nullable=True), schema='control_equipos')
    
    # 4. Crear llave foránea e índice
    op.create_foreign_key(op.f('fk_inventario_stock_ubicacion_id_ubicaciones'), 'inventario_stock', 'ubicaciones', ['ubicacion_id'], ['id'], source_schema='control_equipos', referent_schema='control_equipos', ondelete='RESTRICT')
    op.create_index(op.f('ix_control_equipos_inventario_stock_ubicacion_id'), 'inventario_stock', ['ubicacion_id'], unique=False, schema='control_equipos')
    
    # 5. Recrear la restricción única con la nueva columna
    op.create_unique_constraint('uq_item_ubicacion_lote', 'inventario_stock', ['tipo_item_id', 'ubicacion_id', 'lote'], schema='control_equipos')


def downgrade() -> None:
    """Downgrade schema."""
    pass # Omitido intencionalmente por seguridad
