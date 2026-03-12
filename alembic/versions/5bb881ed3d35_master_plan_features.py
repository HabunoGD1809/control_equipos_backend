"""
Master Plan Features: Ubicaciones, Soft Deletes, Avatar, IP Audit y Handoffs

Revision ID: 5bb881ed3d35
Revises: 4aa970dc2c24
Create Date: 2026-03-10 13:32:42.532476
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '5bb881ed3d35'
down_revision: Union[str, None] = '4aa970dc2c24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Crear el nuevo catálogo de Ubicaciones Físicas
    op.create_table('ubicaciones',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('nombre', sa.Text(), nullable=False),
        sa.Column('edificio', sa.Text(), nullable=True),
        sa.Column('departamento', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ubicaciones')),
        sa.UniqueConstraint('nombre', name=op.f('uq_ubicaciones_nombre')),
        schema='control_equipos'
    )

    # 2. Migración de Datos: 
    # Extraemos las ubicaciones de texto libre que ya existen y las insertamos en el catálogo nuevo
    op.execute("""
        INSERT INTO control_equipos.ubicaciones (nombre)
        SELECT DISTINCT ubicacion_actual 
        FROM control_equipos.equipos 
        WHERE ubicacion_actual IS NOT NULL AND TRIM(ubicacion_actual) <> ''
        ON CONFLICT (nombre) DO NOTHING;
    """)

    # 3. Soft Deletes (Borrado Lógico) para catálogos
    tables_for_soft_delete = ['usuarios', 'proveedores', 'tipos_item_inventario', 'software_catalogo']
    for table in tables_for_soft_delete:
        op.add_column(table, sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False), schema='control_equipos')

    # 4. Avatar URL y Auditoría Forense (IP/User-Agent)
    op.add_column('usuarios', sa.Column('avatar_url', sa.Text(), nullable=True), schema='control_equipos')
    op.add_column('movimientos', sa.Column('ip_origen', sa.String(length=100), nullable=True), schema='control_equipos')
    op.add_column('movimientos', sa.Column('user_agent', sa.Text(), nullable=True), schema='control_equipos')

    # 5. FIX CADENA DE CUSTODIA (Handoff)
    # Actualizamos la función para que las Asignaciones y Salidas Temporales 
    # nazcan como 'En Proceso' en lugar de 'Completado', forzando al usuario a "Recibir".
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
        v_estado_mov_inicial TEXT := 'Completado'; -- Estado por defecto
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
                v_ubicacion_final := p_destino;
                p_origen := COALESCE(p_origen, v_estado_equipo.ubicacion_actual);
                v_estado_mov_inicial := 'En Proceso'; -- 🚀 Requiere acuse de recibo del destino

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
                v_estado_mov_inicial := 'En Proceso'; -- 🚀 Requiere acuse de recibo del empleado

            WHEN 'Transferencia Bodega' THEN
                v_estado_final_id := v_estado_equipo.estado_id;
                v_ubicacion_final := p_destino;
                p_origen := COALESCE(p_origen, v_estado_equipo.ubicacion_actual);
                v_estado_mov_inicial := 'En Proceso'; -- 🚀 Requiere acuse de recibo de la otra bodega
            ELSE
                RAISE EXCEPTION 'Tipo de movimiento no válido: %', p_tipo_movimiento;
        END CASE;

        INSERT INTO control_equipos.movimientos (equipo_id, usuario_id, tipo_movimiento, origen, destino, proposito, fecha_prevista_retorno, recibido_por, observaciones, autorizado_por, estado)
        VALUES (p_equipo_id, p_usuario_id, p_tipo_movimiento, p_origen, p_destino, p_proposito, p_fecha_prevista_retorno, p_recibido_por, p_observaciones, p_autorizado_por, v_estado_mov_inicial)
        RETURNING id INTO v_movimiento_id;

        UPDATE control_equipos.equipos SET estado_id = v_estado_final_id, ubicacion_actual = v_ubicacion_final, updated_at = NOW() WHERE id = p_equipo_id;

        RETURN v_movimiento_id;
    END;
    $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    # 1. Revertir función a 'Completado' por defecto
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
    END;
    $$ LANGUAGE plpgsql;
    """)

    # 2. Revertir columnas
    op.drop_column('movimientos', 'user_agent', schema='control_equipos')
    op.drop_column('movimientos', 'ip_origen', schema='control_equipos')
    op.drop_column('usuarios', 'avatar_url', schema='control_equipos')
    
    tables_for_soft_delete = ['usuarios', 'proveedores', 'tipos_item_inventario', 'software_catalogo']
    for table in tables_for_soft_delete:
        op.drop_column(table, 'is_active', schema='control_equipos')
        
    op.drop_table('ubicaciones', schema='control_equipos')
