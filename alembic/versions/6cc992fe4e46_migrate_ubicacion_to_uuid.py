"""
Migrate ubicacion_actual text to ubicacion_id UUID with View Refactor

Revision ID: 6cc992fe4e46
Revises: 5bb881ed3d35
Create Date: 2026-03-10 13:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = '6cc992fe4e46'
down_revision: Union[str, None] = '5bb881ed3d35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. ELIMINAR VISTA MATERIALIZADA (Para romper la dependencia que bloqueaba el drop column)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS control_equipos.mv_mantenimientos_proximos")

    # 2. AÑADIR NUEVA COLUMNA Y LLAVE FORÁNEA
    op.add_column('equipos', sa.Column('ubicacion_id', UUID(as_uuid=True), nullable=True), schema='control_equipos')
    
    op.create_foreign_key(
        'fk_equipos_ubicacion_id_ubicaciones', 
        'equipos', 'ubicaciones', 
        ['ubicacion_id'], ['id'], 
        source_schema='control_equipos', referent_schema='control_equipos',
        ondelete='SET NULL'
    )
    
    # 3. MIGRACIÓN DE DATOS (Mapear el texto existente en equipos al ID de la tabla ubicaciones)
    op.execute("""
        UPDATE control_equipos.equipos e
        SET ubicacion_id = u.id
        FROM control_equipos.ubicaciones u
        WHERE e.ubicacion_actual = u.nombre;
    """)

    # 4. ELIMINAR COLUMNA DE TEXTO ANTIGUA
    op.drop_column('equipos', 'ubicacion_actual', schema='control_equipos')

    # 5. ACTUALIZAR FUNCIÓN: buscar_equipos (Refactor con JOIN a Ubicaciones)
    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.buscar_equipos(termino TEXT)
    RETURNS TABLE (
        id UUID, nombre TEXT, numero_serie TEXT, marca TEXT, modelo TEXT,
        ubicacion_actual TEXT, estado_nombre TEXT, relevancia FLOAT4
    ) AS $$
    DECLARE query_term TEXT;
    BEGIN
        query_term := string_agg(lexeme || ':*', ' & ' ORDER BY positions) FROM unnest(to_tsvector('spanish', termino));
        IF query_term IS NULL OR query_term = '' THEN query_term := termino; END IF;
        RETURN QUERY
        SELECT e.id, e.nombre, e.numero_serie, e.marca, e.modelo,
               u.nombre AS ubicacion_actual, ee.nombre AS estado_nombre,
               ts_rank_cd(e.texto_busqueda, to_tsquery('spanish', query_term)) AS relevancia
        FROM control_equipos.equipos e
        LEFT JOIN control_equipos.estados_equipo ee ON e.estado_id = ee.id
        LEFT JOIN control_equipos.ubicaciones u ON e.ubicacion_id = u.id
        WHERE e.texto_busqueda @@ to_tsquery('spanish', query_term)
        ORDER BY relevancia DESC, e.nombre ASC;
    END; $$ LANGUAGE plpgsql;
    """)

    # 6. ACTUALIZAR FUNCIÓN: busqueda_global (Refactor con JOIN a Ubicaciones)
    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.busqueda_global(termino TEXT)
    RETURNS TABLE (
        tipo TEXT, id UUID, titulo TEXT, descripcion TEXT, relevancia FLOAT4, metadata JSONB
    ) AS $$
    DECLARE query_term TEXT;
    BEGIN
        query_term := string_agg(lexeme || ':*', ' & ' ORDER BY positions) FROM unnest(to_tsvector('spanish', termino));
        IF query_term IS NULL OR query_term = '' THEN query_term := termino; END IF;
        RETURN QUERY
        SELECT
            'equipo' AS tipo, e.id, e.nombre AS titulo,
            'Serie: ' || e.numero_serie || ' | Marca: ' || COALESCE(e.marca, 'N/A') || ' | Modelo: ' || COALESCE(e.modelo, 'N/A') AS descripcion,
            ts_rank_cd(e.texto_busqueda, to_tsquery('spanish', query_term)) AS relevancia,
            jsonb_build_object(
                'numero_serie', e.numero_serie,
                'marca', e.marca,
                'modelo', e.modelo,
                'ubicacion', u.nombre,
                'estado_id', e.estado_id
            ) AS metadata
        FROM control_equipos.equipos e
        LEFT JOIN control_equipos.ubicaciones u ON e.ubicacion_id = u.id
        WHERE e.texto_busqueda @@ to_tsquery('spanish', query_term)
        UNION ALL
        SELECT 'documento', d.id, d.titulo, COALESCE(d.descripcion, 'Sin descripción'), ts_rank_cd(d.texto_busqueda, to_tsquery('spanish', query_term)), jsonb_build_object('equipo_id', d.equipo_id, 'tipo_documento_id', d.tipo_documento_id, 'nombre_archivo', d.nombre_archivo, 'enlace', d.enlace) FROM control_equipos.documentacion d WHERE d.texto_busqueda @@ to_tsquery('spanish', query_term)
        UNION ALL
        SELECT 'mantenimiento', m.id, 'Mantenimiento ID: ' || m.id::TEXT, 'Técnico: ' || m.tecnico_responsable || ' | Obs: ' || COALESCE(m.observaciones, 'N/A'), ts_rank_cd(m.texto_busqueda, to_tsquery('spanish', query_term)), jsonb_build_object('equipo_id', m.equipo_id, 'tipo_mantenimiento_id', m.tipo_mantenimiento_id, 'tecnico', m.tecnico_responsable, 'fecha_programada', m.fecha_programada, 'estado', m.estado) FROM control_equipos.mantenimiento m WHERE m.texto_busqueda @@ to_tsquery('spanish', query_term)
        ORDER BY relevancia DESC, tipo ASC, titulo ASC;
    END; $$ LANGUAGE plpgsql;
    """)

    # 7. RECREAR VISTA MATERIALIZADA (Consumiendo la nueva relación UUID -> Text)
    op.execute("""
    CREATE MATERIALIZED VIEW control_equipos.mv_mantenimientos_proximos AS
    SELECT m.id AS mantenimiento_id,
        m.equipo_id,
        e.nombre AS equipo_nombre,
        e.numero_serie AS equipo_serie,
        u.nombre AS equipo_ubicacion,
        tm.nombre AS tipo_mantenimiento_nombre,
        m.fecha_proximo_mantenimiento,
        m.estado AS mantenimiento_estado,
        m.fecha_proximo_mantenimiento::date - CURRENT_DATE AS dias_restantes
    FROM control_equipos.mantenimiento m
    JOIN control_equipos.equipos e ON m.equipo_id = e.id
    JOIN control_equipos.tipos_mantenimiento tm ON m.tipo_mantenimiento_id = tm.id
    LEFT JOIN control_equipos.ubicaciones u ON e.ubicacion_id = u.id
    WHERE m.fecha_proximo_mantenimiento IS NOT NULL 
      AND m.fecha_proximo_mantenimiento >= now() 
      AND m.fecha_proximo_mantenimiento <= (now() + '30 days'::interval) 
      AND (m.estado <> ALL (ARRAY['Completado'::text, 'Cancelado'::text]))
    ORDER BY m.fecha_proximo_mantenimiento;
    """)

    # 8. RECREAR ÍNDICES DE LA VISTA
    op.execute("CREATE INDEX idx_mv_mantenimientos_proximos_equipo ON control_equipos.mv_mantenimientos_proximos (equipo_id)")
    op.execute("CREATE INDEX idx_mv_mantenimientos_proximos_fecha ON control_equipos.mv_mantenimientos_proximos (fecha_proximo_mantenimiento)")
    op.execute("CREATE UNIQUE INDEX idx_mv_mantenimientos_proximos_mantenimiento_id ON control_equipos.mv_mantenimientos_proximos (mantenimiento_id)")


def downgrade() -> None:
    # Proceso de reversión: Eliminar vista, restaurar columna de texto y recrear vista vieja
    op.execute("DROP MATERIALIZED VIEW IF EXISTS control_equipos.mv_mantenimientos_proximos")
    op.add_column('equipos', sa.Column('ubicacion_actual', sa.Text(), nullable=True), schema='control_equipos')
    op.execute("""
        UPDATE control_equipos.equipos e
        SET ubicacion_actual = u.nombre
        FROM control_equipos.ubicaciones u
        WHERE e.ubicacion_id = u.id;
    """)
    op.drop_constraint('fk_equipos_ubicacion_id_ubicaciones', 'equipos', schema='control_equipos', type_='foreignkey')
    op.drop_column('equipos', 'ubicacion_id', schema='control_equipos')
    # Aquí se debería recrear la vista original si fuera necesario un downgrade completo.
