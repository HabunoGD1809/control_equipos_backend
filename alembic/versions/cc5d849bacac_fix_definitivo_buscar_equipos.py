"""fix_definitivo_buscar_equipos

Revision ID: cc5d849bacac
Revises: 0bbd98e3773d
Create Date: 2026-04-02 11:28:02.966909

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc5d849bacac'
down_revision: Union[str, None] = '0bbd98e3773d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Eliminamos cualquier rastro de la función vieja
    op.execute("DROP FUNCTION IF EXISTS control_equipos.buscar_equipos(text);")
    
    # 2. Creamos la función blindada con casteo explícito a character varying
    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.buscar_equipos(query_term text)
    RETURNS TABLE (
        id uuid,
        nombre character varying,
        numero_serie character varying,
        marca_id uuid,
        modelo character varying,
        ubicacion_actual character varying,
        estado_nombre character varying,
        relevancia double precision
    )
    LANGUAGE plpgsql
    AS $function$
    BEGIN
        RETURN QUERY
        SELECT e.id, 
               CAST(e.nombre AS character varying), 
               CAST(e.numero_serie AS character varying), 
               e.marca_id, 
               CAST(e.modelo AS character varying),
               CAST(u.nombre AS character varying) AS ubicacion_actual, 
               CAST(ee.nombre AS character varying) AS estado_nombre,
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
