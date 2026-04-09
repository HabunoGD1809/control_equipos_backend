"""fix_buscar_equipos_marca

Revision ID: 0bbd98e3773d
Revises: d34ccb1f8240
Create Date: 2026-04-02 10:40:55.537903

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bbd98e3773d'
down_revision: Union[str, None] = 'd34ccb1f8240'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Eliminamos cualquier versión anterior de la función
    op.execute("DROP FUNCTION IF EXISTS control_equipos.buscar_equipos(text);")
    
    # 2. Recreamos la función usando el tipo 'text' universal de Postgres y casteos explícitos
    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.buscar_equipos(query_term text)
    RETURNS TABLE (
        id uuid,
        nombre text,
        numero_serie text,
        marca_id uuid,
        modelo text,
        ubicacion_actual text,
        estado_nombre text,
        relevancia double precision
    )
    LANGUAGE plpgsql
    AS $function$
    BEGIN
        RETURN QUERY
        SELECT e.id, 
               CAST(e.nombre AS text), 
               CAST(e.numero_serie AS text), 
               e.marca_id, 
               CAST(e.modelo AS text),
               CAST(u.nombre AS text) AS ubicacion_actual, 
               CAST(ee.nombre AS text) AS estado_nombre,
               CAST(ts_rank_cd(e.texto_busqueda, plainto_tsquery('spanish', query_term)) AS double precision) AS relevancia
        FROM control_equipos.equipos e
        LEFT JOIN control_equipos.estados_equipo ee ON e.estado_id = ee.id
        LEFT JOIN control_equipos.ubicaciones u ON e.ubicacion_id = u.id
        WHERE e.texto_busqueda @@ plainto_tsquery('spanish', query_term)
        ORDER BY relevancia DESC, e.nombre ASC;
    END;
    $function$;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS control_equipos.buscar_equipos(text);")
    
    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.buscar_equipos(query_term text)
    RETURNS TABLE (
        id uuid,
        nombre character varying,
        numero_serie character varying,
        marca character varying,
        modelo character varying,
        ubicacion_actual character varying,
        estado_nombre character varying,
        relevancia double precision
    )
    LANGUAGE plpgsql
    AS $function$
    BEGIN
        RETURN QUERY
        SELECT e.id, e.nombre, e.numero_serie, e.marca, e.modelo,
               u.nombre AS ubicacion_actual, ee.nombre AS estado_nombre,
               CAST(ts_rank_cd(e.texto_busqueda, plainto_tsquery('spanish', query_term)) AS double precision) AS relevancia
        FROM control_equipos.equipos e
        LEFT JOIN control_equipos.estados_equipo ee ON e.estado_id = ee.id
        LEFT JOIN control_equipos.ubicaciones u ON e.ubicacion_id = u.id
        WHERE e.texto_busqueda @@ plainto_tsquery('spanish', query_term)
        ORDER BY relevancia DESC, e.nombre ASC;
    END;
    $function$;
    """)
