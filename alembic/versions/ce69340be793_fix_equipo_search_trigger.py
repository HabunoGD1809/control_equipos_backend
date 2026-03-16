"""fix_equipo_search_trigger

Revision ID: ce69340be793
Revises: d74c0747cb81
Create Date: 2026-03-13 18:30:11.017408

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ce69340be793'
down_revision: Union[str, None] = 'd74c0747cb81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.actualizar_busqueda_equipo()
    RETURNS TRIGGER AS $$
    DECLARE
        v_ubicacion_nombre VARCHAR;
    BEGIN
        -- Buscar el nombre de la ubicación si el UUID no es nulo
        IF NEW.ubicacion_id IS NOT NULL THEN
            SELECT nombre INTO v_ubicacion_nombre FROM control_equipos.ubicaciones WHERE id = NEW.ubicacion_id;
        ELSE
            v_ubicacion_nombre := '';
        END IF;

        NEW.texto_busqueda =
            setweight(to_tsvector('spanish', COALESCE(NEW.nombre, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.numero_serie, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.codigo_interno, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.marca, '')), 'B') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.modelo, '')), 'B') ||
            setweight(to_tsvector('spanish', COALESCE(v_ubicacion_nombre, '')), 'C') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.centro_costo, '')), 'C') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.notas, '')), 'D');
            
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
    CREATE OR REPLACE FUNCTION control_equipos.actualizar_busqueda_equipo()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.texto_busqueda =
            setweight(to_tsvector('spanish', COALESCE(NEW.nombre, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.numero_serie, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.codigo_interno, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.marca, '')), 'B') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.modelo, '')), 'B') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.ubicacion_actual, '')), 'C') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.centro_costo, '')), 'C') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.notas, '')), 'D');
            
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
