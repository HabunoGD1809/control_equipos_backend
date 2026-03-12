"""Add Reportes Table

Revision ID: 2c65ae33746e
Revises: 6cc992fe4e46
Create Date: 2026-03-12 13:51:08.847897

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '2c65ae33746e'
down_revision: Union[str, None] = '6cc992fe4e46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Solo creamos la tabla nueva de reportes. Ignoramos todo el ruido de ALTER TABLES y DROP TABLES.
    op.create_table('reportes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('usuario_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tipo_reporte', sa.String(), nullable=False),
        sa.Column('formato', sa.String(), nullable=False),
        sa.Column('parametros', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('estado', sa.String(), nullable=False),
        sa.Column('archivo_path', sa.String(), nullable=True),
        sa.Column('archivo_size_bytes', sa.Integer(), nullable=True),
        sa.Column('error_msg', sa.Text(), nullable=True),
        sa.Column('fecha_solicitud', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('fecha_completado', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['usuario_id'], ['control_equipos.usuarios.id'], name=op.f('fk_reportes_usuario_id_usuarios'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_reportes')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_reportes_estado'), 'reportes', ['estado'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_reportes_id'), 'reportes', ['id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_reportes_tipo_reporte'), 'reportes', ['tipo_reporte'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_reportes_usuario_id'), 'reportes', ['usuario_id'], unique=False, schema='control_equipos')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_control_equipos_reportes_usuario_id'), table_name='reportes', schema='control_equipos')
    op.drop_index(op.f('ix_control_equipos_reportes_tipo_reporte'), table_name='reportes', schema='control_equipos')
    op.drop_index(op.f('ix_control_equipos_reportes_id'), table_name='reportes', schema='control_equipos')
    op.drop_index(op.f('ix_control_equipos_reportes_estado'), table_name='reportes', schema='control_equipos')
    op.drop_table('reportes', schema='control_equipos')
