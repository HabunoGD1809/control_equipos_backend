"""fix_busqueda_global_tecnico_id

Revision ID: 97d20dc79275
Revises: a86e5b4f8bd7
Create Date: 2026-04-09 19:56:58.976590

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97d20dc79275'
down_revision: Union[str, None] = 'a86e5b4f8bd7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Eliminamos la función actual que busca la columna vieja
    op.execute("DROP FUNCTION IF EXISTS control_equipos.busqueda_global(text);")
    
    # 2. Recreamos la función con la corrección en Mantenimientos (tecnico_id)
    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.busqueda_global(query_term text)
    RETURNS TABLE (
        tipo text,
        id uuid,
        titulo text,
        descripcion text,
        relevancia double precision,
        metadata jsonb
    )
    LANGUAGE plpgsql
    AS $function$
    BEGIN
        RETURN QUERY
        
        -- 1. BÚSQUEDA EN EQUIPOS
        SELECT 
            CAST('equipo' AS text) AS tipo, 
            e.id, 
            CAST(e.nombre AS text) AS titulo,
            CAST('Serie: ' || e.numero_serie || ' | Marca: ' || COALESCE(m_marca.nombre, 'N/A') || ' | Modelo: ' || COALESCE(e.modelo, 'N/A') AS text) AS descripcion,
            CAST(ts_rank_cd(e.texto_busqueda, plainto_tsquery('spanish', query_term)) AS double precision) AS relevancia,
            jsonb_build_object(
                'numero_serie', e.numero_serie,
                'marca', m_marca.nombre,
                'modelo', e.modelo,
                'ubicacion', u.nombre,
                'estado_id', e.estado_id
            ) AS metadata
        FROM control_equipos.equipos e
        LEFT JOIN control_equipos.ubicaciones u ON e.ubicacion_id = u.id
        LEFT JOIN control_equipos.marcas m_marca ON e.marca_id = m_marca.id
        WHERE e.texto_busqueda @@ plainto_tsquery('spanish', query_term)
        
        UNION ALL
        
        -- 2. BÚSQUEDA EN DOCUMENTOS
        SELECT 
            CAST('documento' AS text) AS tipo, 
            d.id, 
            CAST(d.titulo AS text) AS titulo, 
            CAST(COALESCE(d.descripcion, 'Sin descripción') AS text) AS descripcion, 
            CAST(ts_rank_cd(d.texto_busqueda, plainto_tsquery('spanish', query_term)) AS double precision) AS relevancia, 
            jsonb_build_object(
                'equipo_id', d.equipo_id, 
                'tipo_documento_id', d.tipo_documento_id, 
                'nombre_archivo', d.nombre_archivo, 
                'enlace', d.enlace
            ) AS metadata 
        FROM control_equipos.documentacion d 
        WHERE d.texto_busqueda @@ plainto_tsquery('spanish', query_term)
        
        UNION ALL
        
        -- 3. BÚSQUEDA EN MANTENIMIENTOS (AQUÍ ESTÁ LA CORRECCIÓN: tecnico_id)
        SELECT 
            CAST('mantenimiento' AS text) AS tipo, 
            mt.id, 
            CAST('Mantenimiento ID: ' || mt.id::TEXT AS text) AS titulo, 
            CAST('Técnico ID: ' || COALESCE(mt.tecnico_id::text, 'N/A') || ' | Obs: ' || COALESCE(mt.observaciones, 'N/A') AS text) AS descripcion, 
            CAST(ts_rank_cd(mt.texto_busqueda, plainto_tsquery('spanish', query_term)) AS double precision) AS relevancia, 
            jsonb_build_object(
                'equipo_id', mt.equipo_id, 
                'tipo_mantenimiento_id', mt.tipo_mantenimiento_id, 
                'tecnico', mt.tecnico_id, 
                'fecha_programada', mt.fecha_programada, 
                'estado', mt.estado
            ) AS metadata 
        FROM control_equipos.mantenimiento mt 
        WHERE mt.texto_busqueda @@ plainto_tsquery('spanish', query_term)
        
        ORDER BY relevancia DESC, tipo ASC, titulo ASC;
    END;
    $function$;
    """)


def downgrade() -> None:
    # Si hacemos rollback, simplemente borramos la función
    op.execute("DROP FUNCTION IF EXISTS control_equipos.busqueda_global(text);")
