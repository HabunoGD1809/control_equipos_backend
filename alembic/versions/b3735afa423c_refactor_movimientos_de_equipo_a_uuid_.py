"""Refactor movimientos de equipo a UUID ubicaciones

Revision ID: b3735afa423c
Revises: 83e3bd570973
Create Date: 2026-03-12 20:38:27.798611

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3735afa423c'
down_revision: Union[str, None] = '83e3bd570973'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Agregar columnas UUID a movimientos
    op.add_column('movimientos', sa.Column('ubicacion_origen_id', sa.UUID(), nullable=True), schema='control_equipos')
    op.add_column('movimientos', sa.Column('ubicacion_destino_id', sa.UUID(), nullable=True), schema='control_equipos')

    # 2. Crear las llaves foráneas y los índices
    op.create_foreign_key(op.f('fk_movimientos_ubicacion_origen_id_ubicaciones'), 'movimientos', 'ubicaciones', ['ubicacion_origen_id'], ['id'], source_schema='control_equipos', referent_schema='control_equipos', ondelete='SET NULL')
    op.create_foreign_key(op.f('fk_movimientos_ubicacion_destino_id_ubicaciones'), 'movimientos', 'ubicaciones', ['ubicacion_destino_id'], ['id'], source_schema='control_equipos', referent_schema='control_equipos', ondelete='SET NULL')
    
    op.create_index(op.f('ix_control_equipos_movimientos_ubicacion_origen_id'), 'movimientos', ['ubicacion_origen_id'], unique=False, schema='control_equipos')
    op.create_index(op.f('ix_control_equipos_movimientos_ubicacion_destino_id'), 'movimientos', ['ubicacion_destino_id'], unique=False, schema='control_equipos')

# 3. Modificar las restricciones de verificación (CHECK constraints)
    # Usamos execute con IF EXISTS para evitar errores si el nombre varía por el dialecto
    op.execute("ALTER TABLE control_equipos.movimientos DROP CONSTRAINT IF EXISTS ck_movimientos_check_origen_destino_asignacion;")
    op.execute("ALTER TABLE control_equipos.movimientos DROP CONSTRAINT IF EXISTS ck_movimientos_check_origen_entrada;")
    
    # En las constraints de PostgreSQL con Alembic, los % se escapan con %%
    op.create_check_constraint('ck_movimientos_check_origen_destino_asignacion', 'movimientos', "tipo_movimiento NOT LIKE '%%Asignacion%%' OR (ubicacion_origen_id IS NOT NULL AND ubicacion_destino_id IS NOT NULL)", schema='control_equipos')
    op.create_check_constraint('ck_movimientos_check_origen_entrada', 'movimientos', "tipo_movimiento != 'Entrada' OR ubicacion_origen_id IS NOT NULL", schema='control_equipos')

    # 4. Eliminar las columnas de texto viejo
    op.drop_column('movimientos', 'origen', schema='control_equipos')
    op.drop_column('movimientos', 'destino', schema='control_equipos')

    # 5. ACTUALIZAR LA FUNCIÓN SQL PARA USAR UUIDs
    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.registrar_movimiento_equipo(
        p_equipo_id uuid, 
        p_usuario_id uuid, 
        p_tipo_movimiento text, 
        p_ubicacion_origen_id uuid DEFAULT NULL::uuid, 
        p_ubicacion_destino_id uuid DEFAULT NULL::uuid, 
        p_proposito text DEFAULT NULL::text, 
        p_fecha_prevista_retorno timestamp with time zone DEFAULT NULL::timestamp with time zone, 
        p_recibido_por text DEFAULT NULL::text, 
        p_observaciones text DEFAULT NULL::text, 
        p_autorizado_por uuid DEFAULT NULL::uuid
    )
    RETURNS uuid
    LANGUAGE plpgsql
    AS $function$
    DECLARE
        v_movimiento_id UUID;
        v_estado_equipo RECORD;
        v_estado_final_id UUID;
        v_ubicacion_final_id UUID;
        v_current_user_has_auth_perm BOOLEAN;
        v_estado_mov_inicial TEXT := 'Completado';
    BEGIN
        SELECT ee.nombre, ee.permite_movimientos, ee.requiere_autorizacion, e.ubicacion_id, e.estado_id
        INTO v_estado_equipo
        FROM control_equipos.equipos e
        JOIN control_equipos.estados_equipo ee ON e.estado_id = ee.id
        WHERE e.id = p_equipo_id
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Equipo no encontrado (ID: %)', p_equipo_id;
        END IF;

        IF NOT v_estado_equipo.permite_movimientos THEN
            RAISE EXCEPTION 'El equipo con estado "%" no permite movimientos actualmente.', v_estado_equipo.nombre;
        END IF;

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

        IF p_tipo_movimiento = 'Asignacion Interna' AND v_estado_equipo.nombre <> 'Disponible' THEN
            RAISE EXCEPTION 'Solo se pueden asignar equipos que están en estado "Disponible". Estado actual: "%".', v_estado_equipo.nombre;
        END IF;

        CASE p_tipo_movimiento
            WHEN 'Salida Temporal' THEN
                SELECT id INTO v_estado_final_id FROM control_equipos.estados_equipo WHERE nombre = 'Prestado';
                v_ubicacion_final_id := p_ubicacion_destino_id;
                p_ubicacion_origen_id := COALESCE(p_ubicacion_origen_id, v_estado_equipo.ubicacion_id);
                v_estado_mov_inicial := 'En Proceso';

            WHEN 'Salida Definitiva' THEN
                SELECT id INTO v_estado_final_id FROM control_equipos.estados_equipo WHERE nombre = 'Dado de Baja';
                v_ubicacion_final_id := p_ubicacion_destino_id;
                p_ubicacion_origen_id := COALESCE(p_ubicacion_origen_id, v_estado_equipo.ubicacion_id);

            WHEN 'Entrada' THEN
                SELECT id INTO v_estado_final_id FROM control_equipos.estados_equipo WHERE nombre = 'Disponible';
                v_ubicacion_final_id := p_ubicacion_destino_id; 

            WHEN 'Asignacion Interna' THEN
                SELECT id INTO v_estado_final_id FROM control_equipos.estados_equipo WHERE nombre = 'En Uso';
                v_ubicacion_final_id := p_ubicacion_destino_id;
                p_ubicacion_origen_id := COALESCE(p_ubicacion_origen_id, v_estado_equipo.ubicacion_id);
                v_estado_mov_inicial := 'En Proceso';

            WHEN 'Transferencia Bodega' THEN
                v_estado_final_id := v_estado_equipo.estado_id;
                v_ubicacion_final_id := p_ubicacion_destino_id;
                p_ubicacion_origen_id := COALESCE(p_ubicacion_origen_id, v_estado_equipo.ubicacion_id);
                v_estado_mov_inicial := 'En Proceso';
            ELSE
                RAISE EXCEPTION 'Tipo de movimiento no válido: %', p_tipo_movimiento;
        END CASE;

        INSERT INTO control_equipos.movimientos (equipo_id, usuario_id, tipo_movimiento, ubicacion_origen_id, ubicacion_destino_id, proposito, fecha_prevista_retorno, recibido_por, observaciones, autorizado_por, estado)
        VALUES (p_equipo_id, p_usuario_id, p_tipo_movimiento, p_ubicacion_origen_id, p_ubicacion_destino_id, p_proposito, p_fecha_prevista_retorno, p_recibido_por, p_observaciones, p_autorizado_por, v_estado_mov_inicial)
        RETURNING id INTO v_movimiento_id;

        UPDATE control_equipos.equipos SET estado_id = v_estado_final_id, ubicacion_id = v_ubicacion_final_id, updated_at = NOW() WHERE id = p_equipo_id;

        RETURN v_movimiento_id;
    END; 
    $function$;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    pass
