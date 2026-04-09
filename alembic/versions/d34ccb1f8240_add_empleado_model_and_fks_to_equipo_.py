"""Add Empleado model and FKs to Equipo, Movimiento, Usuario

Revision ID: d34ccb1f8240
Revises: ea2eec0480b6
Create Date: 2026-03-31 19:24:47.668405

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd34ccb1f8240'
down_revision: Union[str, None] = 'ea2eec0480b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Crear la tabla de Empleados
    op.create_table('empleados',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('nombre_completo', sa.String(length=255), nullable=False),
        sa.Column('cargo', sa.String(length=150), nullable=True),
        sa.Column('email_corporativo', sa.String(length=255), nullable=True),
        sa.Column('departamento_id', sa.UUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['departamento_id'], ['control_equipos.departamentos.id'], name=op.f('fk_empleados_departamento_id_departamentos'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_empleados')),
        schema='control_equipos'
    )
    op.create_index(op.f('ix_control_equipos_empleados_departamento_id'), 'empleados', ['departamento_id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_empleados_email_corporativo'), 'empleados', ['email_corporativo'], unique=True, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_empleados_nombre_completo'), 'empleados', ['nombre_completo'], unique=False, schema='control_equipos')

    # 2. Añadir FK a Equipos
    op.add_column('equipos', sa.Column('empleado_asignado_id', sa.UUID(), nullable=True), schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_equipos_empleado_asignado_id'), 'equipos', ['empleado_asignado_id'], unique=False, schema='control_equipos')
    op.create_foreign_key(op.f('fk_equipos_empleado_asignado_id_empleados'), 'equipos', 'empleados', ['empleado_asignado_id'], ['id'], source_schema='control_equipos', referent_schema='control_equipos', ondelete='SET NULL')

    # 3. Añadir FK a Movimientos
    op.add_column('movimientos', sa.Column('empleado_destino_id', sa.UUID(), nullable=True), schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_movimientos_empleado_destino_id'), 'movimientos', ['empleado_destino_id'], unique=False, schema='control_equipos')
    op.create_foreign_key(op.f('fk_movimientos_empleado_destino_id_empleados'), 'movimientos', 'empleados', ['empleado_destino_id'], ['id'], source_schema='control_equipos', referent_schema='control_equipos', ondelete='SET NULL')

    # 4. Añadir FK a Usuarios
    op.add_column('usuarios', sa.Column('empleado_id', sa.UUID(), nullable=True), schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_usuarios_empleado_id'), 'usuarios', ['empleado_id'], unique=True, schema='control_equipos')
    op.create_foreign_key(op.f('fk_usuarios_empleado_id_empleados'), 'usuarios', 'empleados', ['empleado_id'], ['id'], source_schema='control_equipos', referent_schema='control_equipos', ondelete='SET NULL')


def downgrade() -> None:
    # 1. Revertir Usuarios
    op.drop_constraint(op.f('fk_usuarios_empleado_id_empleados'), 'usuarios', schema='control_equipos', type_='foreignkey')
    op.drop_index(op.f('ix_control_equipos_usuarios_empleado_id'), table_name='usuarios', schema='control_equipos')
    op.drop_column('usuarios', 'empleado_id', schema='control_equipos')

    # 2. Revertir Movimientos
    op.drop_constraint(op.f('fk_movimientos_empleado_destino_id_empleados'), 'movimientos', schema='control_equipos', type_='foreignkey')
    op.drop_index(op.f('ix_control_equipos_movimientos_empleado_destino_id'), table_name='movimientos', schema='control_equipos')
    op.drop_column('movimientos', 'empleado_destino_id', schema='control_equipos')

    # 3. Revertir Equipos
    op.drop_constraint(op.f('fk_equipos_empleado_asignado_id_empleados'), 'equipos', schema='control_equipos', type_='foreignkey')
    op.drop_index(op.f('ix_control_equipos_equipos_empleado_asignado_id'), table_name='equipos', schema='control_equipos')
    op.drop_column('equipos', 'empleado_asignado_id', schema='control_equipos')

    # 4. Eliminar Tabla Empleados
    op.drop_index(op.f('ix_control_equipos_empleados_nombre_completo'), table_name='empleados', schema='control_equipos')
    op.drop_index(op.f('ix_control_equipos_empleados_email_corporativo'), table_name='empleados', schema='control_equipos')
    op.drop_index(op.f('ix_control_equipos_empleados_departamento_id'), table_name='empleados', schema='control_equipos')
    op.drop_table('empleados', schema='control_equipos')
